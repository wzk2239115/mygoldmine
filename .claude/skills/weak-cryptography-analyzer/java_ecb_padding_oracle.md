# Java ECB 填充预言攻击审计

## Details

### 典型代码特征
```java
// ECB模式 + PKCS5Padding（易受填充预言攻击）
import javax.crypto.Cipher;

Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
cipher.init(Cipher.DECRYPT_MODE, secretKey);
byte[] decrypted = cipher.doFinal(ciphertext);  // 抛出BadPaddingException

// DES-ECB + PKCS5Padding
Cipher cipher = Cipher.getInstance("DES/ECB/PKCS5Padding");
cipher.init(Cipher.ENCRYPT_MODE, key);
byte[] encrypted = cipher.doFinal(plaintext);

// 默认ECB模式（隐式ECB + PKCS5Padding）
Cipher cipher = Cipher.getInstance("AES");  // 默认AES/ECB/PKCS5Padding
cipher.init(Cipher.DECRYPT_MODE, key);

// 异常处理暴露填充状态
try {
    byte[] data = cipher.doFinal(encrypted);
    return "success";
} catch (BadPaddingException e) {
    return "invalid padding";  // 时序差异或错误消息泄露
} catch (Exception e) {
    return "other error";
}

// HTTP响应暴露填充状态
@PostMapping("/decrypt")
public String decrypt(String token) {
    try {
        cipher.doFinal(Base64.decode(token));
        return "OK";
    } catch (BadPaddingException e) {
        return "Invalid token";  // 不同错误信息
    } catch (IllegalBlockSizeException e) {
        return "Invalid length";
    }
}

// 日志泄露填充信息
try {
    decrypted = cipher.doFinal(data);
} catch (BadPaddingException e) {
    log.error("Padding error: " + e.getMessage());  // 日志可观察
    throw new InvalidDataException();
}

// 可配置的ECB模式
String transformation = config.getString("cipher.mode");  // "AES/ECB/PKCS5Padding"
Cipher cipher = Cipher.getInstance(transformation);

// Spring加密工具配置ECB
@Bean
public TextEncryptor textEncryptor() {
    return Encryptors.text(password, salt);  // 内部可能用ECB
}
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "Cipher\.getInstance.*ECB" --include="*.java"
grep -rn "Cipher\.getInstance(\"AES\")" --include="*.java"  # 默认ECB
grep -rn "Cipher\.getInstance(\"DES\")" --include="*.java"
grep -rn "PKCS5Padding\|PKCS7Padding" --include="*.java"
grep -rn "BadPaddingException" --include="*.java"
grep -rn "doFinal.*catch.*BadPadding" --include="*.java"
```

**高危API模式（L2 跳读）：**
- `Cipher.getInstance("AES/ECB/PKCS5Padding")` 或 `"DES/ECB/PKCS5Padding"`
- `Cipher.getInstance("AES")` 不指定模式（默认ECB+PKCS5）
- `Cipher.getInstance("DES")` 不指定模式
- `cipher.doFinal()` 捕获 `BadPaddingException` 且有差异化处理
- HTTP响应区分 `BadPaddingException` 和其他异常
- 日志记录 `e.getMessage()` / `e.printStackTrace()`
- 异常处理时序差异（catch块内复杂逻辑耗时不同）
- 配置文件包含 `"ECB"` / `"PKCS5"` 关键词
- `transformation` 变量从外部传入或配置读取

**函数调用链追踪（L3 逐行）：**
- 解密入口：RESTful接口 / WebSocket消息处理 / Cookie解密
- 异常传播：`BadPaddingException` 是否向上层抛出
- 响应构造：HTTP状态码、错误消息、响应时间差异
- 日志配置：`log.error()` / `logger.debug()` 输出内容
- 错误页面：`@ExceptionHandler` 是否区分填充错误
- 业务逻辑：解密失败后的重试机制、降级策略
- 加密模式配置：`application.yml` / `@Value("${crypto.mode}")`
- 条件分支：`if (legacy) { useECB() }` 兼容模式

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 直接捕获 `BadPaddingException` 返回不同消息
- HTTP响应体包含 "padding error" / "invalid padding"
- 异常栈打印到日志或响应
- 无统一异常处理：每个catch块返回不同内容
- 解密失败重试次数不限（可被滥用）
- 未验证密文完整性（无HMAC/GCM）

**伪保护识别（L3 逐行）：**
```java
// 统一错误消息但时序差异仍可观察
try {
    data = cipher.doFinal(encrypted);
    processData(data);  // 成功路径有额外耗时
} catch (Exception e) {
    return "Error";  // 消息统一但时序不同
}

// 通用异常捕获但日志泄露
try {
    decrypted = cipher.doFinal(input);
} catch (Exception e) {
    log.debug("Decryption failed: " + e.getClass().getName());  // 日志可观察
    return Response.error();
}

// 限流保护但窗口过大
@RateLimiter(limit = 1000, window = "1m")  // 1000次/分钟仍可攻击
public void decrypt(byte[] data) { ... }

// 条件性ECB使用（开发环境）
if (env.equals("dev")) {
    cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");  // 配置易混入
}

// 误认为AES-256足够安全
if (security.equals("high")) {
    key = generateKey(256);  // 强密钥
    cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");  // 模式仍弱
}

// 错误的异常聚合
catch (GeneralSecurityException e) {
    // 包含BadPaddingException但其他异常处理逻辑不同
    if (retryCount < 3) { retry(); }  // 时序特征
}
```

**跨模块保护追踪（L4）：**
- 全局异常处理器：`@ControllerAdvice` 是否统一处理加密异常
- 日志配置：`logback.xml` / `log4j2.xml` DEBUG级别是否暴露
- 监控告警：APM工具是否记录异常类型和频率
- API网关：Kong/Zuul是否有统一错误响应
- 限流策略：Redis限流器窗口大小和阈值
- 加密库封装：`CryptoUtil.decrypt()` 内部异常处理
- 配置中心：Apollo/Nacos配置项是否允许ECB
- 单元测试：测试用例中ECB配置是否影响生产
- 依赖库：`spring-security-crypto` 版本和配置
- 代码审查规则：SonarQube/Checkstyle是否检测ECB+Padding

## Classify

**确认漏洞：**
- 解密接口可公开访问且区分填充错误
- HTTP响应包含不同错误消息（"bad padding" vs "invalid length"）
- 异常处理时序差异可测量（成功/失败路径耗时不同）
- 日志输出 `BadPaddingException` 且攻击者可读
- Cookie/JWT解密失败返回不同状态码（401 vs 400 vs 500）
- WebSocket/gRPC返回不同错误码
- 无限流或限流阈值过高（允许大量解密尝试）
- ECB模式 + 可观察填充验证 = 高危

**研判误报：**
- 测试代码中的ECB配置（`src/test/` 且不影响生产）
- 示例代码演示填充预言攻击原理（教学用途）
- 已弃用API明确标注 `@Deprecated`
- 解密接口需强认证且有严格限流（<10次/小时）
- 内部服务间RPC调用（网络不可达外部）
- 配置系统确保生产强制GCM模式
- 异常统一返回且时序恒定（添加固定延迟）

**代码异味：**
- 注释 "TODO: migrate to GCM"（计划但未实施）
- 可配置模式但默认ECB（"便于开发"）
- 统一错误消息但无固定时序（仍有侧信道风险）
- 限流存在但阈值基于业务而非安全考量
- 分环境配置：开发ECB，生产"应该"用GCM
- 异常包装：`throw new BusinessException()` 但底层日志仍记录
- 依赖遗留代码注释 "for backward compatibility"

**关键判断点：**
1. **可观察性**：攻击者能否区分填充有效/无效（响应/日志/时序）
2. **访问性**：解密接口是否公开/需认证/内网隔离
3. **限流强度**：允许尝试次数（填充预言需大量请求）
4. **模式组合**：ECB + Padding + 差异化响应 = 三要素齐全
5. **数据敏感性**：解密内容是否包含敏感信息（会话令牌/密码）
6. **演化路径**：新开发用ECB（高危）vs 遗留且有迁移计划

## Low risk

**可接受的低风险场景：**
- 解密接口需双因素认证且严格限流（<5次/小时/用户）
- 完全内网服务且网络物理隔离（无公网暴露）
- 解密数据为非敏感配置（UI主题/缓存键）
- 异常响应统一 + 固定延迟（无时序差异）+ 限流（<10次/分钟）
- 兼容性解密旧数据（只读模式，新数据用GCM）

**降级条件：**
- 有应用层完整性验证（HMAC-SHA256预验证，填充错误不可达）
- 外层认证极强（OAuth2 + mTLS + IP白名单）
- 限流 + WAF规则（检测重复解密尝试模式）
- 解密前验证签名（JWE结构，填充错误前已拒绝）
- 监控告警实时触发（异常频率>10次/分钟立即阻断）
- 数据已过期（解密历史快照，无实时价值）

**注意：** 填充预言攻击原理是通过大量解密尝试推断明文，ECB模式使每个块独立可攻击。即使有限流，如果时间窗口足够长仍可完成攻击。OWASP建议统一使用 `AES/GCM/NoPadding`（认证加密）或 `AES/CBC/PKCS5Padding` + HMAC。任何公开解密接口使用ECB+Padding且有可观察差异都应视为高危。低风险评级仅适用于内网隔离 + 强认证 + 严格限流 + 统一响应 + 固定时序的极端场景。生产环境应迁移至 GCM/CCM 认证加密模式消除填充预言攻击面。