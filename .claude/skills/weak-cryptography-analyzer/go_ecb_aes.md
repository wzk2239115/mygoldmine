# Go AES-ECB 模式明文模式泄露审计

## Details

### 典型代码特征
```go
// 手动实现ECB加密（标准库未提供）
import "crypto/aes"

block, _ := aes.NewCipher(key)
encrypted := make([]byte, len(plaintext))
for i := 0; i < len(plaintext); i += block.BlockSize() {
    block.Encrypt(encrypted[i:], plaintext[i:])  // 逐块加密无IV
}

// 第三方库 crypt2go/ecb
import "github.com/andreburgaud/crypt2go/ecb"

block, _ := aes.NewCipher(key)
mode := ecb.NewECBEncrypter(block)
ciphertext := make([]byte, len(plaintext))
mode.CryptBlocks(ciphertext, plaintext)

// 自定义ECB实现
type ecbEncrypter struct { b cipher.Block }
func (x *ecbEncrypter) CryptBlocks(dst, src []byte) {
    for len(src) > 0 {
        x.b.Encrypt(dst, src[:x.b.BlockSize()])  // 无链接模式
        src, dst = src[x.b.BlockSize():], dst[x.b.BlockSize():]
    }
}

// 配置化ECB选择
if config.Mode == "ecb" {
    return encryptECB(data, key)
}
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "\.Encrypt(" --include="*.go" | grep -v "IV\|iv\|nonce"
grep -rn "ecb\|ECB" --include="*.go"
grep -rn "crypt2go/ecb\|andreburgaud" go.mod go.sum
grep -rn "NewCipher.*for.*Encrypt" --include="*.go"
```

**高危API模式（L2 跳读）：**
- `aes.NewCipher()` 后循环调用 `block.Encrypt()` 无IV
- 导入 `github.com/andreburgaud/crypt2go/ecb`
- `ecb.NewECBEncrypter()` / `ecb.NewECBDecrypter()`
- 自定义 `type *Encrypter` 实现 `cipher.BlockMode` 无IV字段
- `for i := 0; i < len(data); i += aes.BlockSize` 循环模式
- 魔数特征：IV参数缺失、`make([]byte, 16)` 零IV复用

**函数调用链追踪（L3 逐行）：**
- 检查 `cipher.BlockMode` 实现：是否缺少IV/counter状态
- 加密入口函数参数：`Encrypt(key, data []byte)` 无IV参数
- 配置解析逻辑：`case "ecb":` / `mode := cfg.GetString("cipher.mode")`
- 条件分支：`if strings.ToUpper(mode) == "ECB"`
- 包装函数：`encryptAES()` 内部实现检查是否有IV生成
- 结构体字段：`type Config struct { Mode string }` 值为 "ecb"

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 加密函数签名无IV参数且无内部生成
- `block.Encrypt()` 循环调用无状态传递
- 配置文件允许 `mode: ecb` 且无校验
- 注释显示 "ECB mode for simplicity"
- 无模式白名单或安全策略检查

**伪保护识别（L3 逐行）：**
```go
// 误认为AES-256足够安全（忽略模式问题）
if securityLevel == "high" {
    key := make([]byte, 32)  // AES-256
    return encryptECB(data, key)  // 强密钥+弱模式仍不安全
}

// 小数据量降级逻辑
if len(data) < 1024 {
    return quickECB(data, key)  // 小数据仍可能泄露模式
}

// 零IV当作CBC使用（实际ECB）
iv := make([]byte, aes.BlockSize)  // 全零IV
// ... 实际实现仍为逐块独立加密

// 错误的性能优化
const useECB = true  // "ECB faster, no IV needed"
```

**跨模块保护追踪（L4）：**
- 依赖检查：`go.mod` 中是否引入 `crypt2go/ecb` 或其他ECB库
- 配置验证：`ValidateCipherConfig()` 函数是否拒绝ECB
- 中间件过滤：加密中间件是否强制 CBC/GCM/CTR
- 单元测试：测试文件中 `mode: ecb` 测试用例是否影响生产
- 环境变量：`CIPHER_MODE=ecb` 是否可在生产环境设置
- 日志审计：搜索 `"using ECB"` / `"mode=ecb"` 运行时日志
- 代码审查规则：`.golangci.yml` 是否配置ECB检测

## Classify

**确认漏洞：**
- 加密结构化数据（JSON/Protobuf/数据库行）
- 图像/文件加密（重复块暴露内容模式）
- 批量用户数据加密（相同明文产生相同密文）
- 长消息流加密（网络协议/日志流）
- API响应体加密（固定字段导致密文可预测）
- 任何可观察多次加密输出的场景

**研判误报：**
- 单次加密单个随机块（如包装16字节随机密钥）
- 测试代码/Benchmark基准对照组（`_test.go` 且不影响生产）
- 示例代码演示ECB缺陷（文档/教学用途）
- 已弃用代码明确标注 `// Deprecated: use GCM`
- 仅读取外部遗留系统的ECB加密数据（兼容性需求）

**代码异味：**
- 注释 "data is random, ECB is safe"（错误假设）
- 可配置模式但 `defaultMode = "ecb"`
- 性能测试结论 "ECB fastest, recommend"
- 开发环境默认ECB，生产环境 "应该" 用GCM（配置易错）
- 先压缩/BASE64后ECB加密（治标不治本）
- 条件编译：`// +build !production` 仍留ECB代码

**关键判断点：**
1. 数据特征：是否存在重复模式（固定头/JSON结构/相同字段值）
2. 数据长度：是否超过16字节（AES块大小）
3. 加密频次：单次 vs 批量加密相同或相似数据
4. 可观察性：攻击者能否收集多个密文样本
5. 实现来源：自实现（高危）vs 第三方库（可能有防御）

## Low risk

**可接受的低风险场景：**
- 加密单个16字节随机会话密钥（且密钥每次唯一）
- 加密预计算哈希值（SHA256输出无内部结构）
- 一次性随机Nonce加密（长度≤16字节且不复用）
- 单元测试Mock（`if testing.Testing()`明确隔离）
- 密钥包装场景（KEK加密DEK，且DEK完全随机）

**降级条件：**
- 数据已充分随机化（KDF/HKDF输出无可预测性）
- 严格单块加密（`len(plaintext) == aes.BlockSize`）
- 明文空间极大（UUID/密钥材料无重复）
- 加密输出不可观察（完全离线且无泄露渠道）
- 外层有认证加密封装（如TLS 1.3内部临时数据）

**注意：** Go标准库未提供ECB说明其不推荐使用。任何手动实现或第三方ECB库都应视为高危。即使数据"看似随机"，也可能存在隐藏模式或未来数据演化导致的重复。生产环境应统一使用 `cipher.NewGCM()` 或 `cipher.NewCTR()`。低风险评级仅适用于单次加密单块完全随机数据的极端场景。