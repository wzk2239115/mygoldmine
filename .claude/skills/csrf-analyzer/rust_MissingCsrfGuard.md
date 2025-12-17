# Rust Web 缺少 CSRF Guard 漏洞

## Details

### 漏洞成因
Rust Web 框架（Actix-web、Rocket、Axum 等）默认不启用 CSRF 防护。若开发者未集成 `actix-csrf`, `rocket_csrf`, `tower-csrf` 等 Guard/Middleware，并依赖 Cookie/Session 执行敏感操作，攻击者可以跨站伪造请求利用用户会话执行操作。

### 代码示例

**易受攻击的代码：**
```rust
#[post("/account/email")]
async fn update_email(session: Session, form: Form<EmailForm>) -> impl Responder {
    if let Some(user_id) = session.get::<i64>("user_id").unwrap() {
        update_email_in_db(user_id, &form.into_inner().email); // 未校验 CSRF
        HttpResponse::Ok().finish()
    } else {
        HttpResponse::Unauthorized().finish()
    }
}
// main.rs 未调用 Csrf middleware/guard
```

**另一个不安全示例（Axum）：**
```rust
async fn transfer(State(app_state): State<AppState>, Form(payload): Form<Transfer>) -> impl IntoResponse {
    let session = app_state.sessions.get(&payload.session_id).unwrap();
    process_transfer(session.user_id, payload.amount); // 无 CSRF Guard
    StatusCode::OK
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 中间件：`Csrf`, `actix_csrf::CsrfMiddleware`, `rocket_csrf::CsrfTokenFairing`
- Session：`Session::get`, `cookies`, `SignedCookieJar`
- 路由：`post`, `put`, `delete`, `Form<...>`

**定位步骤：**
1. 检查 `main.rs` 或 `App` 构建过程中是否添加 CSRF 中间件。
2. 搜索敏感路由处理函数，确认是否获取/验证 Token。
3. 跳读（L2）模板或响应中是否生成 Token。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **Guard 中间件**：如 `App::wrap(Csrf::new(...))`.
- **Token 注入**：通过模板或 JSON 返回 Token。
- **双重提交**：Cookie 与请求参数一致验证。
- **SameSite Cookie**：辅助缓解。

**定位技巧：**
- 检查 API 服务是否使用 `Layer::layer(csrf_layer)`。
- 分析 SSR 模板是否调用 `csrf_token()`.
- 确认不同服务间的 CSRF 配置保持一致。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局启用 Guard + Token 注入 | **L0（快速跳过）** | 风险低 |
| 局部路由未保护 | **L2（跳读）** | 需补齐 |
| 完全未使用 CSRF Guard | **L3（逐行读）** | 高风险 |
| 多服务/多环境存在差异 | **L4（跨模块追踪）** | 需梳理所有部署 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 应用依赖 Cookie/Session 进行敏感操作。
2. 未启用任何 CSRF 防护（Guard、Token、Origin 校验）。
3. 攻击者可构造跨站请求执行操作。

#### 误报
以下情况非漏洞：
1. 接口仅通过 Bearer Token/无状态认证访问。
2. 防护由上游反向代理或 API Gateway 实现。
3. 仅处理只读请求。

#### 代码异味
需记录：
1. Guard 在某些 Feature flag 下被禁用。
2. Token 注入逻辑存在但未在所有模板调用。
3. `SameSite` 设为 `None`，允许跨站携带 Cookie。
4. 多线程环境中 Token 存储不安全。

## Low risk

### 低风险评级场景

#### 1. 内部服务
- **场景：** 仅内网访问，并有安全评估。
- **风险评估：** 攻击面小，但建议启用。

#### 2. SameSite=Strict Cookie
- **场景：** Cookie 配置 Strict。
- **风险评估：** 提供部分缓解，仍需 Guard。

#### 3. 二次验证/MFA
- **场景：** 敏感操作需额外确认。
- **风险评估：** 提高攻击成本，仍建议 Guard。

#### 4. 审计和告警
- **场景：** 记录敏感操作日志并监控异常。
- **风险评估：** 有助于追踪，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问 | 攻击面有限 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 二次验证 | 提高攻击成本 | 中 |
| 审计告警 | 提升检测能力 | 高（仍需启用 Guard）|

