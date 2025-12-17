**Go**（适用于链下组件如中继器、签名服务、CLI 工具）  
常出现在密钥加载、加密操作、配置文件解析等逻辑中，包括但不限于从明文配置文件读取私钥、使用 math/rand 而非 crypto/rand 生成密钥、密钥在错误处理路径中泄露至日志等方式：  
- 非加密 Rand 用于密钥：使用 math/rand 而非 crypto/rand 生成密钥，随机性不足可被预测，详见：Go_NonCryptoRandForKeys.md 

## Details

**代码示例：**
```go
// 漏洞代码：使用 math/rand 生成私钥种子
import "math/rand"

func GeneratePrivateKey() []byte {
    seed := rand.Int63()  // 伪随机数，可预测
    key := make([]byte, 32)
    r := rand.New(rand.NewSource(seed))
    r.Read(key)
    return key
}

// 典型场景：中继器启动时生成临时签名密钥
func (r *Relayer) InitSigner() {
    privateKey := make([]byte, 32)
    rand.Read(privateKey)  // math/rand 不可预测性不足
    r.signer = NewSigner(privateKey)
}
```

**快速定位核心操作（L2:跳读）：**
- 搜索 `import "math/rand"` 并检查是否用于密钥/种子/nonce 生成
- 关注函数名包含 `Generate`/`Create`/`Init` + `Key`/`Seed`/`Secret` 的组合
- 追踪 `rand.Read()`/`rand.Int()`/`rand.NewSource()` 调用点，确认是否流向加密操作
- 重点关注 `keystore`/`wallet`/`signer`/`crypto` 包及中继器初始化代码
- 追踪变量流向：从 `math/rand` 生成的值是否传递给 `ecdsa.Sign()`、`aes.NewCipher()`、KDF 等敏感函数

**快速定位保护机制（L3:逐行读）：**
- 检查是否导入 `crypto/rand`：`import cryptorand "crypto/rand"`
- 验证关键路径是否使用 `cryptorand.Read()` 或 `cryptorand.Reader`
- 确认种子来源：检查是否从系统熵池（`/dev/urandom`）或 HSM 获取
- 审查测试代码是否误用 `math/rand` 且被生产环境引用

## Audit Expertise

**真实漏洞特征总结：**
- **直接生成关键数据**：`k := rand.Intn(n)`（ECDSA k 值）、`seed := rand.Int63()` → `PrivateKey(seed)` 链
- **从固定/可预测源派生**：`rand.NewSource(time.Now().UnixNano())` 使用时间戳（秒级精度不足）
- **在多进程/并发环境被复用**：多个实例共享同一 `rand.Rand` 对象或种子，导致 PRNG 序列相同
- **密钥在生产化 API 中返回**：如 RelayerAPI.GetNewSigningKey() 使用 math/rand，虽是临时密钥但用于签名
- **缺乏源代码审视的导入**：第三方库内隐含 math/rand 使用密钥生成（如某些轻量级钱包库）

**常见误报场景与判断标准：**
- **测试辅助工具**：`testdata/` 或 `_test.go` 中的 mock 私钥生成
  - ✅ 真正的误报：硬编码私钥或使用 math/rand 但仅在单测作用域
  - ❌ 误报的误报：init_test() 中初始化的全局 test fixture 被多个测试复用且可能泄露到集成测试
- **性能优化场景**：负载均衡节点选择 `backends[rand.Intn(len(backends))]`
  - ✅ 真正低风险：与密钥无关，即使预测性也无安全影响
  - ⚠️ 需要二次判断：选择的节点是否涉及密钥签名回调（如自定义签名中继器）
- **已配置种子加固**：项目启动时 `rand.Seed(cryptorand.Int63())`
  - ✅ 大幅降低风险但不完全消除：seed 仅初始化一次，后续 PRNG 序列确定性强
  - ❌ 不够：应改用 `rand.Reader` 或重构为 `crypto/rand`

**审计决策树（快速判定）：**
```
1. 代码中是否存在 math/rand 导入？
   否 → 通过（使用了加密随机源或无随机操作）
   是 → 继续第 2 步

2. math/rand 用途是否与以下相关？
   - 密钥/私钥生成？→ 标记为漏洞（严重）
   - nonce/salt/IV/签名参数？→ 漏洞（高风险）
   - 配置文件路径、重试延迟、采样？→ 继续第 3 步

3. 上下文隔离检查
   - 确认代码仅在 _test.go/testutil 中？→ 低风险（需验证无生产路径）
   - 确认无被外部包导入或作为 public API 返回？→ 低风险
   - 确认密钥独立于该随机值？→ 低风险

4. 密钥关联性分析
   - 随机值是否作为参数传递给 `sha256.Sum()`、`NewCipher()` 等？→ 漏洞
   - 随机值是否用于 KDF/PBKDF 的盐？→ 漏洞（熵不足）
   - 业务上不影响密钥安全？→ 低风险（记录为代码异味）
```

**现场审计技巧：**
1. **追踪种子源头**：当发现 `math/rand` 时立即查询 `rand.Seed()` 调用，确认是否来自 `time.Now()`（可预测）或 `crypto/rand`（复杂但可能单次初始化）
2. **并发性检查**：grep `NewRand` 或全局 `var r *rand.Rand` 声明，验证是否在多 goroutine 中竞态使用（导致相同序列）
3. **依赖库扫描**：对 go.mod 中的关键库（钱包、签名、KMS）运行 `go list -json` 并逐一审查 internal rand usage
4. **时间流逝测试**：若代码依赖 `time.Now().UnixNano()` 作种子，在同一秒内多次调用密钥生成函数，验证是否产生相同密钥（实际漏洞指标）
5. **动态追踪**：在本地运行单元测试并使用 Go 的 race detector：`go test -race` 以捕获并发访问 PRNG 的情况


## Classify

**判定为漏洞：**
- math/rand 直接用于生成签名私钥、加密密钥、会话密钥、JWT secret
- 用于生成 nonce/salt/IV 并直接影响加密强度（如 ECDSA 签名的 k 值）
- 中继器/CLI 工具的密钥派生依赖 math/rand 作为熵源
- 通过 `time.Now()` 初始化的种子用于密钥相关操作（时间精度低于毫秒）
- 第三方库中隐含的非密码级随机数生成器被用于密钥初始化（需追踪调用链）
- 多 goroutine 环境中共享 PRNG 对象导致密钥序列相同（如单例模式的 Signer）

**判定为误报：**
- 仅用于测试环境明确标注的 mock 数据生成（需检查是否泄露到生产）
- 用于非安全敏感的随机选择（如负载均衡节点选择、重试延迟抖动）
- 已通过配置文件/环境变量显式注入高熵种子（需验证种子来源）
- 硬编码的测试私钥/公钥对，从未用于生产环境签名
- 密钥在生成后立即通过 HSM 或 KMS 加密再存储（但仍建议改进源头）

**判定为代码异味：**
- 同时存在 crypto/rand 和 math/rand 导入，需逐一确认调用上下文
- 测试代码中使用 math/rand 但未隔离，存在误用风险
- 条件编译 build tag 中的 math/rand（如 `// +build dev`），需验证生产构建确实排除

## Low risk

- **用途非密钥相关**：仅用于日志采样率、性能监控随机触发、幂等性检查的随机 ID
- **种子已加固**：math/rand 的种子来自 crypto/rand 且周期性重置（需验证实现正确性，通常仍不推荐）
- **冗余保护存在**：密钥同时经过 HSM/KMS 二次加密，即使随机性不足也无法直接提取明文
- **短生命周期**：临时会话密钥存活时间 < 1 分钟且不可重放（需结合业务场景评估）
- **测试网环境**：仅在非主网环境使用且配置明确隔离（需审查部署配置防止混淆）

## Real-World Case Study

**案例 1：Cosmos Relay 中继器密钥生成漏洞**
```go
// 真实漏洞代码（简化）
func (r *Relayer) initSigningKey(chainID string) error {
    seed := time.Now().UnixNano() // 低精度种子
    rand.Seed(seed)
    key := make([]byte, 32)
    rand.Read(key)  // math/rand，攻击者可在同一秒内枚举所有可能密钥
    r.signingKeys[chainID] = key
    return nil
}
```
- **审计判定**：高危漏洞。时间戳精度为秒，攻击者可在目标秒内尝试 10^9 个可能的 PRNG 状态
- **正确修复**：
```go
func (r *Relayer) initSigningKey(chainID string) error {
    key := make([]byte, 32)
    if _, err := cryptorand.Read(key); err != nil {
        return err
    }
    r.signingKeys[chainID] = key
    return nil
}
```

**案例 2：单元测试泄露到集成测试的误报**
```go
// test_helper.go（不在 _test.go 中）
package relay

func NewTestSigner() *Signer {
    rand.Seed(12345)  // mock signer，假硬编码种子
    key := make([]byte, 32)
    rand.Read(key)
    return NewSigner(key)
}

// relay_integration_test.go
func TestRelayWithTestSigner(t *testing.T) {
    signer := NewTestSigner()  // 复用相同密钥！
    // ...
}
```
- **审计发现**：看似低风险（测试用）但实际是漏洞——test helper 在包级别暴露，可被其他包调用
- **判定变更**：从"误报"升级为"漏洞"（容易被无意中用于生产）

**案例 3：负载均衡中的真正低风险**
```go
// loadbalance.go
func (lb *LoadBalancer) SelectBackend(backends []*Backend) *Backend {
    idx := rand.Intn(len(backends))  // math/rand 用于节点选择
    return backends[idx]
}
```
- **审计判定**：低风险（与密钥无关）
- **验证方法**：确认 Backend 选择不涉及密钥签名回调，仅用于路由决策

**审计实战建议：**
- 在 Go 1.20 之前，`rand.Seed()` 是全局的，所有 `math/rand` 操作共享种子，高风险
- 在 Go 1.20+，引入了 `rand.New()` 创建独立 PRNG，但导入旧代码时仍需谨慎
- 对于链上交互组件（签名器、钱包），始终使用 `crypto/rand` 或 `rand.Reader`（Go 1.20+）
- 在审查代码时，查看是否存在单例 PRNG：`var rng = rand.New(rand.NewSource(seed))`，这种模式在并发环境下容易产生相同密钥序列
