# Java Host头未验证 - Servlet API

## Details

### 漏洞成因与常见模式

Host头未验证直接用于业务逻辑（URL构造、重定向、密码重置链接等），可导致缓存中毒、密码重置投毒、SSRF、开放重定向等攻击。

#### 模式1：密码重置链接直接使用Host头

```java
// ✗ 漏洞：直接使用Host头构造密码重置链接
@WebServlet("/password-reset")
public class PasswordResetServlet extends HttpServlet {
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) {
        String email = req.getParameter("email");
        String host = req.getHeader("Host");
        String resetLink = "https://" + host + "/reset?token=" + generateToken(email);
        sendEmail(email, resetLink);  // 攻击者可控制Host头，发送恶意链接
    }
}
```

#### 模式2：动态重定向基于Host头

```java
// ✗ 漏洞：未验证Host头进行重定向
@RequestMapping("/login")
public void login(HttpServletRequest req, HttpServletResponse resp) {
    String host = req.getHeader("Host");
    String redirectUrl = "https://" + host + "/dashboard";
    resp.sendRedirect(redirectUrl);  // 可重定向到攻击者域名
}
```

#### 模式3：API回调地址使用Host头

```java
// ✗ 漏洞：OAuth回调地址未验证
@GetMapping("/oauth/authorize")
public String authorize(HttpServletRequest req) {
    String host = req.getHeader("Host");
    String callbackUrl = "https://" + host + "/oauth/callback";
    return oauthClient.authorize(callbackUrl);  // SSRF风险
}
```

#### 模式4：缓存键使用Host头

```java
// ✗ 漏洞：缓存键包含未验证的Host头
@GetMapping("/api/data")
public ResponseEntity<String> getData(HttpServletRequest req) {
    String host = req.getHeader("Host");
    String cacheKey = "data:" + host;
    String cachedData = cache.get(cacheKey);  // 缓存中毒攻击
    if (cachedData != null) return ResponseEntity.ok(cachedData);
    // ...
}
```

#### 模式5：请求转发未验证Host头

```java
// ✗ 漏洞：反向代理场景未验证Host头
@RequestMapping("/proxy")
public void proxyRequest(HttpServletRequest req, HttpServletResponse resp) {
    String host = req.getHeader("Host");
    String targetUrl = "http://" + host + req.getRequestURI();
    HttpClient.newHttpClient().send(
        HttpRequest.newBuilder().uri(URI.create(targetUrl)).build(),
        HttpResponse.BodyHandlers.ofString()
    );  // SSRF风险
}
```

#### 安全实现参考

```java
// ✓ 安全：白名单验证Host头
private static final Set<String> ALLOWED_HOSTS = Set.of(
    "example.com", "www.example.com", "api.example.com"
);

@WebServlet("/password-reset")
public class SecurePasswordResetServlet extends HttpServlet {
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) {
        String email = req.getParameter("email");
        String host = req.getHeader("Host");

        // ✓ 白名单验证
        if (!ALLOWED_HOSTS.contains(host)) {
            host = "example.com";  // 使用默认安全域名
        }

        String resetLink = "https://" + host + "/reset?token=" + generateToken(email);
        sendEmail(email, resetLink);
    }
}
```

### 审计检查清单

| 优先级 | 检查项 | 审计方法 | 审计等级 |
|--------|--------|---------|----------|
| **P0** | 密码重置/邮件链接 | 搜索 `getHeader("Host")` + `sendEmail/sendMail` 组合，检查是否用于构造链接 | **L2-L3** |
| **P0** | 重定向URL构造 | 搜索 `sendRedirect` + `getHeader("Host")`，检查是否有白名单验证 | **L2** |
| **P0** | OAuth/回调地址 | 搜索 `callback/redirect_uri` + `Host`，检查是否验证域名 | **L3** |
| **P1** | 缓存键使用Host | 搜索 `cache.get/put` + `Host`，检查是否有Vary头或域名验证 | **L3** |
| **P1** | 反向代理/转发 | 搜索 `HttpClient/RestTemplate` + `Host`，检查目标URL是否可控 | **L3-L4** |
| **P2** | API基础URL构造 | 搜索 `getScheme() + Host + getRequestURI()`，检查上下文 | **L2** |
| **P3** | 日志/监控记录 | 搜索 `logger.info/debug` + `Host`，低风险但需确认无敏感操作 | **L1** |

### 审计等级判定

| 等级 | 代码特征 | 审计策略 |
|------|---------|---------|
| **L0** | Host头仅用于日志/监控，无业务逻辑 | 快速跳过，简单确认无重定向/URL构造 |
| **L1** | Host头用于非关键展示（页面标题、面包屑） | 关键词扫描：确认无 `sendRedirect/sendEmail/HttpClient` |
| **L2** | Host头用于单文件内重定向/URL构造 | 跳读：检查是否有 `ALLOWED_HOSTS` 常量或 `contains/equals` 验证 |
| **L3** | Host头跨模块使用（工具类/Service层） | 逐行读：追踪方法调用链，检查每个使用点是否安全 |
| **L4** | Host头在过滤器/拦截器中处理，影响全局 | 跨模块追踪：检查 `Filter/Interceptor` 实现，分析调用链 |

---

## Classify

### 确认漏洞的标准

1. **直接威胁**：Host头直接用于构造外部可见的URL（密码重置、OAuth回调、邮件链接）且无验证
2. **可利用性**：攻击者可通过修改HTTP请求头中的Host字段触发漏洞（非HTTPS SNI限制场景）
3. **无防护机制**：代码中无白名单验证、无域名格式检查、无默认安全域名

### 判定为误报的情况

1. **仅内部使用**：Host头仅用于日志、调试信息，不影响业务逻辑流程
2. **已有验证**：存在白名单检查（`ALLOWED_HOSTS.contains(host)`）、正则匹配（`host.matches("^[a-z]+\\.example\\.com$")`）
3. **基础设施防护**：WAF规则、负载均衡器配置强制验证Host头（需运维确认）
4. **业务场景限制**：多租户SaaS架构中Host头是业务设计的一部分，且有子域名白名单

### 代码异味识别

1. **不完整验证**：仅检查Host头是否为空，未验证域名合法性
2. **弱验证**：使用 `contains` 方法但未锚定（如 `host.contains("example.com")` 可被 `evil-example.com` 绕过）
3. **隐式信任**：注释写明"由前端负载均衡器验证"，但无代码层面的二次验证
4. **不一致处理**：部分端点验证Host头，部分端点不验证

---

## Audit Techniques

### 审计经验：真实漏洞 vs 误报区分

#### 案例1：密码重置链接中的Host头使用

**真实漏洞特征：**
```java
// 代码示例
String resetLink = "https://" + req.getHeader("Host") + "/reset?token=" + token;
mailService.send(email, "Click here: " + resetLink);
```
- **关键观察**：Host头直接拼接到邮件内容中，无任何验证
- **利用路径**：攻击者修改HTTP Host头 → 邮件包含恶意域名 → 用户点击链接到攻击者网站
- **证据链**：`getHeader("Host")` + `sendEmail` + URL拼接 = 必然漏洞
- **审计建议**：如果看到这三个要素同时出现，直接判定为漏洞，不需要验证是否可实际利用

**误报案例：**
```java
// 看起来相似的代码
String hostWithPort = req.getHeader("Host");
String domain = hostWithPort.split(":")[0];  // 提取域名部分
logger.info("User accessed from: " + domain);  // 仅用于日志
```
- **为什么不是漏洞**：Host头仅用于日志记录，不涉及业务逻辑、重定向或外部通信
- **审计建议**：看到Host头时，必须追踪后续使用场景，日志类方法（log/println）通常安全

#### 案例2：重定向中的Host头使用

**真实漏洞特征：**
```java
// 真实漏洞
public void handleLogin(HttpServletRequest req, HttpServletResponse resp) {
    String host = req.getHeader("Host");
    String returnUrl = req.getParameter("return_url");
    String redirectUrl = "https://" + host + returnUrl;  // 攻击者控制returnUrl
    resp.sendRedirect(redirectUrl);
}
```
- **利用路径**：POST到 `/login?return_url=.evil.com` → 重定向到 `https://trusted.com.evil.com`
- **关键线索**：Host头与用户参数（returnUrl）组合使用，缺乏验证
- **审计建议**：任何使用了 `sendRedirect` 的代码都是高优先级审计点

**误报案例：**
```java
// 看起来类似但实际安全
String host = req.getHeader("Host");
if (!isValidHost(host)) {
    host = "example.com";  // 强制使用安全默认值
}
String redirectUrl = "https://" + host + "/dashboard";
resp.sendRedirect(redirectUrl);
```
- **为什么不是漏洞**：存在明确的验证逻辑，不在白名单内使用默认值
- **审计建议**：如果看到 `if/switch` 的验证逻辑，需要逐行分析验证是否充分

**弱验证陷阱：**
```java
// 表面安全但实际有漏洞
if (host.contains("example.com")) {
    resp.sendRedirect("https://" + host + "/dashboard");
}
```
- **问题**：`evil-example.com.attacker.com` 也会通过检查
- **正确做法**：使用 `equals()` 或正则表达式 `^example\.com(:\d+)?$`
- **审计建议**：看到 `contains` 时，要确认是否存在前缀/后缀注入风险

#### 案例3：缓存中毒中的Host头使用

**真实漏洞特征：**
```java
// 真实漏洞
@GetMapping("/static/config")
public ResponseEntity<String> getConfig(HttpServletRequest req) {
    String host = req.getHeader("Host");
    String cacheKey = "config:" + host;  // Host成为缓存键的一部分
    String cached = cache.get(cacheKey);
    if (cached != null) {
        return ResponseEntity.ok().cacheControl(CacheControl.maxAge(1, TimeUnit.DAYS)).body(cached);
    }
    return ResponseEntity.ok(loadConfig());
}
```
- **利用路径**：攻击者以 `Host: attacker.com` 访问 → 生成缓存键 → CDN/代理缓存这个响应 → 其他用户访问也可能命中这个缓存
- **关键指标**：缓存键使用用户可控的Host头，且未设置 `Vary: Host` 响应头
- **审计建议**：任何涉及缓存的代码都需要检查是否正确处理了Vary头

**误报案例：**
```java
// 看起来类似但实际安全
String host = req.getHeader("Host");
String cacheKey = "config:default";  // 缓存键固定
String cached = cache.get(cacheKey);  // Host头被读取但不用于缓存键
return ResponseEntity.ok()
    .header("Vary", "Host")  // 明确声明
    .body(cached);
```
- **为什么不是漏洞**：Host头未用于构建缓存键，且设置了Vary头
- **审计建议**：需要确保缓存键生成逻辑不包含Host头

#### 案例4：OAuth回调地址验证

**真实漏洞特征：**
```java
// 真实漏洞
@GetMapping("/oauth/init")
public String initOAuth(HttpServletRequest req) {
    String host = req.getHeader("Host");
    String callbackUrl = "https://" + host + "/oauth/callback";  // 回调地址完全由Host头决定
    String authorizeUrl = oauthProvider.buildAuthUrl(callbackUrl);
    return "redirect:" + authorizeUrl;
}
```
- **利用路径**：攻击者修改Host头 → 回调URL变为恶意域名 → OAuth服务可能信任该回调地址 → 授权码泄露
- **关键指标**：Host头直接用于OAuth流程中的关键参数
- **审计建议**：搜索 `oauth/authorize/callback` + `Host`，这类结合总是漏洞

**防护验证清单：**
```java
// 安全实现
private static final Set<String> OAUTH_ALLOWED_HOSTS = Set.of(
    "api.example.com", "api-staging.example.com"
);

@GetMapping("/oauth/init")
public String initOAuth(HttpServletRequest req) {
    String host = req.getHeader("Host");

    // ✓ 多层验证
    if (!OAUTH_ALLOWED_HOSTS.contains(host)) {
        throw new UnauthorizedException("Invalid host");
    }

    // ✓ 使用配置化的回调地址，不依赖Host头
    String callbackUrl = oauthConfig.getCallbackUrl(host);
    return "redirect:" + oauthProvider.buildAuthUrl(callbackUrl);
}
```
- **审计建议**：如果代码包含白名单集合且进行了检查，需要验证白名单是否完整

#### 审计高频误判

| 代码模式 | 常见误判 | 正确判断 | 审计技巧 |
|---------|---------|---------|---------|
| `host.split(":")[0]` | 认为是漏洞 | 仅是格式处理 | 追踪返回值的后续用途 |
| `if (host != null && !host.isEmpty())` | 认为验证充分 | 缺乏域名合法性检查 | 检查是否有白名单或正则 |
| `req.getHeader("X-Forwarded-Host")` | 认为比Host更安全 | 同样需要验证 | X-Forwarded-*头同样可伪造 |
| `logger.info("host=" + host)` | 快速判定为低风险 | 需确认logger不会外泄 | 检查日志是否面向用户 |
| `// Host由LB验证` 注释 | 认为可信 | 需代码层验证 | 不信任基础设施，要求防御性编程 |

---

## Low risk

### 低风险场景判定标准

满足以下任一条件时，可评估为低风险（仍需标注并建议修复）：

1. **有限暴露场景**
   - 应用仅部署在内网环境，外部攻击者无法直接访问
   - 应用前置有WAF/CDN且已配置Host头白名单规则
   - 使用HTTPS + HSTS，且证书绑定特定域名（攻击者难以伪造SNI）

2. **业务影响受限**
   - Host头仅用于生成预览链接、临时分享链接（不涉及认证/授权）
   - 密码重置链接额外有短信/App推送验证（双因素保护）
   - 缓存系统已配置按用户会话隔离，Host头中毒影响范围小

3. **部分防护措施**
   - 存在基础格式验证（如长度限制、字符集检查）但不够严格
   - Host头来自 `X-Forwarded-Host` 且由可信代理设置（需确认代理配置）
   - 应用有请求频率限制，降低批量攻击可能性

4. **可审计性强**
   - 所有Host头使用点已集中在工具类方法中，便于后续统一加固
   - 存在监控告警机制，异常Host头会触发安全事件
   - 代码中已有TODO注释标明需要添加验证

### 评级建议

- **低风险 + 内网环境**：建议下一迭代修复，添加白名单验证
- **低风险 + 有WAF防护**：确认WAF规则有效性，代码层面添加防御性编程
- **低风险 + 多因素验证**：优先级降低，但仍应在安全规范中明确禁止未验证使用Host头
