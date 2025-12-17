# PHP OAuth Redirect URI 验证不足

## Details

**漏洞成因**：OAuth 2.0 标准要求严格验证 `redirect_uri` 参数，防止授权码被重定向到攻击者控制的域名。PHP 应用在回调处理中常见的验证不足包括：

1. **不完整的字符串匹配**
   - 对应代码示例：
   ```php
   // 易受攻击的做法
   if (strpos($_GET['redirect_uri'], 'example.com') !== false) {
       // 允许重定向
   }
   // 问题：attacker.com.example.com 会通过验证
   ```
   - 快速定位核心操作的技巧 **[L1: 关键词扫描]**
     - 搜索 `strpos()`, `str_contains()`, `preg_match()` 处理 redirect_uri
     - 关键词：`redirect`, `callback`, `return_url`, `next_url`, `back_url`
     - 检查是否直接使用用户输入的 URI

   - 快速定位保护机制的技巧 **[L2: 跳读]**
     - 查找 `parse_url()` 是否用于域名提取
     - 检查白名单数组是否存在且包含 redirect_uri
     - 寻找 `===` 精确比较或 `in_array(..., true)` 的使用

2. **URL 解析边界情况**
   - 对应代码示例：
   ```php
   // 易受攻击的做法
   $allowed = ['https://example.com/callback'];
   if (in_array($_GET['redirect_uri'], $allowed)) {
       redirect($_GET['redirect_uri']);
   }
   // 问题：scheme 为 http:// 或 https:// 差异、末尾 / 等边界情况
   ```
   - 快速定位核心操作的技巧 **[L1: 关键词扫描]**
     - 搜索 `filter_var(..., FILTER_VALIDATE_URL)`
     - 关键词：`parse_url()`, `header('Location')`, `wp_safe_remote_*`
     - 检查是否有协议校验（http vs https）

   - 快速定位保护机制的技巧 **[L3: 逐行读]**
     - 验证 `parse_url()` 返回的 `host` 与白名单的比较方式
     - 检查路径规范化（移除 `..`, `///` 等）
     - 验证 URL 编码字符（`%2f`, `%3a` 等）的处理

3. **协议混淆和伪协议**
   - 对应代码示例：
   ```php
   // 易受攻击的做法
   $redirect_uri = $_GET['redirect_uri'];
   if (filter_var($redirect_uri, FILTER_VALIDATE_URL)) {
       redirect($redirect_uri);
   }
   // 问题：javascript:, data:, 恶意协议未过滤
   ```
   - 快速定位核心操作的技巧 **[L1: 关键词扫描]**
     - 关键词：`javascript:`, `data:`, `file:`, `vbscript:`
     - 搜索重定向函数：`header()`, `exit()`, `die()` 在 redirect_uri 使用前后
     - 查找 URL 构造：直接拼接 URI 到响应头

   - 快速定位保护机制的技巧 **[L2: 跳读]**
     - 检查白名单是否包含协议校验：`in_array($parsed['scheme'], ['http', 'https'])`
     - 寻找黑名单过滤：`preg_match('/^(javascript|data|file):/i', $uri)`
     - 验证 `is_absolute_url()` 或类似函数的实现

4. **跨域资源污染**
   - 对应代码示例：
   ```php
   // 易受攻击的做法
   $uri = $_REQUEST['redirect_uri'] ?? $_REQUEST['callback_url'];
   return redirect($uri);
   // 问题：多个参数来源，保护机制可能只检查其中之一
   ```
   - 快速定位核心操作的技巧 **[L1: 关键词扫描]**
     - 关键词：`$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE` 处理 redirect_uri
     - 搜索 OAuth callback 方法：`handleCallback`, `authCallback`, `oauthReturn`
     - 检查多个参数别名：`next`, `return_to`, `success_url`, `failure_url`

   - 快速定位保护机制的技巧 **[L2: 跳读]**
     - 追踪所有输入参数的来源
     - 验证是否对所有可能的参数别名都进行了验证
     - 检查 OAuth 库的配置（Laravel Socialite, etc.）中的允许 URL 列表

---

## Classify

**漏洞 vs 误报 vs 代码异味的研判**：

**确认为漏洞**：
- 白名单存在但不规范（字符串包含而非精确域名匹配）
- 协议验证缺失或不完全（`filter_var(FILTER_VALIDATE_URL)` 不足以过滤伪协议）
- 直接使用用户提供的 redirect_uri 而无任何验证
- 多个参数别名但只验证其中一个

**可能为误报**：
- 使用框架提供的 OAuth 流程（如 Laravel Socialite）且白名单已在框架配置中正确定义
- redirect_uri 来自可信的配置文件或数据库记录，而非直接用户输入
- 重定向前有其他验证层（如 CSRF token 校验确保请求合法性）
- 仅用于内部跳转的 redirect_uri（如 `$config['allowed_redirects']`）

**代码异味**：
- 存在 redirect_uri 处理但验证逻辑离散或复杂，难以追踪完整性
- 多个重定向点都处理同一参数，验证不一致
- 使用了弃用的验证函数或不安全的正则表达式

---

## Low risk

**应给予低风险评级的情况**：

1. **受信任的服务间重定向**
   - redirect_uri 来自自身授权数据库表（如 `oauth_clients.redirect_uris`），而非直接用户输入
   - 数据表中的 URI 由管理员审核后存储

2. **二级保护机制充分**
   - OAuth 授权码使用了强绑定（code 与特定 client_id 绑定，不可转移）
   - redirect_uri 校验失败时直接拒绝，而非默认重定向或记录日志后继续

3. **内部应用间跳转**
   - redirect_uri 用于应用内部模块间导航（如从登录页重定向到首页），未涉及外部域名
   - 白名单完整包含所有合法的内部路径

4. **协议和主机双重锁定**
   - 同时验证了协议类型（仅允许 `https`）和完整域名（精确匹配）
   - 使用了规范化的 URL 比较（如 lowercase 处理）

5. **框架内置保护**
   - 使用了知名安全框架的 OAuth 组件，该组件已通过安全审计
   - 框架版本在维护周期内且无已知漏洞
