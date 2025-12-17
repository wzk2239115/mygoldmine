# Java - 不安全的 JWT 验证

## Details

### 代码示例

**典型漏洞场景：**

```java
// 1. 允许 none 算法（无签名）
Jwts.parser()
    .setSigningKey(key)
    .parse(token);  // 使用 parse() 而非 parseClaimsJws()

// 2. 未验证签名直接解析
String[] parts = token.split("\\.");
String payload = new String(Base64.getDecoder().decode(parts[1]));
JSONObject claims = new JSONObject(payload);

// 3. 自定义解析器绕过安全校验
JWT jwt = JWTParser.parse(token);
jwt.getJWTClaimsSet();  // 未调用验证器

// 4. 密钥硬编码或弱密钥
.setSigningKey("secret")
.setSigningKey(DatatypeConverter.parseBase64Binary("MTIzNDU2"))

// 5. 未校验算法头（算法混淆攻击）
Claims claims = Jwts.parser()
    .setSigningKey(publicKey)
    .parseClaimsJws(token)
    .getBody();  // 若 header 指定 HS256，会用公钥当 HMAC 密钥

// 6. 缺少过期校验
Jwts.parser()
    .setSigningKey(key)
    .parseClaimsJws(token);  // 未设置 Clock 或 setAllowedClockSkewSeconds

// 7. 信任 Header 中的 kid/jku
JWSHeader header = jwt.getHeader();
String keyId = header.getKeyID();
Key key = keyMap.get(keyId);  // 攻击者可控 kid，指向恶意密钥
```

**常见库：**
- `io.jsonwebtoken:jjwt` (JJWT)
- `com.auth0:java-jwt` (Auth0)
- `com.nimbusds:nimbus-jose-jwt` (Nimbus)
- `org.springframework.security:spring-security-oauth2-jose`

### 快速定位核心操作的技巧

**【L1】关键词扫描**
```
Jwts.parser | JWT.decode | JWTParser.parse | parseClaimsJws | 
io.jsonwebtoken | com.auth0.jwt | nimbus | JwtDecoder
```

**【L2】跳读定位**
- 搜索 `.parse(` 定位到 JWT 解析入口
- 关注是否直接 `split("\\.")` 手动解析 Base64
- 检查 `setSigningKey()` 前后是否有密钥获取逻辑

**【L3】逐行审查**
- **JJWT**：区分 `parse()` (不验签) vs `parseClaimsJws()` (验签)
- **Auth0**：区分 `JWT.decode()` (不验签) vs `JWTVerifier.verify()` (验签)
- **Nimbus**：检查是否创建 `JWSVerifier` 并调用 `verify()`
- 追踪 `setSigningKey()` 的参数来源，是否硬编码或弱密钥

**【L4】跨模块追踪**
- 密钥来源：从配置文件/数据库/环境变量加载，评估安全性
- 算法白名单：是否在 Filter/Interceptor 层面限制算法
- 自定义解析器：追踪自研 JwtUtil 工具类的实现逻辑
- 框架配置：Spring Security OAuth2 中 `JwtDecoder` Bean 的配置方式

### 快速定位保护机制的技巧

**【L1】关键词扫描**
```
parseClaimsJws | JWTVerifier.verify | requireAlgorithm | 
setSigningKeyResolver | setAllowedClockSkewSeconds | 
JwtDecoder.withSecretKey | NimbusJwtDecoder
```

**【L2】跳读检查**
- 是否存在 `parseClaimsJws()` 或 `verify()` 调用
- 是否配置 `requireAlgorithm()` 或算法白名单
- 是否显式设置 `Clock` 进行过期校验

**【L3】逐行验证**
- **签名校验**：
  - JJWT: `parseClaimsJws()` 而非 `parse()`
  - Auth0: `Algorithm.HMAC256(secret).verify()` 或创建 `JWTVerifier`
  - Nimbus: `new MACVerifier(secret)` + `signedJWT.verify(verifier)`
  
- **算法限制**：
  ```java
  // Auth0
  .requireAlgorithm("HS256", "RS256")
  
  // JJWT (需自定义)
  if (!jwt.getHeader().getAlgorithm().equals("HS256")) throw ...
  
  // Nimbus
  new DefaultJWTProcessor().setJWSKeySelector(
      new JWSVerificationKeySelector<>(JWSAlgorithm.RS256, keySource)
  )
  ```

- **过期校验**：
  ```java
  // JJWT 自动校验 exp，可调整容差
  .setAllowedClockSkewSeconds(60)
  
  // Auth0
  .acceptExpiresAt(System.currentTimeMillis() / 1000)
  
  // Nimbus 自动校验 exp，可设置 Clock
  ```

**【L4】框架级保护**
- **Spring Security**：检查 `JwtDecoder` Bean 是否正确配置
  ```java
  @Bean
  JwtDecoder jwtDecoder() {
      return NimbusJwtDecoder.withSecretKey(secretKey)
          .macAlgorithm(MacAlgorithm.HS256).build();
  }
  ```
- **自定义过滤器**：追踪 Filter 链中是否有统一的 JWT 校验逻辑
- **网关层**：检查 Gateway/Zuul 是否前置验证 JWT

## Classify

### 漏洞判定

**确认为真实漏洞：**
1. **完全不验签**：直接 Base64 解码或使用 `parse()`/`decode()` 不验签方法，且业务逻辑信任 Claims 内容（如权限判断、用户身份）
2. **允许 none 算法**：未限制算法白名单，攻击者可伪造 `{"alg":"none"}` 的 Token
3. **算法混淆可利用**：使用 RS256 验证但未校验算法头，攻击者可降级为 HS256，用公钥当 HMAC 密钥伪造 Token
4. **密钥可预测**：硬编码弱密钥（如 `"secret"`、`"123456"`）或默认密钥，可被暴力破解
5. **kid/jku 注入**：从 Header 中提取 `kid` 动态加载密钥，未校验来源可导致任意密钥注入

### 误报识别

**非漏洞场景：**
1. **仅用于解析结构**：调用 `parse()` 不验签，但后续流程中有独立的签名验证逻辑（如网关已验证，内部服务仅解析）
2. **不可信 Token 未使用**：解析 JWT 但结果未用于安全决策（如仅记录日志、统计分析）
3. **双重验证**：虽使用 `decode()` 但后续调用了 `verify()`
4. **测试代码**：单元测试中的 Mock Token 生成代码（需确认非生产环境）

### 代码异味

**需进一步评估：**
1. **密钥管理不规范**：密钥从配置文件读取但文件权限过宽或版本控制中泄露
2. **过期时间过长**：设置 `exp` 为数年后，虽验签但 Token 生命周期过长增加被盗用风险
3. **缺少 jti 防重放**：验签正常但未实现 Token ID 黑名单机制，注销后的 Token 仍可用
4. **自定义实现**：自研 JWT 工具类但实现存在逻辑缺陷（需深度审计）

## Low risk

**以下场景应评为低风险：**

1. **内网隔离环境**：JWT 仅在内网微服务间传递，且网络边界有强认证（如 mTLS），即使验证不严格，外部攻击者无法触达

2. **已有前置防护**：
   - API 网关层已统一验证 JWT 签名和算法，后端服务重复验证缺失影响有限
   - WAF/安全网关已拦截 `alg:none` 等异常 Token

3. **Token 内容无关键信息**：JWT 中仅包含非敏感数据（如公开的用户昵称），即使被伪造也不影响权限控制，实际权限判断依赖后端 Session 或数据库查询

4. **临时性 Token**：有效期极短（如 5 分钟）且配合刷新机制，配合 IP/设备指纹绑定，窗口期内攻击价值低

5. **只读操作场景**：JWT 仅用于身份展示或查询个人非敏感数据，不涉及写操作或越权风险

6. **强制双因素认证**：关键操作需二次验证（如 OTP、短信验证码），JWT 伪造无法完成完整攻击链

7. **密钥轮换机制完善**：虽密钥在配置文件中，但有自动化定期轮换（如每周更换）且历史 Token 会失效，降低密钥泄露影响

**风险提升因子（需上调严重性）：**
- Token 用于管理员身份验证
- Token 中包含权限信息（如 `role:admin`）且直接用于鉴权
- 外部可访问的接口依赖该 JWT
- Token 有效期超过 24 小时且无刷新机制