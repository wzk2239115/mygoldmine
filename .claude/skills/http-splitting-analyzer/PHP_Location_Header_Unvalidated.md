# PHP Location 头重定向未验证

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `header("Location: " . $url)` 重定向
- `header("Location: $url")` 直接拼接
- `wp_safe_remote_post()` 等框架重定向不安全使用

**快速定位核心操作：**
1. 搜索关键字：`header(`、`Location`、`redirect`
2. 追踪 URL 来源：`$_GET`、`$_POST`、`$_SESSION`
3. 检查是否存在 URL 验证或白名单
4. 查看是否检查了协议和域名

**快速定位保护机制：**
- URL 白名单：`if (in_array($url, $allowed_urls))`
- 域名验证：`parse_url($url, PHP_URL_HOST)` 检查
- 协议限制：仅允许 `http://` 和 `https://`
- 相对 URL：检查是否以 `/` 开头

**代码示例：**
```php
// 危险：用户输入直接重定向
$next = $_GET['next'] ?? '/';
header("Location: " . $next);  // 危险

// 危险：POST 参数
$redirect_to = $_POST['redirect'] ?? '';
header("Location: $redirect_to");  // 危险

// 危险：从 Cookie
$return_url = $_COOKIE['return'] ?? '';
header("Location: " . $return_url);  // 危险
```

## Classify

**漏洞（High）：**
- 用户输入直接用于 Location 头
- 无 URL 格式或域名验证
- 允许任意协议跳转
- 开放重定向漏洞

**误报：**
- Location 值硬编码
- 使用框架安全方法且有验证

**代码异味（Medium）：**
- 仅检查前缀
- 黑名单容易绕过
- 检查不完整

## Low risk

**以下情况评为低风险：**
- Location 值硬编码
- 严格白名单验证
- 仅允许相对 URL + 正则验证
- 管理员配置的 URL

## 审计专业技巧 - 真实漏洞与误报区分

### 真实漏洞特征识别

**特征1：直接拼接 + 用户输入**
```php
// 真实漏洞
$next_page = $_GET['next'];
header("Location: " . $next_page);  // ← 必然漏洞
// 攻击：?next=javascript:alert(1) 或 ?next=http://attacker.com
```

**特征2：部分验证但不完整**
```php
// 真实漏洞（黑名单绕过）
if (strpos($url, 'javascript:') === false) {
    header("Location: " . $url);  // ← 可绕过：data: 协议、//attacker.com
}

// 真实漏洞（域名检查不严）
if (parse_url($url, PHP_URL_HOST) === 'safe.com') {
    header("Location: " . $url);  // ← 可绕过：http://safe.com.attacker.com
}
```

**特征3：不同代码路径混合**
```php
// 真实漏洞（路径判断导致）
if ($is_admin) {
    $url = $_GET['url'];  // 管理员才允许
} else {
    $url = 'default';
}
header("Location: " . $url);  // ← 如果授权检查失败，仍然危险
```

### 常见误报场景

**误报1：相对 URL + 正确检查**
```php
// 正确做法（低风险）
$next = $_GET['next'] ?? '/';
if (strpos($next, '/') === 0 && strpos($next, '//') !== 0) {
    header("Location: " . $next);  // ← 仅允许相对路径，安全
}
// 只能跳转：/profile、/login，不能跳转到外域
```

**误报2：严格白名单验证**
```php
// 正确做法（低风险）
$redirect_map = [
    'profile' => '/user/profile',
    'home' => '/',
    'settings' => '/settings'
];
$page = $_GET['page'] ?? 'home';
if (isset($redirect_map[$page])) {
    header("Location: " . $redirect_map[$page]);  // ← 白名单完全覆盖
}
```

**误报3：框架安全函数（需检查上下文）**
```php
// 误报（取决于框架实现）
wp_safe_redirect($_GET['redirect_to']);  // ← WordPress 提供的安全函数
// 实际上 wp_safe_redirect() 已检查域名

// 真实漏洞（自定义框架函数）
function safe_redirect($url) {
    header("Location: " . $url);  // ← "safe"只是函数名，没实际保护
}
safe_redirect($_GET['redirect']);
```

### 审计决策树

```
发现 header("Location: ...")
    ↓
【检查点1】Location 值来源
    ├─ 硬编码常量 → 安全，END
    ├─ 用户输入 → 继续检查
    └─ 配置文件 → 继续检查
    ↓
【检查点2】验证方式
    ├─ 无验证 → 漏洞（HIGH）
    ├─ 黑名单（strpos、preg_match 排除） → 高风险，检查绕过
    │   └─ 可被协议/域名绕过 → 漏洞（HIGH）
    ├─ 白名单（in_array、array_key_exists） → 低风险
    └─ 正则（^https?://white.com） → 中等，检查锚点
    ↓
【检查点3】协议限制（仅限白名单场景）
    ├─ 显式仅允许 http/https → 安全
    ├─ 未限制 → 风险（data/javascript 可用）
    └─ 允许 file/ftp 等 → 高风险
    ↓
【检查点4】域名验证（仅限接收 URL 场景）
    ├─ parse_url() + 精确匹配 → 安全
    ├─ 字符串包含检查 → 可绕过（safe.com.attacker.com）
    └─ 无域名检查 → 漏洞（HIGH）
```

### 现场审计速查表

| 代码模式 | 风险等级 | 快速判断 |
|---------|--------|--------|
| `header("Location: " . $_GET['x'])` | **HIGH** | 直接拼接，必然漏洞 |
| `if (!str_contains($url, 'bad')) header(...)` | **HIGH** | 黑名单易绕过 |
| `header("Location: " . $config['url'])` | **LOW** | 来源可信 |
| `if (in_array($url, $whitelist)) header(...)` | **LOW** | 白名单完整 |
| `wp_safe_redirect($url)` | **UNKNOWN** | 需确认上文输入校验 |
| `if (parse_url($url, PHP_URL_HOST) === 'safe.com')` | **MEDIUM** | 需检查是否允许子域名 |
| `if (preg_match('/^https:\/\/safe\.com\//')) header(...)` | **LOW** | 正则锚定，较安全 |

### 审计建议

1. **重点关注组合风险**：验证存在但不完整 + 多条代码路径，某条路径可能绕过
2. **测试绕过技巧**：
   - `//attacker.com`（协议相对 URL）
   - `http://safe.com.attacker.com`（子域欺骗）
   - `http://safe.com@attacker.com`（用户信息欺骗）
   - `http://127.0.0.1/` + 内网扫描
   - `data:text/html,<script>alert(1)</script>`
3. **追踪隐性输入**：`$_COOKIE`、`$_SESSION`、数据库字段可能污染
4. **检查授权后绕过**：某些代码仅在特定条件下验证，其他路径未保护
