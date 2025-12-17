# Java Spring CSRF 防护被关闭漏洞

## Details

### 漏洞成因
Spring Security 默认对需要身份认证的 Web 应用启用 CSRF 防护。当开发者在 `SecurityConfig` 中调用 `http.csrf().disable()`，或通过`SecurityFilterChain` 将 CSRF 过滤器移除，所有依赖表单登录或 Cookie 认证的敏感端点将不再校验 Token。常见原因包括误认为 REST API 不需要 CSRF、防止跨域调试不便、或忽略了部分端点仍依赖 Cookie。

### 代码示例

**易受攻击的代码：**
```java
@Configuration
public class SecurityConfig {
    @Bean
    SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf().disable() // 全局关闭 CSRF
            .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
            .formLogin();
        return http.build();
    }
}
```

**另一个不安全示例（特定环境关闭）：**
```java
if ("dev".equals(environment)) {
    http.csrf().disable(); // 开发环境关闭，部署时忘记恢复
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `http.csrf().disable()`, `csrf(AbstractHttpConfigurer::disable)`
- `http.csrf().ignoringRequestMatchers(...)`
- XML 配置：`<csrf disabled="true"/>`

**定位步骤：**
1. 搜索 Security 配置类和 XML，确认是否显式禁用 CSRF。
2. 检查使用 `SecurityFilterChain` 的 Bean 是否调用 `csrf(AbstractHttpConfigurer::disable)`。
3. 跳读（L2）查看是否仅对 REST API 禁用，但敏感端点仍使用表单/Cookie。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **局部豁免**：`ignoringRequestMatchers` 是否仅针对无状态端点。
- **Token 生成**：`CsrfTokenRepository`（Session、Cookie）是否配置。
- **前端整合**：模板是否使用 `<input type="hidden" name="_csrf">`。
- **替代防护**：是否启用 SameSite Cookie、Origin 校验或双重提交。

**定位技巧：**
- 分析项目是否同时提供 REST + Web 界面，避免全局禁用。
- 检查测试/开发配置是否与生产一致。
- 关注登录、注销、支付等端点是否仍依赖 Cookie。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局启用 CSRF，细粒度豁免 | **L0（快速跳过）** | 风险低 |
| 某些端点忽略 CSRF | **L2（跳读）** | 需确认是否必要 |
| 全局 disable | **L3（逐行读）** | 高风险 |
| 多环境配置不一致 | **L4（跨模块追踪）** | 需排查部署差异 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. Spring Security 中全局禁用了 CSRF。
2. 应用存在依赖 Cookie/表单的敏感操作。
3. 未提供等效防护措施。

#### 误报
以下情形不构成漏洞：
1. 系统完全无状态，使用 Bearer Token 且禁用 Cookie。
2. 仅对无需身份验证的公共 GET 接口禁用 CSRF。
3. 外层 API Gateway 已实现 CSRF 防护。

#### 代码异味
需记录的风险：
1. 在调试环境禁用且无自动校验，易遗忘。
2. 自定义 `CsrfTokenRepository` 未被实际使用。
3. `csrf().disable()` 由第三方 starter 自动注入。
4. 未配置登录表单 `_csrf` 隐藏域，导致 Token 未提交。

## Low risk

### 低风险评级场景

#### 1. 后台管理 + MFA
- **场景：** 虽禁用 CSRF，但敏感操作需多因素认证。
- **风险评估：** 攻击难度高，但仍建议恢复防护。

#### 2. 内部系统
- **场景：** 应用仅在内网使用，并通过 VPN 控制访问。
- **风险评估：** 攻击面小，仍需关注内部威胁。

#### 3. 仅 REST API + Stateless
- **场景：** 所有接口使用 Bearer Token，不依赖 Cookie。
- **风险评估：** CSRF 风险较低，需确保无 Cookie 回退路径。

#### 4. 审计日志完整
- **场景：** 对敏感操作记录来源、IP、Token 失败次数。
- **风险评估：** 有助于发现滥用，不能替代防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| MFA / 二次验证 | 提高攻击成本 | 中 |
| 内网/受控环境 | 攻击面有限 | 中 |
| 无状态 API | 不受 CSRF 影响 | 低 |
| 审计与告警 | 提升检测能力 | 高（仍建议启用 CSRF）|

