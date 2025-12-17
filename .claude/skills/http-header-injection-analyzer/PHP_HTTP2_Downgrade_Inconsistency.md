# PHP HTTP/2降级处理不一致

## 基本信息
- **难度等级：** ★★★★★ | **审计时间：** 40-60分钟
- **关键词搜索：** `HTTP/2`, `h2`, `$_SERVER['SERVER_PROTOCOL']`, `apache_request_headers()`, `HTTP_`, `strtolower`, `ucwords`
- **快速检查：** 应用是否处理HTTP/2请求，头字段大小写处理是否一致

## 漏洞成因

HTTP/2协议强制所有头字段小写（如`content-type`），而HTTP/1.1使用Title-Case（如`Content-Type`）。当PHP应用部署在HTTP/2代理后方（如nginx h2-to-h1），若代码假设特定大小写或手动处理头字段规范化，可能导致安全检查绕过、请求走私、缓存中毒等攻击。

### 常见漏洞模式

```php
// ✗ 漏洞：假设头字段为Title-Case
<?php
$headers = getallheaders();
if (isset($headers['Content-Type']) && $headers['Content-Type'] === 'application/json') {
    // HTTP/2请求的头是 content-type（小写），此检查被绕过
    process_json();
}
// 攻击: HTTP/2请求发送 content-type: application/json 绕过检查
?>
```

```php
// ✗ 漏洞：$_SERVER['HTTP_*']大小写不一致
<?php
// $_SERVER中HTTP头被转换为大写+下划线
// 但不同Web服务器处理可能不一致
$auth = $_SERVER['HTTP_AUTHORIZATION'];  // 可能为空
$auth2 = $_SERVER['HTTP_authorization'];  // 可能为空

// 攻击者利用大小写差异绕过认证检查
if (!$auth) {
    deny_access();
}
?>
```

```php
// ✗ 漏洞：手动头规范化有缺陷
<?php
function normalizeHeader($name) {
    // 简单的Title-Case转换，未考虑HTTP/2
    return ucwords(strtolower($name), '-');
}

$headers = getallheaders();
$normalized = [];
foreach ($headers as $name => $value) {
    $normalized[normalizeHeader($name)] = $value;
}
// HTTP/2的 :authority 伪头被错误处理为 :Authority
?>
```

```php
// ✗ 漏洞：安全中间件大小写敏感检查
<?php
$headers = apache_request_headers();
$blocked_headers = ['X-Forwarded-For', 'X-Real-IP'];

foreach ($headers as $name => $value) {
    if (in_array($name, $blocked_headers)) {  // 大小写敏感匹配
        unset($headers[$name]);
    }
}
// HTTP/2的 x-forwarded-for（小写）未被过滤
?>
```

```php
// ✓ 修复：大小写不敏感处理
<?php
$headers = getallheaders();
$content_type = null;

foreach ($headers as $name => $value) {
    if (strcasecmp($name, 'Content-Type') === 0) {
        $content_type = $value;
        break;
    }
}

if ($content_type === 'application/json') {
    process_json();
}
?>
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 硬编码头名检查 | 搜索 `\$headers\['[A-Z]`，检查是否有大小写变体处理 |
| **P0** | 安全检查绕过 | 搜索认证/授权逻辑中的头检查，验证大小写敏感性 |
| **P1** | 自定义头规范化 | 搜索 `ucwords\|strtolower.*header`，检查规范化逻辑 |
| **P1** | HTTP/2伪头处理 | 搜索 `:authority\|:method\|:path`，检查是否正确处理 |
| **P2** | 代理配置审计 | 检查nginx/Apache HTTP/2配置，确认头转换行为 |
| **P2** | 缓存键大小写 | 搜索缓存逻辑，检查头名是否区分大小写 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 仅HTTP/1.1，无HTTP/2支持 | 快速跳过，确认服务器配置 |
| **L1** | 使用框架，框架处理头规范化 | 关键词扫描，确认框架版本 |
| **L2** | 使用$_SERVER['HTTP_*']访问头 | 跳读检查大小写处理 |
| **L3** | 自定义头处理逻辑 | 逐行审计规范化代码 |
| **L4** | 多层代理架构（CDN/LB/PHP-FPM） | 跨层追踪头转换行为 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 应用部署在HTTP/2环境（代理支持h2）
2. 代码中存在大小写敏感的头字段检查
3. 安全功能依赖特定头字段的存在或值

### 典型漏洞特征（满足任一项即确认）
- ✗ `$headers['Content-Type']` 硬编码检查，无小写变体处理
- ✗ `in_array($name, $blocked)` 大小写敏感的黑名单
- ✗ 手动规范化未处理HTTP/2伪头（`:authority`）
- ✗ 缓存键使用原始头名，大小写不一致导致缓存分裂

### 安全排除（任一项充分）
- ✓ 使用`strcasecmp()`或`strtolower()`进行头名比较
- ✓ 框架自动规范化头字段（如Laravel/Symfony）
- ✓ 代理层统一将头转换为Title-Case后再转发
- ✓ 仅HTTP/1.1环境，无HTTP/2支持

### 灰色判定（风险较低但需注意）
- 内部服务，HTTP/2仅用于客户端到LB
- 大小写不一致仅影响非安全功能
- 代理配置可能已处理规范化

---

## 真实漏洞与误报区分经验

### 常见误报场景

#### 误报1：框架自动规范化头字段
```php
// 这是安全的，不是漏洞
// Laravel、Symfony等框架已处理大小写不敏感访问
$auth = $request->header('Authorization');  // 框架内部处理大小写
$content_type = $request->header('content-type');  // 两种写法都有效
```
**判别方法**：检查框架文档，验证框架版本是否>= 该特性引入版本。追踪`Request::header()`的实现，确认使用`strcasecmp()`。

#### 误报2：代理层已规范化转换
```php
// Nginx h2到h1转换后统一为Title-Case
// 应用层无大小写问题
Location: http-proxy
    h2_max_header_size 16k;  // 启用h2转h1
    proxy_pass http://php-fpm;  // 转换后统一为Title-Case
```
**判别方法**：检查nginx/Apache配置，查看代理规则。测试真实HTTP/2请求是否被规范化，可通过修改`Content-Type`为`content-type`观察转发后的样子。

#### 误报3：头字段在非安全上下文使用
```php
// 虽然大小写不敏感，但此处无安全风险
$user_agent = $_SERVER['HTTP_USER_AGENT'];  // 无论大小写都不影响安全
$client_lang = $_SERVER['HTTP_ACCEPT_LANGUAGE'];  // 仅影响功能，非安全
```
**判别方法**：跟踪变量使用，确认是否用于：1) 身份验证/授权 2) 安全决策 3) 缓存键生成 4) WAF规则匹配。仅在安全路径中的大小写敏感才构成真实漏洞。

#### 误报4：静态列表完整覆盖
```php
// 虽然大小写敏感，但列表已完整覆盖所有变体
$headers = getallheaders();
if (in_array($name, ['Content-Type', 'content-type', 'CONTENT-TYPE'])) {
    // 已覆盖所有可能的变体
}
```
**判别方法**：枚举头字段的所有可能大小写变体，验证黑/白名单是否全覆盖。HTTP/2只会发送小写，HTTP/1.1只会发送Title-Case（严格来说）。

### 真实漏洞的关键特征

#### 特征1：安全检查被无条件绕过
```php
// 真实漏洞示例
if (isset($headers['X-API-Key']) && verify_key($headers['X-API-Key'])) {
    // HTTP/2中 x-api-key（小写）会绕过此检查
    allow_request();
} else {
    deny_request();  // 但HTTP/1.1中 X-API-Key 被检查，产生不一致
}
```
**确认标志**：
1. 明确存在HTTP/2代理入口
2. 代码中硬编码的Title-Case头检查
3. 无`strcasecmp()`或小写规范化
4. 检查结果直接影响授权决策

#### 特征2：缓存中毒 + 请求走私
```php
// 真实漏洞：缓存键使用原始头名
$cache_key = 'content:' . $headers['Content-Type'];  // HTTP/1.1使用
$cached = cache_get($cache_key);

// HTTP/2请求用 content-type，缓存键变为 'content:null'
// 可能导致缓存分裂或中毒
```
**确认标志**：
1. 缓存实现检查头字段作为一部分
2. 缓存键生成时大小写敏感
3. 缓存在代理或应用层实现
4. HTTP/2请求可能导致不同的缓存键

#### 特征3：WAF规则绕过
```php
// 真实漏洞：WAF黑名单检查
function check_malicious_headers($headers) {
    $blocked = ['X-File-Upload', 'X-Cmd-Injection'];
    foreach ($headers as $name => $value) {
        if (in_array($name, $blocked)) {  // 大小写敏感
            log_security_event('Blocked: ' . $name);
            return false;
        }
    }
    return true;
}
// HTTP/2请求用 x-file-upload（小写）绕过黑名单检查
```
**确认标志**：
1. 明确的安全中间件实现
2. 黑名单使用大小写敏感匹配
3. 黑名单项目都是安全相关头
4. HTTP/2攻击者可以用小写变体绕过

#### 特征4：会话/认证头绕过
```php
// 真实漏洞：多层认证检查不一致
$sess_header = $headers['X-Session-Token'];  // HTTP/1.1: X-Session-Token
$auth_middleware = function() {
    global $_SERVER;
    $token = $_SERVER['HTTP_X_SESSION_TOKEN'];  // 期望大写下划线
    // HTTP/2的 x-session-token 被转为 HTTP_x_session_token（部分Web服务器）
    // 可能无法匹配
};
```
**确认标志**：
1. 多个地方检查同一安全头
2. 访问方式不一致（getallheaders() vs $_SERVER）
3. 某些检查被绕过，其他检查正常
4. 可导致认证绕过

### 现场审计的区分技巧

| 指标 | 误报特征 | 真实漏洞特征 |
|------|---------|-----------|
| **代理配置** | 代理已规范化头字段为Title-Case | 代理透传原始头或未规范化 |
| **框架使用** | 使用Laravel/Symfony等成熟框架 | 自定义头处理框架或零头检查 |
| **变量追踪** | 头字段仅用于日志/分析 | 头字段用于认证/授权/缓存键 |
| **覆盖度** | 列表已穷举所有大小写变体 | 列表仅硬编码标准形式 |
| **环境确认** | 仅HTTP/1.1或代理已转换 | 确实支持HTTP/2透传 |
| **测试结果** | HTTP/1.1和HTTP/2请求结果相同 | HTTP/2小写头绕过检查 |

---

## 实现建议

### 核心防护方案

**方案1：大小写不敏感的头访问**
```php
<?php
function get_header_insensitive($headers, $name) {
    $lower_name = strtolower($name);
    foreach ($headers as $key => $value) {
        if (strtolower($key) === $lower_name) {
            return $value;
        }
    }
    return null;
}

$headers = getallheaders();
$content_type = get_header_insensitive($headers, 'Content-Type');
?>
```

**方案2：统一头规范化**
```php
<?php
function normalize_headers($headers) {
    $normalized = [];
    foreach ($headers as $name => $value) {
        // 统一转换为小写键
        $key = strtolower($name);
        // 跳过HTTP/2伪头
        if (strpos($key, ':') === 0) {
            continue;
        }
        $normalized[$key] = $value;
    }
    return $normalized;
}
?>
```

**方案3：安全的头黑名单过滤**
```php
<?php
function filter_blocked_headers($headers) {
    $blocked = ['x-forwarded-for', 'x-real-ip', 'x-forwarded-host'];
    $filtered = [];

    foreach ($headers as $name => $value) {
        if (!in_array(strtolower($name), $blocked)) {
            $filtered[$name] = $value;
        }
    }
    return $filtered;
}
?>
```

### 检查清单
- [ ] 所有头名比较使用大小写不敏感方法
- [ ] 安全检查使用`strcasecmp()`或统一小写化
- [ ] 黑名单/白名单使用小写形式
- [ ] 了解代理层的HTTP/2到HTTP/1.1转换行为
- [ ] 测试HTTP/2请求的小写头绕过

---

## 修复优先级

1. **立即修复**：认证/授权逻辑中的大小写敏感头检查
2. **本周修复**：统一所有头访问使用大小写不敏感方法
3. **可选加强**：实现统一的头规范化中间件
4. **长期优化**：使用框架安全API，确保HTTP/2兼容
