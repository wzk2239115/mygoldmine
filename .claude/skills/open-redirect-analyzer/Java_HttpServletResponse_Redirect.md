# Java HttpServletResponse.sendRedirect() 开放重定向漏洞

## Details

### 核心操作示例

```java
// 危险模式：直接使用用户输入作为重定向目标
String redirectUrl = request.getParameter("url");
response.sendRedirect(redirectUrl);

// 危险模式：简单字符串拼接
String redirectUrl = "http://example.com" + request.getParameter("path");
response.sendRedirect(redirectUrl);

// 危险模式：URL编码后仍可被利用
String redirectUrl = request.getParameter("redirect_uri");
response.sendRedirect(URLEncoder.encode(redirectUrl, "UTF-8"));
```

**快速定位核心操作技巧** [L1: 关键词扫描]
- 搜索 `sendRedirect()` 方法调用点
- 追踪参数来源：`getParameter()`、`getHeader()`、`getQueryString()` 等用户输入
- 注意URL构造方式：字符串拼接、三目运算符、条件语句中的重定向

---

### 快速定位保护机制的技巧 [L2: 跳读]

1. **白名单验证**
   - 查找是否存在预定义的重定向目标列表（常见变量名：`ALLOWED_REDIRECTS`、`WHITELIST`、`SAFE_URLS`）
   - 检查在 `sendRedirect()` 前是否对 URL 进行了白名单匹配

2. **域名验证**
   - 定位是否调用了 `URL.getHost()`、`new URI(url).getHost()` 等域名提取逻辑
   - 查看是否与配置的安全域名进行比对
   - 注意是否存在 `startsWith()`、`equals()` 的域名检验

3. **协议检验**
   - 检查是否限制了重定向协议（如仅允许 `http://` 或 `https://`）
   - 查找 `getScheme()`、`startsWith("http")`、`startsWith("https")` 的调用

4. **相对路径检查**
   - 确认是否允许相对路径重定向（如 `/path/to/resource`）
   - 检查是否禁止以 `//` 或 `javascript:` 开头的路径

---

## Classify

### 漏洞判断标准

**确认为漏洞的特征：**
- `sendRedirect()` 直接接收用户可控参数，且参数来自 HTTP 请求
- 在 `sendRedirect()` 调用前不存在上述四类保护机制中的任何一类
- 用户可以构造任意 URL（包括跨域、`javascript:` 协议、Data URI 等）进行重定向

**进阶场景（易误判）：**
1. 部分白名单使用 `contains()` 而非 `equals()` 或 `startsWith()`
   - `whitelist.contains(userUrl)` 可被绕过：`whitesite.com.attacker.com` 可能包含 `whitesite.com` 字符串

2. 协议检验不完整
   - 仅检查 `!url.startsWith("//")` 而忽略 `javascript:` 等伪协议
   - `//` 前缀可被 `%2F%2F` 编码绕过

3. URL 解析的逻辑漏洞
   - 使用 `substring()`、正则表达式进行域名提取，可能无法正确处理 `@` 符号或 `\` 分隔符
   - 例：`http://attacker.com@victim.com` 会将 `victim.com` 作为主机，但浏览器会将 `attacker.com` 作为主机

4. 信任内部重定向机制
   - 如果重定向目标来自数据库或配置文件，但这些来源可被用户间接控制（如通过注入、权限提升）

### 误报场景

- 重定向目标为**硬编码常量**
- 重定向目标仅涉及**查询参数替换**，且路径/域名不可变更
- 重定向在**登出流程**中用于统计，但目标已验证（如某些 SSO 系统的 `redirect_uri`）
- **相对路径重定向**（如 `/secured-page`）且不存在协议转换风险

### 代码异味

- 存在多个重定向点，部分受保护、部分未受保护
- 重定向逻辑与业务逻辑耦合，难以进行统一安全审计
- 使用 `HttpHeaders.LOCATION` 手动设置重定向而非 `sendRedirect()`，可能绕过框架级防护

---

## Low risk

### 应给予低风险评级的情况

1. **完整的白名单验证**
   - 白名单采用 `equals()` 或 `equalsIgnoreCase()` 精确匹配，且不存在正则表达式或通配符的歧义
   - 白名单考虑了 URL 的完整性（包括协议、域名、路径）

2. **严格的域名检验**
   - 使用 `new URL(redirectUrl).getHost()` 标准库进行域名解析，与预定义的域名集合比对
   - 域名集合基于 DNS 或配置文件管理，不存在用户输入的可能性

3. **可靠的相对路径重定向**
   - 仅允许重定向到应用内路径（如 `/success`），且确保不存在 `//`、`\\`、`javascript:` 等特殊前缀
   - 可辅助检查 `!redirectUrl.startsWith("/") || redirectUrl.startsWith("//")`

4. **框架级保护**
   - Spring Security 的 `RedirectAuthenticationSuccessHandler` 通过 `setDefaultTargetUrl()` 设置安全的重定向目标
   - 使用官方推荐的 URL 验证库（如 `apache-commons-validator` 的 `UrlValidator`）
   - 需确认框架版本未存在已知漏洞

5. **业务上受限的重定向**
   - 重定向目标基于用户的个人偏好设置（如存储在数据库中），且经过严格的访问控制
   - 使用 OAuth 2.0 的 `redirect_uri` 参数，且在授权服务器端进行了完整的验证

---
