# Java 状态修改端点缺少 CSRF 校验漏洞

## Details

### 漏洞成因
当 Servlet、Spring MVC 控制器、JAX-RS 端点处理 POST/PUT/DELETE 等状态修改请求时，如果未配置 CSRF 过滤器或 Token 验证逻辑，浏览器携带的会话 Cookie 将导致敏感操作可被跨站发起。常见于自定义 `DispatcherServlet`、独立的管理端点、旧代码未迁移至 Spring Security，或 REST 控制器误认为无 Cookie 参与而忽略 CSRF。

### 代码示例

**易受攻击的代码：**
```java
@RestController
@RequestMapping("/api/account")
public class AccountController {

    @PostMapping("/email")
    public ResponseEntity<Void> updateEmail(@RequestBody EmailPayload payload, HttpSession session) {
        userService.updateEmail(session.getAttribute("userId"), payload.getEmail());
        return ResponseEntity.ok().build(); // 未验证 CSRF Token
    }
}
```

**另一个不安全示例（Servlet 处理删除操作）：**
```java
@WebServlet("/admin/deleteUser")
public class DeleteUserServlet extends HttpServlet {
    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        String id = req.getParameter("id");
        userService.delete(id); // 未检验 Token，依赖 Cookie 认证
        resp.sendRedirect("/admin/users");
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 注解：`@PostMapping`, `@PutMapping`, `@DeleteMapping`, `POST` servlet
- 敏感业务：密码、转账、权限、删除、审批
- Token 获取：`request.getParameter("_csrf")`, `CsrfToken`

**定位步骤：**
1. 搜索所有状态修改端点，确认是否启用 CSRF 过滤。
2. 检查模块是否绕过 Spring Security（如 `security=true`/`false` 配置）。
3. 跳读（L2）查看是否存在 Token 验证逻辑。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **CsrfFilter** 已自动注入，模板中包含 `_csrf`。
- **自定义过滤器** 在 servlet chain 中执行 Token 校验。
- **通用拦截器**：`HandlerInterceptor` 针对所有敏感端点验证 Token。
- **Origin/Referer 校验** 作为补充。

**定位技巧：**
- 确认 REST 端点是否真的无 Cookie：`SessionCreationPolicy.STATELESS`。
- 检查 `withHttpOnlyFalse()` Cookie 是否允许脚本访问。
- 分析第三方集成（如 Swagger UI）是否暴露未保护端点。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局启用 CSRF + 模板注入 Token | **L0（快速跳过）** | 风险低 |
| 个别端点未受保护 | **L2（跳读）** | 需补齐 |
| 大量敏感端点无 Token | **L3（逐行读）** | 高风险 |
| REST 与表单混用，部分绕过 | **L4（跨模块追踪）** | 需梳理所有入口 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 状态修改端点未验证 CSRF Token。
2. 端点使用 Cookie/Session 识别用户。
3. 不存在替代防护手段。

#### 误报
不构成漏洞的情况：
1. 端点采用 Bearer Token，无浏览器自动凭证。
2. 服务端通过双重提交 Cookie 验证。
3. 接口仅供后台服务调用，附带 mTLS/签名。

#### 代码异味
需记录：
1. Token 验证逻辑散落在业务层，易遗漏。
2. 同一端点通过不同路径触发（GET + JS POST）未统一处理。
3. 忘记为异步请求设置 Token，框架默认防护被绕过。
4. 返回 200 但未提示 Token 失效，用户体验差导致禁用。

## Low risk

### 低风险评级场景

#### 1. 管理后台 + MFA
- **场景：** 端点仅管理员使用，操作需二次确认。
- **风险评估：** 攻击难度高，但仍需 Token。

#### 2. 内部系统/受控网络
- **场景：** 接口仅在内网使用。
- **风险评估：** 攻击面小，但防范内部威胁仍重要。

#### 3. SameSite=Strict Cookie
- **场景：** Cookie 配置 Strict。
- **风险评估：** 缓解部分场景，但不兼容全部浏览器。

#### 4. 审计日志与告警
- **场景：** 对敏感操作记录来源和参数。
- **风险评估：** 有助于发现滥用，不能替代防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 二次验证/MFA | 提高攻击成本 | 中 |
| 内网访问 | 攻击面有限 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 审计告警 | 提升检测能力 | 高（仍需补齐 Token）|

