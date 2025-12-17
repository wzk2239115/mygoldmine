# Python Django Email Header Injection

## Details

Django `django.core.mail` 提供的邮件发送函数通过 `EmailMessage` 或 `send_mail()` 接受邮箱地址和邮件头参数。当用户输入直接传入这些参数且未过滤 CRLF，攻击者可注入换行符改变邮件头结构。特别是在构建自定义邮件头时（`headers` 参数），风险更大。

**代码示例与审计要点**

```python
from django.core.mail import EmailMessage
msg = EmailMessage(
    subject=user_subject,
    body=user_body,
    from_email=user_from,
    to=[user_to],
    headers={'X-Custom': user_header}
)
msg.send()
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `EmailMessage`、`send_mail()`、`send_mass_mail()`
- 定位参数来源：`request.POST.get()`、`request.GET.get()`、视图函数的参数
- 查找 `to=`、`from_email=`、`subject=`、`headers=` 等参数
- 检查 `msg.send()` 或 `send()` 调用

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`replace('\r', '')`、`replace('\n', '')`、`re.sub()` 过滤
- 查找邮箱验证：`django.core.validators.validate_email()`、`email_validator` 库
- 检查是否在表单或模型中使用 `EmailField` 和相应的验证
- 查看是否对头部值进行了白名单验证或格式限制

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接传给 `EmailMessage` 的 `to`、`from_email` 等参数
   - 自定义 `headers` 字典的值拼接了用户数据
   - 邮箱地址未通过 `validate_email()` 验证
   - 邮件发送前未进行 CRLF 过滤
   - 能成功注入 `\r\n` 改变邮件头结构

2. **确认为误报的情况**：
   - 所有邮箱字段都在 Django 表单的 `EmailField` 或通过 `validate_email()` 验证
   - 使用了 `django-crispy-forms` 或其他验证框架，自动进行验证
   - 邮箱地址来自数据库中的预设值，用户仅能选择
   - Django 版本已自动进行邮件头验证和 CRLF 转义

3. **代码异味判断**：
   - 存在验证但不完整：仅检查 `'@' in email` 而非完整格式验证
   - 验证在条件分支中不完全覆盖所有邮箱字段
   - 自定义头部值未经任何验证

---

## Low risk

**这些情况应给予低风险评级**

1. **表单验证**：所有邮件相关的输入都通过 Django 表单的 `EmailField` 和自动验证，确保格式正确

2. **显式验证**：使用 `django.core.validators.validate_email()` 对所有邮箱地址进行验证

3. **第三方库**：使用 `email-validator` 库进行严格的 RFC 5321 验证

4. **白名单机制**：邮箱地址仅来自数据库查询的用户信息，用户无法输入任意值

5. **环境隔离**：SMTP 后端为内部专用服务，不对外转发，邮件欺骗风险有限

