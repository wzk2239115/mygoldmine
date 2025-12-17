# Java OAuth2 Redirect_URI 验证不足审计

**漏洞成因**：OAuth2 授权服务器在验证 `redirect_uri` 参数时，校验逻辑缺陷导致攻击者可将授权码重定向到恶意URL，从而劫持用户授权、盗取访问令牌或进行钓鱼攻击。常见于开放授权、API 网关、SSO 中心、第三方应用集成等场景。

---

## Details

**代码示例**：
```java
// 危险：部分字符串匹配（可绕过）
String clientRedirectUri = request.getParameter("redirect_uri");
String registeredUri = getRegisteredUri(clientId);
if (registeredUri.contains(clientRedirectUri)) {  // 使用 contains 或 startsWith
    redirectUser(clientRedirectUri, authCode);
}

// 危险：宽松的正则验证
String pattern = "https?://.*\\.example\\.com.*";  // 支持任意子域
if (clientRedirectUri.matches(pattern)) {
    redirectUser(clientRedirectUri, authCode);
}

// 危险：URL 解析缺陷
URL redirectUrl = new URL(clientRedirectUri);
if (redirectUrl.getHost().endsWith("example.com")) {  // 未处理 IDN、IP 混淆
    redirectUser(clientRedirectUri, authCode);
}

// 较安全：精确匹配白名单
List<String> whitelistedUris = getWhitelistedUris(clientId);
if (whitelistedUris.contains(clientRedirectUri)) {
    redirectUser(clientRedirectUri, authCode);
}
```

**快速定位核心操作** (L1-L2)：
- **L1 关键词扫描**：
  - `redirect_uri`、`redirectUri`、`callback_url`、`callbackUrl`
  - `getParameter("redirect_uri")`、`@RequestParam("redirect_uri")`、`@PathVariable`
  - `sendRedirect()`、`forward()`、`redirect(`、`RedirectView`
  - `response.setHeader("Location", `、`HttpHeaders.LOCATION`
  - OAuth2 授权端点：`/oauth/authorize`、`/oauth2/authorize`、`/auth`
  - Spring Security 相关：`OAuth2AuthorizationRequest`、`DefaultOAuth2AuthorizationRequestResolver`、`RedirectUriValidator`

- **L2 跳读追踪**：
  - 向上溯源 redirect_uri 的获取方式（直接从请求参数获取、从数据库查询、配置文件）
  - 检查 redirect_uri 与白名单/注册 URI 的比对逻辑
  - 关注比对方法：`equals()`、`contains()`、`startsWith()`、`endsWith()`、`matches()`、`compareTo()`
  - 追踪 URL 解析和验证流程，定位协议、域名、路径的校验点

**快速定位保护机制** (L2-L4)：
- **L2 跳读识别**：
  - 是否使用 `equals()` 精确匹配而非 `contains()` 等宽松匹配
  - 是否存在 `URI` / `URL` 白名单列表，查询方式（直接表查询、内存缓存、配置）
  - 是否有 URL 规范化处理：`URI.normalize()`、`URL.toString()` 一致性检查
  - 是否明确校验协议（仅允许 `https://`）

- **L3 逐行验证保护有效性**：
  - 白名单完整性：是否覆盖所有客户端、是否支持多个 URI、是否允许通配符
  - 正则表达式的严谨性：是否支持子域名通配、是否限制路径、是否考虑查询参数和片段
  - URL 规范化缺陷：`//example.com`、`example.com:80` vs `example.com`、大小写敏感性、IDN 编码
  - 跳转实现：是否直接使用用户输入的 URL，是否经过二次验证

- **L4 跨模块追踪**：
  - 追踪 redirect_uri 从请求参数 → 验证逻辑 → 实际跳转的完整链路
  - 检查是否存在多个验证点（授权、令牌换取、刷新令牌时）
  - 验证白名单数据的来源可信性（配置管理、admin 审核、版本控制）
  - 确认错误处理是否安全（404 vs 验证失败，是否泄露白名单信息）

**审计等级**：**L2-L4**
- **L2**：跳读识别比对方法和白名单来源
- **L3**：逐行验证校验逻辑、正则表达式、URL 解析的严谨性
- **L4**：跨模块追踪 redirect_uri 的完整验证流程，检查所有使用点

---

## Classify

**确认为漏洞**：
- 使用 `contains()`、`startsWith()` 等宽松匹配而非 `equals()`，如 `registeredUri.contains(clientRedirectUri)`
- 正则表达式支持通配符或过度宽松：`https?://.*example\\.com.*`、`https?://.*`
- URL 解析不完整，仅校验域名而忽视协议、端口、路径、查询参数
- 白名单缺失或为空列表，导致任意 redirect_uri 被接受
- 未处理 URL 规范化问题：`//example.com`、`example.com/..%2f`、`example.com:80` 与 `example.com` 视为不同
- 支持相对路径跳转：`redirect_uri=/path` 或 `redirect_uri=//example.com`
- 通过 URL 编码、双重编码、Unicode 编码绕过验证的缺陷

**误报**：
- 使用 `equals()` 精确匹配且白名单完整、不支持通配符
- 白名单在数据库或配置中维护，客户端注册时经过人工审核
- URL 经过完整的规范化和多重校验（协议、域名、端口、路径均精确匹配）
- 使用可信的 URL 验证库（如 Apache Commons URL Validator、Spring 官方 RedirectUriValidator）
- 错误处理安全，验证失败直接返回错误而非默认跳转

**代码异味**：
- 正则表达式逻辑复杂但未有注释说明设计意图
- 存在多个 redirect_uri 验证点，逻辑不一致
- 白名单支持部分通配符但规则不清晰（如允许子域名但不允许不同路径）
- 使用自定义 URL 验证逻辑而非框架提供的工具
- 验证逻辑与业务逻辑耦合紧密，难以独立测试和维护

---

## Low Risk

以下情况可评为低风险，但仍建议修复：
- **严格的内网环保**：OAuth2 授权服务仅供内部应用使用，所有客户端通过企业内网访问，redirect_uri 均为内网 IP/域名
- **受限应用场景**：授权流程中 redirect_uri 不是安全关键参数（如某些特定业务场景仅用于日志重定向、分析链接追踪）
- **多层防护存在**：
  - 授权码（Authorization Code）与客户端强绑定，无法跨客户端使用
  - 令牌交换时进行二次 redirect_uri 校验（RFC 6749 规定）
  - WAF/API 网关已拦截恶意域名、已知钓鱼站点
  - 用户授权前有额外确认步骤（显示完整跳转 URL，用户需主动确认）
- **受信客户端清单**：redirect_uri 白名单来自经过安全审计的内部系统、已签署安全协议的商业伙伴
- **影响范围有限**：
  - 仅授予低敏感权限范围（如只读、无用户信息访问）
  - 访问令牌有效期极短（< 5 分钟）
  - 用户可在短时间内发现异常（如邮件通知、登录日志）

**注意**：低风险≠可忽略，redirect_uri 验证是 OAuth2 安全的基石，即使在上述条件下仍建议修复，以防其他风险因素组合。
