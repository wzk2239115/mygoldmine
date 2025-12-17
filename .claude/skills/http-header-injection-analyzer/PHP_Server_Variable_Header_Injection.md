# PHP $_SERVER变量头注入

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `$_SERVER['HTTP_`, `$_SERVER['REQUEST_URI']`, `$_SERVER['PHP_SELF']`, `$_SERVER['QUERY_STRING']`, `getallheaders()`, `apache_request_headers()`
- **快速检查：** $_SERVER中HTTP_*变量是否直接用于响应头或HTML输出

## 漏洞成因

PHP的`$_SERVER`超全局变量中，以`HTTP_`开头的元素直接来自客户端请求头（如`HTTP_HOST`、`HTTP_USER_AGENT`），攻击者可完全控制其内容。若这些值直接用于响应头构造或HTML输出，可导致HTTP头注入、XSS、缓存中毒等攻击。

### 常见漏洞模式

```php
// ✗ 漏洞：HTTP_HOST直接用于重定向
<?php
$host = $_SERVER['HTTP_HOST'];
header("Location: https://$host/login");
// 攻击: Host: evil.com%0d%0aSet-Cookie:admin=true
?>
```

```php
// ✗ 漏洞：HTTP_X_FORWARDED_FOR直接输出
<?php
$ip = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? $_SERVER['REMOTE_ADDR'];
header("X-Client-IP: $ip");
// 攻击: X-Forwarded-For: 1.1.1.1%0d%0aX-Injected:header
?>
```

```php
// ✗ 漏洞：HTTP_ACCEPT_LANGUAGE用于Content-Language
<?php
$lang = $_SERVER['HTTP_ACCEPT_LANGUAGE'];
header("Content-Language: $lang");
// 攻击: Accept-Language: en%0d%0aSet-Cookie:lang=evil
?>
```

```php
// ✗ 漏洞：HTTP_REFERER用于Referer策略
<?php
$referer = $_SERVER['HTTP_REFERER'];
header("Referrer-Policy: origin-when-cross-origin");
echo "<a href='$referer'>返回</a>";  // XSS风险
// 攻击: Referer: javascript:alert(1)//
?>
```

```php
// ✓ 修复：白名单验证 + CRLF过滤
<?php
$allowed_hosts = ['example.com', 'www.example.com'];
$host = $_SERVER['HTTP_HOST'];
$safe_host = str_replace(["\r", "\n"], '', $host);

if (in_array($safe_host, $allowed_hosts)) {
    header("Location: https://$safe_host/login");
} else {
    header("Location: https://example.com/login");
}
?>
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | HTTP_HOST用于URL构造 | 搜索 `\$_SERVER\['HTTP_HOST'\]` + `header\|Location`，检查验证 |
| **P0** | HTTP_X_FORWARDED用于响应 | 搜索 `HTTP_X_FORWARDED`，检查是否直接输出到响应头 |
| **P1** | HTTP_ACCEPT_*用于响应头 | 搜索 `HTTP_ACCEPT_LANGUAGE\|HTTP_ACCEPT`，检查Content-*头 |
| **P1** | HTTP_REFERER输出 | 搜索 `HTTP_REFERER`，检查是否用于HTML或重定向 |
| **P2** | REQUEST_URI/PHP_SELF | 搜索 `REQUEST_URI\|PHP_SELF`，检查XSS和路径遍历 |
| **P2** | getallheaders()遍历 | 搜索 `getallheaders\|apache_request_headers`，检查头值使用 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | $_SERVER仅用于日志记录 | 快速跳过，确认无响应头输出 |
| **L1** | 使用SERVER_NAME替代HTTP_HOST | 关键词扫描，SERVER_NAME更安全 |
| **L2** | 单文件内$_SERVER用于响应头 | 跳读检查过滤和白名单 |
| **L3** | 封装函数处理$_SERVER变量 | 逐行追踪函数内部处理逻辑 |
| **L4** | 框架请求对象封装$_SERVER | 跨模块检查Request类实现 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. $_SERVER['HTTP_*']变量直接或间接用于响应头
2. 未进行CRLF过滤或白名单验证
3. 攻击者可控制对应的HTTP请求头

### 典型漏洞特征（满足任一项即确认）
- ✗ `header("Location: https://{$_SERVER['HTTP_HOST']}/path")`
- ✗ `header("X-Client-IP: {$_SERVER['HTTP_X_FORWARDED_FOR']}")`
- ✗ `echo "<script src='//{$_SERVER['HTTP_HOST']}/js/app.js'></script>"`
- ✗ `header("Content-Language: {$_SERVER['HTTP_ACCEPT_LANGUAGE']}")`

### 安全排除（任一项充分）
- ✓ 使用`$_SERVER['SERVER_NAME']`替代`HTTP_HOST`（Apache配置控制）
- ✓ 白名单验证：`in_array($host, $allowed_hosts)`
- ✓ CRLF过滤：`preg_replace('/[\r\n]/', '', $value)`
- ✓ 框架安全封装：Laravel `$request->getHost()`有验证

### 灰色判定（风险较低但需注意）
- 内网应用，外部攻击者难以利用
- $_SERVER值仅用于非安全功能（如统计）
- 有WAF防护HTTP头注入

---

## 审计专业技巧

### 真实漏洞vs误报的区分

#### 1. 误报典型场景

**场景A：安全的日志输出**
```php
// ✓ 安全：仅用于日志，不影响响应
error_log("User agent: " . $_SERVER['HTTP_USER_AGENT']);
// 分析：日志文件是服务端资源，攻击者无法通过HTTP头注入利用
```

**场景B：框架内置防护**
```php
// ✓ 安全：Laravel Request对象已验证
$host = request()->getHost();  // 内置规范化和验证
// 分析：Laravel通过parse_url()解析，过滤了非法字符
```

**场景C：仅用于本地操作**
```php
// ✓ 安全：仅用于数据库查询参数
$query = "SELECT * FROM logs WHERE ip = '" . mysqli_real_escape_string($conn, $_SERVER['HTTP_X_FORWARDED_FOR']) . "'";
// 分析：即使包含CRLF，也无法注入HTTP头（虽然SQL注入风险存在，但不是HTTP头注入）
```

**场景D：外部变量存储后使用**
```php
// ✓ 相对安全：值已持久化，不再是客户端控制
$ip = $_SERVER['HTTP_X_FORWARDED_FOR'];
$user_record['ip'] = $ip;
$pdo->insert('users', $user_record);
// 后续读取
echo htmlspecialchars($user_record['ip']);  // 已转义
// 分析：虽然初始接收不安全，但整个流程已规范化
```

#### 2. 真实漏洞的确凿迹象

**迹象1：直接响应头构造**
```php
// ✗ 真实漏洞：100%确认
header("X-Custom: " . $_SERVER['HTTP_X_CUSTOM']);
// 原因：PHP header()函数不过滤CRLF，\r\n会中断头部
// 证明：可以注入Set-Cookie等关键头
```

**迹象2：URL重定向注入**
```php
// ✗ 真实漏洞：95%确认
$url = "https://" . $_SERVER['HTTP_HOST'] . "/callback";
header("Location: $url");
// 原因：Location头支持绝对URI，HTTP_HOST可包含Host头走私
// POC：Host: example.com%0d%0aSet-Cookie:admin=1
```

**迹象3：JSON或XML响应中的头值**
```php
// ✗ 真实漏洞：高风险但非直接HTTP头注入
header('Content-Type: application/json');
echo json_encode(['ip' => $_SERVER['HTTP_X_FORWARDED_FOR']]);
// 原因：虽然响应头已正确设置，但如果后续被用作header()参数则有风险
// 风险转移：关键是检查这个JSON是否会被其他代码用于header()
```

#### 3. 审计的关键判断流程

**Step 1：源点识别**
```
搜索: $_SERVER['HTTP_* 或 REQUEST_URI 或 PHP_SELF
检查：变量是否可被客户端完全控制
   • HTTP_*系列 → 100% 用户控制
   • REQUEST_URI → 95% 用户控制（某些前置代理可能规范化）
   • REMOTE_ADDR → 50% 用户控制（X-Forwarded-For可伪造）
```

**Step 2：传播路径追踪**
```
跟踪：$_SERVER值是否经过以下处理
   • 白名单验证 → 停止审计（安全）
   • CRLF过滤正则 → 检查正则是否完整
   • HTML转义(htmlspecialchars/htmlentities) → 仅防XSS，不防HTTP头注入
   • 数据库存储 → 继续追踪该值的读取使用
```

**Step 3：汇聚点检查**
```
最终输出点：
   • header() 函数 → 直接HTTP头注入风险
   • echo/print 在<script>中 → XSS风险，不是头注入
   • 数据库存储 → 非直接风险（已落库）
   • 日志文件 → 低风险（后端资源）
```

### 实战审计技巧速查表

| 检查场景 | 真实漏洞指标 | 常见误报原因 | 审计建议 |
|---------|-----------|-----------|---------|
| `header("X-*: " . $_SERVER['HTTP_X_*'])` | ✗ 确认漏洞 | - | 立即报告 |
| `header("Location: " . $_SERVER['HTTP_HOST'])` | ✗ 确认漏洞 | - | 立即报告 + POC验证 |
| `echo $_SERVER['HTTP_USER_AGENT']` | ✓ XSS（非头注入） | 误认为HTTP头注入 | 分类为XSS审计 |
| `error_log($_SERVER['HTTP_*'])` | ✓ 误报 | 误认为影响响应 | 跳过 |
| `REQUEST_URI` 用于301重定向 | ✗ 头注入风险 | 误认为REQUEST_URI安全 | 检查是否包含CRLF处理 |
| `$_SERVER['REMOTE_ADDR']` 输出响应 | ⚠ 条件漏洞 | 误认为服务端变量安全 | 检查是否走代理（X-Forwarded-For可伪造） |
| 框架请求对象`$request->header()` | ✓ 通常安全 | 误认为框架变量不安全 | 检查框架版本和配置 |

### 审计陷阱与绕过

**陷阱1：不完整的CRLF过滤**
```php
// ✗ 不安全：只过滤了\n，漏掉\r
$safe = str_replace("\n", "", $_SERVER['HTTP_HOST']);
header("X-Host: $safe");
// 攻击：Host: example.com\rSet-Cookie:admin=1
// 原因：PHP某些版本中\r也能中断头部

// ✓ 完整过滤
$safe = preg_replace('/[\r\n\0]/', '', $safe);
```

**陷阱2：信任X-Forwarded-For的攻击者**
```php
// ✗ 常见误判：认为这是安全的
$ip = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? $_SERVER['REMOTE_ADDR'];
// 风险：X-Forwarded-For由客户端完全控制，不可信任
// 正确做法：仅在明确的内网代理场景使用，且验证代理IP

// ✓ 安全做法
if (in_array($_SERVER['REMOTE_ADDR'], $trusted_proxies)) {
    $ip = $_SERVER['HTTP_X_FORWARDED_FOR'];
} else {
    $ip = $_SERVER['REMOTE_ADDR'];
}
```

**陷阱3：多次编码的绕过**
```php
// ✗ 危险：仅过滤一次，可能被多层编码绕过
$safe = str_replace(["\r", "\n"], '', $_SERVER['HTTP_HOST']);
header("X-Host: $safe");
// 攻击向量：某些服务器可能会解码（如URL解码后再处理）

// ✓ 防御：配合白名单
$allowed = ['example.com', 'api.example.com'];
if (!in_array($_SERVER['HTTP_HOST'], $allowed)) {
    die('Invalid host');
}
```

---

## 实现建议

### 核心防护方案

**方案1：使用安全的服务器变量**
```php
<?php
// 使用SERVER_NAME替代HTTP_HOST（需Apache正确配置）
$host = $_SERVER['SERVER_NAME'];

// 或使用白名单验证
$allowed = ['example.com', 'www.example.com'];
$host = in_array($_SERVER['HTTP_HOST'], $allowed)
    ? $_SERVER['HTTP_HOST']
    : 'example.com';
?>
```

**方案2：统一过滤函数**
```php
<?php
function safe_server_var($key) {
    $value = $_SERVER[$key] ?? '';
    // 移除CRLF和NULL字节
    return preg_replace('/[\r\n\0]/', '', $value);
}

$host = safe_server_var('HTTP_HOST');
?>
```

**方案3：使用框架安全方法**
```php
<?php
// Laravel
$host = request()->getHost();  // 内置验证
$ip = request()->ip();         // 安全获取客户端IP

// Symfony
$host = $request->getHost();
?>
```

### 检查清单
- [ ] HTTP_HOST使用白名单验证
- [ ] HTTP_X_FORWARDED_FOR仅用于日志，不信任
- [ ] 所有$_SERVER['HTTP_*']用于响应头前过滤CRLF
- [ ] REQUEST_URI/PHP_SELF输出前HTML转义
- [ ] 考虑使用SERVER_NAME替代HTTP_HOST

---

## 修复优先级

1. **立即修复**：HTTP_HOST直接用于重定向或URL构造
2. **本周修复**：所有HTTP_*变量添加CRLF过滤
3. **可选加强**：实现统一的$_SERVER访问封装函数
4. **长期优化**：使用框架安全API，配置Apache ServerName
