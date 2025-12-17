# NodeJS Email Address Validation Bypass

## Details

Node.js 应用中邮箱地址验证不充分时，攻击者可通过特殊构造的邮箱地址绕过验证逻辑。常见问题包括：使用不完整的正则表达式、仅检查 `@` 符号、未验证域名格式、允许 CRLF 等特殊字符。这可能导致邮件头注入、垃圾邮件发送或系统滥用。

**代码示例与审计要点**

```javascript
// 危险：简单字符串检查
if (email.includes('@') && email.includes('.')) {
    sendEmail(email);
}

// 危险：不完整的正则
if (/^[\w.-]+@[\w.-]+$/.test(email)) {
    sendEmail(email);
}

// 危险：允许换行符
if (email.match(/.+@.+\..+/)) {
    sendEmail(email);
}

// 危险：未验证长度和特殊字符
if (email.indexOf('@') > 0) {
    sendEmail(email);
}
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮箱验证：`includes('@')`、`indexOf('@')`、`test()`、`match()`
- 查找邮件发送函数：`sendMail()`、`transporter.sendMail()`
- 定位验证函数：`validateEmail()`、`isValidEmail()`、`validator.isEmail()`
- 检查是否直接使用 `req.body.email` 等用户输入

**快速定位保护机制 (L2: 跳读)**
- 搜索验证库：`validator.isEmail()`、`email-validator`、`isemail` 包
- 查找正则表达式验证：检查是否符合 RFC 5322
- 检查 CRLF 过滤：`replace(/[\r\n]/g, '')`
- 查看是否验证域名：DNS 查询、MX 记录检查

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 仅检查 `@` 和 `.` 符号存在
   - 正则表达式不完整，允许换行符、空格等
   - 未验证本地部分和域名部分的合法性
   - 允许连续点号、多个 `@` 符号
   - 能通过 `user@domain\r\nBcc:attacker@evil.com` 绕过验证

2. **确认为误报的情况**：
   - 使用 `validator.isEmail()` 标准验证
   - 使用 `email-validator` 或 `isemail` 包验证
   - 正则表达式符合 RFC 5322 标准
   - 额外验证域名 MX 记录

3. **代码异味判断**：
   - 正则验证不完整，未覆盖所有边界情况
   - 验证后未使用验证结果，仍使用原始输入
   - 某些代码路径缺少验证

---

## Low risk

**这些情况应给予低风险评级**

1. **标准库验证**：使用 `validator.isEmail()` 并启用严格模式：`validator.isEmail(email, {allow_display_name: false})`

2. **专用验证库**：使用 `email-validator` 或 `isemail` 包进行 RFC 5322 兼容验证

3. **CRLF 过滤**：在验证后额外进行 `email.replace(/[\r\n]/g, '')` 过滤

4. **DNS 验证**：使用 `dns.resolveMx()` 验证域名 MX 记录是否存在

5. **白名单域名**：仅允许特定域名的邮箱地址，通过域名后缀白名单限制
