# PHP PHPMailer Header Injection

## Details

PHPMailer 库通过 `addAddress()`、`setFrom()`、`addReplyTo()` 等方法设置邮件字段。当这些方法接受用户输入且未进行 CRLF 过滤，攻击者可注入换行符改变邮件头结构。特别是在处理自定义头部（`addCustomHeader()`）时，风险更加严重。

**代码示例与审计要点**

```php
$mail = new PHPMailer\PHPMailer\PHPMailer(true);
$mail->setFrom($userEmail);
$mail->addAddress($userTo);
$mail->Subject = $userSubject;
$mail->addCustomHeader('X-Custom', $userHeader);
$mail->send();
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `PHPMailer`、`addAddress()`、`setFrom()`、`addReplyTo()`、`addCC()`、`addBCC()`
- 定位这些方法的参数来源：`$_GET`、`$_POST`、JSON 请求体
- 查找 `$mail->Subject =` 直接赋值
- 检查 `addCustomHeader()`、`addHeader()` 的自定义头部拼接

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`str_replace()`、`preg_replace()` 过滤换行符
- 查找邮箱验证：`filter_var(..., FILTER_VALIDATE_EMAIL)`、`preg_match()` 正则
- 检查是否使用了 PHPMailer 内置的验证（较新版本）
- 查看是否在应用层进行了白名单验证或头部格式限制

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接传入 `addAddress()`、`setFrom()` 等方法
   - `Subject` 属性直接赋值用户数据
   - `addCustomHeader()` 拼接用户数据
   - 邮箱地址未通过 `filter_var()` 验证
   - 能成功注入 `\r\n` 改变邮件头结构

2. **确认为误报的情况**：
   - 所有邮件地址都通过 `filter_var($email, FILTER_VALIDATE_EMAIL)` 验证
   - 所有邮件头字段值都经过严格的白名单验证
   - 邮箱来自数据库预设数据，用户仅能选择
   - PHPMailer 版本已包含自动 CRLF 验证/转义

3. **代码异味判断**：
   - 验证不完整：仅检查字符串长度或包含 `@` 而非完整验证
   - 验证在条件分支中，覆盖不完全
   - 自定义头部未经任何验证

---

## Low risk

**这些情况应给予低风险评级**

1. **严格邮箱验证**：所有邮箱字段都通过 `filter_var($email, FILTER_VALIDATE_EMAIL)` 验证

2. **白名单机制**：邮箱地址和头部值仅来自数据库或预定义常量，不允许用户自由输入

3. **框架级防护**：PHPMailer 6.x+ 版本已自动对邮件头进行验证和 CRLF 转义

4. **头部格式限制**：自定义头部值仅限字母数字和特定的安全字符，经过严格过滤

5. **部署隔离**：SMTP 服务器为内部专用，不转发至外部邮件系统，风险范围有限

