# Java JWT 弱密钥审计指南

## Details

### 代码示例
```java
// JJWT 库 - 漏洞示例：硬编码密钥
String secret = "123456"; // ⚠️ 弱密钥，易被暴力破解
Key key = Keys.hmacShaKeyFor(secret.getBytes());
Jwts.parserBuilder()
    .setSigningKey(key)
    .build()
    .parseClaimsJws(token);

// java-jwt 库 - 硬编码密钥
Algorithm algorithm = Algorithm.HMAC256("admin123"); // ⚠️ 硬编码弱密钥
JWTVerifier verifier = JWT.require(algorithm).build();

// 危险配置：密钥来自配置文件明文存储
String secret = properties.getProperty("jwt.secret"); // 可能是明文 "myapp123"
```

### 快速定位核心操作（L1: 关键词扫描）
- **密钥初始化关键词**：`Keys.hmacShaKeyFor()`, `Algorithm.HMAC256()`, `Algorithm.HMAC512()`, `SecretKey`, `setSigningKey()`
- **密钥来源点**：`Properties`, `properties.getProperty()`, `getEnv()`, `System.getProperty()`, 配置文件路径
- **搜索模式**：
  ```bash
  grep -rn "HMAC256\|HMAC512\|hmacShaKeyFor" --include="*.java" src/
  grep -rn "jwt.secret\|JWT_SECRET\|token.secret" --include="*.java" --include="*.properties" --include="*.yml"
  ```
- **密钥长度检查**：`String.length()`, `getBytes().length` 应 ≥ 32 字节（256 位）

### 快速定位保护机制（L2: 跳读）
- **密钥来源验证**：
  - L2：检查 `Properties.load()`, `@Value("${jwt.secret}")` 绑定的配置文件位置
  - 确认是否为外部安全存储（环境变量、密钥管理服务）而非代码库内
- **密钥强度验证**：
  - L3：逐行计算密钥长度，HMAC256 要求最少 32 字节，HMAC512 要求 64 字节
  - 检查密钥是否通过 `SecureRandom` 生成而非硬编码常数
- **密钥轮换机制**：
  - L4：跨模块追踪密钥加载逻辑，查找是否有版本控制或定期刷新机制
  - 检查 JwtParserBuilder 中 `SigningKeyResolver` 实现是否支持多密钥验证

## Classify

### 漏洞判定
- **明确漏洞**：
  - 硬编码密钥字面量在源代码中（如 `"admin123"`, `"password"`, `"123456"` 等常用弱密钥）
  - 密钥长度 < 32 字节（HMAC256）或 < 64 字节（HMAC512）
  - 密钥来自代码库内的配置文件（application.properties）而非外部密钥服务
  - 密钥使用可预测的种子或规律性字符串生成

### 误报识别
- **密钥动态注入**：通过环境变量、JVM 参数或密钥管理服务（Vault、AWS Secrets Manager）注入，源代码中仅为占位符
  ```java
  String secret = System.getenv("JWT_SECRET"); // ✓ 运行时注入
  ```
- **测试/开发环境密钥**：位于 test 目录或通过 @ConditionalOnProperty(name="spring.profiles.active", havingValue="dev") 隔离
- **密钥来自外部 HSM**：通过 KeyStore、SmartCard 等硬件模块提供，即使代码有引用也相对安全
- **盐值与密钥分离**：使用 PBKDF2 或 bcrypt 生成的密钥而非直接使用明文

### 代码异味
- **密钥缺乏版本控制**：无法追踪密钥变更历史或轮换计划
- **单密钥依赖**：无备用或旧密钥支持，密钥泄露后无法平滑过渡
- **日志中密钥泄露**：`logger.debug("Key: " + key)` 或异常堆栈中暴露密钥信息

## Audit Professional Techniques（审计技巧）

### 1. 密钥强度快速评估

#### 技巧：字节长度与算法匹配验证
```java
// 查看源码中的密钥长度
String secret = "mySecretKey"; // 11 字节 → HMAC256 需 32+ 字节，存在风险
byte[] keyBytes = secret.getBytes(StandardCharsets.UTF_8);
if (keyBytes.length < 32) { // HMAC256 的最小建议
    // ⚠️ 弱密钥风险
}

// 正确做法：使用足长随机密钥
byte[] keyBytes = new byte[32];
new SecureRandom().nextBytes(keyBytes);
Key key = Keys.hmacShaKeyFor(keyBytes);
```

#### 检查矩阵
| 密钥来源 | 长度检查 | 是否硬编码 | 风险等级 |
|---------|--------|----------|--------|
| 代码内字面值 | < 32B | 是 | 🔴 Critical |
| 配置文件明文 | < 32B | 是 | 🔴 Critical |
| 环境变量 | < 32B | 否 | 🟡 Medium |
| Vault/KMS | 任意 | 否 | 🟢 Low |

### 2. 真实漏洞与误报区分经验

#### 漏洞特征（High Confidence）

**场景A：application.properties 中的明文弱密钥**
```properties
# application.properties
jwt.secret=admin123
server.jwt.key=pass@123
```
- 特征：版本控制系统可见，开发人员可直接修改
- 证据：git log 中包含密钥变更记录或被 .gitignore 忽略但仍存在版本
- 实际风险：源码泄露→密钥泄露→JWT 伪造

**场景B：常见弱密钥组合**
```java
String[] weakSecrets = {"123456", "admin123", "password", "secret", "key", "test"};
// 审计判定：任何包含上述字符串的密钥初始化都可直接上报
```
- 布局破解时间：使用在线 jwt.io 或 hashcat，< 1 秒破解
- 误报可能性：极低（除非是示例代码）

**场景C：密钥长度明显不足**
```java
String secret = "key123"; // 6 字节
Algorithm algo = Algorithm.HMAC256(secret); // ⚠️ 需 32 字节
```

#### 误报识别规则（False Positive Patterns）

**规则1：环境变量注入的占位符**
```java
@Value("${JWT_SECRET:default-test-key}") // 默认值用于 test，生产来自环境变量
private String jwtSecret;
```
- 判定：查看实际部署配置，确认生产环境 JWT_SECRET 是否已设置
- 命令：`docker inspect <image> | grep JWT_SECRET` 或 Kubernetes ConfigMap 检查

**规则2：密钥管理服务中的密钥**
```java
// 从 Vault 动态获取，源码中无实际密钥
@Bean
public Key jwtSigningKey(VaultTemplate vault) {
    String secret = vault.read("secret/jwt-key").getData().get("value");
    return Keys.hmacShaKeyFor(secret.getBytes());
}
```
- 判定：低风险，密钥由专业密钥管理系统保护

**规则3：过期的开发/测试分支代码**
```java
// git branch develop 中的弱密钥，但 master 已修复
if (isDev()) { // 该条件是 test-only 标记
    secret = "dev123"; // 仅开发使用
}
```
- 判定：确认代码是否在生产分支上，以及该条件是否真正隔离

### 3. 跨源密钥来源追踪

#### 技巧：配置来源链溯源
```bash
# Step 1: 找到密钥属性名
grep -rn "jwt.secret\|JWT_SECRET" --include="*.java" src/

# Step 2: 追踪属性来源
grep -rn "jwt.secret" --include="*.properties" --include="*.yml" .

# Step 3: 检查配置加载顺序（Spring 优先级）
# 环境变量 > system properties > properties 文件 > 硬编码
# 优先级：System.getenv() > System.getProperty() > application-{profile}.properties

# Step 4: 验证生产环境配置
# K8s: kubectl get secret jwt-secret -o yaml
# Docker: docker inspect --format='{{json .Config.Env}}' <container>
# 文件系统：ls -la /etc/secrets/jwt* 或 /app/config/
```

#### 密钥版本管理检查
```bash
# 查看密钥变更历史
git log -p --all -S "jwt.secret\|JWT_SECRET" -- application*.properties

# 确认是否存在密钥轮换机制
grep -rn "keyId\|kid\|keyVersion" --include="*.java" src/
```

### 4. 真实审计案例模板

#### 案例1：典型硬编码弱密钥漏洞
```
【标题】JWT 签名密钥硬编码与弱密钥

【受影响代码】
- 文件：src/main/resources/application.properties:45
  内容：jwt.secret=admin@2023
- 文件：com/example/security/JwtConfig.java:23
  方法：Algorithm getAlgorithm()
  库版本：java-jwt 4.0.0

【风险证据】
1. 密钥长度：11 字节 < HMAC256 推荐 32 字节
2. 密钥组成：admin + 年份（可预测）
3. 来源：代码库 application.properties（版本控制可见）
4. git log 显示密钥曾被提交 10 次

【验证方式】
1. 使用 hashcat 破解：time cost < 1ms
2. 构造伪造 token，声称 admin 权限
3. 系统接受并处理该 token

【根本原因】
密钥管理完全依赖代码库，无外部密钥服务集成
```

## Low Risk

### 低风险场景
1. **密钥由专业 KMS 管理**：AWS Secrets Manager, HashiCorp Vault, 或企业 HSM 提供，源码无密钥明文
2. **非对称密钥（RSA/ECDSA）**：公钥用于验证，私钥安全存储，相对硬编码对称密钥更安全
3. **环境隔离明确**：应用仅在隔离容器/虚拟机内运行，网络隔离且无直接源码访问权限
4. **密钥自动轮换**：存在已验证的定期轮换机制（如每月变更），即使泄露影响有限
5. **只读权限限制**：Token 仅用于查询非敏感数据，无状态修改或权限提升可能

### 评级调整依据
- 若密钥用于敏感操作（如删除、转账、权限提升），即使长度足够也应维持中危或高危
- 密钥泄露时间越短（如仅在内存中）可适当降级，但应配合环境隔离措施
- 若存在自动告警和快速轮换能力，可在客观泄露下将风险从高危降至中危