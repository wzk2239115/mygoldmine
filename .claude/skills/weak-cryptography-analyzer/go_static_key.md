# Go 静态密钥硬编码 (Static Key Hardcoding)

## Details

### 典型代码示例

```go
// 场景1: 硬编码加密密钥
const encryptionKey = "1234567890abcdef1234567890abcdef"
cipher, _ := aes.NewCipher([]byte(encryptionKey))

// 场景2: JWT 签名密钥硬编码
var jwtSecret = []byte("my-secret-key-12345")
token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
tokenString, _ := token.SignedString(jwtSecret)

// 场景3: TLS 预共享密钥硬编码
tlsConfig := &tls.Config{
    PreSharedKey: []byte("hardcoded-psk-value"),
}

// 场景4: 密钥派生使用固定盐值
salt := []byte("static-salt-value")
key := pbkdf2.Key(password, salt, 4096, 32, sha256.New)

// 场景5: 对称加密 IV/Nonce 固定
iv := []byte("1234567890123456")
stream := cipher.NewCFBEncrypter(block, iv)

// 场景6: API 密钥/令牌硬编码
const apiToken = "sk_live_abc123def456"
req.Header.Set("Authorization", "Bearer " + apiToken)
```

### 快速定位核心操作 (L1-L3)

**L1 - 关键词扫描：** 搜索 `const.*[Kk]ey|var.*[Ss]ecret|[Pp]assword.*=.*"|apiKey|jwt.*Sign|psk|salt.*=.*\[|iv.*=.*\[`

**L2 - 跳读包导入与常量区：** 
- `crypto/aes|crypto/cipher|crypto/tls|jwt-go|golang-jwt` → 检查全局 const/var 声明
- 函数内搜索 `[]byte("` 后跟固定字符串赋值给密钥类型变量

**L3 - 逐行审计高危函数调用：**
- `aes.NewCipher(key)` → 追溯 key 来源
- `jwt.SignedString(secret)` → 追溯 secret 来源  
- `pbkdf2.Key(..., salt, ...)` → 检查 salt 是否静态
- `cipher.NewCFB*/NewCTR/NewGCM(block, iv)` → 检查 IV/Nonce 是否固定
- `tls.Config{..., PreSharedKey: ...}` → 检查 PSK 来源

### 快速定位保护机制 (L2-L4)

**L2 - 跳读配置加载逻辑：**
- 查找 `os.Getenv|viper.Get|config.Load|flag.String` → 确认密钥是否从环境变量/配置文件读取
- 查找 `ioutil.ReadFile|os.ReadFile` 配合 `.key|.pem|.env` 文件路径

**L3 - 逐行检查密钥管理模式：**
- 导入 `vault|aws-sdk|secrets-manager` → 可能使用密钥管理服务
- 函数调用 `kms.Decrypt|secretsmanager.GetSecretValue` → 动态获取密钥
- 检查 `init()` 或 `main()` 中是否有密钥加载逻辑

**L4 - 跨模块追踪密钥流转：**
- 定位全局变量初始化位置 → 追踪赋值链路
- 检查 `config` 包或 `internal/secrets` 模块 → 确认统一密钥管理
- 分析编译标签 `// +build !prod` → 确认硬编码仅用于测试环境

---

## Classify

### 确认为漏洞
- 生产代码中密钥字符串直接写死且无保护措施
- 密钥长度符合实际使用标准（AES-128/256对应16/32字节）
- 密钥被实际用于敏感操作（加密用户数据、签名身份令牌、TLS握手等）
- 密钥在版本控制历史中可追溯

### 判定为误报
- 密钥仅存在于测试文件（`*_test.go`）且测试数据无敏感性
- 明显的示例值（`"example-key"|"your-secret-here"|"changeme"`）且后续代码有校验逻辑
- 编译条件限制为开发环境（`// +build dev|mock`）
- 密钥长度不合规（如3字节"abc"）且仅用于演示逻辑

### 归类为代码异味
- 默认值兜底场景：优先读取环境变量，失败后回退到硬编码（需确认生产环境变量已配置）
- 公开算法的测试向量（RFC标准测试用例）
- 注释明确标注 `TODO: Move to secrets manager`
- 脱敏后的前缀/后缀片段（如 `keyPrefix := "pk_live_"`）

---

## Low Risk

以下场景可评为**低风险**，但仍需在报告中标注为改进建议：

1. **非敏感上下文密钥**  
   用于本地缓存加密、开发环境数据混淆等非关键场景，泄露不直接导致业务风险

2. **演示/示例代码**  
   位于 `examples/|demo/|docs/` 目录，且 README 明确说明需替换密钥

3. **已失效的密钥**  
   代码注释或 Git 提交记录显示密钥已轮换，历史密钥仅保留用于数据迁移

4. **对称盐值（非密钥）**  
   PBKDF2/scrypt 中固定盐值配合用户密码使用，仅降低彩虹表攻击防护（非直接密钥泄露）

5. **公开协议的固定参数**  
   如 TLS 1.3 中 `PSK_KE` 模式的标识符（非实际加密密钥）

6. **临时测试密钥 + 环境隔离**  
   Docker 测试容器或 CI 环境使用的临时密钥，且无法访问生产网络

**判定依据：** 结合代码注释、部署架构文档、环境变量配置模板综合评估实际暴露风险。