# Go MD5 弱哈希摘要审计

## Details

### 典型代码特征
```go
// crypto/md5 直接调用
import "crypto/md5"

hash := md5.New()
hash.Write([]byte(password))
digest := hash.Sum(nil)

// 快捷函数
passwordHash := md5.Sum([]byte(password))

// 密码验证
stored := md5.Sum([]byte(password))
if bytes.Equal(stored[:], md5.Sum([]byte(input))[:]) {
    // 认证通过
}

// HMAC-MD5 签名
import "crypto/hmac"
mac := hmac.New(md5.New, secretKey)
mac.Write(message)
signature := mac.Sum(nil)

// 文件完整性校验
h := md5.New()
io.Copy(h, file)
checksum := hex.EncodeToString(h.Sum(nil))

// JWT/Token 签名
token := fmt.Sprintf("%s.%x", payload, md5.Sum([]byte(payload+secret)))

// 配置化哈希选择
if config.HashAlgorithm == "md5" {
    return md5.Sum(data)
}

// hash.Hash 接口传入 MD5
func computeDigest(h hash.Hash, data []byte) []byte {
    h.Write(data)
    return h.Sum(nil)
}
digest := computeDigest(md5.New(), sensitiveData)
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "crypto/md5" --include="*.go"
grep -rn "md5\.New\|md5\.Sum" --include="*.go"
grep -rn "hmac\.New.*md5" --include="*.go"
grep -rn '"md5"\|"MD5"' --include="*.go" | grep -i "hash\|algo\|digest"
go list -m all | grep -i "md5"  # 第三方MD5库
```

**高危API模式（L2 跳读）：**
- `md5.New()` 创建 MD5 hasher
- `md5.Sum(data)` 快捷计算 MD5
- `hmac.New(md5.New, key)` 使用 MD5 作为 HMAC 基础
- `hash.Hash` 接口参数传入 `md5.New()`
- `%x` 格式化 MD5 输出用于比较
- 配置项 `algorithm: "md5"` / `HashType: MD5`
- 密码/令牌相关函数内调用 `md5.*`
- 函数名包含 `hashPassword`, `signToken`, `verifySignature` 等

**函数调用链追踪（L3 逐行）：**
- 检查 `hash.Hash` 类型参数来源：`getHasher(algoName string)`
- 密码处理流程：`registerUser()` → `hashPassword()` → `md5.Sum()`
- 签名生成链：`generateToken()` → `sign()` → `hmac.New(md5.New, ...)`
- 配置解析：`viper.GetString("security.hash")` → `case "md5": return md5.New()`
- 条件分支：`if legacy { hasher = md5.New() }`
- 接口实现：`type MD5Hasher struct{}` 实现 `Hasher` 接口
- 工厂模式：`NewHasher(typ string) hash.Hash` 返回值检查
- 中间件：JWT/Auth中间件验证逻辑是否用 MD5

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 密码直接进入 MD5：`md5.Sum([]byte(password))` 无盐
- 单次哈希无迭代：无 PBKDF2/bcrypt/Argon2 封装
- 硬编码算法：`hash := md5.New()` 无动态选择
- 时序比较：`bytes.Equal(hash1, hash2)` 而非 `subtle.ConstantTimeCompare`
- 配置无校验：接受 `hash_type: md5` 且无拒绝逻辑
- 注释显示 "fast hash" / "simple checksum"

**伪保护识别（L3 逐行）：**
```go
// 加盐但仍用 MD5（仍易彩虹表攻击）
salt := generateSalt()
hashed := md5.Sum([]byte(password + salt))

// 多轮迭代但基础算法弱
func slowMD5(data []byte, rounds int) []byte {
    hash := data
    for i := 0; i < rounds; i++ {
        hash = md5.Sum(hash)[:]  // 迭代仍不如专用 KDF
    }
    return hash
}

// HMAC-MD5 用于签名（MD5 碰撞风险）
signature := hmac.New(md5.New, key)
signature.Write(token)
return signature.Sum(nil)  // 长度扩展已防御但碰撞未防

// 条件性降级
if config.HighSecurity {
    return sha256.Sum256(data)
} else {
    return md5.Sum(data)  // 默认路径仍弱
}

// 错误的 "安全" 假设
// "User passwords already bcrypt, MD5 here just for API signature"
apiSig := md5.Sum([]byte(apiKey + timestamp))  // 仍可伪造

// 双重哈希误解
doubleMD5 := md5.Sum(md5.Sum(password)[:])  // 无助于安全
```

**跨模块保护追踪（L4）：**
- 配置文件：`config.yaml` 中 `allowed_hashes` 白名单是否包含 md5
- 环境变量：`HASH_ALGORITHM=md5` 是否可在生产设置
- 依赖库检查：`go.mod` 中是否引入 `golang.org/x/crypto/bcrypt` 等强哈希
- 中间件拦截：认证中间件是否拒绝 MD5 签名的令牌
- 数据库审计：`users` 表 `password_hash` 长度（MD5=32字符，SHA256=64）
- 迁移脚本：是否有密码重哈希任务（MD5 → bcrypt）
- 日志监控：运行时日志 `"using hash algorithm: %s"` 输出值
- 单元测试：测试用例默认哈希是否为 MD5
- 代码审查规则：`.golangci.yml` / `gosec` 是否配置 G401 规则
- TLS配置：`tls.Config.CipherSuites` 是否排除 MD5 签名套件
- 证书验证：`x509.Certificate.SignatureAlgorithm` 是否接受 MD5WithRSA

## Classify

**确认漏洞：**
- 密码存储使用 MD5（无论是否加盐，已可 GPU 快速破解）
- 会话令牌/API 签名使用 HMAC-MD5（碰撞攻击风险）
- JWT 使用 MD5 签名（可伪造令牌）
- 证书/代码签名验证接受 MD5（已实现实用碰撞）
- 密钥派生使用单轮 MD5（`md5.Sum(password+salt)`）
- 文件完整性保护场景（对抗性环境，可前缀碰撞）
- 身份认证/授权决策依赖 MD5 输出
- 无替代算法的强制 MD5 实现

**研判误报：**
- 非对抗场景文件去重（本地备份、缓存键）
- 哈希表内部键生成（纯内存结构，不持久化）
- ETag 生成（HTTP 缓存标识，非安全边界）
- 数据库分片键（无需抗碰撞，仅需分布均匀）
- 调试/日志消息摘要（快速检索非完整性保证）
- 单元测试 Mock 数据（`_test.go` 且明确隔离）
- 已废弃代码路径（`// Deprecated` 注释且生产禁用）
- 只读历史数据（解析遗留系统 MD5，新数据用 SHA256）

**代码异味：**
- 文档声称 "secure hash" 但实现用 MD5
- 新用户用 SHA256，旧用户未迁移仍 MD5
- 配置可选 SHA256 但默认 MD5
- 注释 "TODO: migrate to SHA256" 无时间表
- 性能测试推荐 MD5（"fastest option"）
- 条件编译保留 MD5 代码（`// +build legacy`）
- 哈希算法可协商且 MD5 优先级高于 SHA256

**关键判断点：**
1. 哈希目标：密码/密钥（高危）vs 文件校验（中危）vs 缓存键（低危）
2. 对抗模型：是否需防御碰撞攻击（相同哈希伪造）
3. 破解成本：密码熵低（8位数字）vs 高熵密钥（128位随机）
4. 暴露程度：外部 API vs 内部服务 vs 离线工具
5. 生命周期：长期存储（密码表）vs 临时会话 vs 一次性标识
6. 替代方案：系统是否已集成 SHA256/bcrypt/Argon2

## Low risk

**可接受的低风险场景：**
- 本地文件去重（rsync/backup，无安全边界）
- 内存缓存键生成（Redis key，碰撞仅影响性能）
- 开发环境临时标识（非生产部署）
- 日志消息快速索引（ELK 检索字段，非验证）
- 数据库查询缓存键（MySQL Query Cache 类场景）
- 非安全关键的唯一 ID（临时文件名，无碰撞利用价值）

**降级条件：**
- 碰撞攻击成本远高于资产价值（内部工具无攻击者）
- 数据不涉及认证/授权/签名验证
- 无外部可控输入（无碰撞注入机会）
- 短生命周期数据（临时标识 < 1小时）
- 外层强签名保护（TLS 1.3 + 应用层 Ed25519 封装）
- 明确文档标注 "非安全用途"（代码审查可识别）

**注意：** MD5 已实现实用碰撞攻击（2004年王小云首次破解，现可在秒级生成碰撞），GPU 算力可达 200GH/s（每秒2000亿次哈希）。密码存储场景即使加盐也可被彩虹表/暴力破解快速攻破。任何认证/签名/密钥派生场景必须立即迁移至 SHA-256/SHA-512（完整性）或 bcrypt/Argon2（密码）。文件完整性校验应升级 SHA-256 防御前缀碰撞（Flame 恶意软件案例）。HMAC-MD5 虽防长度扩展但仍受碰撞影响，应迁移 HMAC-SHA256。Go 安全审计工具 `gosec` 规则 G401 会标记 MD5 使用。低风险评级仅适用于完全非安全关键的内部标识场景，且需明确文档说明。
