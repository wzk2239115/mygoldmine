# PHP header() 函数 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `header($header, $replace, $http_response_code)` - 设置 HTTP 头
- `header_remove()` - 删除响应头
- `http_response_code()` - 设置状态码
- 响应头直接拼接：`header("X-Custom: " . $user_input)`

**快速定位核心操作：**
1. 全局搜索关键字：`header(`、`header_remove`、`http_response_code`
2. 追踪头值来源：`$_GET`、`$_POST`、`$_SERVER`、`$_COOKIE`
3. 检查是否存在 CRLF 过滤（`
`、`%0d%0a`）
4. 追踪输入的完整处理链路

**快速定位保护机制：**
- CRLF 检查：`if (strpos($value, "\r") !== false || strpos($value, "\n") !== false)`
- 黑名单过滤：`str_replace(["", "
"], "", $value)`
- 白名单验证：`if (!preg_match('/^[a-zA-Z0-9\-_.]+$/', $value))`
- 框架防护：某些框架自动验证和清理

**代码示例：**
```php
// 危险：用户输入直接用于 header()
$custom = $_GET['name'] ?? '';
header("X-Custom: " . $custom);  // 危险：未过滤 CRLF

// 危险：设置 Location 头
$redirect = $_POST['url'] ?? '/';
header("Location: " . $redirect);  // 危险

// 危险：拼接多个值
$user_id = $_SESSION['user_id'] ?? '';
header("X-User-ID: " . $user_id);  // 危险
```

## Classify

**漏洞（Critical）：**
- GET/POST/Cookie 等用户输入直接拼接进 header() 函数
- 响应头包含 `
` 导致响应分割
- 无任何 CRLF 过滤或验证
- 多个输入来源叠加使用

**误报：**
- 响应头值完全硬编码
- 输入已被框架自动过滤（如 WordPress 等）

**代码异味（Medium）：**
- 仅过滤 `
` 或 `` 之一
- 黑名单不完整（如只过滤 `
` 但未过滤其他形式）
- 使用 URL 编码但未完整验证
- 间接拼接：用户输入 → 变量处理 → header()

## Low risk

**以下情况评为低风险：**
- 响应头值完全硬编码
- 严格的 CRLF 过滤：显式检查并拒绝
- 白名单验证：仅允许特定格式
- 框架内置防护已启用
- 头值来自内部系统且无外部污染

## 审计专业技巧

### 1. 追踪输入源的完整链路

**核心原则：** 不仅看直接的 header() 调用，更要追踪该变量从输入点到使用点的全部处理过程。

**常见追踪场景：**
```php
// 场景1：间接污染 - 变量跨函数传递
function setCustomHeader($value) {
    header("X-Custom: " . $value);  // $value 来自哪里？
}
$user_input = $_GET['name'] ?? '';
setCustomHeader($user_input);  // 追踪回到 GET 参数

// 场景2：数据库取值后拼接
$user = $db->query("SELECT profile FROM users WHERE id = " . $_GET['id']);
header("X-Profile: " . $user['profile']);  // 数据库数据是否被污染？

// 场景3：配置数组拼接
$config = require 'config.php';
$custom_header = $config['custom_header'];
header("X-Config: " . $_GET['mode'] . $custom_header);  // 混合污染源
```

**审计技巧：**
- 使用代码编辑器的"查找引用"功能追踪变量使用点
- 标记每个变量的"信任边界"（内部变量 vs 用户输入）
- 对嵌套函数调用逐层展开检查

### 2. 识别真实漏洞 vs 误报

**真实漏洞特征：**
```php
// 特征1：完全无过滤
$_GET['redirect'] -> header("Location: " . $_GET['redirect'])

// 特征2：过滤不完整
$clean = str_replace("\n", "", $_GET['value']);  // 只过滤 \n，缺少 \r
header("X-Value: " . $clean);  // 仍可通过 %0d 绕过

// 特征3：使用了不安全的"清理"函数
$val = htmlspecialchars($_GET['name']);  // htmlspecialchars 不过滤 CRLF
header("X-Name: " . $val);

// 特征4：条件判断不足
if (strlen($input) < 100) {
    header("X-Data: " . $input);  // 只检查长度，未检查字符内容
}

// 特征5：框架版本过旧，已知有绕过
// Laravel < 5.1 的某些版本有 CRLF 注入漏洞
```

**常见误报场景：**
```php
// 误报1：输入已被框架验证
// WordPress 的 wp_safe_remote_get() 会自动清理响应头
$response = wp_safe_remote_get($_GET['url']);

// 误报2：明确的白名单验证
if (!preg_match('/^[a-zA-Z0-9\-\.]+$/', $_GET['domain'])) {
    exit('Invalid domain');
}
header("X-Domain: " . $_GET['domain']);  // 安全

// 误报3：整数或枚举值
$type = (int)$_GET['type'];  // 强制整数，无法注入 CRLF
header("X-Type: " . $type);

// 误报4：使用了正确的过滤
$clean = preg_replace('/[\r\n]/', '', $_GET['value']);
header("X-Value: " . $clean);  // 两个字符都过滤了

// 误报5：框架内置防护被正确启用
// Symfony 的 Response::headers 会自动验证
$response->headers->set('X-Custom', $input);  // 框架层面会拒绝 CRLF
```

### 3. 识别绕过过滤的技巧

**常见绕过方式（需要识别）：**
```php
// 绕过1：使用 URL 编码的 CRLF (%0d%0a, %0d, %0a)
// 输入：name=test%0d%0aSet-Cookie:%20admin=1
// 未解码检查就直接拼接

// 绕过2：使用其他空白字符
// %0b (垂直制表), %0c (表单换页) 在某些旧服务器可能被解析

// 绕过3：分段注入
$a = $_GET['a'];  // "test\r"
$b = $_GET['b'];  // "\nSet-Cookie: admin=1"
header("X-Data: " . $a . $b);  // 虽然每个都被过滤，组合却成功

// 绕过4：使用框架的特殊字符
// 某些框架允许 `;` 来分隔多个头值
header("X-Value: " . $_GET['v']);  // "val1;Set-Cookie:admin=1"
```

### 4. 审计检查清单

**L1 级审计（关键词扫描）：**
- [ ] 搜索所有 `header(`, `header_remove(` 调用
- [ ] 检查是否有直接字符串拼接：`"..." . $var`
- [ ] 快速标记无明显过滤的代码

**L3 级审计（逐行深入）：**
- [ ] 追踪变量来源（是否来自用户输入）
- [ ] 检查是否存在 CRLF 过滤（位置、完整性）
- [ ] 检查过滤器是否在 header() 调用前应用
- [ ] 检查是否有条件绕过（if-else 分支）
- [ ] 验证框架版本是否有已知漏洞

**深层检查项：**
- [ ] 多层变量赋值：`$a = $b = $_GET['x']`
- [ ] 动态头名称：`header($dynamic_header_name . ": " . $value)`
- [ ] 响应头在 buffer 中被延迟输出
- [ ] 是否使用了 `ob_start()` 等输出缓冲函数
- [ ] 框架中间件是否有额外防护

### 5. 实战案例分析

**案例1：真实漏洞**
```php
// 某 CMS 系统
$lang = $_GET['lang'] ?? 'en';
$filename = "/lang/" . $lang . ".txt";
if (file_exists($filename)) {
    header("Content-Language: " . $lang);  // 危险！
}
// 输入：lang=en%0d%0aSet-Cookie:%20admin=1
// 结果：注入 Set-Cookie 头
```

**案例2：误报（初看像漏洞）**
```php
// 某框架
$redirect = $_GET['return'] ?? '/';
if (filter_var($redirect, FILTER_VALIDATE_URL)) {
    header("Location: " . $redirect);  // 看起来无过滤，实际上 FILTER_VALIDATE_URL 会拒绝 CRLF
}
```

**案例3：过滤不完整的漏洞**
```php
// 某应用
$safe = str_replace(["\n", "%0a", "%0A"], "", $_GET['id']);
header("X-ID: " . $safe);
// 仍可通过 \r (%0d) 和 %0D 绕过，实现响应分割
```
