# Java Email Address Validation Bypass

## Details

Java 应用中邮箱地址验证不充分时，攻击者可通过特殊构造的邮箱地址绕过验证逻辑。常见问题包括：使用不完整的正则表达式、仅检查 `@` 符号、未使用标准验证库、允许 CRLF 等特殊字符。这可能导致邮件头注入、垃圾邮件发送或系统滥用。

**代码示例与审计要点**

```java
// 危险：简单字符串检查
if (email.contains("@") && email.contains(".")) {
    sendEmail(email);
}

// 危险：不完整的正则
if (email.matches("^[\\w\\.-]+@[\\w\\.-]+$")) {
    sendEmail(email);
}

// 危险：未验证长度和特殊字符
if (email.indexOf("@") > 0) {
    sendEmail(email);
}

// 危险：允许换行符
if (Pattern.matches(".+@.+\\..+", email)) {
    sendEmail(email);
}
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮箱验证：`contains("@")`、`indexOf("@")`、`matches()`、`Pattern.matches()`
- 查找邮件发送：`send()`、`sendMail()`、`mailSender.send()`
- 定位输入来源：`request.getParameter()`、`@RequestParam`、`@PathVariable`
- 检查是否直接使用用户输入而无验证

**快速定位保护机制 (L2: 跳读)**
- 搜索标准验证：`EmailValidator.getInstance().isValid()`、`@Email` 注解
- 查找 CRLF 过滤：`replaceAll("\\r", "")`、`replaceAll("\\n", "")`
- 检查 Bean Validation 使用：`@Valid`、`@Validated`
- 查看是否使用 Spring Validation 或 Hibernate Validator

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 仅检查 `@` 和 `.` 符号存在
   - 正则表达式不完整，允许换行符、空格等特殊字符
   - 未验证本地部分和域名部分的合法性
   - 允许连续点号、多个 `@` 符号
   - 能通过 `user@domain\r\nBcc:attacker@evil.com` 绕过验证

2. **确认为误报的情况**：
   - 使用 `EmailValidator.getInstance().isValid()` 标准验证
   - 使用 Bean Validation 的 `@Email` 注解并启用验证
   - 正则表达式符合 RFC 5322 标准
   - 额外进行 CRLF 过滤

3. **代码异味判断**：
   - 正则验证不完整，未覆盖所有边界情况
   - 使用 `@Email` 注解但未在方法上使用 `@Valid` 触发验证
   - 验证在某些代码路径中缺失

---

## Low risk

**这些情况应给予低风险评级**

1. **Commons Validator**：使用 `org.apache.commons.validator.routines.EmailValidator.getInstance().isValid()` 验证

2. **Bean Validation**：使用 `@Email` 注解配合 `@Valid` 或 `@Validated` 自动验证

3. **组合验证**：结合 `EmailValidator` 和 CRLF 过滤：`email.replaceAll("[\\r\\n]", "")`

4. **白名单验证**：邮箱地址仅来自数据库查询或预定义列表，用户无法输入任意值

5. **Spring Validation**：使用 Spring 的验证框架在控制器层统一验证所有输入
