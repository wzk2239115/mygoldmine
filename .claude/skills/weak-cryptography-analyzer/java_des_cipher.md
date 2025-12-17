# Java DES 弱加密算法审计

## Details

### 典型代码特征
```java
// Cipher API 使用 DES
Cipher cipher = Cipher.getInstance("DES");
SecretKey key = KeyGenerator.getInstance("DES").generateKey();
cipher.init(Cipher.ENCRYPT_MODE, key);
byte[] encrypted = cipher.doFinal(plaintext);

// 显式指定 DES/ECB/PKCS5Padding
Cipher cipher = Cipher.getInstance("DES/ECB/PKCS5Padding");
cipher.init(Cipher.ENCRYPT_MODE, secretKey);

// 使用 DESKeySpec 创建密钥
DESKeySpec desKeySpec = new DESKeySpec(keyBytes);
SecretKeyFactory keyFactory = SecretKeyFactory.getInstance("DES");
SecretKey secretKey = keyFactory.generateSecret(desKeySpec);

// 3DES (DESede) 仍基于 DES 原语
Cipher cipher = Cipher.getInstance("DESede/CBC/PKCS5Padding");
KeyGenerator keyGen = KeyGenerator.getInstance("DESede");

// BouncyCastle 提供商使用 DES
Security.addProvider(new BouncyCastleProvider());
Cipher cipher = Cipher.getInstance("DES", "BC");

// 硬编码 DES 密钥
byte[] keyBytes = {0x01, 0x23, 0x45, 0x67, (byte)0x89, (byte)0xAB, (byte)0xCD, (byte)0xEF};
SecretKeySpec key = new SecretKeySpec(keyBytes, "DES");

// JWT 使用 DES 签名
Algorithm algorithm = Algorithm.DES256("secret");  // 错误用法
JWTVerifier verifier = JWT.require(algorithm).build();
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "Cipher.getInstance.*DES" --include="*.java"
grep -rn "KeyGenerator.getInstance.*DES" --include="*.java"
grep -rn "DESKeySpec\|DESedeKeySpec" --include="*.java"
grep -rn "\"DES\"\|\"DESede\"\|\"3DES\"" --include="*.java"
grep -rn "Algorithm.DES\|HMAC.*DES" --include="*.java"
```

**高危 API 模式（L2 跳读）：**
- `Cipher.getInstance("DES")` / `getInstance("DES/ECB/*")`
- `Cipher.getInstance("DESede")` 3DES 系列
- `KeyGenerator.getInstance("DES")` / `getInstance("DESede")`
- `new DESKeySpec(byte[])` / `new DESedeKeySpec(byte[])`
- `SecretKeySpec(keyBytes, "DES")` 硬编码密钥
- `SecretKeyFactory.getInstance("DES")`
- 魔数：密钥长度 8 字节（DES）/ 24 字节（3DES）
- JWT 库错误配置使用 DES 算法

**函数调用链追踪（L3 逐行）：**
- 定位 `Cipher.getInstance()` 参数来源：字符串常量/配置文件/枚举
- 配置文件解析：`properties.getProperty("cipher.algorithm")`
- 枚举定义：`enum CipherType { DES, AES }` 检查 DES 分支
- Spring 配置：`@Value("${crypto.algorithm}")` 注入值检查
- 加密工具类：`CryptoUtil.encrypt()` 内部算法选择逻辑
- 数据库加密：Hibernate `@ColumnTransformer` / MyBatis TypeHandler
- 条件逻辑：`if(legacyMode) { return "DES"; }`

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 硬编码 `Cipher.getInstance("DES")` 无算法协商
- 配置文件默认值为 `cipher.algorithm=DES`
- 无算法白名单验证或版本检查
- 初始化代码无弱算法警告或拒绝逻辑
- `switch(algorithm)` 包含 `case "DES":` 分支

**伪保护识别（L3 逐行）：**
```java
// 3DES 仍是弱算法（有效密钥 112 位不足 128 位标准）
if(securityLevel > 1) {
    cipher = Cipher.getInstance("DESede/CBC/PKCS5Padding");  // 仍不够强
}

// 误认为 CBC 模式足以弥补 DES 弱点
Cipher cipher = Cipher.getInstance("DES/CBC/PKCS5Padding");
IvParameterSpec ivSpec = new IvParameterSpec(iv);  // 模式不解决密钥长度问题

// 配置降级逻辑
try {
    cipher = Cipher.getInstance("AES/GCM/NoPadding");
} catch(Exception e) {
    cipher = Cipher.getInstance("DES");  // 危险的降级路径
}

// 多层封装但底层仍用 DES
public class SecureEncryptor {
    private static final String ALGORITHM = "DES";  // 名不副实
    public byte[] secureEncrypt(byte[] data) { ... }
}
```

**跨模块保护追踪（L4）：**
- JCE 策略检查：`Security.getAlgorithms("Cipher")` 可用算法列表
- 运行时限制：自定义 SecurityManager 是否拒绝 DES
- Spring Security 配置：加密器工厂是否强制 AES
- 配置中心审计：Apollo/Nacos 中 `crypto.*` 配置项
- 依赖库版本：旧版 commons-codec / jose4j 可能默认弱算法
- Docker 镜像：JRE 版本是否限制弱算法（JDK 9+ 可配置）
- 合规检查：SonarQube / SpotBugs 规则是否启用 DES 检测
- JWT 库配置：`auth0-jwt` / `nimbus-jose-jwt` 算法白名单
- ORM 审计：实体类 `@Encrypted` 注解指定的算法

## Classify

**确认漏洞：**
- JWT/JWS 签名或加密使用 DES 算法
- 数据库敏感字段加密（身份证/银行卡/密码）
- 用户会话 Cookie 加密存储
- HTTPS 客户端证书/自签名证书使用 DES
- API 密钥、Access Token 加密传输
- 文件上传加密存储（用户隐私文件）
- 支付/交易数据加密保护
- 无替代算法的生产环境强制 DES

**研判误报：**
- 单元测试/集成测试用例（`src/test/java` 路径）
- 示例代码/文档注释中的演示（JavaDoc 示例）
- 已废弃方法明确标注 `@Deprecated` 且默认禁用
- 兼容性层仅解密历史数据（只读模式，新数据用 AES）
- Mock 对象/Stub 实现（测试替身非生产逻辑）
- 条件编译排除：`if(false)` / `// @Ignore` 测试方法

**代码异味：**
- 配置可选但默认 DES（应默认 AES-256-GCM）
- 日志显示 "Using DES for compatibility" 无迁移计划
- 3DES 作为"安全升级"方案（应直接 AES-256）
- 算法枚举中 DES 优先级高于 AES
- 注释 "TODO: 替换为 AES" 但代码仍活跃调用
- 性能测试结论"DES 更快"作为选择理由
- 可配置白名单包含 `allowedAlgorithms=DES,AES`

**关键判断点：**
1. 加密目标：测试数据 vs 生产敏感数据（PII/PCI DSS）
2. 调用路径：初始化测试 vs 实际业务逻辑（Controller/Service 层）
3. 替代方案：系统是否有 AES/ChaCha20 并行实现
4. 生命周期：活跃维护 vs 遗留兼容代码（Git blame 提交时间）
5. 攻击面：内部工具 vs 外部暴露 API（公网可访问）

## Low risk

**可接受的低风险场景：**
- 解密 10 年前归档数据（一次性迁移任务，非常驻服务）
- 与遗留系统互操作（第三方只支持 DES 且专线隔离）
- 开发环境快速原型（`application-dev.yml` 明确标注）
- 性能基准测试对照组（JMH Benchmark 非业务代码）
- 已有外层强加密的二次混淆（TLS 1.3 内部额外加密）
- 教学/培训代码（演示加密流程但不涉及真实数据）

**降级条件：**
- 数据已公开或低敏感度（非用户隐私/金融信息）
- 短期过渡方案有明确迁移时间表（项目看板可查）
- 访问受严格网络隔离（内网专用且 ACL 白名单）
- 仅向后兼容读取，所有写入已用 AES-256-GCM
- 攻击窗口极短（临时令牌 < 5 分钟有效期 + 一次性使用）
- 数据量极小且无重复模式（单次加密 16 字节随机密钥）

**注意：** DES 56 位密钥可在数小时内暴力破解（现代 GPU 集群），任何涉及 PCI DSS / GDPR / 等保 2.0 合规的系统应立即迁移至 AES-256-GCM 或 ChaCha20-Poly1305。3DES (DESede) 虽密钥长度增加但基于 DES 原语仍不推荐（NIST SP 800-131A 已弃用）。低风险评级不代表接受长期使用，仅适用于有明确迁移计划的过渡期。
