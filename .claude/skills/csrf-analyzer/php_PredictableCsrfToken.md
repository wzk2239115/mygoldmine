# PHP 可预测 CSRF Token 漏洞

## Details

### 漏洞成因
部分 PHP 应用为生成 CSRF Token 使用弱随机函数（如 `md5(time())`, `uniqid()`, `mt_rand()`），或将 Token 与公开信息（用户名、时间戳）拼接，导致攻击者可预测或暴力穷举 Token。若 Token 生成后未与会话绑定、更未限制有效期，攻击者可构造跨站请求冒充受害者执行敏感操作。

### 代码示例

**易受攻击的代码：**
```php
function generate_csrf_token() {
    return md5(time()); // 时间戳可预测
}

$_SESSION['csrf_token'] = generate_csrf_token();
```

```php
function check_csrf_token($token) {
    return hash_equals($_SESSION['csrf_token'], $token);
}
// Token 长期不刷新，同一值可使用多次
```

**另一个不安全示例（使用 uniqid）：**
```php
$_SESSION['csrf_token'] = uniqid($_SESSION['user_id'], true); // 与 user_id 相关，可被推测
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Token 生成：`md5(time())`, `uniqid`, `mt_rand`, `substr(hash(`
- 会话绑定：`$_SESSION['csrf_token']`
- Token 验证：`hash_equals`, `$_POST['_csrf']`

**定位步骤：**
1. 搜索生成 Token 的函数，评估随机性来源。
2. 确认 Token 是否关联会话、是否一次性。
3. 跳读（L2）Token 是否在登录或操作后刷新。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **安全随机**：`random_bytes`, `openssl_random_pseudo_bytes`.
- **会话绑定**：Token 存储在 `$_SESSION`.
- **一次性**：验证后立即删除或刷新。
- **时间限制**：设置过期时间并检查。

**定位技巧：**
- 查看是否将 Token 发送至客户端后保存在 Cookie 中（需双重提交）。
- 确认 Token 长度和编码（至少 128 bit）。
- 分析 Token 是否通过 URL 传递导致泄露。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 `random_bytes` + 会话绑定 | **L0（快速跳过）** | 风险低 |
| 随机函数弱（md5/time） | **L3（逐行读）** | 高风险 |
| Token 可多次使用/跨会话复用 | **L4（跨模块追踪）** | 极高风险 |
| Token 长期不刷新 | **L2（跳读）** | 需改进 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. Token 生成基于弱随机或可预测值。
2. Token 未与会话绑定或可重复使用。
3. 攻击者可预测/推测 Token 并伪造请求。

#### 误报
以下情况可视为误报：
1. 使用安全随机源并绑定会话。
2. Token 仅用于只读操作记录。
3. Token 生成虽可预测，但需额外一次性验证（如短信）。

#### 代码异味
需记录：
1. 使用 `uniqid`、`mt_rand` 等函数。
2. Token 生成后保存在客户端而非服务端。
3. Token 包含用户名、时间戳等易猜测信息。
4. Token 验证后不刷新，长期有效。

## Low risk

### 低风险评级场景

#### 1. 管理后台 + 审计
- **场景：** 若攻击成功仍有操作日志可追踪。
- **风险评估：** 攻击面有限，但仍应修复。

#### 2. 短期内刷新 Token
- **场景：** Token 仅短时间有效，定期刷新。
- **风险评估：** 缩小窗口，但仍需安全随机。

#### 3. SameSite=Strict Cookie
- **场景：** 减少跨站请求成功率。
- **风险评估：** 辅助缓解，不替代修复。

#### 4. 二次验证
- **场景：** 敏感操作需短信/OTP。
- **风险评估：** 提升攻击成本，仍应改用强随机。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 后台 + 审计 | 攻击面有限 | 中 |
| Token 频繁刷新 | 缩短预测窗口 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 二次验证 | 提高攻击成本 | 高（仍需安全随机）|

