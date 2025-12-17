# Java Spring RedirectView 用户输入未验证漏洞

## Details

### 核心代码示例

Spring 框架中使用 `RedirectView` 或 `redirect:` 前缀处理重定向时，直接使用用户输入构造重定向 URL 的典型模式：

```java
// 危险模式 1：直接注入用户参数到 RedirectView
@GetMapping("/process")
public ModelAndView handleRequest(@RequestParam String targetUrl) {
    return new ModelAndView(new RedirectView(targetUrl));
}

// 危险模式 2：redirect: 前缀 + 用户输入拼接
@PostMapping("/next-step")
public String processStep(@RequestParam String nextPage) {
    return "redirect:" + nextPage;
}

// 危险模式 3：通过 Model 或 request 属性传递用户输入至视图层
@GetMapping("/callback")
public String oauthCallback(@RequestParam String code, @RequestParam String state) {
    String redirectUri = request.getParameter("redirect_uri");
    // 【审计重点】redirectUri 未验证即传入 RedirectView，攻击者可指向恶意域名
    return "redirect:" + redirectUri;
}

// 危险模式 4：RedirectView 与 setExposeModelAttributes(true)
@GetMapping("/dynamic")
public ModelAndView dynamicRedirect(HttpServletRequest request) {
    ModelAndView mav = new ModelAndView();
    String userTarget = request.getParameter("url");
    RedirectView view = new RedirectView(userTarget);
    view.setExposeModelAttributes(true);  // 即使暴露模型属性，用户输入仍未被验证
    mav.setView(view);
    return mav;
}

// 危险模式 5：使用 UriComponentsBuilder 但未验证最终 URL
@GetMapping("/forward")
public String forward(@RequestParam String host, @RequestParam String path) {
    String redirectUrl = UriComponentsBuilder.newInstance()
            .scheme("http")
            .host(host)  // 【审计重点】host 直接来自用户输入
            .path(path)
            .build()
            .toUriString();
    return "redirect:" + redirectUrl;
}
```

**快速定位到核心操作的技巧** 【L1:关键词扫描】

- 搜索 `RedirectView`、`new RedirectView()`、`redirect:` 前缀
- 扫描 `getParameter()`、`getHeader()`、`@RequestParam` 等参数获取方式
- 查找 `UriComponentsBuilder`、`ServletUriComponentsBuilder` 的 URL 拼接逻辑
- 定位视图层配置中是否存在通过参数名进行 URL 构造的模式（如 `viewName + userInput`）
- 关注登录、OAuth、回调等需要重定向的端点

**快速定位到保护机制的技巧** 【L2:跳读】【L3:逐行读】

- **白名单验证**（L2）：查找是否存在 `isValidRedirectUrl()`、`isSafeUrl()`、`isAllowedHost()` 等验证方法调用
  - 检查白名单是否基于 `java.net.URI`、`java.net.URL` 等标准库进行解析
  - 验证是否使用 `equals()`/`equalsIgnoreCase()`（精确匹配）而非 `contains()`/`startsWith()` 容易被绕过的方法
  - 关注白名单是否采用配置文件（如 `application.yml`、`@ConfigurationProperties`）管理
- **域名提取与验证**（L3）：追踪从重定向 URL 中提取域名的逻辑
  - 确认是否使用 `new URL(redirectUrl).getHost()`、`new URI(redirectUrl).getHost()` 进行解析
  - 检查提取后的域名是否与预定义的信任域名集合进行比对
  - 关注是否存在对 URL 中 `@` 符号、`\` 分隔符的处理缺陷
- **协议检验**（L2）：查看 `redirect:` 前缀前是否进行了协议限制
  - 搜索 `startsWith("http://")` 或 `startsWith("https://")` 的检查
  - 注意是否还排除了 `javascript:`、`data:`、`vbscript:` 等伪协议
  - 关注 `//` 协议相对 URL 的处理（如是否禁止 `startsWith("//")`）
- **相对路径检查**（L2）：确认是否仅允许应用内相对路径
  - 搜索是否强制检验 `!redirectUrl.startsWith("/")` 或 `redirectUrl.startsWith("/")`
  - 检查是否禁止 `../` 等路径遍历的写法
  - 关注 Spring 框架配置是否有 URL rewriting 规则可能导致逃逸

---

## Classify

### 研判流程

1. **确认参数来源**：targetUrl 等重定向目标参数是否完全来自用户输入（GET、POST、Header、Cookie、Request Attribute）
2. **追踪 RedirectView 构造**：
   - `new RedirectView(userInput)` → 直接传入用户输入 = 高风险
   - 经过 StringBuilder/UriComponentsBuilder 拼接后才传入 → 检查拼接过程中是否验证
3. **检查验证策略**：
   - 无任何验证 → 确认漏洞
   - 仅检查格式或协议 → 代码异味（协议检查不能防止跨域重定向）
   - 仅客户端验证 → 代码异味（易被绕过）
   - 使用完整白名单或严格的域名验证 → 安全
4. **跨模块追踪**【L4:跨模块追踪】：
   - 检查重定向目标是否从数据库、缓存、配置源取值，若是则追踪该源是否可被用户间接控制
   - 追踪 Spring Interceptor、Filter 是否存在在重定向前进行的全局验证
   - 如使用 Spring Security，检查 `RedirectAuthenticationSuccessHandler`、`RedirectAuthenticationFailureHandler` 的配置

### 漏洞判定标准

**确认为漏洞的特征**：
- `RedirectView` 或 `redirect:` 前缀直接接收或构造用户可控参数
- 在 `RedirectView` 构造或字符串返回前不存在上述保护机制
- 用户可以构造任意 URL（包括跨域、伪协议、相对路径转义等）

**进阶场景（易误判）**：
1. **白名单使用 contains() 而非 equals()**
   - 代码：`whitelistDomains.contains(extractedHost)` 可被绕过
   - 绕过：`whitesite.com.attacker.com` 包含 `whitesite.com` 字符串，但实际域名为 attacker.com

2. **协议检验不完整**
   - 仅检查 `!url.startsWith("//")` 忽略 `javascript:`、`data:` 伪协议
   - `//` 可被 `%2F%2F` URL 编码绕过，需确认解码时机

3. **URI/URL 解析的逻辑漏洞**
   - 使用 `substring()` 或正则表达式提取域名，可能无法正确处理 `@` 符号
   - 例：`http://attacker.com@victim.com` 中，`substring("://", "")` 可能提取错误
   - Java URL 解析器会将 `victim.com` 作为主机，但浏览器会将 `attacker.com` 作为主机（基本身份认证）

4. **UriComponentsBuilder 拼接逻辑缺陷**
   - 用户可控的 host 或 path 未验证直接传入
   - 特殊字符（如 `?`、`#`、`@`）可能改变 URL 的解析结果

5. **框架级防护被绕过**
   - Spring Security `authorizedRedirectHosts` 使用模式匹配，某些正则表达式可被绕过
   - 例：正则 `.*\.example\.com` 可被 `attacker.com\nwhite.example.com` 绕过（如果支持多行）

### 误报场景

- 重定向目标为**硬编码常量** 或 **方法返回值固定**
- 重定向仅涉及**查询参数替换**，基础路径和域名不可变更
- 重定向在**登出流程**中用于统计，目标已通过严格白名单验证（如 OAuth2 授权服务器的 `redirect_uri`）
- **相对路径重定向**（如 `redirect:/success`），且不存在协议转换、`//` 前缀、路径遍历的风险
- 使用 Spring Framework 内置的 `RedirectView` 且设置了 `contextRelative=true`（仅允许相对于 web 应用根目录的路径）

### 代码异味

- 存在多个重定向端点，部分受保护、部分未受保护（风险不一致）
- 重定向验证逻辑分散在业务代码中而非通过统一的拦截器或工具方法实现
- 使用 `HttpServletResponse.setHeader("Location", userInput)` 手动设置而非 `RedirectView`，可能绕过框架级防护
- 白名单配置不明确（如硬编码在代码中、不易维护），导致新增域名时遗漏更新

---

## Low risk

### 应给予低风险评级的情况

1. **完整的白名单验证**
   - 白名单采用 `equals()`、`equalsIgnoreCase()` 或编译为 Pattern 的正则表达式进行精确匹配
   - 白名单考虑了 URL 的**完整性**（协议 + 域名 + 路径），而非仅验证域名
   - 白名单源自配置文件、环境变量或数据库中的受信来源，不存在用户输入的可能

2. **严格的域名检验**
   - 使用 `new URL(redirectUrl).getHost()` 或 `new URI(redirectUrl).getHost()` 等标准库进行规范化解析
   - 提取后的域名与预定义的信任域名集合进行 `equals()` 比对，不使用 `contains()` 或 `startsWith()`
   - 信任域名集合基于配置管理，不受用户输入影响
   - 同时验证协议为 `http://` 或 `https://`，排除其他伪协议

3. **可靠的相对路径重定向**
   - 仅允许重定向到应用内路径（如 `redirect:/success`、`redirect:/pages/home`）
   - 严格检查：`!redirectUrl.startsWith("//") && !redirectUrl.contains("://")` 且 `redirectUrl.startsWith("/")`
   - 不存在 `../` 路径遍历、特殊字符（`?`、`#`、`@`）改变解析结果的可能
   - Spring Framework 配置中设置 `RedirectView` 的 `contextRelative=true`，确保相对于应用根目录

4. **框架级保护**
   - 使用 Spring Security 的 `RedirectAuthenticationSuccessHandler` 配合 `setDefaultTargetUrl()` 设置安全的重定向目标
   - Spring Security 的 `authorizedRedirectHosts` 配置明确限制了允许的重定向域名，且正则表达式已经过严格测试
   - 使用官方推荐的 URL 验证库（如 `apache-commons-validator` 的 `UrlValidator` 与自定义白名单组合）
   - 确认使用的框架版本不存在已知的重定向相关漏洞（查看 CVE 数据库）

5. **业务上受限的重定向**
   - 重定向目标基于用户的个人设置（如存储在数据库中），且经过严格的访问控制和白名单验证
   - 使用 OAuth 2.0 的 `redirect_uri` 参数，且在**授权服务器端**进行了完整的验证（客户端预先注册，授权时精确比对）
   - 重定向目标为来自受信来源（如配置中心、内部服务）的 URL，不涉及用户输入

---
