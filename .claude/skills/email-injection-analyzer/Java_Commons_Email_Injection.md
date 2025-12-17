# Java Commons Email Injection

## Details

Apache Commons Email 库是 JavaMail 的简化封装。当使用 `SimpleEmail`、`MultiPartEmail` 或 `HtmlEmail` 类处理邮件时，若用户输入直接传入邮件头字段（`addTo()`、`setFrom()`、`setSubject()` 等）未经验证和过滤，攻击者可注入 CRLF 字符改变邮件头结构。

**代码示例与审计要点**

```java
import org.apache.commons.mail.SimpleEmail;

// 危险：直接使用用户输入
SimpleEmail email = new SimpleEmail();
email.setHostName("smtp.example.com");
email.addTo(userEmail);  // 用户输入
email.setFrom(userFrom);  // 用户输入
email.setSubject(userSubject);  // 用户输入
email.setMsg(message);
email.send();

// 危险：自定义头部
email.addHeader("X-Custom", userInput);
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `org.apache.commons.mail.`、`SimpleEmail`、`HtmlEmail`、`MultiPartEmail`
- 查找方法调用：`addTo()`、`addCc()`、`addBcc()`、`setFrom()`、`setSubject()`
- 定位参数来源：`request.getParameter()`、`@RequestParam`、表单数据
- 检查 `addHeader()` 的自定义头部设置

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`replaceAll("\\r", "")`、`replaceAll("\\n", "")`
- 查找邮箱验证：Apache Commons Validator、`EmailValidator.getInstance().isValid()`
- 检查是否使用 Bean Validation：`@Email` 注解
- 查看 Commons Email 版本（较新版本有改进的验证）

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接传给 `addTo()`、`setFrom()`、`setSubject()` 等方法
   - 自定义头部拼接用户数据：`addHeader("X-Custom", userInput)`
   - 未进行 CRLF 过滤或邮箱格式验证
   - 能通过注入 `\r\n` 添加额外的邮件头
   - Commons Email 版本较旧，缺少内置保护

2. **确认为误报的情况**：
   - 使用 `EmailValidator.getInstance().isValid()` 验证所有邮箱地址
   - 所有字段都通过 Bean Validation 的 `@Email` 注解验证
   - 头部值经过 CRLF 过滤
   - 邮箱地址来自数据库查询，用户无法输入任意值

3. **代码异味判断**：
   - 验证不完整：仅检查 `contains("@")` 而非完整格式验证
   - 验证在某些代码路径中缺失
   - 自定义头部值未经任何验证

---

## Low risk

**这些情况应给予低风险评级**

1. **Commons Validator**：使用 `EmailValidator.getInstance().isValid()` 验证所有邮箱地址

2. **Bean Validation**：在数据模型上使用 `@Email` 注解，确保自动验证

3. **CRLF 过滤**：所有用户输入在传入 Commons Email 前都经过 `replaceAll("[\\r\\n]", "")` 过滤

4. **白名单验证**：邮箱地址仅来自数据库预设数据或有限的可控列表

5. **新版本库**：使用 Commons Email 1.5+ 版本，具有改进的安全性和验证机制
