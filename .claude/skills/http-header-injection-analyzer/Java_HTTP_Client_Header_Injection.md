# Java HttpClient请求头注入

## Details

### 漏洞成因与常见模式

使用HttpClient、RestTemplate等客户端发起HTTP请求时，若请求头直接使用用户输入构造且未过滤CRLF，可导致SSRF、请求走私、认证绕过等攻击。攻击者可注入恶意头部改变请求语义。

#### 模式1：HttpClient直接设置用户输入头

```java
// ✗ 漏洞：用户输入直接设置请求头
public void makeRequest(String userAgent) {
    HttpClient client = HttpClient.newHttpClient();
    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create("https://api.example.com"))
        .header("User-Agent", userAgent)  // 未过滤CRLF
        .build();
    // 攻击: userAgent="Custom\r\nX-Admin:true"
}
```

#### 模式2：Apache HttpClient动态头注入

```java
// ✗ 漏洞：未验证的Authorization头
public String fetchData(String token) {
    CloseableHttpClient client = HttpClients.createDefault();
    HttpGet request = new HttpGet("https://api.example.com/data");
    request.setHeader("Authorization", "Bearer " + token);  // token可注入CRLF
    // 攻击: token="valid\r\nX-Role:admin"
    HttpResponse response = client.execute(request);
    return EntityUtils.toString(response.getEntity());
}
```

#### 模式3：RestTemplate头注入

```java
// ✗ 漏洞：自定义头未过滤
@Service
public class ApiService {
    @Autowired
    private RestTemplate restTemplate;

    public String callApi(String customHeader) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Custom-Header", customHeader);  // 未验证用户输入
        HttpEntity<String> entity = new HttpEntity<>(headers);
        return restTemplate.exchange(
            "https://api.example.com", HttpMethod.GET, entity, String.class
        ).getBody();
    }
}
```

#### 模式4：代理场景请求转发

```java
// ✗ 漏洞：转发请求时复制用户头
@PostMapping("/proxy")
public ResponseEntity<String> proxyRequest(
    @RequestHeader Map<String, String> headers, @RequestBody String body) {

    HttpRequest.Builder builder = HttpRequest.newBuilder()
        .uri(URI.create("https://backend.example.com"));

    headers.forEach((key, value) -> builder.header(key, value));  // 直接复制所有头
    // 攻击: 发送 "X-Admin: false\r\nX-Admin: true"

    HttpRequest request = builder.POST(HttpRequest.BodyPublishers.ofString(body)).build();
    return ResponseEntity.ok(HttpClient.newHttpClient().send(request,
        HttpResponse.BodyHandlers.ofString()).body());
}
```

#### 模式5：API密钥拼接注入

```java
// ✗ 漏洞：API密钥字段可控
public void sendWebhook(String apiKey, String data) {
    OkHttpClient client = new OkHttpClient();
    Request request = new Request.Builder()
        .url("https://webhook.example.com")
        .addHeader("X-API-Key", apiKey)  // 未验证apiKey格式
        .post(RequestBody.create(data, MediaType.parse("application/json")))
        .build();
    // 攻击: apiKey="valid\r\nContent-Length:0\r\n\r\nGET /admin"
    client.newCall(request).execute();
}
```

#### 安全实现参考

```java
// ✓ 安全：CRLF过滤 + 白名单验证
public class SecureHttpClient {
    private static final Pattern CRLF_PATTERN = Pattern.compile("[\r\n]");
    private static final Set<String> ALLOWED_HEADERS = Set.of(
        "User-Agent", "Accept", "Content-Type", "Authorization"
    );

    private String sanitizeHeaderValue(String value) {
        if (value == null) return "";
        return CRLF_PATTERN.matcher(value).replaceAll("");
    }

    public void makeRequest(Map<String, String> headers) {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
            .uri(URI.create("https://api.example.com"));

        headers.forEach((key, value) -> {
            // ✓ 白名单验证头名
            if (ALLOWED_HEADERS.contains(key)) {
                // ✓ CRLF过滤头值
                builder.header(key, sanitizeHeaderValue(value));
            }
        });

        HttpClient.newHttpClient().sendAsync(builder.build(),
            HttpResponse.BodyHandlers.ofString());
    }
}
```

### 审计检查清单

| 优先级 | 检查项 | 审计方法 | 审计等级 |
|--------|--------|---------|----------|
| **P0** | HttpRequest.header | 搜索 `.header(` + 用户输入变量，检查CRLF过滤 | **L2** |
| **P0** | RestTemplate自定义头 | 搜索 `HttpHeaders.set/add` + 请求参数来源 | **L2-L3** |
| **P0** | Apache HttpClient.setHeader | 搜索 `setHeader\|addHeader` + 动态值，检查过滤 | **L2** |
| **P1** | 代理转发头复制 | 搜索 `@RequestHeader Map` + `forEach.*header`，检查是否全量复制 | **L3** |
| **P1** | Authorization/API-Key | 搜索 `Authorization\|X-API-Key` + 参数拼接，检查格式验证 | **L2** |
| **P2** | OkHttp自定义头 | 搜索 `addHeader` + 用户输入，检查来源 | **L2** |
| **P3** | WebClient动态头 | 搜索 `WebClient.*header` + 参数，检查链式调用 | **L3** |

### 审计等级判定

| 等级 | 代码特征 | 审计策略 |
|------|---------|---------|
| **L0** | 请求头全部硬编码常量 | 快速跳过，确认无变量 |
| **L1** | 请求头来自配置文件/环境变量 | 关键词扫描：确认非请求参数 |
| **L2** | 单文件内直接使用请求参数 | 跳读：检查是否有 `replaceAll("[\r\n]", "")` |
| **L3** | 请求头由Service层构造 | 逐行读：追踪方法参数来源和传递链 |
| **L4** | 拦截器/过滤器统一处理头 | 跨模块追踪：检查 `ClientHttpRequestInterceptor` 实现 |

---

## Classify

### 确认漏洞的标准

1. **用户输入可达**：请求头值直接或间接来自HTTP请求参数、表单字段、路径变量
2. **无CRLF过滤**：代码未调用 `replaceAll("[\r\n]", "")` 或正则过滤
3. **影响后端请求**：该请求发往内部API、第三方服务、数据库代理等关键后端

### 判定为误报的情况

1. **已有过滤**：存在全局拦截器对所有请求头进行CRLF过滤
2. **白名单严格**：请求头仅允许枚举值（如固定的几种Content-Type）
3. **框架自动保护**：使用的HTTP客户端库版本自动拒绝CRLF（需验证库版本和配置）
4. **仅内部调用**：请求头来自内部服务的可信响应（但需确认内部服务安全性）

### 代码异味识别

1. **不完整过滤**：仅过滤 `\n` 未过滤 `\r`，或仅trim处理
2. **过滤时机错误**：先发起请求后记录日志时过滤（攻击已完成）
3. **隐式信任**：注释"调用方已验证"，但无代码验证
4. **混合使用**：部分头过滤，部分头不过滤

### 审计专业技巧：真实漏洞vs误报

#### 技巧1：追踪用户输入源头的三层审计

真实漏洞需要满足**完整的污染链**，不能中途有过滤。审计时需要：

```java
// ✗ 真实漏洞：完整污染链（可进一步证实）
@GetMapping("/api")
public String api(@RequestParam String token) {  // 来源1：用户输入
    String value = sanitizeForLog(token);         // 可能混淆审计：这是日志过滤！
    HttpRequest req = HttpRequest.newBuilder()
        .header("Authorization", token)            // 来源2：直接使用原始token
        .build();
}

// ✓ 误报：虽然有用户输入，但链条被打断
@GetMapping("/api")
public String api(@RequestParam String token) {
    String sanitized = token.replaceAll("[\r\n]", "");  // 关键：在setHeader之前过滤
    HttpRequest req = HttpRequest.newBuilder()
        .header("Authorization", sanitized)
        .build();
}
```

**审计技巧**：不要只看参数来源，需要在IDE中追踪**变量赋值链**：
- 步骤1：定位 `.header()` 或 `setHeader()` 调用
- 步骤2：找到头值变量的定义点
- 步骤3：逐层回溯该变量是否经过过滤（Ctrl+左键跳转）
- 步骤4：若中间有任何 `replaceAll/Pattern/sanitize` 调用，则可能是误报

#### 技巧2：HTTP客户端库版本检测

不同库的自防护程度差异巨大：

```java
// 检查pom.xml或build.gradle中的版本
// HttpClient 4.5.13+ 有内置的头部验证（但需启用）
<dependency>
    <groupId>org.apache.httpcomponents</groupId>
    <artifactId>httpclient</artifactId>
    <version>4.5.13</version>  <!-- ✓ 较新，可能有防护 -->
</dependency>

// 而这个版本很危险：
<version>4.2.6</version>  <!-- ✗ 2013年版本，无任何防护 -->
```

**审计技巧**：
- 必须检查 `pom.xml`/`build.gradle` 的库版本
- 搜索库的 **Release Notes**，确认是否修复了CRLF验证
- 即使新版本，也要检查是否被 `config` 关闭了防护

```java
// 某些库可以禁用防护（反而更危险）
HttpClientBuilder.create()
    .setHttpClientConfigCallback(config -> config
        .setAllowedHeaderValue(HttpClientConfig.ALL))  // ✗ 显式允许所有值
    .build();
```

#### 技巧3：全局拦截器真伪验证

代码可能声称有拦截器防护，但需要实际验证：

```java
// ✗ 假防护1：拦截器存在但不处理该头
@Component
public class SecurityInterceptor implements ClientHttpRequestInterceptor {
    @Override
    public ClientHttpResponse intercept(HttpRequest request,
        byte[] body, ClientHttpRequestExecution execution) {
        String auth = request.getHeaders().get("Authorization");  // 只读没有修改
        logger.info("Auth: {}", auth);  // 仅日志，不过滤
        return execution.execute(request, body);
    }
}

// ✓ 真防护：实际清理了头部
@Component
public class SecurityInterceptor implements ClientHttpRequestInterceptor {
    private static final Pattern CRLF = Pattern.compile("[\r\n]");

    @Override
    public ClientHttpResponse intercept(HttpRequest request,
        byte[] body, ClientHttpRequestExecution execution) {
        request.getHeaders().forEach((name, values) -> {
            request.getHeaders().put(name,
                values.stream()
                    .map(v -> CRLF.matcher(v).replaceAll(""))
                    .collect(Collectors.toList()));
        });
        return execution.execute(request, body);
    }
}
```

**审计技巧**：
- 在拦截器类中搜索 `Pattern.compile` 或正则相关的字眼
- 检查拦截器是否**真正修改了request对象**的headers
- 仅记录日志的拦截器**不算防护**（攻击已发生）
- 需要验证拦截器是否被正确注册到HttpClient（查看Bean配置）

#### 技巧4：代理转发场景的精准判断

代理模式下最容易误报：

```java
// ✗ 真实漏洞：盲目复制所有上游请求头
@PostMapping("/proxy/**")
public ResponseEntity<?> proxyRequest(
    @RequestHeader Map<String, String> headers,
    HttpServletRequest originalRequest) {

    HttpRequest.Builder builder = HttpRequest.newBuilder();
    headers.forEach((k, v) -> {
        builder.header(k, v);  // 攻击者可伪造 "X-Admin: true"
    });
    return new ResponseEntity<>(client.send(builder.build(),
        HttpResponse.BodyHandlers.ofString()).body());
}

// ✓ 防护1：白名单仅转发必要头
final Set<String> PROXY_HEADERS = Set.of("Content-Type", "Accept", "User-Agent");
headers.forEach((k, v) -> {
    if (PROXY_HEADERS.contains(k)) {  // ✓ 白名单检查
        builder.header(k, v);
    }
});

// ✓ 防护2：转发时添加签名确保完整性
headers.forEach((k, v) -> {
    if (isProxyableHeader(k)) {
        builder.header(k, v);
    }
});
builder.header("X-Forwarded-Signature",
    hmac(headers, secretKey));  // 后端可验证完整性
```

**审计技巧**：
- 搜索 `@RequestHeader Map` 模式
- 检查是否有 **白名单检查** 或 **签名验证**
- 即使有过滤，也要检查是否是 **黑名单**（黑名单可被绕过）
- 重点：代理的安全性 = 转发时的头部限制

#### 技巧5：隐藏的格式验证伪防护

很多代码用"格式验证"来宣传防护，但可能并不充分：

```java
// ✗ 伪防护：只验证格式，无法阻止CRLF
public void setToken(String token) {
    // token匹配: /^[a-zA-Z0-9_.]+$/ 但不包含检查换行
    if (!token.matches("[a-zA-Z0-9_.]+")) {
        throw new IllegalArgumentException("Invalid token");
    }
    request.header("Authorization", token);  // ✗ 过滤不完整
}

// ✓ 真正防护：主动移除危险字符
public void setToken(String token) {
    if (!token.matches("[a-zA-Z0-9_.]+")) {
        throw new IllegalArgumentException("Invalid token");
    }
    String safe = token.replaceAll("[\r\n\0]", "");  // ✓ 双重防护
    request.header("Authorization", safe);
}
```

**审计技巧**：
- 看到 `matches(regex)` 不要以为安全，需要确认正则包含的**字符范围**
- 正则检查可以绕过CRLF的错误例子：`^[a-zA-Z0-9]+$` 在某些库中**不会匹配\r\n**，但用户已通过验证
- 正确做法：**同时** 做格式验证 + 显式移除危险字符

#### 技巧6：跨域污染链的发现

用户输入可能通过多个中间步骤到达：

```java
// 场景：用户数据先存库，再取出当作请求头
@PostMapping("/register")
public void register(@RequestParam String nickname) {  // 来源：用户输入
    userService.save(new User(nickname));  // 存入数据库
}

@GetMapping("/profile")
public void getProfile() {
    User user = userService.getCurrentUser();
    // 问题：这是真实漏洞还是误报？

    // ✗ 如果nickname直接作为请求头：真实漏洞
    request.header("X-User-Name", user.nickname);

    // ✓ 但如果数据库/ORM框架在取出时自动过滤：可能误报
    // （需要验证Hibernate/MyBatis的实现）
}
```

**审计技巧**：
- 当发现参数来自数据库，**不要假设数据库数据已安全**
- 需要追踪：数据 **入库时** 是否有过滤，**出库后** 是否有处理
- 关键问题：请求头注入漏洞 = 出库后仍无CRLF过滤
- 若入库时有过滤（如业务层的字符集限制），需要验证过滤强度

---

## Low risk

### 低风险场景判定标准

满足以下任一条件时，可评估为低风险（仍需标注并建议修复）：

1. **受限目标**
   - 请求仅发往公开只读API（无认证、无状态修改）
   - 目标服务有严格的请求头验证（会拒绝异常头）
   - 使用HTTPS且目标服务启用HSTS

2. **有限影响**
   - 注入的头部不影响业务逻辑（如User-Agent、Referer）
   - 目标API无基于头部的认证/授权机制
   - 不涉及缓存、代理等可能被中毒的中间件

3. **部分防护**
   - 请求头值有长度限制（<50字符）且有字符集检查
   - 使用的HTTP客户端库版本较新（部分库自动规范化头部）
   - 存在请求频率限制，降低批量注入风险

4. **监控完备**
   - 所有对外请求已配置日志监控
   - 异常请求头会触发告警
   - 有请求重放机制可追溯问题

### 评级建议

- **低风险 + 只读API**：优先级降低，但建议统一过滤增强防御
- **低风险 + 严格目标验证**：确认目标服务防护有效性，代码仍应加固
- **低风险 + 长度限制**：评估限制是否足够（CRLF注入可能仅需20字符）
