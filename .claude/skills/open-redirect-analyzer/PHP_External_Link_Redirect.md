# PHP 外部链接跳转

**漏洞类型**: 应用未验证重定向目标域名，用户可控的 URL 参数被用于 HTTP 重定向（`Location` 头），导致用户被引导至恶意网站

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// header() 直接跳转 - 最常见
$redirect_url = $_GET['redirect'];
header("Location: " . $redirect_url);
exit;

// POST 参数跳转
$next_page = $_POST['next'];
header('Location: ' . $next_page);

// 请求参数拼接跳转
$url = isset($_REQUEST['url']) ? $_REQUEST['url'] : '/';
header("Location: $url");
exit();

// 使用 http_response_code() 的跳转
$target = $_GET['target'];
header("Location: " . $target);
http_response_code(302);

// 框架级重定向 - Laravel 示例
redirect($request->get('redirect_to'));

// Symfony 示例
return new RedirectResponse($_GET['url']);

// 自定义跳转函数封装
function redirect($url) {
    header('Location: ' . $url);
    exit;
}
$to = $_GET['goto'];
redirect($to);

// 重定向状态码变种
$page = $_GET['page'];
header("Location: " . $page, true, 301);  // 301 永久重定向

// 在 Location 头中使用变量插值
header('Location: /redirect?target=' . $_GET['ref']);

// 使用 header() 变种：addHeader
header('Location: '. $_REQUEST['url']);
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 重定向函数: `header("Location:`, `header('Location`, `http_response_code()`, `redirect()`, `RedirectResponse`
- 跳转参数来源: `$_GET['redirect']`, `$_GET['url']`, `$_GET['target']`, `$_POST['next']`, `$_REQUEST['ref']`, `$params['goto']`
- 参数名关键词: `redirect`, `url`, `target`, `next`, `goto`, `return`, `back`, `ref`, `referrer`, `page`, `link`
- 框架函数: `redirect()`, `RedirectResponse`, `return redirect()`, `Redirect::to()`

**L2 跳读定位**:
- 从路由处理器或控制器方法入口扫描参数获取
- 追踪参数从 `$_GET/$_POST/$_REQUEST` 到 `header()` 调用的完整数据流
- 重点关注: 参数是否直接用于 `Location` 头、是否存在字符串拼接或变量插值
- 检查参数在传递给重定向函数前是否经过任何验证或转换
- 留意隐式跳转: 通过状态码（301/302/307）或 `Location` 头进行的所有重定向

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- URL 解析验证: 调用 `parse_url()` 检查 `host` 或 `scheme` 组件
- 协议限制: 正则 `/^https?:\/\//i`, `in_array($scheme, ['http','https'])`
- 相对路径验证: `strpos($url, '/') === 0` 或 `strpos($url, 'http') === false`
- 域名白名单: `in_array($host, $allowedDomains)`, `preg_match('/\.(example\.com|trusted\.com)$/', $host)`
- 前缀验证: `preg_match('/^\//', $url)` 限制为仅相对路径

**L3 逐行分析**:
- URL 解析实现完整性:
  - `parse_url()` 后是否同时检查 `scheme` 和 `host`
  - 是否考虑协议省略形式 (`//example.com`) 的绕过
  - 是否处理无效或缺失的 URL 组件
- 相对路径绕过风险:
  - 简单的 `strpos($url, 'http') === false` 可被 `HTTP://` (大小写) 绕过
  - 简单的 `startsWith($url, '/')` 可被 `//attacker.com` (协议相对 URL) 绕过
  - 需检查是否仅禁止 `http://` 而未禁止 `https://`, `ftp://`, `javascript:` 等
- 白名单绕过风险:
  - `strpos($host, 'example.com') !== false` 可被 `example.com.attacker.com` 绕过
  - `substr()` 截断验证可能遗漏多层子域名
  - 需验证是否使用严格的后缀匹配或完全相等比对
- 编码绕过风险:
  - 是否过滤了 URL 编码形式 (`%2F` 代表 `/`)
  - 是否处理了 Unicode 或 Punycode 编码的域名

**L4 跨模块追踪**:
- 追踪参数在中间件或工具类中的处理完整实现
- 检查框架级的全局输入过滤器是否处理跳转 URL
- 验证是否存在二次处理: URL 未经验证被多个地方使用
- 检查 cookie 或 session 中是否存储了未验证的重定向 URL（作为持久化参数）
- 审查日志记录是否包含跳转目标，便于事后溯源

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 重定向 URL 完全由用户可控，无任何域名或协议限制
- 可通过构造任意域名 URL 进行跳转 (如 `http://attacker.com`)
- 协议未限制，允许 `javascript:`, `data:`, `ftp://` 等危险协议
- 可使用协议相对 URL (`//attacker.com`) 进行跳转
- 保护机制存在绕过缺陷:
  - 仅检查字符串前缀而不解析 URL 结构
  - 白名单验证不严谨 (如子域名、编码绕过、进制转换)
  - 使用黑名单而非白名单 (如仅禁止 `http://` 但允许 `HTTP://` 或 `//`)

**误报判定**:
- 重定向 URL 来自硬编码配置或后台管理员设置的白名单，非普通用户输入
- 用户仅可控路径部分，域名完全硬编码 (如 `https://example.com/{$userPath}`)
- 使用严格的白名单验证:
  - `parse_url()` 后同时验证 `scheme` (仅 `http`/`https`) 和 `host`
  - `in_array($host, $allowedDomains, true)` 完全匹配
  - 相对路径用 `/^\/[^\/]` 严格匹配，排除协议相对 URL
- 重定向目标完全来自内部系统生成 (如数据库存储的白名单 URL)

**代码异味**:
- 仅有协议限制但无域名验证 (允许任意域名的 http/https URL)
- 仅检查相对路径但未防护协议相对 URL (`//attacker.com` 形式)
- 使用黑名单而非白名单 (如仅禁止 `http://`, `https://` 但允许其他协议)
- 白名单验证使用模糊匹配 (`strpos()`, `preg_match('/example.com/')`) 易被子域名或后缀绕过
- URL 参数被存储在 session/cookie 中再次使用，产生二次传播风险
- 重定向 URL 来自用户上传的文件或外部数据源，未经验证

---

## Low risk

### 低风险场景

**权限与访问控制受限**:
- 重定向功能仅限认证用户、特定角色或管理员访问
- 需强认证方式 (MFA、OAuth) 且有完整的审计日志
- 功能部署在内网环境，非面向公网

**业务场景限制**:
- 重定向仅用于内部系统导航，目标 URL 来自可信的内部资源
- 重定向参数由系统根据用户身份生成，非用户直接输入
- 用户可控参数仅为 ID、参数名等，实际 URL 由后端配置查表生成

**缓解措施与防护**:
- 有基础的相对路径验证 (仅允许 `/` 开头) 且场景中无需跨域跳转
- 使用白名单但覆盖场景内的所有合法目标 (如内部系统列表)
- 存在 referer 验证或 CSRF token 检查，增加攻击成本
- 有请求速率限制和异常检测，可及时发现滥用

**部分缓解措施**:
- 有协议限制 (仅 `http`/`https`) 且用户无法直接控制域名 IP 地址
- 重定向前有中间确认页面 (如跳转提示)，用户需显式点击确认
- 目标 URL 被记录在审计日志中，便于事后溯源和责任认定
- 使用短链接或令牌代替 URL 直接存储，增加攻击复杂度

**业务风险低**:
- 关键操作（转账、密码修改、权限变更）不依赖重定向进行
- 应用仅涉及非敏感信息或测试数据，用户损失有限
