# Go_PlaintextKeyInConfig - 配置中的明文密钥

**适用范围**：链下组件（中继器、签名服务、CLI 工具、预言机节点）

**漏洞成因**：私钥以明文形式硬编码或存储在配置文件（.yaml/.toml/.json/.env）中，缺乏加密保护，导致文件访问者可直接获取敏感密钥。

---

## Details

**典型代码模式**：

```go
// config.yaml 或 config.toml
type Config struct {
    PrivateKey string `yaml:"private_key"`  // 直接存明文
    Mnemonic   string `yaml:"mnemonic"`
}

func LoadKey(cfg *Config) (*ecdsa.PrivateKey, error) {
    return crypto.HexToECDSA(cfg.PrivateKey)  // 从配置直接加载
}
```

**快速定位核心操作**（审计等级：**L1-L2**）：
- **关键词扫描**：搜索 `private_key`、`priv_key`、`secret_key`、`mnemonic`、`seed_phrase` 等字段名
- **文件特征**：检查 `.yaml`、`.toml`、`.json`、`.env` 配置文件中的字符串赋值
- **加载函数**：追踪 `viper.Get()`、`yaml.Unmarshal()`、`json.Unmarshal()` 后直接使用的密钥字段
- **硬编码检测**：grep `const.*Key.*=.*"0x[a-fA-F0-9]{64}"` 或类似模式

**快速定位保护机制**（审计等级：**L2-L3**）：
- **加密层检查**：查找 `aes.NewCipher()`、`age.Decrypt()`、`keyring` 库调用，确认密钥是否先解密再使用
- **环境变量隔离**：验证是否从 `os.Getenv()` 或密钥管理服务（KMS/Vault）获取而非配置文件
- **权限控制**：检查配置文件是否有 `0600` 权限设置逻辑或访问控制注释
- **缺失信号**：若密钥字段直接从 Unmarshal 到私钥对象无中间处理层，大概率无保护

---

## Classify

**漏洞**：
- 明文密钥可直接用于签署链上交易（validator 私钥、热钱包私钥）
- 配置文件暴露在版本控制（Git）、日志系统、备份存储中
- 多环境共享配置文件且缺乏访问控制

**误报**：
- 密钥为测试网专用且代码注释明确标注 `// TESTNET ONLY`
- 配置值为公钥或地址而非私钥
- 字段名包含 `Key` 但实际存储的是 API Key（非加密资产私钥）

**代码异味**：
- 使用明文配置但仅限本地开发环境，且有环境隔离机制（如 `config.dev.yaml` vs `config.prod.yaml`）
- 配置文件加密但密码硬编码在代码中（只是转移问题）

---

## Low risk

**降级场景**：
- **只读冷钱包场景**：私钥对应账户无资产，仅用于身份验证或消息签名
- **单次性临时密钥**：密钥生命周期 < 1 小时且每次启动重新生成
- **严格隔离部署**：配置文件在硬件加密的受限环境（HSM、SGX enclave）中，文件系统权限 `0400` 且仅特权进程可读
- **低价值测试网**：明确标注测试网环境且链上资产价值为零
- **已有上层缓解措施**：配合多签机制，单个私钥无法独立完成交易授权

---

## 审计专业技巧

### 区分真实漏洞 vs 误报

**场景1：配置文件中的字符串字段**

真实漏洞标志：
```go
// config.yaml - 实际案例
validator:
  private_key: "0x1234567890abcdef..."  // 66字符十六进制串（私钥特征）
  sign_key: "sk_live_4eC39HqLyjWDarht..."  // API密钥格式但用于链上操作
```

常见误报：
```go
// config.yaml
keys:
  encryption_key: "${ENCRYPTION_KEY_ID}"  // 占位符，非实际密钥
  api_key_template: "sk_{{ .Env }}_xxxx"  // 模板变量
  public_key: "0x742d35Cc6634C0532925a3..." // 66字符但是公钥（首字符区分度差）
```

**审计技巧**：
1. 利用 ECDSA 私钥特征：`HexToECDSA()` 接受 64 字符十六进制串（256 bit）
2. 追踪数据流：`cfg.PrivateKey` → `crypto.HexToECDSA()` → `*ecdsa.PrivateKey` 用于签名
3. 检查公钥推导：若存储的是通过 `privateKey.Public()` 生成的值，则为公钥（误报）
4. 版本控制检查：在 `.gitignore` 中显式排除 `config.*.yaml` 但仓库历史包含数据（已泄漏）

**场景2：环境变量 vs 明文配置**

真实漏洞：
```go
func init() {
    // 环境变量值硬编码在二进制中（strings 可读）
    os.Setenv("PRIVATE_KEY", "0x...")  // ❌ 明文初始化

    // 或者从配置文件读取后直接使用
    cfg := loadConfig("config.yaml")  // config.yaml 在仓库中（❌）
}
```

合理做法：
```go
func init() {
    // 仅在运行时从安全来源读取
    key := os.Getenv("PRIVATE_KEY")  // ✓ 环境变量（由部署工具注入）
    if key == "" {
        // 从 Vault/KMS 读取
        key = fetchFromVault("prod/validator-key")  // ✓ 动态加载
    }
}
```

**审计检查点**：
- `os.Getenv()` 是否仅在启动时调用，而非在 `init()` 中赋初值
- 是否存在 "fallback" 逻辑，如 `getenv() or default hardcoded value`（❌ 真漏洞）
- 环境变量是否在日志中被打印（grep `log.*PASSWORD\|log.*KEY` 确认泄漏面）

**场景3：测试密钥 vs 生产密钥**

真实漏洞特征：
```go
// config.prod.yaml - 这个文件不应该在版本控制中
validator_key: "0xdeadbeef..."  // 关键：这个密钥确实对应真实账户
sign_key: "0xcafebabe..."

// 且在部署脚本中：
cp config.prod.yaml /etc/myapp/config.yaml  // 直接复制明文文件
```

误报表现：
```go
// config.test.yaml - 明确标记为测试
test_validator_key: "0x0000000000000000..."  // 全零密钥（虚拟）
test_mnemonic: "abandon abandon abandon..."  // 已公开的测试助记词

// 注释明确说明
// TESTNET ONLY - This key has zero value
// Generated from hardhat --network goerli
```

**区分方法**：
1. 检查密钥对应账户：将公钥投影到链浏览器，查询余额和交易历史
   - 有资产转入/转出 → 真实生产密钥（真漏洞）
   - 从未有交易或仅有测试网交易 → 测试密钥（风险降低）
2. 检查 Git 历史：`git log --all --full-history -- config.prod.yaml` 追踪是否曾泄漏到公开仓库
3. 检查密钥派生树：若密钥来自公开助记词（BIP39）且路径为标准测试路径 → 低风险

**场景4：加密密钥和业务密钥混淆**

真实漏洞：
```go
type Config struct {
    PrivateSigningKey string  // ❌ ECDSA 私钥用于交易签名
    PrivateEncryptKey string  // ✓ AES-256 密钥（加密体制不同）
}

// 两者都明文存储但危害程度不同
cfg := loadConfig()
signingKey, _ := crypto.HexToECDSA(cfg.PrivateSigningKey)  // 直接用于链上交易
encryptKey, _ := hex.DecodeString(cfg.PrivateEncryptKey)   // 用于加密存储敏感数据
```

**审计检查点**：
- 区分密钥用途：`sign_key`（链上操作，高危） vs `encryption_key`（本地加密，中危）
- 多签合约中的密钥：单一 signer 密钥 vs 多个 cosigner 集合（风险存在但有缓解）
- 检查初始化代码中的密钥转换：`HexToECDSA()` 调用点代表真正的私钥使用

**场景5：配置文件权限检查**

表面漏洞但实际低风险：
```bash
# 配置文件世界可读
ls -la config.yaml
# -rw-r--r-- 1 root root config.yaml  # ❌ 权限 644

# 但审计发现：
# 1. 容器化部署，config.yaml 仅在构建时暴露，运行时使用 secret mount
# 2. 文件内容在容器启动后销毁
# 3. 私钥从 Kubernetes secret 注入到环境变量而非文件
```

真正的漏洞：
```bash
# 权限不足且实际被多个用户访问
-rw-r--r-- 1 validator validator config.yaml
# 同一机器上其他用户能 cat 此文件
# 或：文件备份到可共享的云存储（AWS S3、Google Cloud Storage）
```

---

## 常见审计陷阱与规避方法

### 1. "我们只在开发环境用明文密钥"（高危误判）

**常见声称**：
```
"开发时用明文配置，生产环境从 Vault 读取，所以代码中的硬编码没问题"
```

**审计陷阱**：
- 版本控制中仍包含 `config.dev.yaml` 并包含真实测试网私钥
- CI/CD 流程使用同一份配置（开发配置被误用于测试网部署）
- 开发密钥被泄漏到 GitHub Issues、Slack、临时日志

**规避方法**：
- 即使声称"仅开发"也要验证：检查 Git 历史中是否有生产密钥混入 dev 分支
- 确认 CI/CD 中有明确的环境隔离（不同分支对应不同密钥来源）
- 要求提供配置文件的访问日志或 K8s RBAC 配置证明隔离

### 2. "这是示例代码/文档"（低风险误判）

**真实案例**：
```go
// 仓库根目录 example_config.yaml
private_key: "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

// 文档声称："这只是示例，用户应使用自己的密钥"
// 但 GitHub Issue 截图显示有人照搬这个例子到生产
```

**审计规避**：
- 检查 issue/discussion 中是否有人实际使用示例密钥
- 用示例中的公钥搜索链浏览器（查看是否被实际部署过）
- 检查示例密钥是否出现在测试代码中（间接证据：维护者认为这个密钥是已知的）

### 3. 加密配置文件但密码硬编码（假安全）

**典型案例**：
```go
func LoadEncryptedConfig() {
    encKey := "hardcoded_encryption_key_32bytes!"  // ❌ 转移了问题

    encryptedData := readFile("config.enc")
    plaintext, _ := aes.Decrypt(encKey, encryptedData)

    cfg := parseYAML(plaintext)  // ✓ 解密后安全，但 encKey 本身不安全
}
```

**审计验证**：
- 跟踪加密密钥来源：若 encKey 来自 `const` 或硬编码字符串 → 0 分
- 检查 `config.enc` 文件是否真的在版本控制外（`.gitignore` vs 实际仓库）
- 要求加密密钥也从安全来源（Vault/KMS）加载

---

## 实战审计检查清单

- [ ] **关键词搜索**：`grep -r "private_key\|priv_key\|secret_key\|signing_key" config/`
- [ ] **文件特征检查**：是否存在 `.yaml/.json/.env/.toml` 文件在版本控制中
- [ ] **数据流追踪**：从配置加载 → 转换为密钥对象 → 使用场景（签名/加密）
- [ ] **Git 历史审计**：`git log --all -- config.prod.*` 检查是否曾泄漏
- [ ] **环境隔离验证**：CI/CD 流程中开发/测试/生产是否使用不同的密钥来源
- [ ] **权限检查**：配置文件权限是否 ≤ 0600，是否有 umask 保护逻辑
- [ ] **容器化检查**：密钥是否通过 docker secret / K8s secret 注入而非构建时包含
- [ ] **链上验证**：将公钥投影到链浏览器确认是否真实账户及资产规模
- [ ] **回归测试**：修复后验证是否所有启动流程都成功从安全来源读取密钥
