# Java Spring 响应头 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `response.setHeader(name, value)` - ServletResponse
- `response.addHeader(name, value)` - 添加响应头
- `HttpHeaders.set()` - Spring 响应头设置
- `ResponseEntity` 的 headers 参数
- `response.getHeaderNames()` 和 `response.setHeader()` 的组合

**快速定位核心操作：**
1. 搜索关键字：`setHeader`、`addHeader`、`HttpHeaders`、`ResponseEntity`
2. 追踪响应头值来源：`request.getParameter()`、`request.getHeader()`、`@RequestParam`
3. 检查是否存在 CRLF 过滤逻辑
4. 追踪 Servlet Filter 中的头部处理

**快速定位保护机制：**
- CRLF 检查：`if (value.contains("\r") || value.contains("\n")) throw new Exception()`
- 黑名单过滤：`value.replace("
", "").replace("", "").replace("
", "")`
- 白名单验证：`if (!value.matches("^[a-zA-Z0-9\-_.]+$")) throw Exception()`
- Spring Security 防护：检查是否启用了 HttpHeaderSecurity

**代码示例：**
```java
// 危险：用户输入直接设置为响应头
@GetMapping("/send-header")
public void sendHeader(HttpServletResponse response,
                       @RequestParam String name) {
    response.setHeader("X-Custom", name);  // 危险：未过滤 CRLF
}

// 危险：Spring ResponseEntity
@GetMapping("/response-entity")
public ResponseEntity<String> responseEntity(@RequestParam String value) {
    HttpHeaders headers = new HttpHeaders();
    headers.set("X-Data", value);  // 危险
    return new ResponseEntity<>("OK", headers, HttpStatus.OK);
}

// 危险：addHeader
@GetMapping("/add")
public void addHeader(HttpServletResponse response,
                      @RequestParam String param) {
    response.addHeader("X-Param", param);  // 危险
}
```

## Classify

**漏洞（Critical）：**
- HTTP 请求参数（Query、Form、Header）直接用于 `setHeader()`
- 无 CRLF 过滤或值验证
- 多个输入来源叠加拼接
- 响应头可被分割导致响应格式错误

**误报：**
- 响应头值完全硬编码
- Spring Security 已启用自动防护
- 框架层级已进行验证

**代码异味（Medium）：**
- 仅过滤 `
` 或 `` 之一
- 黑名单过滤但不完整
- 输入来自配置文件或数据库但未验证

## Audit Skills

**真实漏洞识别技巧：**

1. **追踪请求参数流向**
   - 关键函数：`request.getParameter()` → `response.setHeader()`
   - 特别关注：`@RequestParam`、`@RequestBody` 注解的参数
   - 查看参数是否经过拦截器（Interceptor）或过滤器（Filter）
   - 检查是否存在 Servlet 容器级别的防护

2. **识别绕过过滤的技巧**
   - 仅检查 `\r\n` 但未检查 `\n`（换行符）或 `\r`（回车符）
   - 过滤大小写敏感字符如 `%0d%0a`、`&#10;` 等编码形式
   - 检查 `replace()` 后是否可二次替换（e.g., `"a\r\nb".replace("\r\n", "")`）
   - 响应头字段名称注入（Java 版本差异）

3. **Spring 框架特性检查**
   - Spring 4.0+ 对某些头部自动进行清理（取决于版本）
   - 检查 Spring Security 版本和相关配置
   - 查看 `WebMvcConfigurer` 是否定义了拦截器
   - 分析 `RestTemplate`、`WebClient` 等客户端是否存在反向CRLF

4. **误报常见原因**
   - **硬编码值**：如 `response.setHeader("X-Version", "1.0.0")`
   - **白名单验证**：`if (!value.matches("[a-zA-Z0-9\-_.]*")) throw ...`
   - **强制类型转换**：数值型参数转换为 Int，自动过滤特殊字符
   - **框架防护**：Spring Security 的 `HttpHeaderSecurity` 已启用
   - **URL 编码**：某些框架自动解码参数，导致看似有CRLF但实际被编码

**真实案例分析：**

```java
// 真实漏洞（危险）
@GetMapping("/redirect")
public void redirect(HttpServletResponse response,
                     @RequestParam String url) {
    response.setHeader("Location", url);  // 直接设置重定向
    // 攻击：?url=http://evil.com%0dSet-Cookie:%20admin=true
}

// 明显误报（安全）
@GetMapping("/api/version")
public ResponseEntity<String> getVersion() {
    HttpHeaders headers = new HttpHeaders();
    headers.set("X-API-Version", "2.0.1");  // 硬编码，完全安全
    return new ResponseEntity<>("OK", headers, HttpStatus.OK);
}

// 隐蔽漏洞（需深入分析）
@GetMapping("/track")
public ResponseEntity<String> track(HttpServletResponse response,
                                     @RequestParam String sessionId) {
    String sanitized = sessionId.replaceAll("\r\n", "");
    response.setHeader("X-Session", sanitized);  // 风险：仅过滤CRLF组合
    // 攻击：?sessionId=abc%0dSet-Cookie:%20hack=1（纯\r可能绕过）
}

// 真实防护（安全）
@GetMapping("/safe")
public ResponseEntity<String> safe(HttpServletResponse response,
                                    @RequestParam String token) {
    if (!token.matches("[a-zA-Z0-9]{32}")) {
        throw new IllegalArgumentException("Invalid token");
    }
    response.setHeader("X-Token", token);  // 白名单验证
    return new ResponseEntity<>("OK", HttpStatus.OK);
}
```

**高级审计技巧：**

1. **容器版本识别**：检查 `web.xml` 中的版本声明，不同 Tomcat/Jetty 版本对CRLF处理不同
2. **编码层级**：区分 URL 编码、HTML 编码、Unicode 编码可能导致的绕过
3. **中间件防护**：检查 Nginx/Apache 反向代理层是否过滤响应头
4. **异常处理**：某些框架在CRLF时抛出异常，需要验证异常处理逻辑
5. **动态配置检查**：响应头值来自数据库或配置文件时，验证数据源是否可控

## Low risk

**以下情况评为低风险：**
- 响应头值完全硬编码
- 实现了严格的 CRLF 过滤和验证
- 使用白名单验证
- 响应头值来自内部系统且已验证
