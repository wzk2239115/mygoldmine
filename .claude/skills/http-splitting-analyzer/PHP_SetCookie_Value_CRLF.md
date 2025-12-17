# PHP setcookie() 值 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `setcookie($name, $value, ...)` - 标准 Cookie 设置
- `setcookie()` 后直接拼接用户输入
- `$_COOKIE` 从请求中读取后重新设置

**快速定位核心操作：**
1. 搜索关键字：`setcookie(`、`Set-Cookie`、`$_COOKIE`
2. 追踪 Cookie 值来源：`$_GET`、`$_POST`、`$_COOKIE`、会话数据
3. 检查是否存在 CRLF 过滤
4. 追踪 Cookie 构造过程

**快速定位保护机制：**
- CRLF 检查：`if (strpos($value, "\r") !== false || strpos($value, "\n") !== false)`
- 值验证：`if (!preg_match('/^[a-zA-Z0-9\-_]*$/', $value))`
- URL 编码：`urlencode($value)`
- 框架防护：某些框架自动过滤

**代码示例：**
```php
// 危险：用户输入直接设置 Cookie
$token = $_GET['token'] ?? '';
setcookie('session', $token);  // 危险

// 危险：POST 参数
$auth = $_POST['auth'] ?? '';
setcookie('auth_token', $auth);  // 危险

// 危险：从 Cookie 重新设置
$old_id = $_COOKIE['id'] ?? '';
setcookie('user_id', $old_id);  // 危险
```

## Classify

**漏洞（Critical）：**
- 用户输入直接用于 Cookie 值
- 无 CRLF 过滤或验证
- 导致响应分割

**误报：**
- Cookie 值硬编码
- 系统生成的值
- 框架管理的 Cookie

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接拼接

## Low risk

**以下情况评为低风险：**
- Cookie 值硬编码
- 严格 CRLF 过滤
- 白名单验证
- 内部来源且已验证

## 审计专业技巧

### 1. 污点追踪重点

**第一步：定位 setcookie() 调用**
```php
// 搜索所有 setcookie 调用，重点关注：
setcookie($name, $userInput);      // 第二个参数是否受污染
setcookie('name', $a . $b . $c);  // 拼接表达式中是否包含用户输入
setcookie($dynamic, 'value');      // 动态 Cookie 名称是否受污染
```

**第二步：回溯数据来源**
- 直接来自：`$_GET`、`$_POST`、`$_REQUEST`、`$_COOKIE`
- 间接来源：数据库、文件、外部 API（需验证是否在写入时已过滤）
- 函数返回值：用户定义函数、危险函数（`urldecode()`、`base64_decode()` 等）

**第三步：识别过滤点**
```php
// 真正有效的过滤
if (strpos($value, "\r") === false && strpos($value, "\n") === false) {
    setcookie('name', $value);  // 安全
}

// 不安全的过滤
$safe = str_replace("\r\n", "", $value);  // 可用 %0d%0a 绕过
setcookie('name', $safe);

// 不完整的过滤
$safe = str_replace("\n", "", $value);    // 只过滤 \n，\r 可绕过
setcookie('name', $safe);
```

### 2. 真实漏洞特征

**案例1：会话固定结合 CRLF 注入**
```php
// 漏洞代码
if (isset($_GET['session_id'])) {
    setcookie('SESSIONID', $_GET['session_id']);
}
// 攻击向量：?session_id=attacker%0d%0aSet-Cookie:%20admin=1
// 结果：攻击者可注入额外的 Cookie 头
```

**案例2：语言偏好设置**
```php
// 漏洞代码
$lang = $_GET['lang'] ?? 'en';
setcookie('language', $lang);
// 攻击向量：?lang=en%0d%0aContent-Length:%200
// 结果：导致 HTTP 响应分割，缓存投毒
```

**案例3：用户名保存在 Cookie**
```php
// 漏洞代码
if ($login_success) {
    setcookie('username', $_POST['username']);
}
// 注意：用户名可能包含 URL 解码的字符
// ?username=user%0d%0aX-Injected-Header:%20value
```

**案例4：引用循环陷阱**
```php
// 漏洞代码
$id = $_COOKIE['user_id'] ?? $_GET['id'];
setcookie('user_id', $id);
// 风险：如果初始请求注入了 Cookie，后续会持久化
```

### 3. 常见误报排查

**误报1：框架自动处理**
```php
// Laravel
Session::put('key', $value);  // 框架自动过滤，不是漏洞

// Symfony
$response->headers->setCookie($cookie);  // HttpFoundation 自动过滤

// 查看框架源码确认是否存在过滤
```

**误报2：硬编码 Cookie 名称+动态值审查**
```php
// 看起来危险，但需要深入分析
setcookie('tracking_id', $value);

// 关键问题：$value 的来源是什么？
// 如果来自 hash('sha256', $user_id)，则安全
// 如果来自 $_GET，则危险
```

**误报3：多层过滤容易忽视**
```php
// 第一层过滤可能隐藏
$value = sanitize_cookie_value($_GET['token']);

// 第二层过滤在框架中
setcookie('token', $value);

// 必须查看 sanitize_cookie_value() 的实现，可能包含 CRLF 检查
```

**误报4：条件分支中的安全操作**
```php
// 危险的代码片段可能被条件限制
if (isset($_GET['premium'])) {
    setcookie('level', $_GET['premium']);  // 这可能在 if 中被过滤
}

// 需要看完整的 if 块，检查是否有前置验证
```

### 4. 审计检查清单

| 检查项 | 审计方法 | 误报风险 |
|-------|--------|--------|
| 用户输入来源 | 追踪 `$_*` 超全局变量 | 看错变量名（$_USER vs $_POST） |
| 过滤函数 | 逐行阅读过滤逻辑 | 不完整过滤被误判为安全 |
| 框架保护 | 查看框架文档+源码 | 版本差异导致保护变化 |
| 编码转换 | 检查 `urldecode()`、`base64_decode()` | 多层编码时遗漏某层 |
| 正则表达式 | 验证白名单的完整性 | 未考虑 Unicode/多字节字符 |
| 函数返回值 | 追踪用户函数的所有分支 | 某个分支未过滤 |

### 5. 高级绕过案例分析

**案例：不完整的正则表达式**
```php
// 看起来安全但可被绕过
if (preg_match('/^[a-zA-Z0-9]+$/', $_GET['id'])) {
    setcookie('id', $_GET['id']);
}
// 绕过：Unicode 字符 \u000d（CR）可能被某些 PHP 版本接受
```

**案例：双 URL 编码绕过**
```php
// 脆弱的多层过滤
$value = urldecode($_GET['token']);
$value = str_replace('%0a', '', $value);
setcookie('token', $value);
// 绕过：%250a（编码的 %0a）可绕过
```

**案例：函数的多重含义**
```php
// 陷阱：trim() 不能过滤 CRLF
$value = trim($_GET['value']);  // 仅移除空格和制表符
setcookie('setting', $value);   // 仍然危险！

// 正确做法
$value = trim($_GET['value'], "\r\n");
setcookie('setting', $value);
```

### 6. 实战审计步骤

1. **快速扫描**：使用 `grep -n "setcookie"` 定位所有调用点
2. **污点分析**：对每个 `setcookie()` 调用，追踪第二、三参数的来源
3. **过滤验证**：如果看到 `str_replace`、`preg_match`，需要：
   - 逐个字符验证过滤规则
   - 检查是否遗漏了十六进制编码的 CRLF（`\x0d`、`\x0a`）
4. **框架检查**：识别代码使用的框架，查其文档中的 Cookie 处理部分
5. **报告确认**：在实际环境中测试，确保注入点是可达的且未被 WAF 阻止
