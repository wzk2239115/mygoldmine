# Go 缺少 CSRF 中间件漏洞

## Details

### 漏洞成因
Go Web 框架（Gin、Echo、Beego、Fiber 等）默认不启用 CSRF 防护，需要显式引入中间件（如 `gorilla/csrf`、`gin-contrib/csrf`）。如果在处理 POST/PUT/DELETE 等敏感请求时未使用这些中间件，或仅针对部分路由启用，浏览器会自动携带 Session Cookie，使攻击者能够跨站伪造请求执行敏感操作。

### 代码示例

**易受攻击的代码：**
```go
r := gin.Default()
// 未使用 csrf.Middleware(...)

r.POST("/profile/email", func(c *gin.Context) {
    userID := c.MustGet("userID").(int64)
    email := c.PostForm("email")
    updateEmail(userID, email) // 无 Token 验证
    c.JSON(http.StatusOK, gin.H{"ok": true})
})
```

**另一个不安全示例（Echo 框架）：**
```go
e := echo.New()
// e.Use(middleware.CSRF()) 被注释

e.POST("/api/transfer", transferHandler) // 依赖 Cookie，无 CSRF 防护
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Gin：`csrf.Middleware`, `csrf.Init`
- Gorilla：`csrf.Protect`, `csrf.TemplateField`
- Echo：`middleware.CSRF`
- Fiber：`csrf.New`, `app.Use(csrf.New(...))`

**定位步骤：**
1. 搜索项目是否引入 CSRF 中间件。
2. 检查是否只在部分路由组使用中间件。
3. 跳读（L2）确认敏感端点是否在中间件保护范围内。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **全局中间件**：在 `app.Use` 中统一启用。
- **Token 注入**：模板或 API 响应写入 `csrf.Token`.
- **访问限制**：为 API 端点同时配置双重提交或 Origin 校验。

**定位技巧：**
- 检查 `csrf.Protect` 中的选项：`Secure`, `FieldName`, `HeaderName`.
- 确认 REST API 是否确实不依赖 Cookie（`WithCredentials`）。
- 关注 `SkipCheck`/`Exempt` 配置是否包含敏感路由。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局启用中间件 + Token 注入 | **L0（快速跳过）** | 风险低 |
| 局部路由未覆盖 | **L2（跳读）** | 需补齊 |
| 完全未启用 CSRFMiddlewares | **L3（逐行读）** | 高风险 |
| 多服务混用导致绕过 | **L4（跨模块追踪）** | 需梳理网关/服务边界 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 项目依赖 Cookie 会话进行敏感操作。
2. 对应路由未启用任何 CSRF 中间件或防护。
3. 无其它等效防护机制。

#### 误报
以下情况非漏洞：
1. API 仅通过 Bearer Token/Basic Auth 调用。
2. 路由由 API Gateway 负责 CSRF 防护。
3. 控制器仅处理只读请求。

#### 代码异味
需记录：
1. 中间件启用在 `POST` 之外的方法，配置错误。
2. Token 使用默认字段，与前端约定不一致导致开发者移除。
3. 多租户场景下 Token 未隔离可能互相影响。
4. 尚未更新 gorilla/csrf 至最新版本，存在已知漏洞。

## Low risk

### 低风险评级场景

#### 1. 内部管理系统
- **场景：** 仅内部用户访问，并有额外认证。
- **风险评估：** 攻击面小，但仍建议启用。

#### 2. SameSite=Strict Cookie
- **场景：** Session Cookie 设置 Strict。
- **风险评估：** 提供部分缓解，仍建议 CSRF 中间件。

#### 3. 二次验证
- **场景：** 提交后需短信/OTP 确认。
- **风险评估：** 提高攻击成本，但不替代中间件。

#### 4. 审计日志
- **场景：** 记录所有敏感操作并监控异常。
- **风险评估：** 有助于追踪滥用，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部系统 | 攻击面有限 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 二次验证 | 提高攻击成本 | 中 |
| 审计与告警 | 提升检测能力 | 高（仍需启用 CSRF）|

