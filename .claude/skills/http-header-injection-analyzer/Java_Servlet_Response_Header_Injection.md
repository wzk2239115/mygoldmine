# Java Servlet响应头CRLF注入

## Details

### 漏洞成因与常见模式

HTTP响应头以CRLF（`\r\n`）作为行分隔符。若用户输入未经过滤直接拼接到响应头，攻击者可注入`\r\n\r\n`实现HTTP响应拆分，导致XSS、缓存中毒、会话劫持等攻击。

#### 模式1：直接设置响应头值

```java
// ✗ 漏洞：用户输入直接设置响应头
@WebServlet("/set-header")
public class HeaderServlet extends HttpServlet {
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        String lang = req.getParameter("lang");
        resp.setHeader("Content-Language", lang);  // 未过滤CRLF
        // 攻击: ?lang=en%0d%0aContent-Length:0%0d%0a%0d%0a<script>alert(1)</script>
    }
}
```

#### 模式2：重定向Location头注入

```java
// ✗ 漏洞：未过滤的重定向URL
@WebServlet("/redirect")
public class RedirectServlet extends HttpServlet {
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        String url = req.getParameter("url");
        resp.setHeader("Location", url);
        resp.setStatus(302);
        // 攻击: ?url=http://example.com%0d%0aSet-Cookie:admin=true
    }
}
```

#### 模式3：Content-Disposition文件名注入

```java
// ✗ 漏洞：文件名未过滤
@GetMapping("/download")
public void downloadFile(HttpServletRequest req, HttpServletResponse resp) {
    String filename = req.getParameter("filename");
    resp.setHeader("Content-Disposition", "attachment;filename=" + filename);
    // 攻击: ?filename=file.txt%0d%0aX-Injected:malicious
}
```

#### 模式4：自定义响应头注入

```java
// ✗ 漏洞：动态添加响应头
@RestController
public class ApiController {
    @GetMapping("/api")
    public ResponseEntity<String> getData(
        @RequestHeader("X-Custom") String customHeader) {
        return ResponseEntity.ok()
            .header("X-Response-ID", customHeader)  // 未验证用户输入
            .body("data");
    }
}
```

#### 模式5：Cookie值注入

```java
// ✗ 漏洞：Cookie值未过滤
@WebServlet("/set-cookie")
public class CookieServlet extends HttpServlet {
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        String value = req.getParameter("value");
        Cookie cookie = new Cookie("user", value);  // Servlet 3.0前版本不验证
        resp.addCookie(cookie);
        // 攻击: ?value=admin%0d%0aSet-Cookie:session=hijacked
    }
}
```

#### 安全实现参考

```java
// ✓ 安全：CRLF过滤 + 白名单验证
public class SecureHeaderServlet extends HttpServlet {
    private static final Pattern CRLF_PATTERN = Pattern.compile("[\r\n]");

    private String sanitizeHeader(String value) {
        if (value == null) return "";
        // 移除所有CRLF字符
        return CRLF_PATTERN.matcher(value).replaceAll("");
    }

    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        String lang = req.getParameter("lang");
        String safeLang = sanitizeHeader(lang);

        // ✓ 额外白名单验证
        if (safeLang.matches("^[a-z]{2}(-[A-Z]{2})?$")) {
            resp.setHeader("Content-Language", safeLang);
        }
    }
}
```

### 审计检查清单

| 优先级 | 检查项 | 审计方法 | 审计等级 |
|--------|--------|---------|----------|
| **P0** | setHeader/addHeader | 搜索 `setHeader\|addHeader` + 参数来源，检查是否过滤 `\r\n` | **L2** |
| **P0** | sendRedirect | 搜索 `sendRedirect` + 用户输入，检查是否有URL编码或验证 | **L2** |
| **P0** | Cookie值设置 | 搜索 `new Cookie` + 参数来源，检查Servlet版本（<3.0易受攻击） | **L2** |
| **P1** | Content-Disposition | 搜索 `Content-Disposition` + 文件名参数，检查是否转义 | **L2** |
| **P1** | ResponseEntity.header | 搜索 `ResponseEntity.*header` + `@RequestParam/@RequestHeader` | **L2-L3** |
| **P2** | HttpHeaders动态设置 | 搜索 `HttpHeaders.set/add` + 变量，追踪变量来源 | **L3** |
| **P3** | 响应包装器 | 搜索 `HttpServletResponseWrapper` 子类，检查 `setHeader` 重写 | **L4** |

### 审计等级判定

| 等级 | 代码特征 | 审计策略 |
|------|---------|---------|
| **L0** | 响应头值来自常量/配置文件 | 快速跳过，确认无用户输入 |
| **L1** | 响应头值来自数据库，但有ORM转义 | 关键词扫描：确认数据来源非请求参数 |
| **L2** | 单文件内直接使用请求参数 | 跳读：检查 `setHeader` 前是否有 `replaceAll("[\r\n]", "")` |
| **L3** | 响应头值由Service层返回 | 逐行读：追踪方法返回值，检查中间处理逻辑 |
| **L4** | 全局响应拦截器/过滤器处理 | 跨模块追踪：检查 `Filter/HandlerInterceptor` 实现链 |

---

## Classify

### 确认漏洞的标准

1. **用户输入可达**：响应头值直接或间接来自HTTP请求参数（`getParameter/getHeader/getCookies`）
2. **无CRLF过滤**：代码中未调用 `replaceAll("[\r\n]", "")`、`replaceAll("\r|\n", "")` 或类似过滤方法
3. **框架版本脆弱**：Servlet < 3.0 或 Tomcat < 6.0.33（无内置CRLF检查）或Spring < 5.3（部分场景绕过）

### 审计专业技巧

#### 技巧1：区分响应头注入与日志注入的危害差异

```java
// ✗ 真正的漏洞：可实现HTTP响应拆分
String userInput = req.getParameter("lang");
resp.setHeader("Content-Language", userInput);  // 危害等级：CRITICAL

// 低风险：仅在日志中出现CRLF，无法修改HTTP响应格式
String userInput = req.getParameter("id");
log.info("User accessed: " + userInput);  // 危害等级：LOW（仅日志污染）
```

**审计经验**：响应头注入危害取决于：
- 响应头是否影响浏览器行为（如Set-Cookie、Location、Content-Type）
- 是否能实现HTTP响应拆分（`\r\n\r\n` 分离响应头与响应体）
- 是否涉及缓存层（代理缓存可持久化恶意响应）

#### 技巧2：识别"防御性编程"与实际防护的区别

```java
// 情形A：虚假防护（常见误报来源）
String filename = req.getParameter("filename");
// 仅为防止乱码的URLDecode，并非CRLF防护
String decoded = URLDecoder.decode(filename, "UTF-8");
resp.setHeader("Content-Disposition", "attachment;filename=" + decoded);  // ✗ 仍可注入

// 情形B：真实防护（确实安全）
String filename = req.getParameter("filename");
String safe = filename.replaceAll("[\r\n]", "");
resp.setHeader("Content-Disposition", "attachment;filename=" + safe);  // ✓ 安全
```

**审计经验**：常见的"虚假防护"方法：
- URLEncode/URLDecode 只处理特殊字符编码，不过滤CRLF
- trim()/isEmpty() 仅处理空白符，无法移除 `\r\n`
- 字符替换不完整（如只替换 `\r\n` 但未处理单独的 `\r` 或 `\n`）
- 错误的正则表达式（如 `replaceAll("\\n", "")` 在Windows环境漏掉 `\r`）

#### 技巧3：追踪隐式类型转换引入的漏洞

```java
// 审计难点：toString()或String.format()引入的漏洞
Object userInput = req.getParameter("id");
// 第一步：转字符串时用户输入值可能包含CRLF
resp.setHeader("X-ID", userInput.toString());  // ✗ 漏洞！

// 陷阱：在对象toString()中转换，审计时可能遗漏
class CustomObj {
    private String userVal;
    @Override
    public String toString() {
        return "value=" + userVal;  // 用户输入未过滤
    }
}
resp.setHeader("X-Data", new CustomObj(userInput).toString());  // ✗ 漏洞！
```

**审计经验**：需要检查所有可能的字符串转换路径：
- 追踪变量赋值链，确认每一步是否都经过过滤
- 检查自定义对象的 `toString()` 实现
- 注意 `String.format()`、`String.valueOf()` 等隐式转换

#### 技巧4：鉴别真实漏洞 vs 误报的5步法

| 步骤 | 验证方法 | 是否漏洞 |
|------|--------|--------|
| 1️⃣ 输入来源追踪 | 确认参数来自 `getParameter/getHeader` | NO → 误报 |
| 2️⃣ 过滤检查 | 搜索参数名称前200行，确认是否有 `replaceAll(...)` | NO → 漏洞 |
| 3️⃣ 过滤完整性 | 确认过滤字符包含 `\r` 和 `\n` | NO → 漏洞（不完整过滤） |
| 4️⃣ 框架版本 | 检查Servlet版本和Spring版本 | <3.0 → 漏洞；>=3.0 → 低风险 |
| 5️⃣ 防线深度 | 全局Filter是否对所有响应做CRLF检查 | NO → 漏洞；YES → 低风险 |

### 判定为误报的情况

1. **框架自动保护**：Servlet 3.0+ 且容器会自动拒绝包含CRLF的响应头（需测试验证）
2. **已有过滤**：存在全局Filter实现CRLF过滤，且所有响应都经过此Filter
3. **白名单验证**：响应头值仅允许预定义的枚举值（如语言代码、MIME类型）
4. **仅内部API**：接口仅供内部系统调用，且调用方已验证参数（需确认调用链）

### 代码异味识别

1. **不完整过滤**：仅过滤 `\n` 未过滤 `\r`，或仅过滤单个CRLF（`\r\n` → 空字符串）
2. **顺序错误**：先设置响应头后验证参数（攻击已生效）
3. **注释依赖**：代码注释"前端已验证"，但后端无二次检查
4. **版本混用**：部分代码使用安全API（`setHeader`），部分手动拼接响应字符串

### 实战审计案例分析

#### 案例1：Spring Framework中的隐蔽漏洞

```java
// 场景：使用HttpHeaders动态添加响应头
@GetMapping("/data")
public ResponseEntity<String> getData(@RequestParam String token) {
    HttpHeaders headers = new HttpHeaders();
    headers.set("Authorization", "Bearer " + token);  // ✗ CRLF未过滤
    return new ResponseEntity<>("data", headers);
}

// 审计结论：低风险（Spring 5.3+自动检查）vs 漏洞（Spring < 5.2）
// 需要检查Spring版本：grep -r "<version>.*spring" pom.xml
```

#### 案例2：自定义Cookie工具类的"防护假象"

```java
// 常见的工具类模式（容易误报）
public class CookieUtils {
    public static void setCookie(HttpServletResponse resp, String name, String value) {
        // 开发者认为这里已保护，但实际不完整
        if (value.length() > 100) return;  // 仅检查长度
        Cookie c = new Cookie(name, value);
        resp.addCookie(c);  // ✗ 漏洞！Servlet 3.0前不防护CRLF
    }
}

// 审计结论：需要检查Servlet版本，而非仅看工具类是否"保护"
```

#### 案例3：请求头反射导致的响应头污染

```java
// 真实漏洞：请求头 → 响应头的直接传递
@GetMapping("/reflect")
public ResponseEntity<String> reflect(
    @RequestHeader("X-Custom") String customHeader,
    HttpServletResponse resp) {
    resp.setHeader("X-Echo", customHeader);  // ✗ 漏洞！
    return ResponseEntity.ok("ok");
}

// 审计关键：追踪所有 @RequestHeader → setHeader 的路径
// 搜索策略：grep -n "@RequestHeader" | 记录参数名 | grep -n "setHeader" 该参数名
```

---

## Low risk

### 低风险场景判定标准

满足以下任一条件时，可评估为低风险（仍需标注并建议修复）：

1. **容器自动防护**
   - Servlet 3.0+ 容器（Tomcat 7+、Jetty 9+）且无特殊配置禁用CRLF检查
   - Spring Framework 5.3+ 使用 `ResponseEntity` 且未降级到Servlet API
   - 已启用 `http.response.header.validation=true`（某些容器配置）

2. **受限使用场景**
   - 响应头值来自有限字符集（仅字母数字、无特殊字符）
   - 用户输入长度严格限制（<10字符）且有前端正则验证
   - 响应头仅在非关键业务流程中使用（如调试信息、统计标识）

3. **多层防护**
   - WAF规则明确拦截 `%0d%0a` 和URL编码变体
   - 反向代理（Nginx/Apache）配置 `ignore_invalid_headers on`
   - CDN层面已部署响应头过滤规则

4. **业务影响有限**
   - 响应头仅影响客户端展示（如 `Content-Language`），无安全功能
   - 应用无缓存机制，CRLF注入无法实现缓存中毒
   - 不涉及认证Cookie，仅普通业务Cookie

### 评级建议

- **低风险 + Servlet 3.0+**：确认容器版本，建议添加防御性编程代码
- **低风险 + WAF防护**：代码层面仍应修复，避免依赖外部防护
- **低风险 + 有限字符集**：评估字符集是否真正安全（如是否包含 `-` 可能绕过某些过滤）
