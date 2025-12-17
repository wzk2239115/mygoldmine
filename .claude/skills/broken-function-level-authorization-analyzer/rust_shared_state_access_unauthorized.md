# Rust｜共享状态访问缺少授权策略

## Details

### 漏洞成因
Rust 应用常将全局状态（如配置、任务队列、缓存）封装在 `Arc<Mutex<T>>` 或 `State<T>` 中供多个 handler 访问。如果共享状态操作未绑定角色策略，任何已登录用户都可读取或修改敏感状态（例如更改系统配置、管理其他租户数据）。问题多见于 Axum/Actix 的全局 `AppState`、Rocket 的 `State<T>`。

### 代码示例

**易受攻击示例：**
```rust
struct AppState {
    config: Arc<RwLock<SystemConfig>>,
}

async fn update_config(State(state): State<AppState>, Json(payload): Json<ConfigUpdate>) -> impl IntoResponse {
    let mut config = state.config.write().unwrap();
    config.apply(payload); // 未检查调用者角色
    StatusCode::NO_CONTENT
}
```

**安全示例：**
```rust
async fn update_config(State(state): State<AppState>, AuthUser(user): AuthUser, Json(payload): Json<ConfigUpdate>) -> impl IntoResponse {
    if !user.permissions.contains("config:update") {
        return StatusCode::FORBIDDEN;
    }
    state.config.write().unwrap().apply(payload, &user);
    StatusCode::NO_CONTENT
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `State`, `Arc<Mutex`, `Arc<RwLock`, `shared_state`, `config`, `update`, `set_*`。

**定位步骤：**
1. 找出对全局状态的写操作；
2. 跳读（L2）确认是否同时获取用户上下文；
3. 检查是否存在 `AuthUser` extractor，但 handler 未使用。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 权限检查函数（policy），在状态写入前调用；
- 状态对象暴露受限接口，只允许管理员调用；
- 多租户隔离（按租户划分存储）；
- 审计日志与告警。

**定位技巧：**
- 逐行读（L3）状态写入逻辑，确认是否受限；
- 跨模块追踪（L4）其他 handler 是否复用此状态并可能绕过权限。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 状态操作统一校验权限 | **L0（快速跳过）** | 风险低 |
| 部分操作校验 | **L2（跳读）** | 需确认 |
| 状态写入完全无授权 | **L3（逐行读）** | 高风险 |
| 状态跨模块共享 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 共享状态写操作缺乏授权；
2. 普通用户可修改敏感配置或资源；
3. 造成越权影响。

#### 误报
1. 状态只读或仅缓存公开数据；
2. 操作仅在内部后台调用且有额外控制；
3. 写入时由状态对象内部校验权限。

#### 代码异味
1. 依赖请求中传入的 `is_admin`；
2. 使用环境变量或配置切换权限而无校验；
3. 缺乏操作日志。

## Low risk

### 低风险评级场景

#### 1. 状态仅记录非敏感指标
- **评估：** 可标低风险。

#### 2. 运行在隔离环境并受监控
- **评估：** 攻击面小。

#### 3. 即将引入策略控制层
- **评估：** 暂降级，跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感 | 影响有限 | 低 |
| 隔离环境 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
