# Java - Disabled CSRF Protection

## Details

### 代码示例
```java
// Spring Security 配置类中显式禁用
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http.csrf().disable()  // 核心风险点
            .authorizeRequests()
            .anyRequest().authenticated();
    }
}

// Lambda 风格配置
http.csrf(csrf -> csrf.disable())

// 部分路径禁用
http.csrf().ignoringAntMatchers("/api/**")

// 传统 XML 配置
<http>
    <csrf disabled="true"/>
</http>
```

### 快速定位核心操作 **[L1-L2]**
- **关键词扫描 (L1)**：搜索 `csrf().disable()`、`csrf(csrf -> csrf.disable())`、`<csrf disabled="true">`、`ignoringAntMatchers`
- **配置类识别 (L2)**：定位 `@EnableWebSecurity`、`WebSecurityConfigurerAdapter`、`SecurityFilterChain` 注解的类
- **跳读技巧 (L2)**：直接跳转至 `configure(HttpSecurity http)` 方法体，扫描 `.csrf()` 链式调用
- **XML 配置 (L1)**：在 `spring-security.xml` 中搜索 `<csrf>` 标签属性

### 快速定位保护机制 **[L3-L4]**
- **Token 验证逻辑 (L3)**：检查自定义 Filter 中是否实现 `X-CSRF-TOKEN`、`_csrf` 参数校验
- **拦截器排查 (L3)**：审查 `HandlerInterceptor`、`@ControllerAdvice` 中的 CSRF 检查逻辑
- **跨模块追踪 (L4)**：若禁用 CSRF，需追踪：
  - 是否引入 JWT/OAuth2 等无状态认证（验证 token 生成与校验完整性）
  - Controller 层是否存在 `SameSite=Strict` Cookie 设置
  - 是否实现自定义 `CsrfTokenRepository`
- **配置优先级 (L3)**：检查是否存在多个 `SecurityFilterChain` Bean，确认配置覆盖关系

## Classify

### 判定为漏洞
- **Session 认证 + 禁用 CSRF**：传统表单登录且依赖 Cookie/Session，无任何 Token 验证机制
- **状态化操作未保护**：存在修改用户信息、转账、权限变更等 POST/PUT/DELETE 接口且无二次验证
- **关键路径豁免**：`ignoringAntMatchers` 排除了敏感操作路径（如 `/admin/**`、`/user/delete`）

### 判定为误报
- **纯 API 服务**：明确使用 JWT/OAuth2 Bearer Token，所有请求需携带 Authorization Header
- **无状态设计**：每个请求通过签名验证身份（如 HMAC、RSA 签名），不依赖浏览器 Cookie
- **公开只读接口**：仅提供 GET 查询且无副作用操作

### 判定为代码异味
- **防护降级**：从 CSRF 启用改为禁用，但未补充等效保护措施
- **配置不一致**：测试环境禁用但生产环境启用，存在配置漂移风险
- **注释说明缺失**：禁用 CSRF 无任何技术决策文档或代码注释

## Low Risk

- **纯后端服务**：不对外提供 Web 前端，仅供内部微服务间调用（需确认调用链无浏览器入口）
- **短期迁移**：明确从 Session 迁移至 JWT 的过渡期，且已有时间表和替代方案设计
- **双因素防护**：已实现验证码、短信验证、邮箱确认等二次验证覆盖所有敏感操作
- **严格 CORS + SameSite**：配置 `SameSite=Strict`、Origin 白名单严格限制且定期审计
- **只读 API 网关**：接口仅提供数据查询，所有写操作通过独立认证通道（如管理后台 + MFA）