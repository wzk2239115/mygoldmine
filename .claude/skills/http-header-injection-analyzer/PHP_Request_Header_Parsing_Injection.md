# PHP 请求头解析注入

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `getallheaders()`, `apache_request_headers()`, `$_SERVER['HTTP_`, `http_get_request_headers()`, `foreach.*headers`, `$headers[`
- **快速检查：** 是否遍历请求头并用于响应或业务逻辑，是否有头名/值的验证

## 漏洞成因

PHP的`getallheaders()`和`apache_request_headers()`函数返回所有HTTP请求头，这些头完全由客户端控制。若遍历这些头并直接用于响应头设置、日志记录或业务逻辑，攻击者可注入恶意头值，导致HTTP响应拆分、日志注入、安全检查绕过等攻击。

### 常见漏洞模式

```php
// ✗ 漏洞：遍历请求头并设置响应头
<?php
$headers = getallheaders();
foreach ($headers as $name => $value) {
    if (strpos($name, 'X-Custom-') === 0) {
        header("$name: $value");  // 直接透传，可注入CRLF
    }
}
// 攻击: X-Custom-Test: value%0d%0aSet-Cookie:admin=true
?>
```

```php
// ✗ 漏洞：请求头用于认证决策
<?php
$headers = apache_request_headers();
if (isset($headers['X-Internal-Auth']) && $headers['X-Internal-Auth'] === 'trusted') {
    // 绕过认证
    grant_admin_access();
}
// 攻击: 添加 X-Internal-Auth: trusted 头
?>
```

```php
// ✗ 漏洞：请求头写入日志（日志注入）
<?php
$headers = getallheaders();
$log_entry = date('Y-m-d H:i:s') . " - UA: " . $headers['User-Agent'];
file_put_contents('/var/log/app.log', $log_entry . "\n", FILE_APPEND);
// 攻击: User-Agent: normal\n2024-01-01 00:00:00 - ADMIN LOGIN SUCCESS
?>
```

```php
// ✗ 漏洞：头值用于数据库查询
<?php
$headers = getallheaders();
$api_key = $headers['X-API-Key'];
$result = $db->query("SELECT * FROM users WHERE api_key = '$api_key'");
// SQL注入风险
?>
```

```php
// ✓ 修复：白名单验证 + 过滤
<?php
$allowed_headers = ['X-Request-ID', 'X-Correlation-ID'];
$headers = getallheaders();

foreach ($headers as $name => $value) {
    if (in_array($name, $allowed_headers)) {
        $safe_value = preg_replace('/[\r\n\0]/', '', $value);
        header("$name: $safe_value");
    }
}
?>
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 头透传到响应 | 搜索 `getallheaders\|apache_request_headers` + `header(`，检查过滤 |
| **P0** | 头用于认证/授权 | 搜索 `\$headers\[.*auth\|token\|key`，检查是否信任客户端头 |
| **P1** | 头值写入日志 | 搜索 `getallheaders` + `file_put_contents\|fwrite\|log`，检查日志注入 |
| **P1** | 头值用于SQL查询 | 搜索 `\$headers\[` + `query\|execute`，检查SQL注入 |
| **P2** | 遍历所有请求头 | 搜索 `foreach.*getallheaders`，评估处理逻辑安全性 |
| **P2** | 自定义头解析 | 搜索 `explode\(":".*HTTP_RAW`，检查手动解析逻辑 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 不使用getallheaders()，仅固定$_SERVER | 快速跳过 |
| **L1** | 使用特定头，有白名单检查 | 关键词扫描确认白名单完整 |
| **L2** | 遍历头但有基础过滤 | 跳读检查CRLF过滤和白名单 |
| **L3** | 头值用于业务逻辑判断 | 逐行追踪数据流和决策点 |
| **L4** | 自定义HTTP解析器 | 跨模块检查解析器实现 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 使用getallheaders()/apache_request_headers()获取请求头
2. 头值直接用于响应头、认证决策或数据库查询
3. 无白名单验证或CRLF/特殊字符过滤

### 典型漏洞特征（满足任一项即确认）
- ✗ `foreach (getallheaders() as $k => $v) { header("$k: $v"); }`
- ✗ `if ($headers['X-Admin'] === 'true') { ... }` 信任客户端头
- ✗ `$db->query("... WHERE key = '{$headers['X-API-Key']}'")`
- ✗ `file_put_contents($log, $headers['User-Agent'])` 无转义

### 安全排除（任一项充分）
- ✓ 头名白名单：`in_array($name, ['X-Request-ID'])`
- ✓ CRLF过滤：`preg_replace('/[\r\n\0]/', '', $value)`
- ✓ 内部头由可信代理设置且有验证（如X-Real-IP）
- ✓ 头值经过参数化查询或转义处理

### 灰色判定（风险较低但需注意）
- 头仅用于日志但有基础转义
- 内网应用，请求头来源可控
- 有WAF过滤恶意头

---

## 审计专业技巧：真实漏洞与误报区分

### 常见误报场景（无需修复）

#### 1. **静态头使用 - 无风险**
```php
// ✓ 错误触发：搜索 $_SERVER['HTTP_X_FORWARDED_FOR']
// 实际无风险：仅读取单个预定义头
$trusted_ip = $_SERVER['HTTP_X_REAL_IP'] ?? $_SERVER['REMOTE_ADDR'];
// 风险评估：固定头名，无遍历，值仅用于日志/统计
```
**判断依据**：没有`foreach`或动态头名拼接

#### 2. **内部API网关场景 - 低风险**
```php
// ✓ 容易误报：多层代理，X-Real-IP/X-Forwarded-For
$headers = getallheaders();
if (isset($headers['X-Forwarded-For'])) {
    $forwarded = explode(',', $headers['X-Forwarded-For']);
    $client_ip = trim($forwarded[0]);
    // 仅提取IP用于访问控制日志
    log_client_access($client_ip);
}
// 风险评估：IP提取逻辑安全，无CRLF风险（IP格式受限）
```
**判断依据**：值经过格式验证（IP正则），无SQL/命令注入风险

#### 3. **框架自动处理 - 无风险**
```php
// ✓ Laravel/Symfony框架
$request->headers->get('X-Request-ID');  // 框架已处理安全
// Slim框架
$request->getHeaderLine('Content-Type');  // 返回单个值，安全
```
**判断依据**：框架文档确认已做CRLF防护

#### 4. **仅读取内容长度/类型 - 低风险**
```php
// ✓ 误报示例
$headers = getallheaders();
if ($headers['Content-Length'] > 1000000) {
    reject_request('File too large');
}
// 风险评估：Content-Length值为数字，无法注入CRLF
```
**判断依据**：头值格式受限（数字、枚举值），不可能注入危险字符

### 真实漏洞特征 - 必须修复

#### 1. **关键漏洞：头直接进响应头**
```php
// ✗ 必须修复：直接透传请求头到响应
$headers = getallheaders();
foreach ($headers as $name => $value) {
    // 问题：$name和$value都来自客户端
    header("X-Echo-$name: $value");
    // 攻击：X-Echo-Test: value\r\nSet-Cookie: admin=true
}

// 改进版本看起来安全但仍有问题
$safe_value = htmlspecialchars($value);
header("X-Echo: $safe_value");  // ✗ htmlspecialchars对CRLF无效
```
**确认漏洞**：使用`header()`前未过滤`\r\n\0`

#### 2. **关键漏洞：头用于认证决策**
```php
// ✗ 必须修复：完全信任客户端头
$headers = apache_request_headers();
if ($headers['X-API-Secret'] === 'prod-secret-key') {
    $_SESSION['is_admin'] = true;  // 认证逻辑错误
}

// 也是漏洞：多层验证但最后信任了头
if (isset($headers['Authorization'])) {
    $token = substr($headers['Authorization'], 7);  // Bearer token
    if (token_is_valid($token) && $headers['X-Admin-Flag'] === '1') {
        // ✗ 即使token有效，X-Admin-Flag也不应信任
        grant_admin_privilege();
    }
}
```
**确认漏洞**：头值直接影响权限决策，未通过代码逻辑/会话验证

#### 3. **关键漏洞：SQL注入风险**
```php
// ✗ 必须修复：头值直接进SQL（即使有引号也不够）
$headers = getallheaders();
$api_key = $headers['X-API-Key'];
$result = $db->query("SELECT * FROM users WHERE api_key = '$api_key'");

// ✗ 仍是漏洞：单引号绕过
$user = $db->query("SELECT * FROM users WHERE email = '{$headers['X-User-Email']}'");

// ✓ 正确做法：参数化查询
$result = $db->prepare("SELECT * FROM users WHERE api_key = ?")->execute([$api_key]);
```
**确认漏洞**：头值进入SQL语句，未使用参数化查询

#### 4. **中等漏洞：日志注入 + 审计风险**
```php
// ✗ 日志注入：伪造审计日志
$headers = getallheaders();
$log_entry = date('Y-m-d H:i:s') . " - USER: " . $headers['X-User'];
error_log($log_entry);
// 攻击：X-User: admin\n2024-01-01 00:00:00 - CRITICAL: SYSTEM BREACH

// ✗ 仍然有问题：只过滤了User-Agent
$ua = $headers['User-Agent'] ?? '';
$ua = str_replace("\n", " ", $ua);  // 只过滤\n
// ✗ 问题：\r\n也能换行（Windows行尾）

// ✓ 正确方法
$ua = preg_replace('/[\r\n\0]/', '', $ua);
$ua = substr($ua, 0, 500);  // 限制长度防止日志溢出
```
**确认漏洞**：日志包含用户可控内容，且无CRLF过滤

### 审计决策树

```
┌─ getallheaders() 或 apache_request_headers() 使用？
│
├─ NO → L0等级，跳过
│
└─ YES → 检查以下条件
   │
   ├─ [P0] 是否有 foreach/in_array/isset 迭代头？
   │   │
   │   ├─ YES + 用于 header() 输出
   │   │   └─ 检查是否过滤了 /[\r\n\0]/
   │   │       ├─ NO → 漏洞 L3/L4
   │   │       └─ YES + 有白名单 → 安全
   │   │
   │   ├─ YES + 用于认证/授权
   │   │   └─ 直接? → 漏洞 L4（权限绕过）
   │   │       间接（TOKEN校验后）? → 检查头是否影响决策
   │   │
   │   └─ YES + 用于数据库
   │       └─ 是否参数化?
   │           ├─ NO → 漏洞 L4（SQL注入）
   │           └─ YES → 安全
   │
   ├─ [P1] 是否写入日志/文件？
   │   │
   │   ├─ YES + 无CRLF过滤 → 漏洞 L2（日志注入）
   │   └─ YES + 有 preg_replace(/[\r\n]/) → 安全
   │
   └─ [P2] 仅读取单个头值？
       └─ 是否格式受限？
           ├─ IP/数字/枚举 → 安全 L0
           └─ 自由文本 + 用于DB → 检查参数化
```

### 审计沟通要点

**与开发讨论时的话术：**

- **如果开发说"我们有WAF保护"**：
  ```
  WAF是纵深防御，但代码内部不应该依赖WAF
  询问：有没有代码层面的检查？即使WAF被绕过怎么办？
  追问：如果这是内部应用，没有WAF呢？
  ```

- **如果开发说"这只在日志里，不影响应用"**：
  ```
  确认：日志是否被外部系统解析（如ELK/Splunk）？
  提示：日志注入可伪造审计日志，影响安全事件调查
  关键：即使"只是日志"，也要过滤CRLF
  ```

- **如果开发说"头值来自可信来源"**：
  ```
  反问：在什么场景下是可信的？有网络拓扑图吗？
  测试：能否从互联网直接发送这个头？
  结论：HTTP头总是可由网络上任何人伪造，除非有认证签名
  ```

---

## 实现建议

### 核心防护方案

**方案1：白名单 + 过滤**
```php
<?php
function get_safe_headers() {
    $allowed = ['X-Request-ID', 'X-Correlation-ID', 'Accept-Language'];
    $headers = getallheaders();
    $safe = [];

    foreach ($headers as $name => $value) {
        if (in_array($name, $allowed)) {
            $safe[$name] = preg_replace('/[\r\n\0]/', '', $value);
        }
    }
    return $safe;
}
?>
```

**方案2：安全的日志记录**
```php
<?php
function log_request($headers) {
    $ua = $headers['User-Agent'] ?? 'unknown';
    // 移除换行符防止日志注入
    $safe_ua = str_replace(["\r", "\n"], ' ', $ua);
    // 限制长度
    $safe_ua = substr($safe_ua, 0, 200);

    error_log("Request from UA: $safe_ua");
}
?>
```

**方案3：认证头验证**
```php
<?php
// 不信任客户端头进行认证
// 内部头应由可信代理设置，并验证来源IP
function validate_internal_request() {
    $trusted_proxies = ['10.0.0.1', '10.0.0.2'];
    $client_ip = $_SERVER['REMOTE_ADDR'];

    if (!in_array($client_ip, $trusted_proxies)) {
        return false;  // 不信任非代理来源的内部头
    }

    return isset($_SERVER['HTTP_X_INTERNAL_AUTH']);
}
?>
```

### 检查清单
- [ ] getallheaders()返回值使用白名单过滤
- [ ] 头值用于响应头前过滤CRLF
- [ ] 不信任客户端头进行认证决策
- [ ] 头值写入日志前转义换行符
- [ ] 头值用于SQL查询使用参数化

---

## 修复优先级

1. **立即修复**：请求头直接透传到响应头
2. **本周修复**：移除基于客户端头的认证逻辑
3. **可选加强**：实现统一的头值获取和过滤函数
4. **长期优化**：使用框架安全API获取请求头
