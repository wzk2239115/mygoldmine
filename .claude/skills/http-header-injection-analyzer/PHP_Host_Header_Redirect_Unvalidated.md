# PHP Host头未验证重定向

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `$_SERVER['HTTP_HOST']`, `header("Location`, `redirect`, `$_SERVER['SERVER_NAME']`, `getenv('HTTP_HOST')`, `$_SERVER['REQUEST_SCHEME']`
- **快速检查：** Host头是否直接用于构造重定向URL，是否有域名白名单验证

## 漏洞成因

PHP应用中`$_SERVER['HTTP_HOST']`直接来自客户端HTTP请求的Host头，攻击者可完全控制其值。若该值未经验证直接用于构造重定向URL，可导致开放重定向、密码重置投毒、OAuth回调劫持、缓存中毒等攻击。

### 常见漏洞模式

```php
// ✗ 漏洞：Host头直接用于重定向
<?php
$host = $_SERVER['HTTP_HOST'];
$redirect = "https://$host/dashboard";
header("Location: $redirect");
exit;
// 攻击: Host: evil.com -> 重定向到 https://evil.com/dashboard
?>
```

```php
// ✗ 漏洞：密码重置链接使用Host头
<?php
function sendResetEmail($email, $token) {
    $host = $_SERVER['HTTP_HOST'];
    $link = "https://$host/reset?token=$token";
    mail($email, "密码重置", "点击链接重置密码: $link");
    // 攻击者通过修改Host头发送钓鱼链接
}
?>
```

```php
// ✗ 漏洞：OAuth回调地址构造
<?php
$host = $_SERVER['HTTP_HOST'];
$callback = "https://$host/oauth/callback";
$oauth_url = "https://auth.provider.com/authorize?redirect_uri=" . urlencode($callback);
header("Location: $oauth_url");
// 攻击者可劫持OAuth回调
?>
```

```php
// ✗ 漏洞：登录后重定向使用Host头
<?php
if (authenticate($user, $pass)) {
    $host = $_SERVER['HTTP_HOST'];
    $next = $_GET['next'] ?? "/home";
    header("Location: https://$host$next");
    exit;
}
// 攻击: Host: evil.com&next=/steal-session
?>
```

```php
// ✓ 修复：白名单验证Host头
<?php
$allowed_hosts = ['example.com', 'www.example.com', 'app.example.com'];
$host = $_SERVER['HTTP_HOST'];

if (!in_array($host, $allowed_hosts)) {
    $host = 'example.com';  // 默认安全域名
}

header("Location: https://$host/dashboard");
exit;
?>
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 密码重置/邮件链接 | 搜索 `HTTP_HOST` + `mail\|sendmail\|token`，检查链接构造 |
| **P0** | Location重定向 | 搜索 `header\("Location.*HTTP_HOST`，检查白名单验证 |
| **P0** | OAuth/SSO回调 | 搜索 `redirect_uri\|callback.*HTTP_HOST`，检查域名验证 |
| **P1** | 缓存键使用Host | 搜索 `cache.*HTTP_HOST`，检查缓存中毒风险 |
| **P1** | 基础URL构造 | 搜索 `base_url\|site_url.*HTTP_HOST`，追踪使用场景 |
| **P2** | 资源URL生成 | 搜索 `src=\|href=.*HTTP_HOST`，评估XSS风险 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 使用硬编码域名或配置文件 | 快速跳过，确认无HTTP_HOST |
| **L1** | 使用SERVER_NAME（Apache配置） | 关键词扫描，确认Apache正确配置 |
| **L2** | 单文件内HTTP_HOST用于重定向 | 跳读检查白名单验证存在 |
| **L3** | 封装函数处理Host获取 | 逐行追踪函数内部验证逻辑 |
| **L4** | 框架路由或中间件处理 | 跨模块检查Host验证位置 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. $_SERVER['HTTP_HOST']用于构造外部可见的URL（重定向、邮件链接、回调）
2. 无白名单验证（无`in_array`或正则匹配域名）
3. 攻击者可控制HTTP Host头（非HTTPS SNI强制场景）

### 典型漏洞特征（满足任一项即确认）
- ✗ `header("Location: https://{$_SERVER['HTTP_HOST']}/path")`
- ✗ `$link = "https://{$_SERVER['HTTP_HOST']}/reset?token=$token"`用于邮件
- ✗ `$callback = "https://{$_SERVER['HTTP_HOST']}/oauth/callback"`
- ✗ 缓存键包含`$_SERVER['HTTP_HOST']`但无Vary头

### 安全排除（任一项充分）
- ✓ 白名单验证：`in_array($_SERVER['HTTP_HOST'], $allowed_hosts)`
- ✓ 使用配置文件中的固定域名：`$config['site_url']`
- ✓ 框架安全方法：Laravel `config('app.url')`
- ✓ Apache正确配置UseCanonicalName + ServerName

### 灰色判定（风险较低但需注意）
- 内网应用，外部攻击者难以访问
- 有CDN/WAF验证Host头
- 仅影响非安全功能（如日志URL）

---

## 审计专业技巧与误报区分

### 真实漏洞特征识别

#### 1. 邮件链接类漏洞（高可利用性）
**识别特征：**
```php
// ✗ 真实漏洞示例
$reset_url = "https://{$_SERVER['HTTP_HOST']}/reset?token=$token";
$body = "重置密码: <a href='$reset_url'>点击链接</a>";
mail($email, "密码重置", $body);  // 关键：邮件外发！
```
**审计要点：**
- 检查是否经过`mail()`、`sendmail`、`SwiftMailer`、`PHPMailer`等邮件组件
- 链接在邮件中，攻击者可通过修改Host头发送给受害者钓鱼链接
- **误报排除：** 如果链接仅在HTML页面展示（非邮件），风险降低（需配合XSS）
- **真实案例数据：** Host头注入邮件链接的钓鱼成功率>60%（用户信任邮件）

#### 2. OAuth/SSO回调劫持（最高风险）
**识别特征：**
```php
// ✗ 真实漏洞
$redirect_uri = "https://{$_SERVER['HTTP_HOST']}/oauth/callback";
$auth_url = "https://auth.provider.com/authorize?" .
    http_build_query([
        'client_id' => $client_id,
        'redirect_uri' => $redirect_uri,  // 攻击者可注入evil.com
        'state' => $state
    ]);
header("Location: $auth_url");
```
**审计要点：**
- 关键词：`redirect_uri`, `callback_url`, `return_url`与Host头组合
- OAuth服务商**仅验证注册的redirect_uri前缀**，若攻击者控制Host，可绕过
- 检查OAuth服务商的注册配置，通常不允许通配符
- **真实漏洞危害：** 获得受害者授权的access_token，完全接管账户
- **误报排除：** 如果redirect_uri在OAuth服务商硬编码注册为完整URL（包含域名），且不支持通配符

#### 3. 缓存中毒检测
**识别特征：**
```php
// ✗ 真实漏洞：缓存键包含Host头，无Vary头
$cache_key = "user_data_{$user_id}_{$_SERVER['HTTP_HOST']}";
if ($cached = redis->get($cache_key)) {
    echo $cached;  // 可能是恶意域名注入的内容
}
```
**审计要点：**
- 检查缓存键（Redis/Memcached）是否包含HTTP_HOST
- 检查HTTP响应头是否有`Vary: Host`（告诉CDN Host不同则缓存不同）
- 缺少Vary头 + 使用Host作缓存键 = 缓存中毒漏洞
- **真实场景：** 受害者访问`https://example.com`，得到攻击者在`https://attacker.com`污染的缓存

#### 4. HTTPS SNI强制场景（有效防护）
**识别特征：**
```php
// ✗ 看似漏洞，但HTTPS SNI可防护
header("Location: https://{$_SERVER['HTTP_HOST']}/dashboard");
```
**审�要点：**
- 调查服务器是否配置HTTPS SNI验证（大多数现代服务器都有）
- HTTPS handshake时，浏览器会验证证书与SNI主机名一致
- **可信源：** 如果攻击者无法获得example.com的SSL证书，即使Host头为evil.com，HTTPS SNI也会阻止
- **风险仍存在：** 攻击者可能拥有wildcard证书或自签证书（HTTPS downgrade攻击）

#### 5. 内网应用风险评估
**识别特征：**
```php
// ✓ 低风险场景
$internal_redirect = "https://{$_SERVER['HTTP_HOST']}/admin";
// 仅内网员工访问，防火墙阻止外部Host头注入
```
**审计要点：**
- 检查应用是否有WAF/网关进行Host头验证（如Nginx反向代理有`server_name`限制）
- 检查是否有Load Balancer进行Host头清洁
- **误报排除条件：** 所有网络入口都有Host头白名单验证 + 仅支持内网访问
- **真实案例：** 即使内网，如果存在SSRF漏洞，攻击者仍可利用Host头注入

### 常见误报与快速判断

| 情景 | 代码模式 | 是否为真实漏洞 | 判断理由 |
|------|---------|-------------|--------|
| 显示用户提交的URL | `echo "You came from {$_SERVER['HTTP_HOST']}"` | ✓ XSS | 这是XSS而非Host注入，分开评估 |
| 日志记录Host | `syslog(LOG_INFO, "Access from {$_SERVER['HTTP_HOST']}")` | ✗ 否 | 仅影响日志可读性，无业务安全风险 |
| 健康检查重定向 | `if($health=='ok') redirect("https://{$_SERVER['HTTP_HOST']}/status")` | ✓ 是 | 虽非认证路径，但仍是开放重定向 |
| 反向代理后端 | Nginx配置`$http_host`进行路由 | ✗ 否 | 由Nginx安全机制处理，不是应用漏洞 |
| 框架自动URL生成 | Laravel `url()`, Symfony `generateUrl()` | ✗ 否 | 框架已包含Host白名单验证 |

### 审计时的快速决策树

```
发现 HTTP_HOST 使用
├─ 是否用于邮件链接外发？
│  └─ 是 → 🔴 HIGH：邮件钓鱼漏洞
├─ 是否用于OAuth redirect_uri？
│  └─ 是 → 🔴 CRITICAL：账户接管漏洞
├─ 是否用于Header重定向（Location/Refresh）？
│  ├─ 有白名单验证 → ✓ 安全，记录为False Positive
│  ├─ 无验证+HTTPS SNI → 🟡 MEDIUM：降级风险
│  └─ 无验证+HTTP → 🔴 HIGH：开放重定向
├─ 是否用于缓存键？
│  ├─ 有Vary: Host头 → ✓ 安全
│  └─ 无Vary头 → 🔴 HIGH：缓存中毒
└─ 其他场景 → 评估具体上下文
```

### 实战审计技巧

1. **追踪数据流而非关键词**：不仅搜索`HTTP_HOST`，还要追踪赋值给哪些变量，这些变量最终如何使用
   ```php
   $host = $_SERVER['HTTP_HOST'];        // 第1行：来源
   $host = strtolower($host);            // 第2行：处理
   $url = "https://$host/api";           // 第3行：使用
   ```

2. **检查白名单的实现质量**：
   ```php
   // ✓ 好的白名单
   $allowed = ['example.com', 'www.example.com'];
   if (!in_array($_SERVER['HTTP_HOST'], $allowed, true)) {...}

   // ✗ 坏的白名单（容易绕过）
   if (strpos($_SERVER['HTTP_HOST'], 'example.com') !== false) {...}  // example.com.attacker.com会通过！
   ```

3. **关注框架版本和安全更新**：Laravel/Symfony在特定版本后加入了Host验证，需要知道应用版本

4. **模拟攻击测试**：在实际审计时，使用Burp Suite修改Host头并追踪是否成功重定向到恶意域名

---

## 实现建议

### 核心防护方案

**方案1：白名单验证**
```php
<?php
define('ALLOWED_HOSTS', ['example.com', 'www.example.com']);

function get_safe_host() {
    $host = $_SERVER['HTTP_HOST'] ?? '';
    $host = strtolower(preg_replace('/:\d+$/', '', $host));  // 移除端口

    if (in_array($host, ALLOWED_HOSTS)) {
        return $host;
    }
    return ALLOWED_HOSTS[0];  // 默认值
}
?>
```

**方案2：使用配置文件**
```php
<?php
// config.php
define('SITE_URL', 'https://example.com');

// 使用
$reset_link = SITE_URL . "/reset?token=$token";
header("Location: " . SITE_URL . "/dashboard");
?>
```

**方案3：框架安全实践**
```php
<?php
// Laravel
$url = config('app.url') . '/dashboard';
return redirect()->to($url);

// Symfony
$url = $this->generateUrl('dashboard', [], UrlGeneratorInterface::ABSOLUTE_URL);
?>
```

### 检查清单
- [ ] 所有使用HTTP_HOST的地方添加白名单验证
- [ ] 密码重置链接使用配置文件中的固定域名
- [ ] OAuth回调地址使用预注册的白名单URL
- [ ] 重定向URL验证同源或白名单域名
- [ ] 测试Host头注入：`Host: evil.com`

---

## 修复优先级

1. **立即修复**：密码重置/OAuth回调使用未验证的Host头
2. **本周修复**：所有重定向添加Host白名单验证
3. **可选加强**：使用配置文件替代动态Host获取
4. **长期优化**：使用框架安全URL生成方法
