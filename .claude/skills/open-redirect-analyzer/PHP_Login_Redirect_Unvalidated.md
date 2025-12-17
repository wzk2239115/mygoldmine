# PHP 登录后未验证重定向

**PHP** 登录后通过 return_url、redirect_to、next 等参数重定向，未校验目标地址，允许跳转到恶意域名。

## Details

**核心漏洞成因**：
登录成功后，应用直接将用户提供的 URL 参数传入重定向函数（`header("Location: ...")`、`redirect()`），未对其进行任何验证，导致攻击者可控制目标 URL。

**危险代码示例**：
```php
// 快速定位核心操作（L1:关键词扫描）：搜索 header("Location:") 或 redirect()
if (authenticate($username, $password)) {
    $returnUrl = $_GET['return_url'] ?? '/dashboard';
    header("Location: " . $returnUrl);  // 直接拼接用户输入
    exit;
}

// 其他危险函数
redirect($_POST['next']);              // 框架重定向函数
header("Location: " . $url);           // 原生PHP
setcookie('...', ...); header("Location: {$_GET['url']}");
```

**快速定位保护机制（L2:跳读）**：
- 检查是否存在 `parse_url()` 对 URL 的域名验证
- 查找 `$_SERVER['HTTP_HOST']` 或 `getHost()` 的比较逻辑
- 搜索 `whitelist`、`allowed_hosts`、`allowed_redirect_hosts` 配置
- 查找 `preg_match()` 或 `str_starts_with()` 的白名单检验
- 检查是否使用了如 `filter_var($url, FILTER_VALIDATE_URL)` 的 URL 验证函数

## Classify

**确认为漏洞的条件**：
1. 用户可控制的参数（GET/POST 中的 `return_url`、`redirect_to`、`next`、`url` 等）直接用于 `header("Location: ...")` 或框架重定向函数
2. 未对目标 URL 进行任何验证，或仅进行弱验证（如检查 URL 是否以 `/` 开头而实际允许 `//attacker.com`）
3. 可以重定向到任意外部域名（跨域重定向）
4. 通过 PoC 验证：登录成功后访问 `?return_url=https://attacker.com`，观察浏览器是否执行重定向

**判定为误报的条件**：
- URL 参数来自内部逻辑生成（如数据库查询结果），非用户直接可控
- 存在严格的域名白名单检验：`$allowedHosts = ['example.com', 'app.example.com']; if (!in_array(parse_url($url, PHP_URL_HOST), $allowedHosts)) { ... }`
- 使用了框架内置的安全重定向函数（如 Laravel 的 `redirect()->intended()` 配合 session 存储）
- 重定向仅限于相对路径或同域 URL：`if (parse_url($url, PHP_URL_SCHEME) !== null) { reject; }`

**识别代码异味（可能但不确定）**：
- 存在 URL 验证但不够严格（如仅检查不以 `http://` 开头，但未处理 `//` 或 `javascript:`）
- 使用了 URL 编码/解码函数后再重定向，可能导致绕过
- 存在多层重定向逻辑，某个环节可能遗漏验证

## Low risk

以下场景可降低风险评级：

1. **相对路径重定向**：仅允许以 `/` 开头的相对 URL，且在跳转前验证路径不包含特殊字符
2. **明确的白名单检验**：维护包含所有允许重定向域名的严格白名单，每次跳转前逐一对比
3. **来自可信来源**：参数从内部逻辑生成（如用户历史访问记录存储在 session 中），而非 GET/POST 参数
4. **协议限制**：仅允许 `https://` 协议，拒绝 `http://`、`javascript:`、`data:` 等协议
5. **域名验证**：验证目标 URL 的主机名必须属于应用的合法域名，如：
   ```php
   $url = $_GET['return_url'];
   $parsed = parse_url($url);
   $allowedDomains = ['example.com', 'app.example.com'];
   if (empty($parsed['host']) || !in_array($parsed['host'], $allowedDomains)) {
       header("Location: /dashboard");
       exit;
   }
   header("Location: " . $url);
   ```
6. **框架级防护**：使用经过审计的开源框架级重定向函数，这些函数已内置防护逻辑
