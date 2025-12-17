# Java Set-Cookie 值 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `response.addCookie(cookie)` - 添加 Cookie 到响应
- `response.setHeader("Set-Cookie", value)` 直接设置
- `HttpSession.setAttribute()` 后设置 Cookie
- `new Cookie(name, value)` 后 `response.addCookie()`

**快速定位核心操作：**
1. 搜索关键字：`addCookie`、`Set-Cookie`、`new Cookie`
2. 追踪 Cookie 值来源：`getParameter()`、`getHeader()`、会话数据
3. 检查是否存在 CRLF 过滤
4. 追踪 Cookie 构造过程

**快速定位保护机制：**
- 值验证：`if (value.contains("") || value.contains("
")) throw Exception()`
- URL 编码：`URLEncoder.encode(value, "UTF-8")`
- 白名单验证：`if (!value.matches("^[a-zA-Z0-9\-_.]*$")) throw Exception()`
- Cookie 框架处理：使用 HttpOnly、Secure 标记

**代码示例：**
```java
// 危险：用户输入直接作为 Cookie 值
@GetMapping("/setCookie")
public void setCookie(HttpServletResponse response,
                      @RequestParam String token) {
    Cookie cookie = new Cookie("session", token);  // 危险：未验证
    response.addCookie(cookie);
}

// 危险：直接设置 Set-Cookie 头
@GetMapping("/header-cookie")
public void headerCookie(HttpServletResponse response,
                         @RequestParam String val) {
    response.setHeader("Set-Cookie", "auth=" + val);  // 危险
}

// 危险：从外部来源
@GetMapping("/external")
public void externalCookie(HttpServletResponse response,
                           HttpServletRequest request) {
    String userAgent = request.getHeader("User-Agent");
    response.addCookie(new Cookie("client", userAgent));  // 危险
}
```

## Classify

**漏洞（Critical）：**
- 用户输入直接用于 Cookie 值
- 无 CRLF 过滤或验证
- 可导致响应分割

**误报：**
- Cookie 值硬编码
- Session ID 系统生成
- 使用框架管理的 Cookie

**代码异味（Medium）：**
- 仅过滤一个字符
- 黑名单不完整
- 间接拼接

## Low risk

**以下情况评为低风险：**
- Cookie 值硬编码
- 严格 CRLF 过滤
- 白名单验证
- 使用加密 Cookie 框架

## 审计专业技巧

### 1. 真实漏洞特征识别

**真漏洞特征（需要深入分析）：**
- 用户可控输入直接进入 Cookie 值，且无任何过滤
- 日志或监控代码中能看到带 `%0a%0d` 的请求被记录
- 存在多步链路拼接：`getParameter()` → 处理函数 → `addCookie()`
- Cookie 值来自外部接口（如用户上传、第三方 API）
- 过滤逻辑在 Cookie 值设置前被 bypass（例如解码两次）

**验证方法：**
```java
// 真实漏洞：拼接过程中 CRLF 未被过滤
String userInput = request.getParameter("value");
String cookieValue = "token=" + userInput;  // 危险：直接拼接
response.setHeader("Set-Cookie", cookieValue);

// 真实漏洞：过滤不完整，仅过滤 \r
if (!value.contains("\r")) {  // 漏掉了 \n
    response.addCookie(new Cookie("auth", value));
}

// 真实漏洞：循环过滤被绕过
value = value.replace("\r", "").replace("\n", "");
// 但没有处理编码后的形式：%0d、%0a、&#13;、&#10;
```

### 2. 误报和低风险的准确判断

**常见误报情况：**

a) **系统生成的 Session ID**
```java
// 低风险：使用 Java 的随机生成器
String sessionId = UUID.randomUUID().toString();  // 完全系统生成
response.addCookie(new Cookie("JSESSIONID", sessionId));
```
- 判断依据：检查是否来自 `java.util.UUID`、`java.security.SecureRandom`、`Apache Commons Lang`
- 这些方法生成的值不含特殊字符

b) **框架自动处理的 Cookie**
```java
// 低风险：Spring Security 自动设置
@EnableWebSecurity
public class SecurityConfig {
    // Spring 框架内部处理 CRLF 编码和过滤
}
```
- 判断依据：`@EnableWebSecurity`、`Spring Session`、`HttpOnly` 标签存在
- 框架在底层已进行安全处理

c) **明确的白名单验证**
```java
// 低风险：严格的正则验证
if (value.matches("^[a-zA-Z0-9\\-_.]{1,32}$")) {
    response.addCookie(new Cookie("user", value));
} else {
    throw new IllegalArgumentException("Invalid value");
}
```
- 判断依据：正则限制长度 + 只允许安全字符 + 有异常抛出

### 3. 审计中的陷阱和技巧

**陷阱 1: 多层编码/解码的过滤绕过**
```java
// 看似安全，但实际有问题
String value = URLDecoder.decode(request.getParameter("token"), "UTF-8");
if (!value.contains("\r") && !value.contains("\n")) {
    response.addCookie(new Cookie("auth", value));
}
// 问题：如果原始参数是 %250d（对 %0d 的 URL 编码），解码后变成 %0d
// 再经过一次解码就是 \r，过滤逻辑被绕过
```
**审计技巧：** 追踪所有的 decode、unescape 操作，检查是否在验证之前多次执行

**陷阱 2: 黑名单不完整**
```java
// 危险的黑名单过滤
value = value.replace("\r", "").replace("\n", "");
// 但遗漏了其他可能性：
// - %0d、%0a（URL 编码）
// - &#13;、&#10;（HTML 实体）
// - \x0d、\x0a（转义序列）
```
**审计技巧：** 搜索所有 `replace()` 或 `filter()` 操作，计算覆盖的字符集

**陷阱 3: 条件判断的逻辑错误**
```java
// 错误的逻辑
if (role == "admin" || value.length() < 100) {
    // 不进行过滤就设置 Cookie
    response.addCookie(new Cookie("data", userInput));
}
// 漏洞：只要 role != "admin" 或 length >= 100，就会跳过设置 Cookie
// 但其实应该两个条件都满足才能设置
```
**审计技巧：** 仔细审查条件判断，尤其是 `||` 和 `&&` 的使用

### 4. 实战审计检查清单

| 项目 | 检查内容 | 真漏洞表现 |
|------|--------|---------|
| **来源追踪** | 用户输入是否直接来自 request | 能在参数中注入 CRLF |
| **过滤位置** | 过滤是否在 Cookie 设置前进行 | 过滤在设置后、或被绕过 |
| **字符覆盖** | 是否同时检查 `\r`、`\n`、编码形式 | 仅过滤一种形式 |
| **编码操作** | 是否有多次 encode/decode | 解码次数 > 验证次数 |
| **异常处理** | 验证失败是否抛异常 | 验证失败仍继续执行 |
| **加密框架** | 是否使用 HttpOnly、Secure | 明文传输敏感 Cookie |

### 5. 真实案例区分

**案例 1：真漏洞**
```java
@PostMapping("/api/login")
public void login(HttpServletResponse response,
                  @RequestParam String username) {
    // 来自用户输入
    String sessionToken = username + "_" + System.currentTimeMillis();
    // 未验证直接设置
    response.setHeader("Set-Cookie", "session=" + sessionToken);
}
// 漏洞：username 可含 CRLF，可以注入新的 HTTP 头
// PoC: GET /api/login?username=admin%0d%0aX-Injected-Header:evil
```

**案例 2：误报**
```java
@PostMapping("/api/profile")
public void setPreference(HttpServletResponse response,
                          @RequestParam String theme) {
    // 虽然来自用户输入，但有验证
    if (theme.matches("^(light|dark|auto)$")) {
        response.addCookie(new Cookie("theme", theme));
    } else {
        response.sendError(400, "Invalid theme");
    }
}
// 低风险：白名单限制了可能的值，不含 CRLF 字符
```

### 6. 报告建议

- **确认真漏洞：** 提供 PoC 和漏洞链路图
- **区分误报：** 说明具体的安全保护措施
- **提供修复方案：** 推荐使用框架 API 或完整的字符集过滤
