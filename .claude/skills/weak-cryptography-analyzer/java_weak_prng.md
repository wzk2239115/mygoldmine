# Java 不安全伪随机数生成器（Weak PRNG）审计

## Details

### 典型代码特征
```java
// 场景1: Random 生成加密密钥
Random random = new Random();
byte[] key = new byte[16];
random.nextBytes(key);
SecretKeySpec secretKey = new SecretKeySpec(key, "AES");
Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
cipher.init(Cipher.ENCRYPT_MODE, secretKey);

// 场景2: Random 生成 JWT 签名密钥
Random rand = new Random(System.currentTimeMillis());
byte[] jwtSecret = new byte[32];
rand.nextBytes(jwtSecret);
Algorithm algorithm = Algorithm.HMAC256(jwtSecret);

// 场景3: Random 生成会话令牌/CSRF Token
String token = Long.toHexString(new Random().nextLong());
session.setAttribute("csrfToken", token);

// 场景4: Random 生成密码重置令牌
Random random = new Random();
String resetToken = String.format("%016x", random.nextLong());
user.setResetToken(resetToken);

// 场景5: Math.random() 生成敏感标识
String apiKey = "key_" + Math.random();
String sessionId = UUID.randomUUID().toString(); // UUID v4 某些实现基于 Random

// 场景6: Random 固定种子（完全可预测）
Random random = new Random(12345L);
byte[] iv = new byte[16];
random.nextBytes(iv);

// 场景7: ThreadLocalRandom 用于密钥生成
byte[] salt = new byte[16];
ThreadLocalRandom.current().nextBytes(salt);
SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
KeySpec spec = new PBEKeySpec(password, salt, 65536, 256);
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "new Random()" --include="*.java"
grep -rn "Math\.random()" --include="*.java"
grep -rn "ThreadLocalRandom\.current()" --include="*.java"
grep -rn "Random.*nextBytes\|nextInt\|nextLong" --include="*.java"
grep -rn "import java\.util\.Random" --include="*.java"
grep -rn "UUID\.randomUUID()" --include="*.java" # 特定 JVM 实现可能不安全
```

**高危 API 模式（L2 跳读）：**
- `new Random()` / `new Random(seed)` → 检查后续 `nextBytes()` / `nextInt()` / `nextLong()` 调用
- `Math.random()` 生成字符串拼接到 Token/Key/SessionID
- `ThreadLocalRandom.current().nextBytes(key)` 密钥材料生成
- `Random.nextLong()` 转十六进制作为会话标识
- `Random` 与 `SecretKeySpec` / `KeySpec` / `IvParameterSpec` 同行出现
- `Random` 生成值进入 JWT 签名、HMAC 密钥、数据库 salt 字段
- 固定种子：`new Random(常量)` / `new Random(System.currentTimeMillis())`

**函数调用链追踪（L3 逐行）：**
- 定位密钥生成函数：`generateKey()` / `createToken()` / `generateSecret()`
- 追踪 `byte[] key` 数据流：从 `Random.nextBytes()` 到 `Cipher.init()` / `KeyGenerator` / `SecretKeyFactory`
- 检查 Token 生成逻辑：`nextLong().toString(16)` / `nextInt(Integer.MAX_VALUE)`
- 配置文件审计：`random.seed=` / `prng.algorithm=` / `secure.random=false`
- Spring Security：`RandomValueStringGenerator` 实现类检查
- 会话管理：`HttpSession.getId()` 自定义实现
- 密码重置流程：`ResetTokenGenerator` / `OTPGenerator` 实现
- 盐值生成：`Random` 输出进入 `PBKDF2` / `BCrypt` salt 参数

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 直接使用 `java.util.Random` 无包装
- 类型声明 `Random random` 而非 `SecureRandom`
- `Math.random()` 直接用于安全相关场景
- `new Random()` 无参构造（种子基于系统时间可预测）
- 固定种子初始化：`new Random(常量)` / `new Random(0)`

**伪保护识别（L3 逐行）：**
```java
// 多轮 Random 仍线性同余可预测
Random rand = new Random();
for(int i = 0; i < 1000; i++) {
    key[i % 16] ^= rand.nextInt();  // 迭代不增加熵
}

// 固定种子的伪随机化
long seed = "fixedString".hashCode(); // 可枚举
Random random = new Random(seed);

// ThreadLocalRandom 用于密钥（虽优于 Random 但仍非密码学安全）
byte[] key = new byte[32];
ThreadLocalRandom.current().nextBytes(key);  // 不符合 FIPS 140-2

// 混合弱随机源
long seed = System.currentTimeMillis() ^ System.nanoTime(); // 可推测
Random random = new Random(seed);

// SecureRandom 降级逻辑
SecureRandom secureRandom;
try {
    secureRandom = SecureRandom.getInstanceStrong();
} catch (Exception e) {
    secureRandom = new Random(); // 危险降级（类型不兼容但可能强转）
}

// UUID 依赖实现（某些平台 v4 基于弱 PRNG）
String token = UUID.randomUUID().toString(); // 需确认 JVM 实现
```

**跨模块保护追踪（L4）：**
- JCA 配置：`java.security` 文件中 `securerandom.source=/dev/urandom` 配置
- Spring Security：`RandomValueStringGenerator` 默认实现是否 `SecureRandom`
- JWT 库审计：`jjwt` / `auth0-jwt` / `nimbus-jose-jwt` 密钥生成逻辑
- Shiro/OAuth2：Session ID / Access Token 生成器实现类
- ORM 层：Hibernate `@GeneratedValue` UUID 策略检查
- 容器配置：Tomcat `sessionIdGenerator` / Jetty `SessionIdManager` 类名
- 工具类审计：`CryptoUtil` / `TokenHelper` / `KeyGenerator` 全局单例
- 依赖库：Apache Commons `RandomStringUtils`（3.13+ 前基于 `Random`）
- 配置中心：Nacos/Apollo `security.random.algorithm` 配置项
- 代码质量工具：SpotBugs `PREDICTABLE_RANDOM` / SonarQube `java:S2245` 规则

## Classify

**确认漏洞：**
- JWT/JWS 签名密钥通过 `Random` 生成
- 会话令牌、CSRF Token、API Key 使用 `Random` 生成
- 对称加密密钥（AES/DES）通过 `Random.nextBytes()` 生成
- 密码重置/邮箱验证码使用 `Math.random()` / `Random.nextInt()`
- PBKDF2/BCrypt/SCrypt 盐值从 `Random` 获取
- IV/Nonce（CBC/GCM 模式）使用 `Random` 生成
- TLS 预共享密钥（PSK）/ 自定义握手随机数
- OAuth2 `state` 参数、授权码 `code` 使用弱 PRNG
- 数据库加密字段密钥管理基于 `Random`

**研判误报：**
- 单元测试/Mock 数据生成（`src/test/java` 路径）
- 随机排序/洗牌算法（非安全决策）
- 游戏逻辑/抽奖算法（公平性需求而非不可预测性）
- 负载均衡随机选择（性能优化场景）
- 缓存键随机后缀（避免雪崩，碰撞无安全影响）
- Demo/Example 代码明确标注非生产使用
- `@Ignore` / `@Disabled` 测试方法

**代码异味：**
- 配置可选但默认 `Random`（应默认 `SecureRandom`）
- 注释 "TODO: 替换为 SecureRandom" 但代码仍生产使用
- `RandomFactory` 同时提供 `getRandom()` 和 `getSecureRandom()` 但默认返回前者
- `ThreadLocalRandom` 用于会话管理（虽优于 `Random` 但不满足密码学强度）
- UUID v4 无明确指定熵源（依赖 JVM 默认实现）
- 文档声称"随机令牌"但实现用 `Math.random()`
- `Random` 用于盐值但注释"足够随机"

**关键判断点：**
1. 生成目标：测试数据/性能优化 vs 密钥/令牌/凭证
2. 可预测性后果：业务逻辑异常 vs 身份伪造/数据泄露
3. 攻击面：内部工具 vs 外部暴露 API（公网/多租户）
4. 熵源要求：是否需满足 NIST SP 800-90A / FIPS 140-2
5. 替代实现：系统是否有 `SecureRandom` 并行方案

## Low risk

**可接受的低风险场景：**
- 开发环境调试标识（明确标注 `application-dev.yml`）
- 性能测试数据生成（JMH Benchmark / 压测脚本）
- 内部管理后台请求追踪 ID（非认证凭证）
- 短期过渡方案有明确迁移时间表（看板可查）
- 已有外层强认证的二次随机化（OAuth2 + mTLS）
- 教学代码演示加密流程（培训材料非业务代码）

**降级条件：**
- 生成值不直接用于访问控制决策（如日志追踪 ID）
- 多因素认证中的非关键因子（主认证基于 SecureRandom）
- 极短生命周期令牌（< 30 秒 + 单次使用 + 速率限制）
- 网络严格隔离的内部系统（专线 + IP 白名单）
- 已有额外熵源混合（虽不推荐但降低可预测性）
- 攻击成本远超资产价值（需具体量化）

**注意：** `java.util.Random` 基于线性同余算法（LCG），种子可在 2^48 复杂度内爆破，`Math.random()` 内部仍用 `Random`。固定种子或可推测种子（如 `System.currentTimeMillis()`）可直接预测后续序列。任何密码学用途（密钥/令牌/盐值/IV）必须使用 `SecureRandom.getInstanceStrong()` 或 `SecureRandom.getInstance("NativePRNGBlocking")`。`ThreadLocalRandom` 虽性能优于 `Random` 但同样非密码学安全。符合 PCI DSS / GDPR / 等保 2.0 要求的系统应使用 NIST SP 800-90A 认证的 DRBG 实现。低风险评级不代表长期可接受，需明确迁移计划。