# Java Spring响应头CRLF注入

## Details

### 漏洞成因与常见模式

Spring MVC/WebFlux在构造响应头时，若使用用户输入未过滤CRLF，可导致HTTP响应拆分。虽然Spring 5.3+对部分场景有自动防护，但自定义响应处理、WebFlux响应式编程等场景仍存在风险。

#### 模式1：ResponseEntity自定义头注入

```java
// ✗ 漏洞：ResponseEntity直接使用用户输入
@GetMapping("/api/data")
public ResponseEntity<String> getData(@RequestParam String lang) {
    return ResponseEntity.ok()
        .header("Content-Language", lang)  // 未过滤CRLF
        .body("data");
    // 攻击: ?lang=en%0d%0aSet-Cookie:admin=true
}
```

#### 模式2：HttpServletResponse直接设置

```java
// ✗ 漏洞：Spring Controller中直接操作Servlet API
@GetMapping("/download")
public void downloadFile(@RequestParam String filename, HttpServletResponse response) {
    response.setHeader("Content-Disposition",
        "attachment; filename=" + filename);  // 未过滤
    // 攻击: ?filename=file.txt%0d%0aX-XSS-Protection:0
}
```

#### 模式3：WebFlux响应式头注入

```java
// ✗ 漏洞：WebFlux ServerResponse未过滤
@Bean
public RouterFunction<ServerResponse> route() {
    return route(GET("/api"), request -> {
        String customHeader = request.queryParam("header").orElse("");
        return ServerResponse.ok()
            .header("X-Custom", customHeader)  // 未验证
            .bodyValue("data");
    });
}
```

#### 模式4：HandlerInterceptor添加头

```java
// ✗ 漏洞：拦截器全局添加用户相关头
@Component
public class CustomInterceptor implements HandlerInterceptor {
    @Override
    public void postHandle(HttpServletRequest request,
                          HttpServletResponse response,
                          Object handler, ModelAndView modelAndView) {
        String userId = request.getParameter("user_id");
        response.setHeader("X-User-ID", userId);  // 未过滤
    }
}
```

#### 模式5：重定向视图注入

```java
// ✗ 漏洞：重定向URL未验证
@GetMapping("/login")
public String login(@RequestParam(required = false) String returnUrl) {
    // 认证逻辑...
    return "redirect:" + returnUrl;  // returnUrl可包含CRLF
    // 攻击: ?returnUrl=/home%0d%0aSet-Cookie:session=hijacked
}
```

#### 安全实现参考

```java
// ✓ 安全：CRLF过滤 + ResponseEntity
@RestController
public class SecureController {
    private static final Pattern CRLF_PATTERN = Pattern.compile("[\r\n]");

    private String sanitize(String value) {
        return value == null ? "" : CRLF_PATTERN.matcher(value).replaceAll("");
    }

    @GetMapping("/api/data")
    public ResponseEntity<String> getData(@RequestParam String lang) {
        String safeLang = sanitize(lang);

        // ✓ 额外白名单验证
        if (safeLang.matches("^[a-z]{2}(-[A-Z]{2})?$")) {
            return ResponseEntity.ok()
                .header("Content-Language", safeLang)
                .body("data");
        }
        return ResponseEntity.badRequest().build();
    }
}
```

### 审计检查清单

| 优先级 | 检查项 | 审计方法 | 审计等级 |
|--------|--------|---------|----------|
| **P0** | ResponseEntity.header | 搜索 `ResponseEntity.*header(` + `@RequestParam/@PathVariable` | **L2** |
| **P0** | HttpServletResponse.setHeader | 搜索 `response.setHeader` + 参数来源 | **L2** |
| **P0** | redirect视图 | 搜索 `"redirect:"` + 字符串拼接，检查URL验证 | **L2** |
| **P1** | ServerResponse.header | 搜索 `ServerResponse.*header` + `queryParam/pathVariable` | **L2-L3** |
| **P1** | HandlerInterceptor头处理 | 搜索 `implements HandlerInterceptor` + `setHeader` | **L3-L4** |
| **P2** | ResponseBodyAdvice | 搜索 `@ControllerAdvice` + `ResponseBodyAdvice` + 头处理 | **L4** |
| **P3** | 自定义HttpMessageConverter | 搜索 `HttpMessageConverter` 实现 + 头设置 | **L4** |

### 审计等级判定

| 等级 | 代码特征 | 审计策略 |
|------|---------|---------|
| **L0** | 响应头全部来自配置/常量 | 快速跳过，确认无请求参数 |
| **L1** | 响应头来自数据库查询结果 | 关键词扫描：确认非直接用户输入 |
| **L2** | Controller内直接使用请求参数 | 跳读：检查 `header()` 调用前是否有过滤 |
| **L3** | Service层构造响应头值 | 逐行读：追踪方法返回值来源 |
| **L4** | 拦截器/切面全局处理 | 跨模块追踪：检查 `@ControllerAdvice/HandlerInterceptor` 链 |

---

## Classify

### 确认漏洞的标准

1. **用户输入可达**：响应头值直接或间接来自 `@RequestParam/@PathVariable/@RequestHeader`
2. **无CRLF过滤**：代码未调用 `replaceAll("[\r\n]", "")` 或正则过滤
3. **框架版本风险**：Spring < 5.3 或使用了绕过保护的方式（直接操作Servlet API、WebFlux特定场景）

### 判定为误报的情况

1. **框架自动保护**：Spring 5.3+ 的 `ResponseEntity` 在特定场景自动拒绝CRLF（需验证具体场景）
2. **全局过滤器**：存在 `@ControllerAdvice` 统一对所有响应头过滤
3. **白名单枚举**：响应头值仅允许预定义枚举（使用 `@Validated` + 自定义验证器）
4. **内部API**：接口仅供内部前端调用，且前端已严格验证（需确认调用链）

### 代码异味识别

1. **不完整过滤**：仅过滤 `\n` 未过滤 `\r`
2. **Spring版本假设**：注释"Spring自动处理"，但未验证版本或使用场景
3. **混合使用**：部分Controller使用 `ResponseEntity`（安全），部分直接操作 `HttpServletResponse`（风险）
4. **过滤位置错误**：在日志记录时过滤，但设置响应头时未过滤

---

## Audit Tips

### 审计专业技巧

#### 1. 响应头来源追踪方法论

**三步追踪法**：
- **第一步**：定位所有 `.header(key, value)` 或 `.setHeader(key, value)` 调用
- **第二步**：回溯value的来源（是否包含RequestParam/PathVariable/Header）
- **第三步**：检查value在到达header()前的处理链（过滤、转换、查询）

**工具支持**：IDE的"Find Usage"追踪参数流，或SAST工具"污点追踪"报告

#### 2. 框架版本特定审计

| Spring版本 | 风险场景 | 审计重点 |
|-----------|--------|--------|
| < 5.2 | 全部直接使用Servlet API | 严格审计所有setHeader调用 |
| 5.2-5.3 | ResponseEntity限制CRLF，但Servlet API无保护 | 检查是否混用两个API |
| ≥ 5.3 | ResponseEntity自动过滤，WebFlux仍需注意 | 关注非ResponseEntity的头设置 |
| WebFlux | ServerResponse的header()在高版本保护有限 | 逐个排查reactive路由 |

**快速版本判定**：
```bash
# 在pom.xml/build.gradle中查看
# Spring Framework版本 vs Spring Boot版本对应关系
# Spring Boot 3.0+ → Spring Framework 6.0+（自动过滤更激进）
```

#### 3. 真实漏洞vs误报的分类识别

**真实漏洞的必要充分条件**：
1. ✅ 用户输入可达（RequestParam/PathVariable/Header）
2. ✅ 无CRLF过滤（或过滤不完整）
3. ✅ 涉及关键安全头：`Set-Cookie`、`Location`、`Authorization`

**常见误报案例分析**：

**误报案例1：数据库存储的头值**
```java
@GetMapping("/api/user")
public ResponseEntity<User> getUser(@RequestParam Long id) {
    User user = userRepository.findById(id);  // 来自数据库
    return ResponseEntity.ok()
        .header("X-User-Role", user.getRole())  // ✓ 非直接用户输入
        .body(user);
}
// 判定：✓ 低风险。虽然来自参数查询，但value来自数据库存储而非请求
// 注意：若getRole()未做过滤，理论上恶意管理员可修改数据库注入，但审计关注点应在用户侧输入
```

**误报案例2：枚举类型过滤**
```java
public enum HeaderValue {
    LANG_EN("en"), LANG_ZH("zh"), LANG_ES("es");
    private String value;
}

@GetMapping("/api")
public ResponseEntity<String> getData(@RequestParam HeaderValue lang) {
    return ResponseEntity.ok()
        .header("Content-Language", lang.getValue())  // ✓ 枚举限制
        .body("data");
}
// 判定：✓ 安全。Spring @RequestParam自动反序列化，非法值直接返回400
```

**误报案例3：Interceptor中的受控头**
```java
@Component
public class TraceIdInterceptor implements HandlerInterceptor {
    @Override
    public void postHandle(HttpServletRequest request, HttpServletResponse response,
                          Object handler, ModelAndView modelAndView) {
        String traceId = MDC.get("traceId");  // ✓ 来自内部生成
        response.setHeader("X-Trace-ID", traceId);  // 非直接用户输入
    }
}
// 判定：✓ 安全。traceId由应用内部生成（UUID/UUID.randomUUID()）
// 但需验证：MDC是否被外部污染（如某个filter中被设置）
```

**真实漏洞案例1：重定向头注入**
```java
@GetMapping("/oauth/callback")
public String handleCallback(@RequestParam String redirect_uri) {
    return "redirect:" + redirect_uri;  // ✗ 直接拼接
}
// 攻击：/oauth/callback?redirect_uri=/home%0d%0aSet-Cookie:token=hijacked
// 判定：✗ 高风险。Location头可被控制
```

**真实漏洞案例2：Content-Disposition注入（文件下载）**
```java
@GetMapping("/download")
public ResponseEntity<byte[]> download(@RequestParam String filename) {
    return ResponseEntity.ok()
        .header("Content-Disposition", "attachment;filename=" + filename)  // ✗ 无验证
        .body(fileContent);
}
// 攻击：?filename=test.txt%0d%0aX-XSS-Protection:0
// 判定：✗ 高风险。虽然是下载场景，但CRLF注入本质未被杜绝
```

#### 4. 审计现场检查技巧

**技巧1：响应头池化检查**
```java
// 搜索这些模式
@GetMapping
@PostMapping
public ResponseEntity<...> method(...) {
    ResponseEntity.ok()
        .header(...  // 立即看下一行
        .header(...  // 是否存在多个header调用
        .body(...);
}
// 发现多个header → 逐个检查每个的value来源
```

**技巧2：WebFlux链式调用**
```
// 在router函数中搜索
route(GET("/endpoint"), request ->
    ServerResponse.ok()
        .header(key,
            request.queryParam("something")  // ← 直接在这里？
                .orElse("default"))
        .bodyValue(...)
```

**技巧3：Spring版本快速识别**
```bash
# 1. 查看pom.xml最高层
<spring-boot.version>2.7.0</spring-boot.version>  # → Spring 5.3.x
<spring-boot.version>3.0.0</spring-boot.version>  # → Spring 6.0.x

# 2. 若有混乱，看source:
private static final String SPRING_VERSION = SpringFramework.getVersion();
```

**技巧4：自定义过滤器的效果验证**
```java
// 过滤器代码看起来这样：
private String sanitizeHeader(String value) {
    return value.replaceAll("[\\r\\n]", "");  // ✓ 正确写法
}

// 但这样是错的：
private String sanitizeHeader(String value) {
    return value.replace("\n", "").replace("\n", "");  // ✗ typo：两次replace相同
    // 或仅replace("\n")，漏掉\r
}
```

#### 5. 误报降级判定的审计证据收集

审计时若怀疑误报，需要记录以下证据：

| 证据 | 如何收集 |
|------|--------|
| 框架版本 | pom.xml中读取spring-boot-starter-web版本 |
| 过滤实现 | grep出现的sanitize/filter方法，检查正则 |
| 调用链完整性 | 使用IDE追踪参数到header()的全路径 |
| WAF规则 | 查询运维文档或web server配置（nginx.conf/Apache httpd.conf） |
| 头的安全等级 | 判断该头是否涉及认证、授权、跨域（高危）还是仅展示（低危） |

#### 6. 常见绕过模式识别

**绕过1：Unicode/双编码**
```java
// 审计时需要检查：过滤器是否只处理ASCII编码
String sanitized = value.replaceAll("[\\r\\n]", "");
// 若value包含 %0d（编码形式），replaceAll可能无效
// 需要URLDecode后再过滤
```

**绕过2：异常处理中的头设置**
```java
@ExceptionHandler(Exception.class)
public ResponseEntity<ErrorResponse> handleException(Exception ex) {
    return ResponseEntity.status(500)
        .header("X-Error-Details", ex.getMessage())  // ✗ getMessage()未过滤
        .body(new ErrorResponse());
}
```

**绕过3：多个框架混用**
```
// Spring MVC controller中调用了
response.setHeader(...)  // Servlet API，无Spring保护
// vs
ResponseEntity.ok().header(...)  // Spring保护的API
```

---

---

## Low risk

### 低风险场景判定标准

满足以下任一条件时，可评估为低风险（仍需标注并建议修复）：

1. **Spring版本防护**
   - Spring Framework 5.3+ 且仅使用 `ResponseEntity` API
   - 未直接调用 `HttpServletResponse.setHeader`
   - 未使用 `redirect:` 拼接用户输入

2. **受限输入**
   - 响应头值来自有限字符集（仅字母数字）
   - 使用 `@Pattern` 注解验证输入格式
   - 输入长度严格限制（<20字符）

3. **多层防护**
   - WAF规则拦截 `%0d%0a` 编码
   - 反向代理（Nginx）配置 `ignore_invalid_headers on`
   - 应用启用 `server.error.include-message=never`（减少信息泄露）

4. **业务影响有限**
   - 响应头仅用于客户端展示（Content-Language、X-Request-ID）
   - 不涉及认证/授权相关头（Set-Cookie、Authorization）
   - 应用无共享缓存，无中毒风险

### 评级建议

- **低风险 + Spring 5.3+**：确认所有响应头设置使用 `ResponseEntity`，避免Servlet API
- **低风险 + 有WAF**：代码层仍应修复，不应依赖外部防护
- **低风险 + 字符集限制**：评估正则是否足够严格（`.` 可能匹配CRLF）
