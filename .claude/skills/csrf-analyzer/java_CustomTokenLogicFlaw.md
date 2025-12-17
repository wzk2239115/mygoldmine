# Java 自定义 CSRF Token 逻辑漏洞

## Details

### 漏洞成因
当开发者绕过 Spring Security 默认实现，自行编写 Filter/Interceptor 验证 CSRF Token 时，常见错误包括：仅检测 Token 是否存在、不区分大小写、允许空字符串、忽略失效时间、未绑定用户/会话、或在验证失败后继续执行链路。这些逻辑缺陷使得攻击者可复用 Token、构造空值绕过或直接跳过校验。

### 代码示例

**易受攻击的代码：**
```java
public class CsrfFilter implements Filter {
    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest req = (HttpServletRequest) request;
        if ("POST".equalsIgnoreCase(req.getMethod())) {
            String token = req.getHeader("X-CSRF-Token");
            if (token == null || token.isEmpty()) { // 仅检查是否为空
                ((HttpServletResponse) response).sendError(403);
                return;
            }
        }
        chain.doFilter(request, response); // 未与服务端存储值比对
    }
}
```

**另一个不安全示例（大小写放宽 + 默认通过）：**
```java
if (!expectedToken.equalsIgnoreCase(actualToken)) {
    log.warn("csrf mismatch"); // 记录日志但继续执行
}
// chain.doFilter 调用在 if 之后，无条件放行
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `Filter`, `OncePerRequestFilter`, `HandlerInterceptor`
- Token 获取：`req.getHeader`, `req.getParameter`, `req.getCookie`
- 校验逻辑：`equalsIgnoreCase`, `StringUtils.hasText`, `if (token == null)`

**定位步骤：**
1. 搜索包含 “CSRF” 字符的自定义过滤器、拦截器。
2. 检查是否与 `HttpSession` 或 `CsrfTokenRepository` 对比预期值。
3. 跳读（L2）确认验证失败时是否阻断请求。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **预期 Token 获取**：`req.getSession().getAttribute("CSRF_TOKEN")`.
- **严格比较**：区分大小写、不可为空、不可重复使用。
- **过期控制**：Token 带时间戳并验证有效期。
- **错误处理**：验证失败时返回 403，不继续调用 `chain.doFilter`.

**定位技巧：**
- 确认 Token 是否绑定用户/会话，防止跨用户使用。
- 检查日志输出是否泄露 Token。
- 分析是否存在 GET 请求也需要 Token 的特例。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 自定义逻辑严格绑定会话 | **L0（快速跳过）** | 风险低 |
| 存在空值/大小写绕过 | **L3（逐行读）** | 高风险 |
| 验证失败仍放行 | **L4（跨模块追踪）** | 直接导致防护失效 |
| 仅记录日志不拒绝请求 | **L3（逐行读）** | 高风险 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. Token 验证逻辑存在明显缺陷（空值、大小写、未绑定、默认通过）。
2. 敏感操作依赖该逻辑防护。
3. 攻击者可轻松构造请求绕过。

#### 误报
以下情形可视为误报：
1. 自定义逻辑只是补充检查，核心校验仍由 Spring Security 完成。
2. Token 验证失败后由全局异常处理阻断（需要确认）。
3. 接口并未依赖 Cookie，CSRF 风险不成立。

#### 代码异味
需记录的隐患：
1. Token 存储在静态变量，集群环境中不同节点不同步。
2. 多种 Token 策略并存，易导致覆盖/遗漏。
3. Token 通过 URL 参数传递，可能被日志记录。
4. 缺少自动化测试确保逻辑正确。

## Low risk

### 低风险评级场景

#### 1. 内部系统 + 日志复核
- **场景：** 内部接口，出现异常时人工复核。
- **风险评估：** 攻击面小，但仍应修复逻辑。

#### 2. 短期临时系统
- **场景：** 临时工具，已设定下线时间。
- **风险评估：** 风险相对较低，但不建议忽视。

#### 3. SameSite=Strict Cookie
- **场景：** 配合严格 SameSite。
- **风险评估：** 兼容性有限，仍需修复。

#### 4. 完整监控
- **场景：** 对 Token 验证失败频次进行告警。
- **风险评估：** 有助于快速定位问题，但无法阻止攻击。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部环境 | 攻击面有限 | 中 |
| 临时系统 | 风险窗口有限 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 告警监控 | 提升检测能力 | 高（仍需修复逻辑）|

