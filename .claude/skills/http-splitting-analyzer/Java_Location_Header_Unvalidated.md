# Java Location 头重定向未验证

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `response.sendRedirect(url)` - Servlet 重定向
- `response.setHeader("Location", url)` 直接设置
- `response.setStatus(301/302) + setHeader("Location", url)`
- Spring `RedirectView`、`RedirectAttributes`
- `HttpServletResponse.sendRedirect()`

**快速定位核心操作：**
1. 搜索关键字：`sendRedirect`、`Location`、`setStatus(3`
2. 追踪 URL 来源：`getParameter()`、`getHeader()`、路径参数
3. 检查是否存在 URL 验证或白名单
4. 追踪完整的重定向链路

**快速定位保护机制：**
- URL 白名单：`if (url.startsWith(TRUSTED_DOMAIN)) sendRedirect(url)`
- 域名验证：`URL.getHost()` 检查
- Scheme 限制：仅允许 `http://` 和 `https://`
- 相对 URL：仅允许以 `/` 开头的相对路径

**代码示例：**
```java
// 危险：用户输入直接重定向
@GetMapping("/redirect")
public void redirect(HttpServletResponse response,
                     @RequestParam String url) throws IOException {
    response.sendRedirect(url);  // 危险：无验证
}

// 危险：setHeader 设置 Location
@GetMapping("/jump")
public void jump(HttpServletResponse response,
                 @RequestParam String target) {
    response.setHeader("Location", target);  // 危险
    response.setStatus(302);
}

// 危险：Spring
@GetMapping("/go")
public String redirect(@RequestParam String next) {
    return "redirect:" + next;  // 危险
}
```

## Classify

**漏洞（High）：**
- 用户输入直接用于重定向 URL
- 无域名或 URL 格式验证
- 允许任意协议跳转
- 开放重定向漏洞

**误报：**
- 重定向目标硬编码
- 使用框架内置方法且有验证
- 仅允许相对 URL

**代码异味（Medium）：**
- 仅检查前缀但未验证域名
- 黑名单过滤容易绕过
- 检查不完整

## Low risk

**以下情况评为低风险：**
- 使用框架方法生成 URL
- 严格白名单验证
- 仅允许相对 URL + 正则验证
- 输入由管理员配置

## 审计专业技巧

### 真实漏洞的特征

**1. 输入源头追踪（最关键）**
- 来自 `@RequestParam`、`@PathVariable`、`request.getParameter()`
- 来自 HTTP 头部：`X-Forwarded-For`、自定义跳转头
- 来自请求体（JSON/XML）中的 URL 字段
- **注意**：同一变量可能在多个地方使用，追踪其他用途时可能发现其他漏洞

**真实案例分析：**
```java
// 真实漏洞：callback 参数来自用户输入
@GetMapping("/oauth/callback")
public void oauthCallback(HttpServletResponse response,
                         @RequestParam String callback) throws IOException {
    // 执行OAuth验证逻辑...
    response.sendRedirect(callback);  // 直接重定向到用户指定URL
}
// 攻击：/oauth/callback?callback=https://attacker.com/steal
```

**2. 验证机制的完整性检查**
- 仅检查 `startsWith()` 但不检查协议：`if (url.startsWith("https"))`
  - 绕过：`https.evil.com`、`httpsss://evil.com`
- 只验证域名但允许路径：`if (url.contains("mysite.com"))`
  - 绕过：`evil.com/mysite.com`
- 使用黑名单而非白名单
  - 绕过：新增恶意域名、使用 IP 地址、URL 编码等

**常见不完整验证：**
```java
// 误区1：仅检查前缀，未验证完整域名
if (url.startsWith("https://example.com")) {
    response.sendRedirect(url);  // 错误：https://example.com.evil.com
}

// 误区2：使用 contains 检查
if (url.contains("example.com")) {
    response.sendRedirect(url);  // 错误：https://evil.com?domain=example.com
}

// 正确做法：使用 URL 对象验证
try {
    URL u = new URL(url);
    if ("example.com".equals(u.getHost())) {
        response.sendRedirect(url);
    }
} catch (MalformedURLException e) {
    // 拒绝无效URL
}
```

**3. 协议绕过检测**
- `javascript://` - 可执行 JavaScript
- `data:text/html,<script>alert('XSS')</script>` - 数据 URL
- 双协议：`//evil.com` - 相对于当前协议
- `//` 开头在某些浏览器环境下会使用当前协议

**4. 编码和格式绕过**
- URL 编码：`%2F` 代替 `/`、`%3A` 代替 `:`
- Unicode 编码：`%u002F` 等
- 8进制编码：`\057` 代替 `/`
- 大小写变异：`HTTps://`、`jAvAsCrIpT://`

### 误报的真实案例

**1. 硬编码重定向（100% 安全）**
```java
@GetMapping("/go-home")
public String goHome() {
    return "redirect:/dashboard";  // 完全硬编码，无风险
}

@GetMapping("/legacy-redirect")
public void legacy(HttpServletResponse response) throws IOException {
    response.sendRedirect("https://docs.example.com");  // 硬编码URL
}
```
**判断标准**：追踪方法参数和局部变量，确保重定向目标不依赖任何用户输入

**2. 完整的白名单验证**
```java
private static final Set<String> ALLOWED_URLS = Set.of(
    "https://example.com/page1",
    "https://example.com/page2",
    "https://partner.example.com/"
);

@GetMapping("/redirect")
public void redirect(HttpServletResponse response,
                    @RequestParam String target) throws IOException {
    if (ALLOWED_URLS.contains(target)) {
        response.sendRedirect(target);  // 严格白名单
    }
}
```
**判断标准**：白名单必须完整列举或使用精确前缀匹配 + 协议限制

**3. 仅限相对 URL 的重定向**
```java
@GetMapping("/safe-redirect")
public void safeRedirect(HttpServletResponse response,
                        @RequestParam String path) throws IOException {
    if (path != null && path.startsWith("/") && !path.contains("//")) {
        response.sendRedirect(path);  // 仅允许相对路径
    }
}
// 安全：/safe-redirect?path=/dashboard
// 拒绝：/safe-redirect?path=https://evil.com
// 拒绝：/safe-redirect?path=//evil.com
```

**4. Spring Security 的安全重定向**
```java
@GetMapping("/login")
public void login(HttpServletResponse response,
                 @RequestParam(required = false) String redirect) {
    String safeRedirect = getDefaultRedirectUrl();
    if (redirect != null && isValidLocalUrl(redirect)) {
        safeRedirect = redirect;
    }
    response.sendRedirect(safeRedirect);
}

private boolean isValidLocalUrl(String url) {
    try {
        URI uri = new URI(url);
        // 不允许绝对URL（有 scheme 和 host）
        return uri.getScheme() == null && uri.getHost() == null;
    } catch (URISyntaxException e) {
        return false;
    }
}
```

### 区分真实漏洞 vs 误报的审计清单

| 检查项 | 真实漏洞标志 | 安全标志 | 审计建议 |
|--------|---------|---------|---------|
| **输入来源** | 用户参数（GET/POST/Path） | 硬编码或安全配置 | 追踪所有参数来源 |
| **验证方式** | 无验证或黑名单 | 完整白名单或相对URL | 检查验证逻辑的完整性 |
| **协议检查** | 不检查或不完整 | 仅允许http/https | 尝试绕过（javascript:等） |
| **域名检查** | contains()、startsWith() | 精确 URL 对象检查 | 手动构造绕过Payload |
| **相对路径** | 允许任意路径 | `^/` 且无 `//` | 检查是否限制 `//evil.com` |
| **编码处理** | 直接使用或部分解码 | 完整URL解析后检查 | 考虑URL编码、Unicode |

### 常见陷阱和技巧

**陷阱1：信任 referer 作为验证**
```java
// 错误：referer 可伪造
String referer = request.getHeader("Referer");
if (referer.startsWith("https://example.com")) {
    response.sendRedirect(userInput);  // 漏洞
}
```

**陷阱2：假设框架自动验证**
```java
// 错误：Spring 不会自动验证重定向URL
@GetMapping("/redirect")
public String redirect(@RequestParam String url) {
    return "redirect:" + url;  // 需要手动验证
}
```

**陷阱3：忽视特殊浏览器行为**
```java
// 在某些环境中，//evil.com 会使用当前协议重定向
response.sendRedirect("//evil.com/steal");  // 可能不安全
```

**技巧：测试 XSS payload 来验证**
```java
// 如果下列 payload 被反射，说明有XSS（更严重的问题）
String payload = "javascript:alert('XSS')";
// 如果 redirect 参数反射到HTML，即使不是开放重定向也有XSS
```

### 高危场景速记

- **OAuth/SSO 回调**：通常接受回调URL，易被滥用
- **支付跳转**：支付完成后重定向，常见漏洞点
- **扫二维码**：二维码中的 URL 参数易被篡改
- **邮件链接**：用户点击邮件中的链接进行重定向
- **跨域通知**：Webhook、第三方通知的回调URL

## 审计注意事项

1. **不要假设框架安全**：即使使用Spring、Struts等框架，仍需人工检查验证
2. **追踪完整链路**：URL 可能经过多个方法传递，需追踪到最终使用点
3. **考虑编码绕过**：不仅检查源代码，还要考虑运行时的URL编码/解码行为
4. **测试相对URL缺陷**：`//` 开头的相对URL容易被忽视
5. **验证白名单的maintenance**：需检查白名单是否完整、是否及时更新
