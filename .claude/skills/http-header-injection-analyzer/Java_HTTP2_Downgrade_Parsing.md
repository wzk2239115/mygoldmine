# Java HTTP/2降级解析不一致

## Details

### 漏洞成因与常见模式

HTTP/2使用伪头字段（pseudo-header）如`:method`、`:path`等，在降级到HTTP/1.1时，若服务器/代理对头字段的规范化处理不一致，可导致请求走私、认证绕过、缓存中毒等攻击。Java应用中Tomcat、Jetty、Netty等服务器的H2C降级行为是审计重点。

#### 模式1：伪头字段与真实头混用

```java
// ✗ 漏洞场景：应用信任HTTP/2伪头字段，但未验证降级后的真实头
@GetMapping("/**")
public ResponseEntity<String> handleRequest(HttpServletRequest request) {
    String path = request.getHeader(":path");  // HTTP/2伪头
    if (path == null) {
        path = request.getRequestURI();  // HTTP/1.1回退
    }
    // 攻击: HTTP/2请求同时包含 :path=/admin 和 Host: evil.com
    // 降级后可能导致path解析不一致
    return processRequest(path);
}
```

#### 模式2：头字段大小写不一致

```java
// ✗ 漏洞：HTTP/2头字段全小写，降级后大小写处理不一致
@Component
public class AuthFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                   HttpServletResponse response,
                                   FilterChain filterChain) {
        String auth = request.getHeader("Authorization");  // 大小写敏感
        if (auth == null) {
            auth = request.getHeader("authorization");  // 小写检查
        }
        // 攻击: HTTP/2发送 authorization:token，降级后可能被不同中间件解析为不同值
        validateAuth(auth);
        filterChain.doFilter(request, response);
    }
}
```

#### 模式3：重复头字段处理

```java
// ✗ 漏洞：HTTP/2不允许重复伪头，但降级后可能产生重复头
@PostMapping("/api")
public String handleApi(HttpServletRequest request) {
    // HTTP/2: :method POST, 降级后可能出现: Method: POST 和 Method: GET
    String method = request.getMethod();  // 取第一个还是最后一个？

    Enumeration<String> contentTypes = request.getHeaders("Content-Type");
    // 降级后可能存在多个Content-Type头，取值不一致
    String contentType = contentTypes.hasMoreElements() ? contentTypes.nextElement() : "";

    return processRequest(method, contentType);
}
```

#### 模式4：Transfer-Encoding与Content-Length冲突

```java
// ✗ 漏洞：HTTP/2禁止Content-Length，降级后可能产生TE:CL走私
@PostMapping("/proxy")
public String proxyRequest(@RequestBody String body, HttpServletRequest request) {
    // HTTP/2请求无Content-Length，但降级后代理可能添加
    String contentLength = request.getHeader("Content-Length");
    String transferEncoding = request.getHeader("Transfer-Encoding");

    // 不同服务器对TE和CL优先级处理不一致，可能导致请求走私
    HttpRequest proxyReq = HttpRequest.newBuilder()
        .uri(URI.create("http://backend"))
        .header("Content-Length", contentLength)
        .POST(HttpRequest.BodyPublishers.ofString(body))
        .build();

    return HttpClient.newHttpClient().send(proxyReq,
        HttpResponse.BodyHandlers.ofString()).body();
}
```

#### 模式5：Host头与:authority不一致

```java
// ✗ 漏洞：HTTP/2使用:authority，降级后可能与Host头不一致
@WebServlet("/admin")
public class AdminServlet extends HttpServlet {
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        String host = req.getHeader("Host");
        String serverName = req.getServerName();  // 可能来自:authority

        // 攻击: HTTP/2 {:authority=admin.internal, Host=evil.com}
        // 降级后不同组件可能读取不同的Host值
        if (isAuthorized(host)) {
            // 授权检查基于Host，但实际路由基于:authority
            resp.getWriter().write("Admin panel");
        }
    }
}
```

#### 安全实现参考

```java
// ✓ 安全：统一规范化头字段处理
@Component
public class SecureH2CFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                   HttpServletResponse response,
                                   FilterChain filterChain) {
        // ✓ 规范化处理：拒绝HTTP/2伪头字段在HTTP/1.1中出现
        if (request.getHeader(":path") != null ||
            request.getHeader(":method") != null) {
            response.setStatus(400);
            return;
        }

        // ✓ 检查重复头字段
        if (Collections.list(request.getHeaders("Host")).size() > 1) {
            response.setStatus(400);
            return;
        }

        // ✓ 禁止TE与CL共存
        if (request.getHeader("Transfer-Encoding") != null &&
            request.getHeader("Content-Length") != null) {
            response.setStatus(400);
            return;
        }

        filterChain.doFilter(request, response);
    }
}
```

### 审计检查清单

| 优先级 | 检查项 | 审计方法 | 审计等级 |
|--------|--------|---------|----------|
| **P0** | 伪头字段直接使用 | 搜索 `getHeader(":path"\|":method"\|":authority")`，检查是否规范化 | **L3** |
| **P0** | Host与:authority混用 | 搜索 `getHeader("Host")` + `getServerName()`，检查一致性 | **L3** |
| **P0** | TE与CL共存 | 搜索 `Transfer-Encoding` + `Content-Length` 同时设置 | **L3-L4** |
| **P1** | 重复头字段处理 | 搜索 `getHeaders()` + 枚举遍历，检查取第一个还是最后一个 | **L3** |
| **P1** | 头字段大小写敏感 | 搜索 `getHeader` + 字符串比较，检查是否统一大小写 | **L2** |
| **P2** | 代理转发降级 | 搜索 `HttpClient\|RestTemplate` + H2C配置，检查头规范化 | **L4** |
| **P3** | 服务器配置 | 检查 `server.xml/application.yml` H2C启用配置 | **L1** |

### 审计等级判定

| 等级 | 代码特征 | 审计策略 |
|------|---------|---------|
| **L0** | 应用未启用HTTP/2或H2C | 快速跳过，检查配置文件确认 |
| **L1** | 启用HTTP/2但不处理伪头字段 | 关键词扫描：搜索 `:path/:method/:authority` |
| **L2** | 单文件内有头字段处理 | 跳读：检查是否有大小写规范化、重复检查 |
| **L3** | 跨层头字段传递（Filter→Controller） | 逐行读：追踪头字段在各层的处理逻辑 |
| **L4** | 代理/网关场景降级处理 | 跨模块追踪：检查前置代理配置与应用协议协商逻辑 |

---

## 审计专业技巧

### 真实漏洞与误报的区分经验

#### 1. 协议降级链路判定

**真实漏洞特征**：
- 应用明确启用HTTP/2（`server.http2.enabled=true` 或 Connector 配置 `protocol="org.apache.coyote.http2.Http2Protocol"`）
- 同时处理HTTP/1.1请求（存在不同的头字段处理逻辑）
- 前置代理（Nginx/HAProxy/ALB）与应用间通信使用H2C（明文HTTP/2）

**排查方法**：
```bash
# 检查Tomcat配置
grep -r "protocol=" server.xml | grep -i "http2"
# 检查Spring Boot配置
grep -r "http2.enabled\|h2.enabled" application.yml application.properties
# 检查Netty配置
grep -r "Http2FrameCodec\|Http2ServerUpgradeCodec" *.java
```

**误报常见情况**：
- 配置中启用HTTP/2，但生产环境实际由前置代理处理全部降级，应用只收到HTTP/1.1
- 代码有旧的HTTP/2头字段兼容代码，但实际从未触发（通过前置代理规范化）

#### 2. 头字段处理一致性检测

**真实漏洞判定**：
```java
// ✗ 危险：同时提取两种不同协议的头，取值可能不同
String path1 = request.getHeader(":path");       // HTTP/2伪头
String path2 = request.getRequestURI();          // HTTP/1.1路径
String path3 = request.getHeader("X-Original-Path"); // 代理添加的头

if (path1 != null && !path1.equals(path2)) {
    // 这可能被利用：两个路径值不同
    processPath(path1);  // 但实际只应处理path2或path3
}
```

**审计技巧**：
1. 跟踪每个头字段的"来源"：HTTP/2伪头 vs HTTP/1.1真实头 vs 代理注入头
2. 检查是否存在"选择性信任"：某些代码路径信任 `:path`，其他路径信任 `getRequestURI()`
3. 追踪头字段在下游的使用：`SecurityContextHolder.setAuthentication()` 等关键操作

**常见误报**：
- 头字段提取代码有两套实现，但在实际执行流中只有一套被触发
- 代码存在"防御性编程"（如 `if (path == null) path = fallback`），实际运行无安全风险

#### 3. 中间件拦截与修复识别

**标准的安全实现特征**：
```java
// 如果存在以下特征，大概率已修复风险
@Component
public class Http2NormalizationFilter implements Filter {
    @Override
    public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain) {
        HttpServletRequest httpReq = (HttpServletRequest) req;

        // ✓ 关键特征1：明确拒绝HTTP/1.1中的HTTP/2伪头
        for (String pseudoHeader : Arrays.asList(":method", ":path", ":authority", ":scheme")) {
            if (httpReq.getHeader(pseudoHeader) != null) {
                throw new HttpClientErrorException(HttpStatus.BAD_REQUEST);
            }
        }

        // ✓ 关键特征2：检查重复头字段
        String host = httpReq.getHeader("Host");
        if (Collections.list(httpReq.getHeaders("Host")).size() > 1) {
            throw new HttpClientErrorException(HttpStatus.BAD_REQUEST);
        }

        // ✓ 关键特征3：TE和CL冲突检查
        String te = httpReq.getHeader("Transfer-Encoding");
        String cl = httpReq.getHeader("Content-Length");
        if (te != null && cl != null && !cl.matches("\\d+")) {
            throw new HttpClientErrorException(HttpStatus.BAD_REQUEST);
        }

        chain.doFilter(req, resp);
    }
}
```

**识别方法**：
- 搜索全局Filter/Interceptor中是否有伪头字段的明确拒绝逻辑
- 检查 Spring Security 或自定义授权过滤器是否在业务逻辑前执行了头字段规范化
- 查看版本更新日志中是否明确提及H2C降级修复

#### 4. 代理场景的风险差异

**高风险代理配置**：
```
客户端 --HTTP/2--> [Nginx/Envoy] --H2C--> [Java应用]
         (降级)     (内网传输)

风险：Nginx到应用间是明文HTTP/2降级到HTTP/1.1，应用若处理不当可被利用
```

**低风险代理配置**：
```
客户端 --HTTP/2--> [AWS ALB/CLB] --HTTP/1.1--> [Java应用]
         (TLS)      (规范化处理)   (干净)

风险低：ALB进行全面规范化，应用只收到标准HTTP/1.1请求
```

**判定标准**：
- 前置代理是否进行了"完整降级规范化"（不仅转换协议，更要规范化头字段）
- 应用与代理间的连接是否加密（TLS）
- 应用是否仍包含H2C监听端口（`listenAddress=0.0.0.0:8080 protocol=h2c`）

#### 5. 业务影响度评估

**关键业务逻辑检查清单**：

| 业务逻辑点 | 审计方法 | 真实漏洞特征 |
|-----------|---------|-----------|
| **认证** | 搜索 `Authentication\|Principal\|getHeader("Authorization")` | 直接读取头字段判断身份，无规范化 |
| **授权** | 搜索 `@Secured\|@PreAuthorize` + 头字段作为参数 | 权限判定基于可被降级篡改的头 |
| **路由** | 搜索 `@RequestMapping\|@GetMapping` + `getHeader(":path")` | 路由决策依赖伪头字段 |
| **缓存** | 搜索 `Cache-Control\|ETag\|setHeader` + Host/Origin | 缓存键未规范化，可导致跨用户缓存污染 |
| **日志** | 搜索 `logger.info\|MDC.put` + 头字段 | 仅日志审计风险，业务逻辑无影响 |

#### 6. 版本与已知漏洞对应

**需要特别审计的版本范围**：

| 组件 | 易受攻击版本范围 | 修复版本 | 审计优先级 |
|-----|----------------|--------|---------|
| Tomcat | 9.0.0 - 9.0.69 | 9.0.70+ | **L4** |
| Jetty | 9.0 - 11.0.12 | 11.0.13+ | **L4** |
| Netty | 4.1.0 - 4.1.87 | 4.1.88+ | **L3** |
| Spring Boot | 2.6.0 - 2.7.x | 3.0.0+ | **L2** |

**审计建议**：
- 若使用易受攻击版本，则直接判定为 P0 漏洞，不需过度论证
- 若已更新到修复版本，仍需检查应用代码是否有"额外的"不一致处理逻辑

---

## Classify

### 确认漏洞的标准

1. **协议降级路径存在**：应用支持HTTP/2且存在H2C降级或前置有HTTP/2代理
2. **头字段处理不一致**：代码中对HTTP/2伪头字段与HTTP/1.1真实头字段处理逻辑不同
3. **可利用性**：攻击者可通过精心构造的HTTP/2请求触发降级解析差异，影响业务逻辑

### 判定为误报的情况

1. **纯HTTP/1.1应用**：应用和前置代理均不支持HTTP/2，无降级场景
2. **统一规范化**：存在全局Filter对所有协议的头字段进行统一规范化处理
3. **服务器版本安全**：Tomcat 9.0.70+、Jetty 11.0.13+等已修复已知H2C降级漏洞
4. **无关键业务逻辑**：头字段仅用于日志/监控，不影响认证/授权/路由

### 代码异味识别

1. **假设协议一致**：代码注释"仅支持HTTP/1.1"，但配置中启用了HTTP/2
2. **不完整检查**：仅检查 `:path`，未检查 `:method/:authority/:scheme`
3. **取值顺序未明确**：使用 `getHeader()` 获取可能重复的头，未明确取第一个还是最后一个
4. **大小写不一致**：部分代码使用 `Authorization`，部分使用 `authorization`

---

## Low risk

### 低风险场景判定标准

满足以下任一条件时，可评估为低风险（仍需标注并建议修复）：

1. **有限H2C暴露**
   - 仅内网环境启用H2C，外部入口使用HTTPS + TLS ALPN
   - 前置负载均衡器（如AWS ALB）统一处理HTTP/2到HTTP/1.1降级
   - 应用层不直接暴露HTTP/2端口

2. **服务器版本较新**
   - Tomcat 10.1+、Jetty 12+、Netty 4.1.90+（包含H2C降级修复）
   - Spring Boot 3.0+（默认配置更严格）
   - 已部署HTTP/2规范性检查中间件

3. **业务逻辑不依赖头字段**
   - 认证基于JWT（放在请求体），不依赖头字段
   - 路由由Spring MVC注解决定，不依赖 `:path` 解析
   - 无代理转发场景，应用为最终处理方

4. **监控与检测**
   - 启用HTTP/2帧级别日志监控
   - 配置异常头字段告警（如 `:path` 在HTTP/1.1请求中出现）
   - 有流量重放测试覆盖H2C降级场景

### 评级建议

- **低风险 + 内网H2C**：外部入口配置审查，确保无绕过路径
- **低风险 + 新版本服务器**：代码层面仍应添加防御性编程
- **低风险 + 不依赖头字段**：优先级降低，但建议统一规范化处理头字段
