# Java JavaMail Header CRLF Injection

## Details

Java JavaMail API 的 `Message` 类支持通过 `setRecipients()`、`setSubject()`、`setFrom()` 等方法设置邮件头字段。当这些方法直接接受用户输入且未过滤 CRLF，攻击者可注入 `\r\n` 改变邮件头结构，实现邮件欺骗、增加恶意头部、或隐蔽转发邮件。

**代码示例与审计要点**

```java
MimeMessage message = new MimeMessage(session);
message.setFrom(new InternetAddress(userInput));
message.setRecipients(Message.RecipientType.TO, userInput);
message.setSubject(userInput);
Transport.send(message);
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `MimeMessage`、`Message.setFrom()`、`setRecipients()`、`setSubject()`、`setHeader()`
- 定位这些方法的参数来源：`request.getParameter()`、`HttpServletRequest`、表单数据
- 查找 `Transport.send()` 调用前的数据处理
- 检查 `InternetAddress` 构造函数的参数是否包含用户输入

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`replace("\r", "")`、`replace("\n", "")`、正则表达式 `replaceAll("[\\r\\n]+", "")`
- 查找邮箱格式验证：`InternetAddress.validate()`、正则表达式 `matches("...")`
- 检查使用 Apache Commons Validator 的 EmailValidator、Spring Validation 的 `@Email` 注解
- 查看是否有数据库层的邮箱白名单或查询限制

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接传给 `setRecipients()`、`setSubject()`、`setFrom()`
   - `InternetAddress(userInput)` 未进行邮箱格式验证
   - `setHeader()` 拼接用户数据至自定义头部
   - 邮件发送前未进行 CRLF 过滤
   - 能成功注入 `\r\n` 改变邮件头结构

2. **确认为误报的情况**：
   - 所有邮箱字段通过 `InternetAddress.validate()` 或完整的 RFC 5321 正则验证
   - 使用 `InternetAddress` 构造函数抛出异常捕获无效邮箱
   - 邮箱来自数据库或系统白名单，用户仅能选择
   - JavaMail 库版本已自动进行 CRLF 转义（新版本）

3. **代码异味判断**：
   - 验证存在但不完整：仅检查 `contains("@")` 而非完整格式验证
   - `try-catch` 捕获异常但仍使用原始值
   - 验证在条件分支中不完全覆盖所有邮箱字段

---

## Low risk

**这些情况应给予低风险评级**

1. **RFC 5321 验证**：使用 `InternetAddress.validate()` 或标准正则验证所有邮箱地址，确保格式正确且无特殊字符

2. **异常捕获**：所有邮箱字段通过 `new InternetAddress(userInput)` 创建并捕获 `AddressException`，拒绝无效邮箱

3. **白名单机制**：邮箱地址仅来自数据库中的预设值或受限列表，用户无直接输入权限

4. **自动转义**：使用较新版本的 JavaMail（如 Spring Boot 集成的版本），框架已自动处理 CRLF 转义

5. **隔离部署**：SMTP 服务器为内部专用，不与外部邮件系统交互，邮件欺骗风险有限
