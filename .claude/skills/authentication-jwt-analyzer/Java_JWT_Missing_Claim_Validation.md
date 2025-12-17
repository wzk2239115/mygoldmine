# Java JWT Missing Claim Validation

## 漏洞成因
JWT解码后未校验关键声明字段（exp/iss/aud/nbf等），导致过期令牌、未生效令牌或来自非法签发者的令牌被系统接受，突破时间和来源限制。

---

## Details

### 代码示例

**常见库：**
- `io.jsonwebtoken:jjwt`
- `com.auth0:java-jwt`
- `org.jose4j:jose4j`

**典型漏洞模式：**

```java
// 1. JJWT - 仅验签不校验声明
Jwts.parserBuilder()
    .setSigningKey(key)
    .build()
    .parseClaimsJws(token);  // 缺少 requireXxx() 调用

// 2. Auth0 java-jwt - 未配置验证器
JWTVerifier verifier = JWT.require(Algorithm.HMAC256(secret))
    // .withIssuer("trusted-issuer")    // 缺失
    // .withAudience("my-service")      // 缺失
    .build();
verifier.verify(token);

// 3. 手动解析不校验
Claims claims = Jwts.parser().setSigningKey(key).parseClaimsJws(token).getBody();
// 直接使用 claims 而不检查 exp/nbf/iss
```

### 快速定位核心操作（L1/L2）

**关键词扫描（L1）：**
- `parseClaimsJws` / `parseClaimsJwt` / `verify` / `decode`
- `JWT.require` / `Jwts.parser` / `JwtConsumer`
- `getClaims()` / `getBody()`

**跳读检查点（L2）：**
1. 验证器构建代码：是否有 `.require*()` / `.with*()` / `setAllowedClockSkew()` 等声明约束
2. 解析后立即判断：是否有 `claims.getExpiration()` 的时间比对
3. 全局配置：是否在配置文件/Bean初始化中统一设置验证规则

### 快速定位保护机制（L2/L3）

**跳读保护点（L2）：**
- 搜索 `.requireIssuer()` / `.withIssuer()` 确认发行者校验
- 搜索 `.requireAudience()` / `.withAudience()` 确认受众校验
- 搜索 `.require("exp")` / `setRequireExpirationTime(true)` 确认过期检查

**逐行追踪（L3）：**
- 检查 `JwtParserBuilder` 链式调用是否完整配置所有业务必需的声明
- 验证 `JWTVerifier` 构建时是否包含时间容差设置（避免绝对零容忍导致的时钟问题被误认为已修复）
- 确认自定义 `Validator` / `ClaimValidator` 是否真正执行（注意配置但未注入的情况）

**跨模块（L4）：**
- 追踪 Filter/Interceptor 中的JWT验证逻辑调用链，确认未在中间层被短路
- 检查是否存在开发环境特殊分支绕过校验逻辑（`if (env == "dev") skip validation`）

---

## Classify

### 确认漏洞
- **解析成功且未抛出异常**：过期或伪造的token能通过验证进入业务逻辑
- **缺少必需声明校验**：业务依赖 `iss` 区分租户或依赖 `aud` 区分服务，但代码未校验
- **时间窗口无限**：未设置 `exp` 校验，token永久有效

### 判定误报
- **框架自动处理**：Spring Security OAuth2/JWT 使用标准配置，框架已自动校验声明（需确认实际配置启用）
- **外层已拦截**：API网关或上游服务已完整校验，当前代码仅做二次解析获取用户信息
- **仅用于签名验证PoC**：测试代码或工具类，非实际认证路径

### 代码异味
- **部分校验**：仅验证 `exp` 但不验证 `iss/aud`，在单体应用中可能可接受，但多租户/微服务架构存在风险
- **冗余校验**：同时使用库校验 + 手动二次校验，功能正确但代码冗余

---

## Low Risk

### 降级场景
1. **仅内部通信**：JWT仅在同一信任域内服务间传递，且网络隔离，伪造成本极高
2. **短期token + 刷新机制**：token有效期 ≤ 5分钟且存在刷新令牌机制，未校验 `exp` 的窗口期影响有限
3. **二次授权校验**：业务逻辑中对关键操作有独立的权限校验（如数据库查用户状态），JWT仅用于初步识别
4. **只读场景**：token仅用于访问公开只读资源，即使被伪造也无数据篡改风险
5. **已有补偿控制**：WAF/API网关已强制校验声明，应用层是防御纵深的次要防线

### 注意事项
即使评为低风险，仍应记录为技术债：架构演进（如拆分微服务、外部集成）时风险会升级。