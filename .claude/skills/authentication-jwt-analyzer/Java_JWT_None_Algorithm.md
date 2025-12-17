# Java JWT None Algorithm 漏洞审计

## Details

### 代码示例
```java
// JJWT 库 - 漏洞示例
Jwts.parser()
    .setSigningKey(key)
    .parseClaimsJws(token);  // 未禁用 none 算法

// java-jwt 库 - 漏洞示例
Algorithm algorithm = Algorithm.none();  // 显式使用 none
JWTVerifier verifier = JWT.require(algorithm).build();

// 危险配置
Jwts.parser()
    .setAllowedClockSkewSeconds(300)
    // 缺少 requireAlgorithm() 限制
    .parseClaimsJws(token);
```

### 快速定位核心操作（L1: 关键词扫描）
- **搜索关键API**：`Jwts.parser()`, `JWT.require()`, `JWT.decode()`, `parseClaimsJws`, `parseClaimsJwt`
- **算法配置点**：`Algorithm.none()`, `.setSigningKey()`, `.requireAlgorithm()`
- **解析入口**：Controller/Filter/Interceptor 中的 token 解析逻辑
- **扫描模式**：`grep -r "parseClaimsJws\|JWT.require\|Algorithm.none" --include="*.java"`

### 快速定位保护机制（L2: 跳读）
- **白名单检查**：是否调用 `.requireAlgorithm(SignatureAlgorithm.HS256)` 等限制算法
- **配置验证**：
  - JJWT 0.10.x+: 检查 `JwtParserBuilder.requireAlgorithm()`
  - java-jwt: 检查 `Algorithm` 实例化时是否排除 `Algorithm.none()`
- **全局配置**：查找 Security/JWT 配置类中的 `JwtParser` Bean 定义
- **审计路径**：
  1. 定位 JWT 解析入口（L1）
  2. 回溯 JwtParser 实例化位置（L2）
  3. 检查算法白名单设置（L3）
  4. 验证配置是否可被覆盖（L4：跨模块追踪配置加载链）

## Classify

### 漏洞判定
- **明确漏洞**：
  - 显式使用 `Algorithm.none()` 且用于生产环境验证
  - 解析器未设置任何算法限制，直接接受外部 token
  - 配置中明确允许 "none" 算法：`setSigningKeyResolver` 返回 null key
  
### 误报识别
- **仅用于 token 解码**：使用 `JWT.decode()` 而非 `verify()`，后续有独立验证逻辑
- **测试代码**：位于 test 目录或测试类中的 none 算法使用
- **本地 Mock**：开发环境配置且有环境隔离保护
- **已废弃代码**：调用链分析确认该解析器未被引用

### 代码异味
- **依赖旧版本库**：JJWT < 0.10.0 默认行为存在风险，即使代码正确也应升级
- **过度宽松配置**：允许多种算法但未明确禁止 none
- **缺少文档**：安全相关配置无注释说明意图

## Audit Professional Techniques（审计技巧）

### 1. 深度版本与库分析
- **JJWT 0.9.x vs 0.10.x 行为差异**：
  - 0.9.x：默认允许 none 算法，需显式配置禁止
  - 0.10.x+：默认禁止 none，但 Builder API 使用不当仍可绕过
  - 审计策略：检查 `SignatureAlgorithmResolver` 实现，追踪自定义解析器

- **java-jwt 库特殊性**：
  - 版本 3.x-4.x：`Algorithm.none()` 存在但不推荐，需检查是否在验证链中被显式调用
  - 关键点：查看 `JWTVerifier.verify()` 前的 `Algorithm` 对象来源

- **导入语句追踪**：
  ```bash
  grep -r "import.*Algorithm.none\|import.*JWT" --include="*.java" | \
  awk -F: '{print $1}' | sort -u | xargs grep -l "parse\|verify"
  ```

### 2. 真实漏洞与误报区分经验

#### 真实漏洞特征（High Confidence）
1. **场景A：直接 none 算法生产使用**
   - 代码特征：`Algorithm.none()` 直接出现在认证关键路径
   - 证据：无条件分支，无环境检查，token 用于权限决策
   - 示例：
   ```java
   // 真实漏洞
   Algorithm algorithm = Algorithm.none();
   JWTVerifier verifier = JWT.require(algorithm).build();
   DecodedJWT jwt = verifier.verify(token); // 直接使用于权限检查
   ```

2. **场景B：JwtParser 无算法限制**
   - 代码特征：`Jwts.parser().parseClaimsJws()` 未被 `requireAlgorithm()` 链式调用
   - 检测方法：回溯到 JwtParser 实例化位置，确认无 `withSigningKeyResolver` 白名单
   - 风险等级：需结合 key 管理策略判定

3. **场景C：Key 管理缺陷+None 算法**
   - 证据链：无签名密钥配置 + none 算法允许 + 前端可构造 token
   - 实战场景：OAuth2 refresh_token 处理不当，前端直接修改 scope

#### 误报识别规则（False Positive Patterns）
1. **仅解码场景**
   ```java
   // 误报：仅用于解码，验证在后续
   DecodedJWT decoded = JWT.decode(token); // 无验证
   Algorithm algo = Algorithm.HMAC256(secret);
   JWTVerifier verifier = JWT.require(algo).build();
   verifier.verify(token); // 真正的验证点
   ```
   - 关键：`verify()` 出现在单独的、有密钥配置的验证器中

2. **测试代码污染**
   - 标志：文件路径包含 `test/`, `Test`, `Mock`, `Stub`
   - 进一步验证：检查 test 依赖范围（maven scope=test）
   - 陷阱：集成测试可能泄露到生产，需检查打包配置

3. **条件编译隔离**
   ```java
   if (isDevelopment()) {
       algorithm = Algorithm.none(); // @ConditionalOnProperty 或 profiles
   }
   ```
   - 验证点：配置文件、Spring profiles、环境变量，确保生产环境值

4. **降级/容错路径**
   ```java
   try {
       return verifyWithHMAC256(token, secret);
   } catch (JWTVerificationException e) {
       return JWT.decode(token); // 降级，但需检查后续权限验证
   }
   ```
   - 风险评估：降级后是否仍有完整的身份验证

### 3. 跨层审计技巧

#### 技巧一：追踪 JwtParser Bean 生命周期
```bash
# 查找 Spring Bean 定义
grep -r "@Bean\|@Component" --include="*.java" -A 10 | grep -B 5 "JwtParser\|Jwts.parser"
# 输出：确认 bean 的作用域、初始化方法、依赖注入
```

#### 技巧二：验证密钥来源完整性
```java
// 检查 setSigningKeyResolver 是否正确处理空 key
JwtParserBuilder builder = Jwts.parserBuilder()
    .setSigningKeyResolver(new SigningKeyResolver() {
        @Override
        public Key resolveSigningKey(JwsHeader header, Claims claims) {
            if (header.getAlgorithm().equals("none")) {
                return null; // ⚠️ 直接返回 null 导致漏洞
            }
            return loadKey(header.getKeyId());
        }
    });
```

#### 技巧三：上下文分析（Context-Aware Audit）
- **业务流程追踪**：token 生成→传输→解析→权限检查，每个环节是否可信
- **调用链验证**：`Authentication.getPrincipal()` 后是否立即用于权限决策
- **错误处理绕过**：`try-catch` 捕获验证异常后是否有隐性降级

### 4. 真实漏洞示例与审计报告模板

#### 漏洞示例（来自历史 CVE）
```java
// CVE-like: Spring Security + JJWT 0.9.0 组合
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) {
        String token = extractToken(request);
        try {
            Claims claims = Jwts.parser()  // ⚠️ 未调用 requireAlgorithm()
                    .setSigningKey(getKey())
                    .parseClaimsJws(token);
            // 直接使用 claims 中的 userid 进行权限检查
            request.setAttribute("userId", claims.getSubject());
        } catch (SignatureException e) {
            // 空的异常处理，攻击者可尝试 none 算法
            logger.warn("Invalid signature");
        }
    }
}
```

#### 审计报告模板
```
【标题】JWT None Algorithm 漏洞

【受影响代码】
- 文件：com/example/security/JwtAuthenticationFilter.java:45
- 方法：doFilterInternal()
- 库版本：JJWT 0.9.0（建议升级至 0.11.5+）

【验证步骤】
1. 生成 none 算法 token：
   curl -H "Authorization: Bearer $(python3 -c 'import base64; print(base64.urlsafe_b64encode(b\"{\\\"alg\\\":\\\"none\\\"}\").decode().rstrip(\"=\") + \".\" + base64.urlsafe_b64encode(b\"{\\\"sub\\\":\\\"admin\\\"}\").decode().rstrip(\"=\") + \".\")')" http://target/api/user

2. 观察：请求成功，无验证错误，获得 admin 权限

【根本原因】
JwtParser 未通过 requireAlgorithm() 限制算法白名单，在 token 验证前已接受任意算法

【修复建议】
- 升级 JJWT 至 0.11.5+ 并使用 parserBuilder() API
- 明确设置：.requireAlgorithm(SignatureAlgorithm.HS256)
- 添加单元测试验证 none 算法被拒绝
```

## Low Risk

### 低风险场景
1. **内部服务间调用**：Token 由可信服务签发且网络隔离，攻击面受限
2. **二次验证机制**：JWT 验证失败后还有数据库会话校验等后置检查
3. **只读权限**：Token 仅用于查询操作，无敏感数据访问或状态修改权限
4. **短生命周期**：结合 IP 白名单、设备指纹等额外约束，且 token 有效期 < 5 分钟
5. **降级场景**：异常处理中临时使用，有明确的降级监控和告警

### 评级调整依据
- 若存在权限提升路径或敏感数据泄露可能，即使有缓解措施也应维持高危
- 配合网络层访问控制（如 VPN、内网隔离）可降低一级风险
- 业务逻辑本身的容错能力（如幂等性、操作审计）可作为辅助降级因素