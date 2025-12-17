# Python Email Address Validation Bypass

## Details

Python 应用中邮箱地址验证不充分时，攻击者可通过特殊构造的邮箱地址绕过验证逻辑。常见问题包括：仅检查 `@` 符号存在、使用不完整的正则表达式、未验证域名有效性、允许特殊字符等。这可能导致邮件注入、垃圾邮件发送或系统滥用。

**代码示例与审计要点**

```python
# 危险：简单字符串检查
if '@' in email and '.' in email:
    send_email(email)

# 危险：不完整的正则验证
if re.match(r'^[\w\.-]+@[\w\.-]+$', email):
    send_email(email)

# 危险：未验证域名
if re.match(r'.+@.+\..+', email):
    send_email(email)

# 允许危险字符：换行符、空格等
if email.count('@') == 1:
    send_email(email)
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮箱验证逻辑：`if '@' in`、`if email`、`re.match()`、`re.search()`
- 查找邮箱相关函数：`send_mail()`、`EmailMessage`、`sendmail()`
- 定位验证函数：`validate_email()`、`is_valid_email()`、自定义验证函数
- 检查是否直接使用用户输入而无验证

**快速定位保护机制 (L2: 跳读)**
- 搜索标准验证：`django.core.validators.validate_email()`
- 查找第三方库：`email_validator`、`validate_email` 包
- 检查正则表达式是否符合 RFC 5322 标准
- 查看是否验证域名 MX 记录：`dns.resolver.query()`

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 仅检查 `@` 和 `.` 符号存在
   - 正则表达式不完整，允许换行符、空格等特殊字符
   - 未验证本地部分和域名部分的有效性
   - 允许多个 `@` 符号或连续的点号
   - 能通过 `user@domain\r\nBcc:attacker@evil.com` 绕过验证

2. **确认为误报的情况**：
   - 使用 `django.core.validators.validate_email()` 标准验证器
   - 使用 `email-validator` 库的 `validate_email()` 函数
   - 正则表达式符合 RFC 5322 标准且验证域名格式
   - 额外验证域名 MX 记录确保可达

3. **代码异味判断**：
   - 正则表达式部分正确但未覆盖所有边界情况
   - 验证后未使用验证结果，仍使用原始输入
   - 验证在某些条件分支中缺失

---

## Low risk

**这些情况应给予低风险评级**

1. **标准库验证**：使用 `django.core.validators.validate_email()` 或 Django 表单的 `EmailField` 自动验证

2. **第三方库**：使用 `email-validator` 库并启用 DNS 检查：`validate_email(email, check_deliverability=True)`

3. **RFC 兼容正则**：使用完整的 RFC 5322 兼容正则表达式，验证本地部分和域名格式

4. **白名单域名**：仅允许特定域名的邮箱地址，通过域名白名单限制

5. **多层验证**：结合格式验证、CRLF 过滤、域名 MX 记录检查的多层防护机制
