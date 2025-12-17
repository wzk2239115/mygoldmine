# Java RestTemplate 用户可控 URL 请求

## 漏洞成因
RestTemplate 直接使用用户输入的 URL 发起 HTTP 请求，未对目标地址进行白名单验证或协议/内网地址过滤，导致攻击者可访问内网服务、云元数据接口或使用危险协议读取本地文件。

---

## Details

### 代码示例
```java
// 危险模式1：直接传递用户输入
@RestController
public class ProxyController {
    @Autowired
    private RestTemplate restTemplate;
    
    @GetMapping("/fetch")
    public String fetchUrl(@RequestParam String url) {
        String result = restTemplate.getForObject(url, String.class);  // 危险：url完全可控
        return result;
    }
}

// 危险模式2：URL拼接
@PostMapping("/api/proxy")
public ResponseEntity<?> proxyRequest(@RequestBody Map<String, String> params) {
    String targetUrl = "http://" + params.get("host") + "/api/" + params.get("path");
    return restTemplate.exchange(targetUrl, HttpMethod.POST, entity, String.class);
}

// 危险模式3：使用UriComponentsBuilder
public String fetchData(String baseUrl, String endpoint) {
    URI uri = UriComponentsBuilder.fromHttpUrl(baseUrl)  // baseUrl可控
                                  .path(endpoint)
                                  .build().toUri();
    return restTemplate.getForEntity(uri, String.class).getBody();
}
```

### 快速定位核心操作 (L1-L3)
- **L1 关键词扫描**：
  - 搜索 `RestTemplate` 的请求方法：`getForObject`、`getForEntity`、`postForObject`、`exchange`、`execute`
  - 搜索 URL 构造：`UriComponentsBuilder`、`fromHttpUrl`、`fromUriString`
  - 搜索依赖注入：`@Autowired RestTemplate`、`new RestTemplate()`
- **L2 跳读**：
  - 定位到请求方法的第一个参数（URL/URI位置）
  - 向上追溯该参数来源：`@RequestParam`、`@PathVariable`、`@RequestBody` 字段、JSON反序列化对象的属性
  - 检查是否存在 `String.format`、字符串拼接（`+`）、`concat` 等 URL 组装操作
- **L3 逐行读**：
  - 确认 URL 参数是否直接来自用户输入（HTTP 请求参数、请求体、Header）
  - 检查 `UriComponentsBuilder` 的 `fromHttpUrl`/`fromUriString` 方法的参数来源
  - 检查是否使用 `URI.create()` 或 `new URI()` 并追踪构造参数

### 快速定位保护机制 (L2-L4)
- **L2 跳读**：
  - 检查请求方法前是否有 `if` 条件校验：`startsWith`、`contains`、`matches`、`equals`
  - 搜索黑名单关键词：`127.0.0.1`、`localhost`、`0.0.0.0`、`192.168`、`10.`、`169.254`
  - 检查是否调用了 URL 解析方法：`URL.getHost()`、`URI.getHost()`、`getScheme()`
- **L3 逐行读**：
  - 检查协议限制：是否验证 `url.startsWith("http://")` 或 `url.startsWith("https://")`
  - 检查域名白名单：是否与预定义的 `allowedDomains`、`ALLOWED_HOSTS` 进行比对
  - 检查 IP 校验：是否调用 `InetAddress.getByName()` 后判断 `isLoopbackAddress()`、`isSiteLocalAddress()`、`isLinkLocalAddress()`
  - 检查是否配置了自定义 `ClientHttpRequestFactory` 或 `HttpClient` 拦截器
- **L4 跨模块追踪**：
  - 追踪自定义工具类：`URLValidator.validate()`、`SecurityUtils.checkUrl()`、`SafeRestTemplate` 等封装类的内部实现
  - 检查是否有全局拦截器：`ClientHttpRequestInterceptor` 实现类中的 `intercept` 方法
  - 检查配置类中 RestTemplate Bean 的定义，是否配置了 `RequestFactory` 或自定义 `HttpClient` 的连接管理器
  - 追踪 Spring Security 配置，检查是否有 URL 过滤规则

---

## Classify

### 漏洞判定
- URL 的 scheme/host/port/path 任一部分完全来自用户输入且无校验 → **确认漏洞**
- 仅有黑名单过滤但可绕过（如禁止 `127.0.0.1` 但允许 `127.1`、`0x7f.0.0.1`、`2130706433`） → **确认漏洞**
- 协议未限制，可使用 `file://`、`jar://`、`netdoc://` 等 → **确认漏洞**
- URL 拼接逻辑复杂但 host/scheme 部分可控 → **确认漏洞**

### 误报判定
- URL 完全来自硬编码常量、不可变配置文件（application.properties 且非外部可修改） → **误报**
- URL 从数据库白名单表中查询（用户仅提供 ID 索引） → **误报**
- 严格的域名白名单且实现正确（精确匹配或严格的后缀校验，防止 `evil.com?x=allowed.com` 绕过） → **误报**
- 仅路径部分可控且 base URL 固定，且路径已规范化处理 → **误报**

### 代码异味
- 使用正则但未锚定或边界不严格（如 `matches(".*trusted\\.com.*")` 可被 `evil.com/trusted.com` 绕过） → **需进一步测试**
- 校验在 if-else 多个分支中存在遗漏 → **潜在风险**
- URL 校验后又被重新拼接、编码或格式化 → **需追踪完整数据流**
- 使用 `URLEncoder.encode()` 但未正确处理特殊字符 → **可能可绕过**
- 依赖前端校验但后端无验证 → **需确认后端是否可直接调用**

---

## Low risk

### 低风险场景
- **仅公网白名单资源**：URL 严格限定为特定公网域名（CDN、第三方公开 API），且域名列表短且固定
- **无敏感内网环境**：服务部署在容器/云环境且网络策略已隔离，无法访问内网或云元数据服务
- **仅 HEAD/OPTIONS 请求**：使用 `headForHeaders()` 仅获取元数据，不读取响应体，且未启用 `setFollowRedirects`
- **响应不返回给用户**：仅做连通性检查或健康检测，不将响应内容、状态码、Header 暴露给调用方
- **严格超时与重试限制**：连接超时 < 2秒，读取超时 < 5秒，且无自动重试机制
- **请求已全量审计**：所有请求 URL 完整记录到审计日志，具备实时告警和溯源能力
- **需高权限触发**：接口需要管理员权限或特殊 Token，且权限体系无提升漏洞
- **协议限定 HTTPS 且证书校验严格**：未禁用证书验证（未设置 `TrustAllStrategy`、`NoopHostnameVerifier`）

### 注意事项
即使满足低风险条件，仍应在审计报告中说明：该问题虽影响有限，但违反最小权限原则和纵深防御策略，建议修复。