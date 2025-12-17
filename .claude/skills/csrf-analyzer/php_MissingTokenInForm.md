# PHP 表单缺少 CSRF Token 漏洞

## Details

### 漏洞成因
PHP 应用（包括 Laravel、Symfony、ThinkPHP、自研框架）常通过表单处理敏感操作。如果模板未包含隐藏的 CSRF Token 字段，或后端未验证 Token，浏览器会自动附带 Session Cookie，使攻击者能构造跨站表单提交恶意请求。常见于传统 PHP 页面、WordPress 插件、旧版系统未升级 CSRF 防护。

### 代码示例

**易受攻击的代码：**
```php
<!-- profile.php -->
<form action="/profile/update.php" method="POST">
  <input type="text" name="email" value="<?= htmlspecialchars($user['email']) ?>">
  <button type="submit">Save</button>
</form>
<!-- 未渲染任何 CSRF Token -->
```

```php
// update.php
session_start();
if (!isset($_SESSION['user_id'])) {
    http_response_code(401);
    exit;
}
// 未验证 $_POST['_csrf']
update_email($_SESSION['user_id'], $_POST['email']);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 模板：`<form`, `method="post"`, `@csrf` (Blade), `{{ csrf_token() }}`
- 验证：`hash_equals($_SESSION['csrf'], $_POST['_csrf'])`
- 全局配置：`$app['csrf']`, `middleware => VerifyCsrfToken`

**定位步骤：**
1. 搜索表单模板，确认是否输出 Token。
2. 检查处理脚本是否验证 Token。
3. 跳读（L2）Laravel/Symfony 控制器是否利用框架中间件。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **框架默认中间件**：`VerifyCsrfToken`, `CsrfTokenManager`.
- **模板助手**：`@csrf`, `{% csrf_token %}`。
- **Token 校验**：`hash_equals`、`csrf_token_is_valid`.
- **双重提交 Cookie**：是否实现并验证。

**定位技巧：**
- 注意 API 路由是否在 `VerifyCsrfToken` 豁免列表。
- 检查嵌套表单、AJAX 提交是否包含 Token。
- 确认 Token 存储在会话并与用户绑定。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 默认中间件启用且所有表单使用 | **L0（快速跳过）** | 风险低 |
| 单个表单缺 Token | **L2（跳读）** | 需补齐 |
| 大量或核心表单无 Token | **L3（逐行读）** | 高风险 |
| API 与表单共享会话但未统一防护 | **L4（跨模块追踪）** | 需梳理所有入口 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 表单提交敏感操作但未包含 Token。
2. 服务端仍依赖 Cookie 进行身份认证。
3. 无其它 CSRF 防护。

#### 误报
以下情况非漏洞：
1. 表单仅用于查询、无状态变更。
2. 使用一次性验证码、MFA 替代 CSRF 防护。
3. 请求由非浏览器客户端发起且无需 Cookie。

#### 代码异味
需关注：
1. 部分模板使用 Token，部分未使用，可能遗忘。
2. Token 输出但未随请求提交（input name 不一致）。
3. Token 在 JavaScript 中插入，但某些页面未加载脚本。
4. Token 通过 URL 参数传递，易被泄露。

## Low risk

### 低风险评级场景

#### 1. 管理后台 + 审计
- **场景：** 操作仅管理员使用并记录日志。
- **风险评估：** 攻击面小，但仍需 Token。

#### 2. SameSite=Strict Cookie
- **场景：** Session Cookie 设置 Strict。
- **风险评估：** 兼容性有限，不能完全依赖。

#### 3. 二次确认
- **场景：** 表单提交后需短信/验证码确认。
- **风险评估：** 降低风险，但不替代 Token。

#### 4. 内网部署
- **场景：** 系统部署在受控内网。
- **风险评估：** 攻击面小，仍建议补防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理后台 + 审计 | 攻击面有限 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 二次确认 | 提高攻击成本 | 中 |
| 内网部署 | 减少外部攻击 | 高（仍需 Token）|

