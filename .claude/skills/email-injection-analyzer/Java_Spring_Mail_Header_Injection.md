# Java Spring Mail Header Injection

## Details

Spring Framework 通过 `SimpleMailMessage` 或 `MimeMessage` 直接拼接用户输入至邮件头字段，未对 CRLF（`\r\n`）进行过滤。攻击者通过在邮件地址、主题、抄送等字段注入换行符，可篡改邮件头结构，导致邮件欺骗或恶意邮件注入。

**代码示例与审计要点**

```java
SimpleMailMessage message = new SimpleMailMessage();
message.setTo(userInput);  // 直接拼接用户输入
message.setSubject(userInput);
message.setText(body);
mailSender.send(message);
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `SimpleMailMessage`、`MimeMessage`、`setTo()`、`setSubject()`、`setCc()`、`setBcc()`
- 查找这些方法的参数是否来自请求数据（`request.getParameter()`、表单参数、API 输入）
- 检查 `mailSender.send()` 调用前是否进行了验证

**快速定位保护机制 (L2: 跳读)**
- 查看是否在传递给邮件 API 之前进行了输入验证
- 搜索如 `replaceAll("\\r", "")`、`replaceAll("\\n", "")` 这样的 CRLF 过滤代码
- 查找使用 Apache Commons Validator、Spring Validation 的邮箱格式验证
- 检查是否使用了 `@Email` 注解进行属性级验证

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接传入 `setTo()`、`setSubject()`、`setCc()` 等方法
   - 邮件发送前未进行 CRLF 过滤或邮箱验证
   - 输入来源于不可信渠道（外部请求、数据库中的用户数据等）
   - 成功注入 `\r\n` 可改变邮件头结构

2. **确认为误报的情况**：
   - 输入已在其他层进行了严格的邮箱格式验证（正则表达式验证通过 RFC 5322）
   - 使用了成熟的邮件验证库完整验证
   - 仅接受从受信系统（如数据库中预设的邮箱）的邮件地址
   - 不允许任意字符输入，仅限定范围

3. **代码异味判断**：
   - 虽有验证但不够充分（例如仅检查 `contains("@")` 而非完整格式验证）
   - 验证逻辑在邮件发送后执行
   - 验证在条件分支中不完全覆盖所有邮件字段

---

## Low risk

**这些情况应给予低风险评级**

1. **严格邮箱验证**：使用标准库（Spring Validation、Apache Commons Validator）通过完整 RFC 5322 兼容的正则验证，且在邮箱字段上强制校验，能阻止任何特殊字符（包括 CRLF）

2. **白名单验证**：输入仅限于预定义的邮箱列表或从数据库查询预存的可信邮箱地址，不允许用户直接输入

3. **框架级自动防护**：Spring Mail 框架本身（较新版本）对 CRLF 自动转义或拒绝，或依赖 SMTP 服务器的严格头部验证

4. **非邮件头字段**：仅在邮件正文（`setText()`、`setContent()`）中使用用户输入，不涉及邮件头结构

5. **沙箱环境**：SMTP 服务器仅限内部系统使用，不对外发送邮件，降低邮件欺骗的实际影响
