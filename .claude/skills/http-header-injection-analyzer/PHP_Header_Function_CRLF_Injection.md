# PHP header()函数CRLF注入

## 基本信息
- **难度等级：** ★★☆☆☆ | **审计时间：** 15-25分钟
- **关键词搜索：** `header(`, `setcookie(`, `$_GET`, `$_POST`, `$_REQUEST`, `$_SERVER`, `Location:`, `Content-Type:`
- **快速检查：** header()函数参数是否包含用户输入，PHP版本是否 < 5.1.2

## 漏洞成因

PHP的`header()`函数在PHP 5.1.2之前不会过滤CRLF字符。即使在新版本中，若用户输入直接拼接到头值，攻击者仍可能通过编码绕过（如`%0d%0a`）注入任意响应头，实现HTTP响应拆分、XSS、会话固定等攻击。

### 常见漏洞模式

```php
// ✗ 漏洞：用户输入直接拼接到header()
<?php
$lang = $_GET['lang'];
header("Content-Language: $lang");
// 攻击: ?lang=en%0d%0aSet-Cookie:admin=true
?>
```

```php
// ✗ 漏洞：重定向Location头注入
<?php
$url = $_GET['redirect'];
header("Location: $url");
exit;
// 攻击: ?redirect=http://evil.com%0d%0aSet-Cookie:session=hijacked
?>
```

```php
// ✗ 漏洞：Content-Disposition文件名注入
<?php
$filename = $_GET['file'];
header("Content-Disposition: attachment; filename=$filename");
readfile("/uploads/$filename");
// 攻击: ?file=doc.pdf%0d%0aContent-Length:0%0d%0a%0d%0a<script>alert(1)</script>
?>
```

```php
// ✗ 漏洞：Cookie值注入（PHP < 5.1.2）
<?php
$value = $_POST['preference'];
setcookie("pref", $value);  // 旧版本不验证CRLF
// 攻击: preference=dark%0d%0aSet-Cookie:admin=1
?>
```

```php
// ✓ 修复：CRLF过滤 + URL验证
<?php
function sanitize_header($value) {
    return str_replace(["\r", "\n"], '', $value);
}

$lang = sanitize_header($_GET['lang']);
if (preg_match('/^[a-z]{2}(-[A-Z]{2})?$/', $lang)) {
    header("Content-Language: $lang");
}
?>
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | header()直接使用$_GET/$_POST | 搜索 `header\(.*\$_GET\|\$_POST\|\$_REQUEST`，检查是否过滤 |
| **P0** | Location重定向 | 搜索 `header\("Location`，检查URL参数来源和验证 |
| **P1** | Content-Disposition | 搜索 `Content-Disposition`，检查filename是否用户可控 |
| **P1** | setcookie()用户输入 | 搜索 `setcookie\(.*\$_`，检查PHP版本和参数过滤 |
| **P2** | 自定义头设置 | 搜索 `header\("X-`，检查头值是否来自用户输入 |
| **P2** | PHP版本检查 | 确认PHP版本 >= 5.1.2（内置部分CRLF检查） |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 头值全部硬编码，无用户输入 | 快速跳过 |
| **L1** | 头值来自配置文件或常量 | 关键词扫描确认数据来源 |
| **L2** | 单文件内header()使用用户参数 | 跳读检查str_replace过滤 |
| **L3** | 头值由函数返回，跨文件传递 | 逐行追踪函数返回值来源 |
| **L4** | 框架封装的响应头处理 | 跨模块检查框架Response类实现 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. header()/setcookie()参数包含用户输入（$_GET/$_POST/$_REQUEST/$_SERVER）
2. 未进行CRLF过滤（无`str_replace(["\r","\n"], '', $val)`）
3. PHP < 5.1.2 或使用可绕过的过滤方式

### 典型漏洞特征（满足任一项即确认）
- ✗ `header("Location: " . $_GET['url'])`
- ✗ `header("Content-Language: $_GET[lang]")`
- ✗ `setcookie("pref", $_POST['value'])`（PHP < 5.1.2）
- ✗ `header("Content-Disposition: attachment; filename=" . $userInput)`

### 安全排除（任一项充分）
- ✓ PHP >= 5.1.2 且使用`header()`的内置CRLF检查（会触发警告）
- ✓ 存在CRLF过滤：`str_replace(["\r", "\n", "\0"], '', $value)`
- ✓ 白名单验证：`in_array($value, $allowed_values)`
- ✓ 使用框架安全方法：Laravel `response()->header()`

### 灰色判定（风险较低但需注意）
- PHP >= 5.1.2 但可能存在编码绕过
- 过滤不完整（仅过滤`\n`未过滤`\r`）
- 依赖框架但版本未知

---

## 实现建议

### 核心防护方案

**方案1：CRLF完整过滤**
```php
<?php
function safe_header($name, $value) {
    $safe_value = str_replace(["\r", "\n", "\0"], '', $value);
    header("$name: $safe_value");
}
?>
```

**方案2：安全重定向**
```php
<?php
$allowed_urls = ['/', '/dashboard', '/login'];
$redirect = $_GET['redirect'] ?? '/';

if (in_array($redirect, $allowed_urls)) {
    header("Location: $redirect");
} else {
    header("Location: /");
}
exit;
?>
```

**方案3：使用框架安全方法**
```php
<?php
// Laravel
return redirect()->to($url)->header('X-Custom', $value);

// Symfony
$response->headers->set('Content-Language', $lang);
?>
```

### 检查清单
- [ ] 所有header()调用检查CRLF过滤
- [ ] Location重定向使用URL白名单
- [ ] Content-Disposition文件名过滤特殊字符
- [ ] 确认PHP版本 >= 5.1.2
- [ ] 测试CRLF注入：`?param=value%0d%0aSet-Cookie:test=1`

---

## 审计专业技巧

### 1. 追踪用户输入的间接来源

**常见的"隐形"输入源**（容易被忽略）：

```php
// ✗ 风险：虽然直接来自$_SESSION，但$_SESSION由用户控制的SET-COOKIE设置
<?php
setcookie("lang", $_GET['lang']);  // 第一处：直接CRLF注入风险
// ... 后续请求
header("Content-Language: " . $_SESSION['lang']);  // 第二处：间接CRLF风险
?>
```

**审计建议**：
- 搜索`$_SESSION`、`$_COOKIE`时，需要回溯其初始化来源
- 关键词：`$_SESSION['key'] = $_GET`或`setcookie(...$_GET...)`
- 使用追踪工具（如PHPStan）追踪污染数据流

### 2. 编码绕过的识别与验证

**PHP >= 5.1.2的"虚假安心"**：

```php
// ✗ 风险等级：MEDIUM（PHP内置检查会警告但不一定阻止所有场景）
<?php
$lang = $_GET['lang'];
header("Content-Language: $lang");
// PHP会检查\r\n，但某些特殊场景可能绕过：
// 1. 使用null字节分隔: "en\0\r\nSet-Cookie:admin=1"
// 2. 多字节编码: 某些老版本数据库字符编码问题
// 3. 框架二次处理: 某些框架对null字节处理不当
?>
```

**验证技巧**：
- 检查是否存在显式的`str_replace(["\r", "\n", "\0"], '', ...)`
- 搜索`null`、`\0`、`mb_convert_encoding`等关键词
- PHP >= 5.3.4 才完全修复null字节问题

### 3. Location重定向的白名单陷阱

**常见的不安全"白名单"**：

```php
// ✗ 风险：正则表达式不够严格
<?php
if (preg_match('/example\.com/', $_GET['url'])) {  // 可被绕过：evil.com?referer=example.com
    header("Location: " . $_GET['url']);
}
?>

// ✗ 风险：scheme验证不完整
<?php
if (strpos($_GET['url'], 'http') === 0) {  // 可被绕过：httpp://evil.com
    header("Location: " . $_GET['url']);
}
?>

// ✓ 正确：相对路径白名单 + 绝对URL验证
<?php
$allowed = ['/', '/dashboard', '/login', '/profile'];
$redirect = $_GET['redirect'] ?? '/';

if (in_array($redirect, $allowed, true)) {
    header("Location: $redirect");
} else if (filter_var($redirect, FILTER_VALIDATE_URL)) {
    $parsed = parse_url($redirect);
    if ($parsed['host'] === 'trusted-domain.com') {
        header("Location: $redirect");
    }
}
?>
```

**审计检查点**：
- Location头参数是否使用严格的`in_array(..., true)`白名单
- 是否存在`strpos/str_contains`等模糊匹配（容易被绕过）
- 是否同时验证了scheme和domain

### 4. 框架封装的响应头处理

**不同框架的安全差异**：

```php
// ✓ Laravel - 相对安全（自动过滤部分CRLF）
<?php
return response()->header('X-Custom', $userInput);
// Laravel会自动剥离基本CRLF字符
?>

// ⚠ Symfony - 需要版本检查
<?php
// Symfony >= 4.4 修复CRLF漏洞
$response->headers->set('Content-Type', $userInput);
// Symfony < 4.4 存在风险
?>

// ✗ 自定义函数 - 最常见的漏洞点
<?php
class Response {
    public function addHeader($name, $value) {
        header("$name: $value");  // ✗ 直接传入，无过滤
    }
}
?>
```

**审计方法**：
- 查找Response、HttpResponse等类的header方法实现
- 确认框架版本（`composer.lock`）
- 关键搜索：`header(`出现在Response类内

### 5. 真实漏洞 vs 误报的关键判断

| 场景 | 特征 | 判断 | 验证方法 |
|------|------|------|---------|
| **Content-Type** | `header("Content-Type: " . $_GET['type'])` | **真实漏洞** | 注入`; charset=utf-7` 可能导致浏览器解析问题 |
| **X-Custom-Header** | `header("X-Custom: " . $_SESSION['id'])` | **可能误报** | 追踪$_SESSION初始化，如非用户输入则非漏洞 |
| **Set-Cookie** | `header("Set-Cookie: " . $userInput)` | **真实漏洞** | 可直接注入会话劫持攻击 |
| **授权头** | `header("Authorization: Bearer " . $token)` | **通常安全** | 若$token来自内部生成或解密则非漏洞 |
| **Referer检查** | `if ($_SERVER['HTTP_REFERER'] === ...)` | **低风险** | 虽然用户可控但通常不会触发header()注入 |

### 6. 审计排查的高效流程

**快速排查流程（5分钟）**：
1. 搜索所有`header(`调用位置
2. 检查参数是否包含变量（标记为`$`前缀）
3. 追踪变量来源是否为用户输入（`$_GET/$_POST/$_REQUEST/$_SERVER`）
4. 确认是否存在过滤（`str_replace/preg_replace/filter_var`）
5. 查看PHP版本是否 >= 5.1.2

**深度审查流程（15分钟）**：
1. 检查间接污染数据流（如`$_SESSION <- $_GET -> header()`）
2. 验证过滤函数的完整性（是否过滤了`\0`）
3. 对Location重定向进行白名单验证测试
4. 检查是否使用框架API且版本是否安全
5. 搜索是否存在其他CRLF注入点（如`setcookie()`）

---

## 修复优先级

1. **立即修复**：Location重定向直接使用用户输入
2. **本周修复**：所有header()调用添加完整CRLF过滤函数
3. **可选加强**：对Location实现严格白名单验证
4. **长期优化**：升级PHP版本到最新LTS，使用框架安全API
5. **监控加固**：添加日志记录header注入攻击尝试
