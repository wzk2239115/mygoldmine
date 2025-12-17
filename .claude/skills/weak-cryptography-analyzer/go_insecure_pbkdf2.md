# Go PBKDF2 不安全配置审计

## Details

### 典型代码特征
```go
// 低迭代次数（< 10000）
import "golang.org/x/crypto/pbkdf2"
import "crypto/sha1"

key := pbkdf2.Key(password, salt, 1000, 32, sha1.New)  // 迭代1000次，严重不足

// 使用弱哈希函数MD5
import "crypto/md5"
key := pbkdf2.Key(password, salt, 100000, 32, md5.New)  // MD5已破解

// 使用弱哈希函数SHA1
key := pbkdf2.Key(password, salt, 10000, 32, sha1.New)  // SHA1不推荐

// 固定盐值或空盐
salt := []byte("fixedSalt123")  // 硬编码盐
key := pbkdf2.Key(password, salt, 10000, 32, sha256.New)

salt := []byte{}  // 空盐
key := pbkdf2.Key(password, nil, 10000, 32, sha256.New)  // nil盐

// 短盐值
salt := make([]byte, 4)  // 仅4字节，应≥16字节
rand.Read(salt)
key := pbkdf2.Key(password, salt, 10000, 32, sha256.New)

// 可配置的危险默认值
iterCount := config.GetInt("pbkdf2.iterations")  // 默认1000
hashFunc := getHashFunc(config.HashAlgorithm)    // 默认md5
key := pbkdf2.Key(password, salt, iterCount, 32, hashFunc)

// 从外部传入的不可信参数
func DeriveKey(pwd, salt []byte, iter int, hash func() hash.Hash) []byte {
    return pbkdf2.Key(pwd, salt, iter, 32, hash)  // iter可能被设为1
}

// 复用盐值
var globalSalt = []byte("app-global-salt-2024")  // 全局盐复用
func hashPassword(pwd string) []byte {
    return pbkdf2.Key([]byte(pwd), globalSalt, 5000, 32, sha1.New)
}
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "pbkdf2\.Key" --include="*.go"
grep -rn "golang.org/x/crypto/pbkdf2" go.mod
grep -rn "sha1\.New.*pbkdf2\|md5\.New.*pbkdf2" --include="*.go"
grep -rn "pbkdf2.*[0-9]+" --include="*.go" | grep -E "\b([1-9]|[1-9][0-9]{1,3})\b"  # <10000
grep -rn "fixedSalt\|staticSalt\|globalSalt" --include="*.go"
```

**高危API模式（L2 跳读）：**
- `pbkdf2.Key()` 第3参数（迭代次数）< 10000（NIST SP800-132建议≥10000）
- `pbkdf2.Key()` 第5参数使用 `md5.New` 或 `sha1.New`
- `pbkdf2.Key()` 第2参数为字面量字节切片 `[]byte("...")`
- `pbkdf2.Key()` 第2参数为全局变量或常量
- `pbkdf2.Key()` 第2参数为 `nil` 或长度 `< 16`
- 配置解析：`viper.GetInt("iterations")` / `cfg.HashAlgo`
- 魔数特征：`1000`, `4096`, `5000` 等过低值
- 函数签名缺少盐生成逻辑：`HashPassword(pwd string) []byte`

**函数调用链追踪（L3 逐行）：**
- 迭代次数来源：检查配置文件默认值、环境变量、命令行参数
- 哈希函数选择：`switch algo { case "md5": return md5.New }`
- 盐值生成：`rand.Read(salt)` vs 固定值 vs 从数据库查询
- 调用方式：`DeriveKey(password, salt, iterations, hashFunc)` 参数可控性
- 条件分支：`if isLegacy { iter = 1000 }` 兼容模式
- 密钥材料存储：`user.Salt = "base64_encoded"` 是否为空或固定
- 批量密钥派生：循环中是否复用相同盐或低迭代

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 迭代次数硬编码为低值且无配置覆盖
- 哈希函数直接传入 `md5.New` 无校验
- 盐值为常量或全局变量
- 注释显示 "legacy compatibility" / "for speed"
- 无最小迭代次数校验：`if iter < 10000 { return error }`
- 配置文件 `iterations: 1000` 且无验证逻辑

**伪保护识别（L3 逐行）：**
```go
// 条件性低迭代（开发环境降级）
if env == "dev" {
    iter = 1000  // 开发环境用低值，易混入生产
}

// 依赖用户输入的迭代次数
func DeriveKey(iter int) {
    if iter <= 0 { iter = 1 }  // 仅阻止0，未设最小值
    return pbkdf2.Key(pwd, salt, iter, 32, sha256.New)
}

// 错误的性能优化
const fastMode = true  // "faster for mobile clients"
if fastMode {
    return pbkdf2.Key(pwd, salt, 500, 32, sha1.New)
}

// 使用SHA256但迭代过低
key := pbkdf2.Key(pwd, salt, 1000, 32, sha256.New)  // 算法安全但参数不足

// 盐值长度校验但内容固定
if len(salt) < 8 { panic("salt too short") }
salt = []byte("12345678")  // 满足长度但固定内容

// 仅校验非空但不校验唯一性
if len(salt) == 0 { salt = generateSalt() }
// 生成逻辑可能仍为固定值或时间戳

// 错误的向后兼容
version := user.KeyDerivationVersion
if version == 1 {  // 旧用户仍用弱配置
    return pbkdf2.Key(pwd, salt, 1000, 32, md5.New)
}
```

**跨模块保护追踪（L4）：**
- 配置管理：`config.yaml` 中 `pbkdf2.iterations` 默认值检查
- 环境变量：`PBKDF2_ITER` 是否可被外部降低
- 迁移脚本：数据库迁移是否升级旧密钥派生参数
- 用户表字段：`users.password_iterations` / `users.salt` 存储值检查
- 中间件校验：认证中间件是否强制最小迭代次数
- 单元测试：测试用例中低迭代配置是否影响生产默认值
- 依赖版本：`go.mod` 中 `golang.org/x/crypto` 版本（老版本可能无告警）
- 代码审查规则：`golangci-lint` 是否配置自定义规则检测低迭代
- 日志审计：运行时日志 `"deriving key with %d iterations"` 输出值检查
- 性能监控：Benchmark结果若推荐低迭代需警惕

## Classify

**确认漏洞：**
- 密码派生场景使用迭代次数 < 10000（OWASP建议≥10000，理想≥100000）
- 使用 MD5 或 SHA1 作为PRF（已知碰撞攻击）
- 固定盐值导致彩虹表攻击（相同密码产生相同密钥）
- 盐值长度 < 16字节（NIST建议≥16字节）
- 盐值为空或 `nil`（完全无盐）
- 用户密码存储使用弱PBKDF2配置（认证系统）
- API密钥派生使用低迭代（长期密钥材料）
- 加密密钥派生参数可被外部控制降低

**研判误报：**
- 测试文件中低迭代用于加速测试（`_test.go` 且生产无影响）
- 示例代码演示PBKDF2用法（文档/教学，明确标注"仅示例"）
- 已弃用函数明确注释 `// Deprecated: use Argon2id`
- 兼容性解密遗留数据（仅读取旧格式，新数据用强配置）
- 非安全关键场景（如派生UI主题颜色种子）
- 配置系统中高优先级覆盖确保生产使用安全值

**代码异味：**
- 配置默认值弱但 "可由管理员调整"（实际多数未改）
- 注释 "increase in production"（依赖人工记忆易遗漏）
- 性能测试结论建议低迭代（误导开发者）
- 分环境配置但开发环境用弱值（配置易混淆）
- 条件编译保留弱配置代码（`// +build legacy`）
- 哈希函数可配置但默认 SHA1（安全配置非默认）
- 迭代次数可配置但无最小值校验（运维可能误配）

**关键判断点：**
1. 用途性质：密码存储 > API密钥 > 会话密钥 > 非安全材料
2. 迭代次数：<1000（严重）/ 1000-10000（中危）/ ≥10000（基线）/ ≥100000（推荐）
3. 哈希函数：MD5（高危）/ SHA1（中危）/ SHA256/SHA512（可接受）
4. 盐值特性：无盐（高危）/ 固定盐（高危）/ 短盐（中危）/ 唯一随机盐（安全）
5. 参数来源：硬编码低值 > 配置低默认值 > 用户可控 > 强制最小值
6. 演化路径：新系统用弱配置（高危）vs 历史遗留且有迁移计划（可接受）

## Low risk

**可接受的低风险场景：**
- 非密码派生的密钥扩展（如从32字节主密钥派生256字节子密钥，低迭代可接受）
- 确定性密钥派生用于幂等性（如从UUID派生确定性ID，无抗暴力破解需求）
- 本地文件加密且密码已预哈希（上层已用Argon2，PBKDF2仅用于KDF）
- 测试环境Mock且有硬编码隔离（`if testing.Testing()` 且生产不可达）
- 中间临时密钥派生（生命周期 < 1分钟且外层有强认证）

**降级条件：**
- 输入熵已足够（从256位密钥派生，非密码）
- 无抗暴力破解需求（密钥材料已受物理隔离）
- 兼容性只读模式（仅解密历史数据，新数据用强配置）
- 双因素认证叠加（PBKDF2弱但有TOTP/FIDO2补偿）
- 外层限流保护（API级严格限流使暴力破解不可行）
- 密码策略极强（强制20位随机密码，暴力破解成本高）

**注意：** PBKDF2设计目标是抗暴力破解，迭代次数是核心安全参数。NIST SP800-132（2010）建议≥10000次，但随硬件算力增长，OWASP（2023）已建议≥310000次。Go生态更推荐使用 `golang.org/x/crypto/argon2`（Argon2id）替代PBKDF2。任何密码派生场景的低迭代或弱哈希都应视为高危。低风险评级仅适用于非密码、非长期密钥、有外层强认证的极端场景。生产环境密码存储应迁移至 Argon2id 或至少使用 PBKDF2-HMAC-SHA256 with ≥310000 iterations。