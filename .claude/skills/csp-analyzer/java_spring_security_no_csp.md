# java_spring_security_no_csp

**漏洞类型**: Spring Security 框架中未配置或缺失 CSP 响应头设置，或虽有配置但指令不完整，导致 XSS 防护缺失

---

## Details

### 代码示例

**易受攻击的代码模式**:

```java
// 示例1: Spring Security 配置未添加 CSP 响应头
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .authorizeRequests()
            .antMatchers("/admin/**").hasRole("ADMIN")
            .anyRequest().authenticated()
            .and()
            .formLogin();
        return http.build();
        // 缺失 CSP 响应头配置
    }
}

// 示例2: 使用 Spring Security 过滤链但未通过 headers() 配置 CSP
@Configuration
public class WebSecurityConfig extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .authorizeRequests()
                .antMatchers("/").permitAll()
                .antMatchers("/profile").authenticated()
                .and()
            .formLogin()
            .permitAll();
        // 未使用 headers().contentSecurityPolicy() 配置 CSP
    }
}

// 示例3: CSP 配置不完整（仅有 default-src）
@Configuration
@EnableWebSecurity
public class PartialCspConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .headers()
            .contentSecurityPolicy("default-src 'self'"); // 缺少 script-src、style-src 等关键指令
        return http.build();
    }
}

// 示例4: 使用不安全的 CSP 指令（unsafe-inline）
@Configuration
public class UnsafeCspConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .headers()
            .contentSecurityPolicy("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'");
        return http.build();
    }
}

// 示例5: 自定义过滤器但未正确设置 CSP 响应头
@Component
public class CustomSecurityFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        // 仅设置了基础安全头，缺少 CSP
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.setHeader("X-Frame-Options", "DENY");
        // 未设置 Content-Security-Policy 头
        filterChain.doFilter(request, response);
    }
}

// 示例6: 仅配置 Report-Only 模式而非强制执行
@Configuration
@EnableWebSecurity
public class ReportOnlyConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .headers()
            .contentSecurityPolicy("default-src 'self'; script-src 'self'")
            .and()
            .reportOnly(); // 使用 Report-Only 而非强制执行，攻击不被阻止
        return http.build();
    }
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Spring Security 配置类: `@EnableWebSecurity`, `extends WebSecurityConfigurerAdapter`, `SecurityFilterChain`
- HTTP 安全配置方法: `configure(HttpSecurity http)`, `filterChain(HttpSecurity http)`
- 响应头相关: `.headers()`, `.contentSecurityPolicy()`, `.reportOnly()`
- 自定义过滤器: `extends OncePerRequestFilter`, `Filter`, `response.setHeader()`
- 配置文件声明: `spring.security.headers.*`

**L2 跳读定位**:
- 查找所有 `@Configuration` 和 `@EnableWebSecurity` 注解的类
- 在配置类中定位 `filterChain()` 或 `configure()` 方法的实现
- 检查是否调用 `.headers()` 方法，以及是否链式调用 `.contentSecurityPolicy()`
- 追踪自定义过滤器的 `doFilterInternal()` 或 `doFilter()` 方法中的响应头设置
- 搜索 `response.setHeader("Content-Security-Policy"` 的出现位置

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- CSP 响应头配置位置: Spring Security `headers().contentSecurityPolicy()` 方法调用
- CSP 指令定义: 查看传入 `contentSecurityPolicy()` 方法的字符串参数
- 中间件级配置: 搜索 `HttpSecurity` 的 `headers()` 链式调用
- 自定义头部设置: 在过滤器或拦截器中的 `response.setHeader()` 调用

**L3 逐行分析**:
- CSP 策略字符串内容检查:
  - 是否定义了 `default-src` 作为后备指令
  - 是否为 `script-src` 显式指定 `'self'` 而非 `'unsafe-inline'` 或 `*`
  - 是否为 `style-src` 配置了白名单而非允许内联样式
  - 是否定义了 `frame-ancestors 'none'` 防止点击劫持
  - 是否配置了 `report-uri` 或 `report-to` 用于违规报告
- 执行模式检查: 是否使用 `.reportOnly()` 而非强制执行
- 多路由配置: 是否仅在某些特定路由配置了 CSP，其他路由缺失

**L4 跨模块追踪**:
- 追踪 `SecurityFilterChain` 链中其他过滤器是否曾设置或覆盖了 CSP 头
- 检查是否存在多个配置类冲突（如主配置和多个本地配置同时定义）
- 验证是否有过滤器顺序问题导致 CSP 设置被后置过滤器移除
- 检查应用程序启动日志中是否报告了安全头配置异常
- 查验框架级的默认安全头配置是否被禁用（如 Spring Boot 自动配置覆盖）

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- Spring Security 配置中完全未调用 `.headers().contentSecurityPolicy()` 方法
- 虽有 CSP 配置但完全缺少 `script-src` 指令，脚本加载不受控制
- CSP 策略包含 `'unsafe-inline'` 或 `'unsafe-eval'` 允许内联脚本执行
- CSP 中使用 `script-src *` 或仅 `script-src https:` 允许任意域加载脚本
- 所有返回 HTML 的响应都无 CSP 响应头保护
- 仅使用 `.reportOnly()` 模式而非强制执行的 CSP，违规脚本不被阻止

**误报判定**:
- 仅针对纯 API 端点的配置，这些端点不返回 HTML 内容
- 应用有完整且严格的 CSP 配置: 包含 `default-src`、`script-src`、`style-src`、`frame-ancestors` 等关键指令，且无不安全值
- 使用 Helmet 或专门的 CSP 库进行了额外的头部配置，Spring Security 未配置但库已补偿
- 在 `web.xml` 或其他框架级别进行了全局 CSP 配置覆盖
- 有多层防御: 模板引擎使用了自动转义、前端框架进行了 XSS 清理等

**代码异味**:
- CSP 策略仅定义 `default-src 'self'` 而未为 `script-src` 和 `style-src` 单独配置
- 使用黑名单方式配置白名单（如 `script-src 'self' https:` 允许所有 HTTPS 域）
- 有 CSP 配置但条件化应用（如仅对特定用户或特定路由应用），导致部分页面无保护
- CSP 头中使用了不必要的通配符或过于宽松的源（如 `https:` 协议限制）
- 虽配置了 CSP 但未配置 `report-uri` 用于监控违规，无法检测攻击

---

## Low risk

### 低风险场景

**应用架构与功能限制**:
- 应用为纯 API 后端，所有端点返回 JSON/XML 而非 HTML，无 XSS 威胁向量
- 所有用户输出内容都通过模板引擎的默认自动转义机制进行了 HTML 编码
- 应用仅处理可信数据源（管理员或系统生成的内容），无用户生成内容展示
- 页面内容完全静态，由前端框架（Vue、React）以 SPA 方式渲染，后端无权返回 HTML

**防御深度与技术补偿**:
- 虽无 CSP 配置但使用了 Content-Type 明确声明（`charset=UTF-8`）且浏览器强制执行 MIME 检查
- 所有用户可控数据都经过严格的 HTML 转义函数（如 OWASP ESAPI、Spring 的 HtmlUtils.htmlEscape()）
- 使用现代 Java 模板引擎（Thymeleaf 配置 `th:text`、Jinja2 默认转义）进行了默认转义
- 前端框架采用单页应用模式，完全避免了服务端 HTML 生成

**部分有效的缓解措施**:
- CSP 配置虽不完整（缺失某些指令）但核心 `script-src 'self'` 已配置且无不安全值
- 其他 Spring Security 安全头已完整配置（`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`）可部分缓解相关风险
- 应用在受控网络环境部署（内网系统、VPN 保护），外部攻击者无法直接访问
- 使用了 Web 应用防火墙（WAF）或前置反向代理进行了全局 CSP 头注入

**使用情景与权限约束**:
- 后台管理系统仅限公司内部员工访问，且有严格的身份认证和操作日志
- 应用所有表单提交都使用 CSRF Token 保护，XSS 的实际利用价值受限
- 共享浏览上下文的页面数量极少，跨页面 Cookie 盗取的威胁较小
- 应用运行在 `Secure` 和 `HttpOnly` Cookie 配置下，攻击者获得脚本执行也难以直接获取认证凭证
