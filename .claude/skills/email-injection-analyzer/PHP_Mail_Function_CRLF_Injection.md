# PHP Mail Function CRLF Injection

## Details

PHP 内置的 `mail()` 函数在处理邮件头时，若用户输入直接拼接到额外头部参数（第 4 个参数）或邮件地址字段未经过滤，攻击者可注入 CRLF 字符（`\r\n`）添加任意邮件头。这是 PHP 邮件注入最常见的场景，可能导致垃圾邮件发送、邮件欺骗或恶意附件注入。

**代码示例与审计要点**

```php
// 危险：用户输入直接拼接到额外头部
$to = $_POST['email'];
$subject = $_POST['subject'];
$message = $_POST['message'];
$headers = "From: " . $_POST['from'] . "\r\n";  // 直接拼接
$headers .= "Cc: " . $_POST['cc'];
mail($to, $subject, $message, $headers);

// 危险：未验证收件人地址
$email = $_GET['email'];
mail($email, 'Subject', 'Body', 'From: noreply@example.com');
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `mail(` 函数调用
- 查找第 4 个参数（额外头部）的构建逻辑
- 定位用户输入来源：`$_POST`、`$_GET`、`$_REQUEST`、`$_COOKIE`
- 检查头部字符串拼接：`$headers .=`、`"From: " . $var`

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`str_replace("\r\n", "")`、`preg_replace('/[\r\n]/', '')`
- 查找邮箱验证：`filter_var($email, FILTER_VALIDATE_EMAIL)`
- 检查 PHP 版本（5.4.42+ / 5.5.27+ 有额外保护）
- 查看是否使用邮件库替代 `mail()` 函数

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到 `mail()` 函数的第 4 个参数
   - 收件人地址、发件人地址未经验证
   - 未进行 CRLF 字符过滤
   - 能通过注入 `\r\n` 添加额外的邮件头（如 `Bcc`、`Cc`）
   - PHP 版本低于 5.4.42 / 5.5.27（缺少内置保护）

2. **确认为误报的情况**：
   - PHP 版本为 5.4.42+ / 5.5.27+（自动拒绝包含换行符的头部）
   - 所有邮箱地址通过 `filter_var(FILTER_VALIDATE_EMAIL)` 验证
   - 头部值经过 CRLF 过滤
   - 不使用第 4 个参数或仅使用硬编码的头部值

3. **代码异味判断**：
   - 验证不完整：仅检查 `@` 符号存在
   - 过滤不彻底：仅过滤 `\n` 未过滤 `\r`
   - 某些代码路径缺少验证

---

## Low risk

**这些情况应给予低风险评级**

1. **新版本 PHP**：使用 PHP 5.4.42+ / 5.5.27+ 或更高版本，自动拒绝包含换行符的额外头部

2. **CRLF 过滤**：所有用户输入在拼接到头部前都经过 `str_replace(["\r", "\n"], '', $input)` 过滤

3. **邮箱验证**：使用 `filter_var($email, FILTER_VALIDATE_EMAIL)` 验证所有邮箱地址

4. **使用邮件库**：使用 PHPMailer、SwiftMailer 等成熟库替代 `mail()` 函数

5. **硬编码头部**：`mail()` 的第 4 个参数完全硬编码，不包含任何用户输入
