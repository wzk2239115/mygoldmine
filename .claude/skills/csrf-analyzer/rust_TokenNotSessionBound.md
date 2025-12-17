# Rust CSRF Token 未绑定会话漏洞

## Details

### 漏洞成因
在使用 Rust 自定义 CSRF 实现时，如果 Token 生成后未与 session/user 绑定，或存储在共享缓存中未区分用户，攻击者可复用他人 Token。常见于 Actix/Axum 应用使用全局 `HashMap`、Redis 键单独存储 Token，而验证时只检查 Token 是否存在，不校验当前会话，导致跨用户复用。

### 代码示例

**易受攻击的代码：**
```rust
static TOKENS: Lazy<Mutex<HashSet<String>>> = Lazy::new(|| Mutex::new(HashSet::new()));

fn generate_token() -> String {
    let token = uuid::Uuid::new_v4().to_string();
    TOKENS.lock().unwrap().insert(token.clone());
    token
}

fn validate_token(token: &str) -> bool {
    TOKENS.lock().unwrap().contains(token) // 未与 session 绑定
}
```

**另一个不安全示例（Redis 全局键）：**
```rust
redis_conn.set_ex(format!("csrf:{token}"), "1", 600)?;
// 校验时仅检查键是否存在
if redis_conn.exists(format!("csrf:{token}"))? { return true; }
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）**
**关键词扫描：**
- `HashMap`, `HashSet`, `Lazy`, `Mutex` 存储 Token。
- `redis::cmd("SET")`, `set_ex`, `exists`.
- `Session::set("csrf")`, `extensions.insert(CsrfToken(token))`.

**定位步骤：**
1. 搜索 Token 存储位置，确认是否包含 session/user 信息。
2. 检查验证函数是否结合 `session_id`、`user_id`.
3. 跳读（L2）确认 Token 是否一次性使用并刷新。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **会话绑定**：`session.insert("csrf_token", token)` 并在验证时比较。
- **一次性**：验证后删除 Token。
- **过期控制**：设置时间限制。
- **双重提交 Cookie**：匹配 Cookie 与请求字段。

**定位技巧：**
- 查看 Token 是否通过 URL 或日志泄露。
- 评估多节点部署时 Token 存储是否同步。
- 确保使用 `constant_time_eq` 防止时序攻击。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Token 绑定 session 并一次性使用 | **L0（快速跳过）** | 风险低 |
| Token 共享/未绑定 | **L3（逐行读）** | 高风险 |
| Token 可重复使用或不过期 | **L2（跳读）** | 需改善 |
| 多租户/多节点共享 Token | **L4（跨模块追踪）** | 极高风险 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. Token 与会话未绑定或可跨用户使用。
2. 端点依赖 Cookie/Session。
3. 攻击者可获取他人 Token 并伪造请求。

#### 误报
以下情况非漏洞：
1. 使用双重提交 Cookie 并验证 cookie/value 一致。
2. Token 仅用于幂等控制或非 CSRF 场景。
3. 请求不依赖 Cookie（例如 Bearer Token）。

#### 代码异味
需记录：
1. Token 存储在全局 `HashMap`，服务重启导致覆盖。
2. Token 未在登录/注销时刷新。
3. Redis 键未包含租户、session 前缀，易冲突。
4. 验证失败仅记录日志不阻断。

## Low risk

### 低风险评级场景

#### 1. 内部系统
- **场景：** 仅内网使用，并有审计。
- **风险评估：** 攻击面有限，但应修复。

#### 2. 二次验证
- **场景：** 敏感操作需 OTP/MFA。
- **风险评估：** 增加攻击成本，仍需绑定。

#### 3. SameSite=Strict Cookie
- **场景：** Session Cookie 设置 Strict。
- **风险评估：** 提供缓解，但不全面。

#### 4. Token 快速刷新
- **场景：** 每次请求后刷新 Token。
- **风险评估：** 缩短窗口，但仍需绑定会话。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问 + 审计 | 攻击面有限 | 中 |
| 二次验证 | 提高攻击成本 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| Token 快速刷新 | 缩短有效期 | 中 |

