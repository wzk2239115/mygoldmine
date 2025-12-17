# Java SSO 单点登录重定向目标未验证

## Details

### 核心代码示例

```java
// 漏洞模式：直接将请求参数用于重定向
@GetMapping("/sso/callback")
public String handleSSOCallback(@RequestParam("redirect_uri") String redirectUri) {
    return "redirect:" + redirectUri;  // 直接使用参数进行重定向
}

// 漏洞模式：通过 response.sendRedirect() 直接传递参数
@GetMapping("/oauth/authorize")
public void authorize(@RequestParam("return_url") String returnUrl, HttpServletResponse response) throws IOException {
    response.sendRedirect(returnUrl);  // 未经验证的重定向
}

// 漏洞模式：从 session 或数据库恢复后直接使用
@GetMapping("/login/callback")
public String processCallback(HttpSession session) {
    String callbackUrl = (String) session.getAttribute("sso_callback_url");
    return "redirect:" + callbackUrl;  // 若数据源本身被污染则存在漏洞
}

// 漏洞模式：使用 RestTemplate 执行重定向相关逻辑
@GetMapping("/saml/acs")
public ModelAndView handleSAMLResponse(@RequestParam("RelayState") String relayState) {
    // RelayState 通常由 SAML IdP 返回，若未验证可能导致开放重定向
    return new ModelAndView("redirect:" + relayState);
}
```

### 快速定位到核心操作的技巧（L1:关键词扫描）

- 搜索重定向相关的关键字：`redirect:`, `sendRedirect()`, `forward:`, `addHeader("Location", ...)`
- 搜索参数名称模式：`redirect_uri`, `return_url`, `callback_url`, `return_to`, `next`, `target`, `back`, `url`, `referer`, `redirect`, `goto`
- 搜索 SSO/OAuth 相关的处理方法：`@GetMapping/@PostMapping` 中包含 `/callback`, `/authorize`, `/login`, `/oauth`, `/saml`, `/sso` 路径
- 在 Spring 中搜索这些 API 调用：`response.sendRedirect()`, `model.addAttribute("redirect")`, `RedirectView`, `"redirect:"` 视图名称前缀
- 搜索可能污染重定向目标的写入点：`session.setAttribute()`, `cache.put()`, `database.save()`

### 快速定位到保护机制的技巧（L2:跳读）

- 检查重定向前是否存在白名单验证：`allowedDomains.contains()`, `URI_WHITELIST`, `ConfigurableRedirectUriValidator`
- 寻找 URL 解析和主机验证逻辑：`new URL(url).getHost()`, `URI.create(url).getHost()`, `equals()` 字符串比较
- 检查是否使用 Spring Security 内置的重定向验证：`SimpleRedirectInvalidSessionStrategy`, `DefaultRedirectResolver`
- 查找自定义验证函数：`isValidRedirectUrl()`, `isWhitelistedDomain()`, `validateRedirectUri()` 等方法
- 检查是否实现了协议白名单（仅允许 `https://` 或 `http://`），是否排除了 `javascript:`, `data:`, `//` 等危险前缀
- 审查 URL 规范化处理：`UriComponentsBuilder.fromHttpUrl()`, `URLDecoder.decode()`, `java.net.URL` 规范化

---

## Classify

### 漏洞 vs 误报 vs 代码异味的研判标准

**确认为真实漏洞的条件：**

1. **重定向目标完全由用户控制**
   - 参数直接来自 HTTP 请求（`@RequestParam`, `@RequestBody` 等）
   - 未经过任何白名单验证、格式检查或规范化处理
   - 能够导致用户被重定向到任意第三方域名

2. **在 SSO/OAuth 上下文中的严重性**
   - SSO 回调 URL 未验证可导致身份验证流程被劫持
   - 攻击者可通过精心构造的链接窃取身份验证令牌（code, token）
   - 可能绕过 CSRF 保护（某些框架中）

3. **数据流追踪确认**
   - 从源点（用户输入）到汇点（重定向操作）的完整链路
   - 确认中间不存在有效的清洁函数或验证步骤

**判定为误报的条件：**

1. **存在有效的白名单验证**
   - 在重定向前进行了严格的域名白名单检查
   - 使用了 Spring Security 等框架的官方验证机制
   - 白名单验证不存在绕过点（如大小写敏感、协议混淆等）

2. **重定向目标来自可信源**
   - 从数据库/缓存读取但该数据已在系统管理员控制下
   - 来自配置文件等受保护的资源
   - 来自已验证的上游系统（如 SAML IdP 的签名响应）

3. **重定向操作不可到达**
   - 该代码路径在实际应用中永不执行
   - 相应的 endpoint 受限于特殊的身份验证或授权控制

**代码异味的特征：**

- 重定向逻辑存在但通过某种隐蔽的编码/加密机制保护（审计时仍需深入验证其有效性）
- 参数传递存在但被某种不规范的过滤器处理（模糊的安全假设）
- 重定向操作被注释掉或条件编译禁用（未来可能启用的风险）

---

## Low risk

### 应给予低风险评级的情况

1. **协议受限的重定向**
   - 只允许相对路径重定向（如 `redirect:/dashboard` 而不是 `redirect:https://evil.com`）
   - 通过在代码逻辑中强制使用相对路径前缀实现，检查参数不包含 `://`, `//`, `http`, `https` 等协议标记
   - 即使被重定向，用户仍停留在当前应用域名内

2. **全局域名白名单已严格配置**
   - 应用维护了中心化的域名白名单配置（如 `application.yml` 中的 `allowed-domains`）
   - 所有涉及重定向的 endpoint 都强制使用此配置进行验证
   - 白名单验证代码经过充分的单元测试和集成测试验证

3. **用户可控制性有限的场景**
   - 虽然参数可由用户提供，但仅限于特定预定义选项的选择（如下拉列表值）
   - 参数经过严格的枚举类型转换或映射表查询
   - 即使参数被篡改，也只会映射到安全的预定义值

4. **只用于内部管理员操作**
   - 该 endpoint 受到 IP 白名单、VPN、或强身份验证保护
   - 只有具备特殊权限的管理员才能访问
   - 部署在内网环境中，不面向互联网用户

5. **重定向延迟处理且存在用户确认**
   - 系统不是自动重定向，而是显示一个中间页面（如 "Redirecting to XXX..."）
   - 用户需要点击确认才能执行重定向（虽然不能完全防止，但大幅降低利用风险）
   - 显示的目标 URL 清晰可见，用户可识别可疑重定向

6. **重定向目标经过规范化和验证**
   - 使用 `java.net.URL` 或 `org.springframework.web.util.UriComponentsBuilder` 进行规范化
   - 验证解析后的主机名和协议符合白名单
   - 防止了 URL 编码、双重编码、协议混淆等绕过技术

7. **OAuth/SAML 标准框架实现**
   - 使用了 Spring Security OAuth2 或 Spring Security SAML 等官方认可的框架
   - 框架版本为最新维护版本，已修复已知的重定向漏洞
   - `RedirectUriValidator` 或类似机制已正确配置
