# Java OAuth 回调未校验重定向地址

## 漏洞成因
OAuth 回调处理中，服务端接收 `redirect_uri` 或 `state` 参数后，未对重定向目标地址进行严格校验，直接使用该参数构造跳转响应或发起后端请求，导致攻击者可操纵应用访问内网资源或任意外部地址。

---

## Details

### 代码示例
```java
// 危险模式1：直接使用回调参数作为重定向目标
@GetMapping("/oauth/callback")
public void handleCallback(@RequestParam String code, 
                          @RequestParam String redirect_uri, 
                          HttpServletResponse response) throws IOException {
    String accessToken = oauthService.getToken(code);
    response.sendRedirect(redirect_uri + "?token=" + accessToken);  // 危险
}

// 危险模式2：通过 state 参数传递目标地址后发起请求
@GetMapping("/oauth/verify")
public String verifyToken(@RequestParam String state) {
    String targetUrl = Base64.decode(state);  // state编码了目标URL
    HttpURLConnection conn = (HttpURLConnection) new URL(targetUrl).openConnection();
    conn.connect();  // 后端请求用户可控URL
    return "success";
}

// 危险模式3：从数据库读取但未校验存储来源
String callbackUrl = sessionStore.get(sessionId, "callback_url");
RestTemplate restTemplate = new RestTemplate();
restTemplate.getForObject(callbackUrl, String.class);  // 若存储时未校验，仍有风险
```

### 快速定位核心操作 (L1-L3)
- **L1 关键词扫描**：
  - 搜索 OAuth 回调入口：`/oauth/callback`、`/oauth/redirect`、`/auth/callback`
  - 搜索重定向操作：`sendRedirect(`、`setHeader("Location"`、`ResponseEntity.status(302)`
  - 搜索参数名：`redirect_uri`、`redirect_url`、`state`、`return_url`、`callback`
- **L2 跳读**：
  - 定位参数接收点（`@RequestParam`、`request.getParameter()`），向下追踪参数流向
  - 检查是否直接传递给 `sendRedirect()`、`URL()`、`RestTemplate.getForObject()` 等
  - 检查 `state` 参数是否经过解码（Base64/URL解码）后用于构造请求
- **L3 逐行读**：
  - 确认重定向URL是否经过拼接（`+ "?token="`、字符串格式化）
  - 检查是否先存储后使用（session/redis存储的回调地址，追踪存储时的来源）
  - 检查是否有二次跳转（重定向到中间页面再次跳转，关注中间页面逻辑）

### 快速定位保护机制 (L2-L4)
- **L2 跳读**：
  - 检查重定向前是否有条件判断：`startsWith()`、`equals()`、`matches()`
  - 搜索白名单关键词：`allowedDomains`、`REDIRECT_WHITELIST`、`trustedHosts`
  - 检查黑名单过滤（警惕绕过）：是否仅禁止 `127.0.0.1`、`localhost` 等关键词
- **L3 逐行读**：
  - 检查域名提取方式：是否使用 `new URL().getHost()` 提取域名后比对
  - 检查白名单匹配逻辑：是否精确匹配（`equals`）还是后缀匹配（`endsWith`，警惕 `evil.com` 绕过 `.com` 后缀）
  - 检查协议限制：是否仅允许 `http/https`，是否拒绝 `file://`、`javascript:` 等
  - 检查路径校验：是否允许任意路径（`//evil.com` 绕过相对路径判断）
- **L4 跨模块追踪**：
  - 追踪注册阶段：OAuth 客户端注册时是否预登记 `redirect_uri`，回调时是否与预登记值比对
  - 追踪工具方法：如 `OAuthValidator.checkRedirectUri()`、`SecurityUtils.isValidCallback()` 内部实现
  - 检查框架配置：Spring Security OAuth、Shiro 等框架配置中的 `redirect-uri-validator` 实现
  - 追踪中间件/过滤器：是否有全局拦截器统一校验回调参数

---

## Classify

### 漏洞判定
- `redirect_uri` 或 `state` 参数完全来自用户输入且无校验 → **确认漏洞**
- 仅做黑名单过滤（如禁止 `127.0.0.1` 但允许 `127.1`、`0x7f000001`、域名解析到内网IP） → **确认漏洞**（可绕过）
- 白名单使用不当（如 `contains("trusted.com")` 可被 `evil.com?x=trusted.com` 绕过） → **确认漏洞**
- 协议未限制，可使用 `file://`、`jar://`、`javascript:` → **确认漏洞**
- 仅校验域名但允许任意路径（如 `//evil.com` 绕过相对路径判断） → **确认漏洞**

### 误报判定
- `redirect_uri` 在客户端注册时预设，回调时强制精确匹配预设值 → **误报**
- URL 来自服务端硬编码常量或管理员配置的不可变配置 → **误报**
- 使用框架标准实现（如 Spring Security OAuth 默认校验）且版本无已知漏洞 → **误报**
- 重定向目标为相对路径且有 base URL 约束（`sendRedirect("/success")` 无 `://`） → **误报**

### 代码异味
- 白名单校验但正则未锚定（`matches(".*\\.trusted\\.com.*")` 可匹配 `evil.com.attacker.com`） → **需进一步验证**
- 先校验后又进行URL编码/解码处理，可能产生二次解析漏洞 → **需追踪完整流程**
- 不同OAuth流程分支中校验逻辑不一致，部分分支遗漏校验 → **潜在风险**
- 使用 `URI.resolve()` 拼接但基础URL可控 → **需评估拼接逻辑**
- 从缓存/session读取但无法确认存储时的来源和校验 → **需追踪写入点**

---

## Low risk

### 低风险场景
- **仅前端重定向无后端请求**：`sendRedirect()` 仅返回302给客户端，服务端不发起任何到目标地址的请求（无SSRF，但仍有开放重定向风险）
- **OAuth客户端已充分隔离**：回调地址仅用于公网第三方应用跳转，内网无可达敏感资源
- **响应不包含敏感信息**：重定向时不携带 token、用户信息等敏感数据在URL参数中
- **严格的客户端注册审核**：OAuth 客户端注册需人工审核，且回调地址定期复核
- **日志审计完善**：所有回调请求的目标地址完整记录，具备实时告警和溯源能力
- **网络层防护**：服务运行在隔离环境，出站流量受防火墙/网络策略严格限制，无法访问内网关键资产
- **短期凭证且单次有效**：即使重定向到恶意地址，token 立即失效或绑定IP/设备指纹

### 注意事项
OAuth 重定向漏洞即使标记低风险，仍需关注开放重定向（Open Redirect）与 SSRF 的组合利用场景，以及钓鱼攻击风险。建议明确说明风险边界和剩余风险。