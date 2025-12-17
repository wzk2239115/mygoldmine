# PHP CSRF Token 未绑定会话漏洞

## Details

### 漏洞成因
在 PHP 项目中，如果 CSRF Token 生成后未存储在与当前用户会话绑定的存储（`$_SESSION`、Redis、数据库），而是保存在全局变量或仅通过隐藏字段传递，攻击者可复用其它用户的 Token 或跨会话使用，从而绕过防护。常见于自定义防护、轻量框架、或为了兼容 CDN/缓存而移除 `session_start()`。

### 代码示例

**易受攻击的代码：**
```php
$GLOBALS['csrf_tokens'][] = bin2hex(random_bytes(16));
$token = end($GLOBALS['csrf_tokens']);
// 输出到表单，但未与 session 绑定
```

```php
function verify_csrf($token) {
    return in_array($token, $GLOBALS['csrf_tokens']); // 任意用户的 Token 皆可
}
```

**另一个不安全示例（数据库全局表）：**
```php
// tokens 表未包含 user_id/Session 信息
$stmt = $pdo->prepare("INSERT INTO csrf_tokens(token, created_at) VALUES (?, NOW())");
$stmt->execute([$token]);

// 校验时仅检查 token 是否存在
$exists = $pdo->prepare("SELECT 1 FROM csrf_tokens WHERE token = ?");
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Token 存储：`$_SESSION['csrf']`, `setcookie('csrf')`, `Redis::set('csrf:'`
- 验证逻辑：`hash_equals`, `in_array`, `if ($token)`
- 会话管理：`session_start`, `session_id`, `$_COOKIE['PHPSESSID']`

**定位步骤：**
1. 检查 Token 是否写入 `$_SESSION` 或与 user_id 绑定。
2. 确认验证时是否从会话读取匹配 Token。
3. 跳读（L2）Token 是否在验证后销毁。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **会话绑定**：`$_SESSION['csrf_token'] = $token`.
- **Token 多重绑定**：包括 user_id、session_id、IP 等。
- **一次性**：验证后 `unset($_SESSION['csrf_token'])`.
- **过期策略**：Token 存活时间有限。

**定位技巧：**
- 检查 `session.use_strict_mode` 是否启用，防止会话固定。
- 确认 Token 是否通过 Cookie 传输（需双重提交策略）。
- 分析微服务场景，多个应用共享 Token 是否安全。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Token 与 session/user 强绑定 | **L0（快速跳过）** | 风险低 |
| Token 全局共享或跨会话复用 | **L3（逐行读）** | 高风险 |
| Token 可多次使用无过期 | **L2（跳读）** | 需改进 |
| 多系统共享但缺少隔离 | **L4（跨模块追踪）** | 极高风险 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. CSRF Token 未与当前会话/用户绑定。
2. 攻击者可获取他人 Token 并复用。
3. 端点依赖 Cookie 或自动凭证。

#### 误报
以下情况非漏洞：
1. Token 使用双重提交 Cookie，提交值需与 Cookie 一致。
2. Token 仅用于标记幂等请求，与 CSRF 无关。
3. 请求通过一次性验证码授权。

#### 代码异味
需记录的风险：
1. Token 存储在文件/数据库但未清理过期记录。
2. Token 通过 URL 参数在多处使用，容易泄露。
3. 会话管理由前端控制（如 JWT），Token 未与后端状态同步。
4. 使用缓存服务器但未区分租户或环境。

## Low risk

### 低风险评级场景

#### 1. 管理后台 + MFA
- **场景：** 即使 Token 被复用，也需二次验证。
- **风险评估：** 攻击成本高，但仍应修复。

#### 2. Token 短期刷新
- **场景：** 每次请求或短时间内刷新 Token。
- **风险评估：** 缩小窗口，但不替代会话绑定。

#### 3. SameSite=Strict Cookie
- **场景：** Cookie 配置 Strict，减少跨站请求成功率。
- **风险评估：** 有一定缓解，仍需绑定。

#### 4. 审计日志与告警
- **场景：** 记录 Token 验证失败和重复使用情况。
- **风险评估：** 可检测异常，仍需完善。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| MFA / 二次验证 | 提高攻击成本 | 中 |
| Token 快速刷新 | 缩短有效窗口 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 审计告警 | 提升检测能力 | 高（仍需绑定会话）|

