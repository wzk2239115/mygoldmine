# Rust｜Handler 缺少操作权限策略校验

## Details

### 漏洞成因
在 Actix-web、Rocket、Axum 等 Rust Web 框架中，Handler 通常通过 extractor 获取身份信息，但若未进一步校验该身份是否具备对应操作权限，就会导致越权调用。例如仅在登录后即可访问 `/admin` 接口，而不检查角色或策略。

### 代码示例

**易受攻击示例：**
```rust
async fn delete_user(State(app_state): State<AppState>, Path(id): Path<i64>, AuthUser(user): AuthUser) -> impl IntoResponse {
    // AuthUser extractor仅保证登录
    app_state.users.delete(id).await.unwrap();
    StatusCode::NO_CONTENT
}
```

**安全示例：**
```rust
async fn delete_user(State(app_state): State<AppState>, Path(id): Path<i64>, AuthUser(user): AuthUser) -> impl IntoResponse {
    if !user.permissions.contains("user:delete") {
        return StatusCode::FORBIDDEN;
    }
    app_state.users.delete_with_actor(id, &user).await?;
    StatusCode::NO_CONTENT
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `AuthUser`, `Role`, `permissions`, `handler`, `delete`, `admin`, `update`。

**定位步骤：**
1. 查找敏感路由对应的 handler；
2. 跳读（L2）确认是否检查用户权限；
3. 查看 extractor 是否仅提供身份而非权限信息。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 权限中间件（Casbin、Oso、opa-wasm）；
- Handler 内调用策略服务；
- Service 层二次校验；
- 请求使用 `ScopeGuard` 或 `Policy` trait。

**定位技巧：**
- 逐行读（L3）敏感 handler；
- 跨模块追踪（L4）同一 handler 是否被内部任务调用并绕过权限。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Handler 内/外部统一权限策略 | **L0（快速跳过）** | 风险低 |
| 部分 handler 校验 | **L2（跳读）** | 需确认 |
| Handler 完全无权限校验 | **L3（逐行读）** | 高风险 |
| Handler 多入口复用 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. Handler 未校验权限；
2. 普通用户可执行敏感操作；
3. 影响核心数据或系统配置。

#### 误报
1. Handler 仅供内部调用且已限制访问；
2. 操作为只读、无安全影响；
3. 上游网关保证权限不可绕过。

#### 代码异味
1. Handler 依赖请求参数 `admin=true`；
2. 权限 check TODO 未实现；
3. 使用 `unwrap` 忽略权限错误。

## Low risk

### 低风险评级场景

#### 1. 操作仅更新非敏感状态
- **评估：** 可标低风险。

#### 2. 内网专用接口
- **评估：** 攻击面小。

#### 3. 将集成权限策略库
- **评估：** 暂降级，跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感 | 影响有限 | 低 |
| 内部 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
