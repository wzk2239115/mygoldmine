# Java MD5 弱哈希算法审计

## Details

### 典型代码特征
```java
// MessageDigest API 使用 MD5
MessageDigest md = MessageDigest.getInstance("MD5");
md.update(password.getBytes());
byte[] digest = md.digest();

// 密码哈希直接使用 MD5
String hashedPassword = DigestUtils.md5Hex(password);
if(storedHash.equals(hashedPassword)) { /* 认证通过 */ }

// Apache Commons Codec
String md5 = org.apache.commons.codec.digest.DigestUtils.md5Hex(data);
String md5Base64 = Base64.encodeBase64String(DigestUtils.md5(input));

// Spring Security 旧版配置
PasswordEncoder encoder = new MessageDigestPasswordEncoder("MD5");
String encoded = encoder.encode(rawPassword);

// Guava Hashing
HashCode hash = Hashing.md5().hashString(input, StandardCharsets.UTF_8);

// JWT 使用 HMAC-MD5 签名
Algorithm algorithm = Algorithm.HMAC256("secret");  // 错误写法
// 或使用 MD5 摘要作为签名输入
String signature = DigestUtils.md5Hex(header + "." + payload + secret);

// 数据库字段加密前摘要
String userId = DigestUtils.md5Hex(username);  // 用作唯一标识
String token = MD5(timestamp + userId + secret);

// 文件上传校验
MultipartFile file = ...;
String fileMd5 = DigestUtils.md5Hex(file.getInputStream());

// 自定义摘要工具类
public class HashUtil {
    public static String hash(String input) {
        return DigestUtils.md5Hex(input);  // 包装 MD5
    }
}

// MyBatis TypeHandler 使用 MD5
public class PasswordTypeHandler extends BaseTypeHandler<String> {
    @Override
    public void setNonNullParameter(...) {
        ps.setString(i, DigestUtils.md5Hex(parameter));  // 存储前哈希
    }
}

// SHA-1 同样属于弱哈希
MessageDigest sha1 = MessageDigest.getInstance("SHA-1");
byte[] sha1Hash = sha1.digest(password.getBytes());
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "MessageDigest.getInstance.*MD5\|SHA-1" --include="*.java"
grep -rn "DigestUtils.md5\|md5Hex\|sha1Hex" --include="*.java"
grep -rn "Hashing.md5()\|Hashing.sha1()" --include="*.java"
grep -rn "MessageDigestPasswordEncoder.*MD5" --include="*.java"
grep -rn "\"MD5\"\|\"SHA-1\"\|\"SHA1\"" --include="*.java"
grep -rn "HMAC.*MD5\|HmacMD5" --include="*.java"
```

**高危 API 模式（L2 跳读）：**
- `MessageDigest.getInstance("MD5")` / `getInstance("SHA-1")`
- `DigestUtils.md5Hex()` / `DigestUtils.md5()` / `md5DigestAsHex()`
- `org.springframework.util.DigestUtils.md5*` 系列
- `com.google.common.hash.Hashing.md5()` / `.sha1()`
- `MessageDigestPasswordEncoder("MD5")` Spring Security 旧版
- `new Md5Hash(password)` / `new Sha1Hash(password)` Apache Shiro
- `Mac.getInstance("HmacMD5")` / `HmacSHA1`
- 魔数：16 字节摘要长度（MD5）/ 20 字节（SHA-1）
- `String.format("%032x", new BigInteger(1, digest))` MD5 格式化
- JWT 库 `sign()` 方法使用 MD5/SHA1 算法标识

**函数调用链追踪（L3 逐行）：**
- 定位 `MessageDigest.getInstance()` 参数来源：常量/配置/枚举
- 配置文件：`application.properties` 中 `hash.algorithm=MD5`
- 枚举定义：`enum HashType { MD5, SHA256 }` 检查 MD5 分支使用
- Spring 注入：`@Value("${security.hash.algorithm}")` 值检查
- 密码编码器选择：`if(legacy) { return new Md5PasswordEncoder(); }`
- 工具类追踪：`SecurityUtil.hash()` 内部实现算法
- ORM 拦截器：Hibernate `@PrePersist` 中密码哈希逻辑
- 认证流程：`AuthenticationProvider.authenticate()` 密码比对
- API 签名生成：`SignUtil.sign(params)` 实现检查
- 缓存键生成：`CacheKeyGenerator` 是否用 MD5 生成 key

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 密码直接哈希无加盐：`md5Hex(password)` 无 salt 参数
- 单轮哈希无迭代：无 PBKDF2/BCrypt/SCrypt/Argon2
- 硬编码算法字符串：`getInstance("MD5")` 无动态选择
- 时序攻击风险：`hash1.equals(hash2)` 直接比较
- 配置文件默认 MD5：`hash.algorithm=MD5` 且无警告
- 无算法白名单验证或版本检查

**伪保护识别（L3 逐行）：**
```java
// 加盐但仍用 MD5（易被 GPU 暴力破解）
String salted = password + salt;
String hash = DigestUtils.md5Hex(salted);  // 彩虹表仍有效

// 多轮迭代不足（应 >= 10000 轮）
String hash = password;
for(int i = 0; i < 100; i++) {
    hash = DigestUtils.md5Hex(hash);  // 迭代次数过低
}

// HMAC-MD5 仍是弱算法
Mac mac = Mac.getInstance("HmacMD5");
mac.init(new SecretKeySpec(key, "HmacMD5"));  // 底层 MD5 碰撞风险

// SHA-1 作为"升级"方案（已实现碰撞）
MessageDigest sha1 = MessageDigest.getInstance("SHA-1");  // 仍不安全

// 误认为 Base64 编码增强安全性
String encoded = Base64.encodeBase64String(DigestUtils.md5(password));  // 无效保护

// 配置降级逻辑
try {
    return MessageDigest.getInstance("SHA-256");
} catch(NoSuchAlgorithmException e) {
    return MessageDigest.getInstance("MD5");  // 危险降级
}

// 多层包装但底层 MD5
@Service
public class SecureHashService {
    public String secureHash(String input) {
        return DigestUtils.md5Hex(input);  // 名不副实
    }
}
```

**跨模块保护追踪（L4）：**
- Spring Security 配置：`PasswordEncoderFactories` 默认编码器类型
- Shiro 配置：`credentialsMatcher` 是否使用 MD5/SHA1
- JWT 库审计：`auth0-jwt` / `jjwt` 算法白名单配置
- 数据库审计：查找存储过程/触发器中 MD5 调用
- ORM 实体类：`@PrePersist` / `@PreUpdate` 注解方法检查
- 配置中心：Apollo/Nacos 中 `crypto.*` / `security.*` 配置
- 依赖版本：Spring Security < 5.0 默认支持 MD5
- Docker 镜像：JDK 版本是否限制弱算法（JDK 9+ 可配置）
- SCA 扫描：SonarQube / Checkmarx 规则启用状态
- API 网关：Kong/Zuul 签名验证中间件算法检查
- 微服务链路：分布式追踪中 Trace ID 生成算法
- 消息队列：Kafka 消息签名使用的哈希算法

## Classify

**确认漏洞：**
- 用户密码存储使用 MD5/SHA-1（无论是否加盐）
- JWT/JWS 签名或 HMAC 使用 MD5/SHA1
- API 签名验证（OpenAPI Signature）基于 MD5
- 会话令牌/CSRF Token 生成使用 MD5
- 数据库敏感字段哈希（身份证/手机号/邮箱索引）
- 支付签名、交易验证使用 MD5
- OAuth 签名、SSO 令牌生成使用弱哈希
- 文件完整性校验用于安全验证场景（防篡改）
- 数字证书指纹计算用于信任决策
- 无替代算法的生产环境强制 MD5

**研判误报：**
- 单元测试/集成测试用例（`src/test/java` 路径）
- Mock 对象/测试桩实现（Mockito/PowerMock）
- 示例代码/JavaDoc 文档注释中演示
- 已废弃方法明确标注 `@Deprecated` 且默认禁用
- 历史数据兼容层（仅读取旧哈希，新数据用 SHA-256）
- 条件编译排除：`if(false)` / `@Disabled` 测试
- 性能基准测试（JMH Benchmark 对照组）
- 第三方库内部实现（非项目代码调用）

**代码异味：**
- 配置可选 SHA-256 但默认 MD5
- 注释 "临时使用" / "TODO: 升级 SHA-256" 无时间表
- 日志输出 "Using MD5 for compatibility" 无迁移计划
- SHA-1 作为 MD5 的"安全升级"方案
- 算法枚举中 MD5 优先级高于 SHA-256
- 性能理由选择 MD5（"MD5 更快"）
- 可配置白名单包含 `MD5,SHA1,SHA256`
- 新旧用户使用不同算法但未统一升级
- 文档声称"加密存储"实际用 MD5 哈希

**关键判断点：**
1. 哈希目标：测试数据 vs 密码/密钥/签名
2. 安全边界：内部工具 vs 外部暴露 API（互联网可访问）
3. 数据敏感度：公开信息 vs PII/PCI DSS/等保合规数据
4. 对抗模型：是否需防御彩虹表/碰撞攻击
5. 生命周期：临时会话 vs 长期持久化存储
6. 替代方案：系统是否有 BCrypt/Argon2/SHA-256 实现
7. 调用频率：一次性迁移 vs 高频业务逻辑

## Low risk

**可接受的低风险场景：**
- 非安全用途的缓存键生成（Redis Key / ETag）
- 日志追踪 ID 生成（Trace ID / Span ID）
- 文件去重标识（内部系统备份，无对抗场景）
- 分布式锁键生成（内存锁标识）
- 消息幂等性校验（临时去重窗口 < 5 分钟）
- 开发环境/本地测试快速原型
- 读取 10 年前历史数据（一次性迁移脚本）
- 与遗留第三方系统互操作（对方只支持 MD5 且专线隔离）

**降级条件：**
- 数据已公开或低敏感度（非用户隐私/金融数据）
- 短期过渡方案有明确迁移里程碑（看板可查）
- 访问受严格网络隔离（VPC 专网 + 白名单 ACL）
- 仅向后兼容读取，所有新写入用 SHA-256/BCrypt
- 攻击窗口极短（一次性令牌 < 5 分钟 + 使用后失效）
- 已有外层强保护（TLS 1.3 + EdDSA 证书）
- 数据量极小且无重复模式（随机 UUID 无碰撞价值）
- 攻击成本远高于资产价值（内部低价值数据）

**注意：** MD5 已实现实用碰撞攻击（2008 年伪造 SSL 证书、2012 年 Flame 恶意软件），GPU 暴力破解简单密码 MD5 仅需秒级。SHA-1 已被 Google SHAttered 攻击证明碰撞可行（2017）。任何涉及身份认证、数字签名、PCI DSS / GDPR / 等保 2.0 合规的系统应立即迁移至 BCrypt（密码）/ SHA-256（通用哈希）/ HMAC-SHA256（签名）。低风险评级不代表接受长期使用，仅适用于有明确迁移计划的过渡期或非安全关键场景。