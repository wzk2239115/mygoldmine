# PHP Laravel redirect() 未验证重定向

**PHP** Laravel 框架的 `redirect()` 辅助函数直接使用用户可控参数作为重定向目标，未实施白名单验证，允许跳转到恶意域名。

## Details

**核心漏洞成因**：
Laravel 应用在处理重定向时，将用户提供的 URL 参数直接传入 `redirect()` 或 `redirect()->to()` 方法，框架默认不进行域名白名单检验，导致攻击者可控制目标 URL，实现开放重定向。

**危险代码示例**：
```php
// 快速定位核心操作（L1:关键词扫描）：搜索 redirect()、redirect()->to()、->away()

// 登录成功后的重定向
Route::post('/login', function (Request $request) {
    if (Auth::attempt(['email' => $email, 'password' => $password])) {
        $next = $request->input('next');
        return redirect($next);  // 直接使用用户输入
    }
});

// 邮件验证链接
Route::get('/verify-email', function (Request $request) {
    $email = $request->input('email');
    // ... 验证逻辑
    return redirect($request->input('redirect_url'));  // 直接拼接用户参数
});

// 其他危险模式
redirect()->to($_GET['url']);              // ->to() 方法
redirect($request->get('return_url'));     // 双向参数
redirect()->away($_POST['redirect_to']);   // ->away() 绝对 URL
return redirect($redirectUrl);              // 辅助函数直接调用
```

**快速定位保护机制（L2:跳读）**：
- 检查是否存在 `parse_url()` 对重定向 URL 的域名提取
- 查找 `$_SERVER['HTTP_HOST']`、`request()->getHost()` 或 `config('app.url')` 的比较逻辑
- 搜索 `whitelist`、`allowed_redirects`、`safe_redirects` 等配置
- 检查是否使用了 `Url::isValidUrl()`、`filter_var($url, FILTER_VALIDATE_URL)` 等验证函数
- 查找 `preg_match()`、`str_starts_with('/')` 或 `parse_url($url, PHP_URL_SCHEME) === null` 的验证逻辑（L3:逐行读）
- 追踪重定向参数从 request 输入到 redirect() 调用的完整流程，检查是否存在漏洞的参数过滤或白名单检验（L4:跨模块追踪）

## Classify

**确认为漏洞的条件**：
1. 用户可控制的参数（GET/POST 的 `next`、`return_url`、`redirect_to`、`redirect_url`、`url` 等）直接用于 `redirect()`、`redirect()->to()` 或 `redirect()->away()`
2. 未对目标 URL 进行任何验证，或仅进行弱验证（如检查 URL 是否以 `/` 开头而实际允许 `//attacker.com`）
3. 可以重定向到任意外部域名（跨域重定向）
4. 通过 PoC 验证：登录成功后访问 `?next=https://attacker.com`，观察浏览器是否执行重定向

**判定为误报的条件**：
- URL 参数来自内部逻辑或数据库查询，非用户直接可控（如从已验证的 referrer 数据库表查询）
- 存在严格的域名白名单检验：`$allowedHosts = config('app.safe_redirects', []); if (!in_array(parse_url($url, PHP_URL_HOST), $allowedHosts)) { throw new ...; }`
- 使用了 Laravel 框架内置的安全重定向函数（如 `redirect()->intended()` 配合 session 存储的预期 URL，且 session 来自内部逻辑）
- 重定向仅限于相对路径或同域 URL：`if (!parse_url($url, PHP_URL_SCHEME) || parse_url($url, PHP_URL_HOST) === request()->getHost()) { ... }`

**识别代码异味（可能但不确定）**：
- 存在 URL 验证但不够严格（如仅检查不以 `http://` 开头，但未处理 `//` 或 `javascript:`）
- 使用了 URL 编码/解码函数（`urldecode()`、`base64_decode()`）后再重定向，可能导致绕过
- 存在多个重定向路由或中间件，某个环节可能遗漏验证
- 使用了正则表达式验证但逻辑不够严密，如 `/^https?:\/\//` 未处理协议相对 URL `//attacker.com`

## Low risk

以下场景可降低风险评级：

1. **相对路径重定向**：仅允许以 `/` 开头的相对 URL，且在跳转前验证路径不包含 `://` 或 `//`
   ```php
   $redirectUrl = $request->input('next', '/dashboard');
   if (!str_starts_with($redirectUrl, '/') || str_contains($redirectUrl, '://')) {
       throw new Exception('Invalid redirect URL');
   }
   return redirect($redirectUrl);
   ```

2. **明确的白名单检验**：维护包含所有允许重定向域名的配置白名单，每次跳转前验证
   ```php
   $allowedDomains = config('app.safe_redirect_domains', []);
   $url = $request->input('next');
   $host = parse_url($url, PHP_URL_HOST);
   if (!in_array($host, $allowedDomains)) {
       return redirect('/dashboard');
   }
   return redirect($url);
   ```

3. **来自可信来源**：参数从内部逻辑生成（如用户历史访问记录存储在 session 中），而非直接来自 GET/POST 参数

4. **协议与域名限制**：同时验证协议仅为 `https://` 且目标域名属于应用本身
   ```php
   $url = $request->input('return_url', '/');
   $parsed = parse_url($url);
   $appHost = parse_url(config('app.url'), PHP_URL_HOST);
   if ($parsed['scheme'] !== 'https' || $parsed['host'] !== $appHost) {
       return redirect('/');
   }
   return redirect($url);
   ```

5. **使用框架级防护**：依赖 Laravel 经过审计的安全重定向方法，如 `redirect()->intended()` 和 session 协作实现，且 session 数据由框架可信认证体系填充

6. **使用 Middleware 统一拦截**：创建专门的中间件对所有重定向请求进行域名白名单验证，确保无遗漏
   ```php
   // 在 app/Http/Middleware/ValidateRedirectUrl.php
   public function handle(Request $request, Closure $next) {
       $redirectUrl = $request->input('next') ?? $request->input('return_url');
       if ($redirectUrl) {
           $host = parse_url($redirectUrl, PHP_URL_HOST);
           if (!in_array($host, config('app.safe_redirects', []))) {
               abort(403, 'Invalid redirect target');
           }
       }
       return $next($request);
   }
   ```
