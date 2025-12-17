# Java - Weak Spring Security Config

## Details

### 典型代码示例

**场景1：全局 permitAll 滥用**
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http.authorizeRequests()
            .antMatchers("/**").permitAll()  // 所有路径无需认证
            .and().csrf().disable();
    }
}
```

**场景2：敏感路径未保护**
```java
http.authorizeRequests()
    .antMatchers("/public/**").permitAll()
    .antMatchers("/admin/**").permitAll()  // 管理接口开放
    .antMatchers("/api/user/delete").permitAll()  // 危险操作开放
    .anyRequest().authenticated();
```

**场景3：认证链缺失或顺序错误**
```java
http.authorizeRequests()
    .anyRequest().permitAll()  // 先设置全放行
    .antMatchers("/admin/**").hasRole("ADMIN");  // 后设置的规则不生效
```

**场景4：授权粒度过粗**
```java
http.authorizeRequests()
    .antMatchers("/api/**").authenticated()  // 仅要求登录，无角色校验
    .anyRequest().permitAll();
```

**场景5：方法级安全未启用**
```java
@Configuration
public class SecurityConfig {
    // 缺少 @EnableGlobalMethodSecurity 注解
    // Controller中的 @PreAuthorize 不会生效
}
```

---

### 快速定位核心操作的技巧

**【L1：关键词扫描】**
- 搜索类注解：`@EnableWebSecurity`、`@Configuration`
- 搜索配置方法：`configure(HttpSecurity`、`authorizeRequests()`
- 搜索放行关键词：`permitAll()`、`.anonymous()`

**【L2：跳读配置链】**
- 扫描 `antMatchers()` 参数中的路径模式（`/**`、`/admin/**`、`/api/**`）
- 检查链式调用的顺序（Spring Security 按顺序匹配，先匹配先生效）
- 快速识别 `anyRequest()` 的位置和处理方式

**【L3：逐行分析路径规则】**
- 对比路径规则与实际 Controller 映射是否对应
- 检查通配符范围（`/**` vs `/public/*` vs `/public/**`）
- 验证角色名称拼写（`hasRole("ADMIN")` vs 实际角色）

**【L4：跨模块追踪】**
- 检查是否存在多个 SecurityConfig（多配置可能冲突）
- 追踪自定义 Filter 的执行顺序（`addFilterBefore/After`）
- 验证 `UserDetailsService` 的权限分配逻辑

---

### 快速定位保护机制的技巧

**【L1：关键词扫描】**
- 搜索防护注解：`@EnableGlobalMethodSecurity`、`@PreAuthorize`、`@Secured`
- 搜索拦截器：`addFilterBefore`、`OncePerRequestFilter`
- 搜索会话管理：`sessionManagement()`、`SessionCreationPolicy`

**【L2：跳读保护链路】**
- 检查是否配置认证入口：`formLogin()`、`httpBasic()`、`oauth2Login()`
- 扫描异常处理：`exceptionHandling()`、`authenticationEntryPoint()`
- 快速定位 CSRF 状态：`.csrf().disable()` 或 `.csrf()`

**【L3：逐行验证保护覆盖】**
- 检查 `anyRequest()` 后是否跟 `.authenticated()` 或 `.denyAll()`
- 验证自定义 Filter 是否正确注册到 SecurityFilterChain
- 分析 `access()` 表达式的 SpEL 逻辑是否严谨

**【L4：跨模块追踪防御深度】**
- 追踪 Service 层是否有二次权限校验（`@PreAuthorize("hasPermission(...)")`）
- 检查 AOP 切面是否对敏感方法做额外拦截
- 验证数据库查询是否带用户隔离条件（防止越权）

---

## Classify

### 漏洞研判标准

**确认为漏洞的情况：**
1. **暴露高危接口**：管理功能（/admin/\*\*）、数据操作（/delete、/update）、配置修改等路径使用 `permitAll()`
2. **认证完全失效**：全局 `antMatchers("/**").permitAll()` 且无其他拦截机制
3. **规则顺序错误**：先设置 `permitAll()`，后设置的 `authenticated()` 规则不生效
4. **方法级保护失效**：Controller 使用 `@PreAuthorize` 但配置类缺少 `@EnableGlobalMethodSecurity`

**误报的情况：**
1. **路径匹配范围不同**：代码扫描误判通配符范围（如 `/public/*` 仅匹配一级路径）
2. **存在自定义 Filter**：Security 配置宽松，但自定义过滤器已做鉴权（需跨模块追踪）
3. **前端路由防护**：静态资源路径（/static/\*\*）开放是正常行为
4. **测试环境配置**：通过 `@Profile("dev")` 区分环境的宽松配置

**代码异味（低优先级）：**
1. **冗余配置**：多次声明相同路径规则（如同时配置 `/api/**` 和 `/api/user/**`）
2. **过度使用 authenticated()**：所有接口仅要求登录，未细化角色权限（不一定是漏洞，但不符合最小权限原则）
3. **缺少注释**：复杂 SpEL 表达式或特殊路径规则未说明原因

**研判流程：**
1. 先确认路径是否对应敏感功能（查 Controller 映射）
2. 再检查是否存在其他层防护（Filter、AOP、Service 校验）
3. 最后评估业务影响（公开接口的敏感度、可触发的操作危害）

---

## Low risk

### 低风险评级标准

**符合以下条件可降低风险等级：**

1. **接口无敏感操作**  
   开放的路径仅提供查询、统计等只读功能，且数据本身为公开信息（如公告列表、公开文档）

2. **存在业务层二次校验**  
   Security 配置宽松，但 Service 层方法上有 `@PreAuthorize` 注解，或内部逻辑包含手动权限判断

3. **限制条件明确**  
   虽然路径开放，但通过参数校验、IP 白名单、请求头验证等其他方式限制访问

4. **影响范围受控**  
   仅影响非生产环境（通过 `@Profile` 或配置中心动态控制）

5. **功能本身低价值**  
   开放的接口用于健康检查、版本信息、公开 API 文档等非关键功能

6. **需认证但无需授权**  
   要求登录（`authenticated()`）但未细化角色，适用于普通用户功能（如修改个人资料），且操作仅限当前用户数据

7. **补偿性控制到位**  
   虽然配置弱，但有 WAF 防护、API 网关鉴权、数据库行级权限等外部防御措施

**评估注意事项：**
- 低风险不等于无风险，需结合实际业务场景判断
- 若存在多个低风险点组合，可能形成攻击链，需整体评估
- 应在审计报告中说明降级理由，避免遗漏真实风险