# PHP Email Address Validation Bypass

## Details

PHP 应用中邮箱地址验证不充分时，攻击者可通过特殊构造的邮箱地址绕过验证逻辑。常见问题包括：使用不完整的正则表达式、仅检查 `@` 符号、未使用 `filter_var()`、允许 CRLF 等特殊字符。这可能导致邮件头注入、垃圾邮件发送或系统滥用。

**代码示例与审计要点**

```php
// 危险：简单字符串检查
if (strpos($email, '@') !== false && strpos($email, '.') !== false) {
    mail($email, 'Subject', 'Body');
}

// 危险：不完整的正则
if (preg_match('/^[\w\.-]+@[\w\.-]+$/', $email)) {
    sendEmail($email);
}

// 危险：未过滤特殊字符
if (filter_var($email, FILTER_SANITIZE_EMAIL)) {  // 仅清理，未验证
    mail($email, 'Subject', 'Body');
}

// 危险：允许换行符
if (preg_match('/.+@.+\..+/', $email)) {
    sendEmail($email);
}
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮箱验证：`strpos($email, '@')`、`preg_match()`、`filter_var()`
- 查找邮件发送函数：`mail(`、`->send(`、`->sendMail(`
- 定位用户输入：`$_POST['email']`、`$_GET['email']`、`$_REQUEST['email']`
- 检查是否直接使用输入而无验证

**快速定位保护机制 (L2: 跳读)**
- 搜索标准验证：`filter_var($email, FILTER_VALIDATE_EMAIL)`
- 查找 CRLF 过滤：`str_replace(["\r", "\n"], '', $email)`
- 检查白名单验证或数据库查询限制
- 查看是否使用验证库：`egulias/email-validator`

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 仅检查 `@` 和 `.` 符号存在
   - 使用 `FILTER_SANITIZE_EMAIL` 而非 `FILTER_VALIDATE_EMAIL`
   - 正则表达式不完整，允许换行符、空格等
   - 未验证本地部分和域名部分的合法性
   - 能通过 `user@domain\r\nBcc:attacker@evil.com` 绕过验证

2. **确认为误报的情况**：
   - 使用 `filter_var($email, FILTER_VALIDATE_EMAIL)` 验证
   - 使用 `egulias/email-validator` 库进行 RFC 5322 验证
   - 邮箱地址来自数据库查询，用户无法输入任意值
   - 额外进行 CRLF 过滤

3. **代码异味判断**：
   - 正则验证不完整，未覆盖所有边界情况
   - 使用 `FILTER_SANITIZE_EMAIL` 清理后未进行 `FILTER_VALIDATE_EMAIL` 验证
   - 验证在某些代码路径中缺失

---

## Low risk

**这些情况应给予低风险评级**

1. **标准过滤器**：使用 `filter_var($email, FILTER_VALIDATE_EMAIL)` 进行标准验证

2. **专用验证库**：使用 `egulias/email-validator` 库进行严格的 RFC 5322 兼容验证

3. **组合验证**：结合 `FILTER_VALIDATE_EMAIL` 和 CRLF 过滤：`str_replace(["\r", "\n"], '', $email)`

4. **白名单验证**：邮箱地址仅来自数据库预设数据，用户仅能选择不能输入

5. **双重验证**：先验证格式，再通过发送验证邮件确认地址真实性和可达性
