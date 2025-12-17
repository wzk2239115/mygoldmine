# Python Flask-Mail Injection

## Details

Flask-Mail 扩展通过 `Message` 类发送邮件时，若用户输入直接传入邮件头字段（收件人、发件人、主题等）未经验证和过滤，攻击者可注入 CRLF 字符改变邮件头结构。Flask-Mail 依赖底层的 `smtplib` 和 `email` 模块，继承了相同的注入风险。

**代码示例与审计要点**

```python
from flask_mail import Mail, Message

# 危险：直接使用用户输入
msg = Message(
    subject=request.form.get('subject'),
    sender=request.form.get('from'),
    recipients=[request.form.get('to')]
)
msg.body = request.form.get('body')
msg.add_recipient(request.form.get('cc'))
mail.send(msg)

# 危险：自定义头部
msg.extra_headers = {'X-Custom': request.args.get('header')}
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `flask_mail.Message`、`Message(`、`mail.send()`
- 查找参数赋值：`subject=`、`sender=`、`recipients=`、`cc=`、`bcc=`
- 定位用户输入来源：`request.form.get()`、`request.args.get()`、`request.json`
- 检查 `extra_headers`、`add_recipient()` 的使用

**快速定位保护机制 (L2: 跳读)**
- 搜索验证装饰器：`@validate`、表单验证
- 查找 CRLF 过滤：`replace('\r\n', '')`、`replace('\n', '')`
- 检查 Flask-WTF 表单验证：`EmailField`、`validators.Email()`
- 查看是否使用蓝图级别的输入验证中间件

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接传给 `Message` 构造函数的参数
   - `recipients`、`cc`、`bcc` 列表包含未验证的用户输入
   - `extra_headers` 字典值拼接用户数据
   - 未进行 CRLF 过滤或邮箱格式验证
   - 能成功注入 `\r\n` 改变邮件头

2. **确认为误报的情况**：
   - 使用 Flask-WTF 的 `EmailField` 并启用验证
   - 所有邮箱地址通过 `wtforms.validators.Email()` 验证
   - 使用 `email-validator` 库额外验证
   - 邮箱地址来自用户模型的数据库字段，不直接接受输入

3. **代码异味判断**：
   - 验证存在但不完整（仅检查字符串非空）
   - 验证在某些请求路径中缺失
   - 使用了 `validate_on_submit()` 但表单定义中缺少 `Email` 验证器

---

## Low risk

**这些情况应给予低风险评级**

1. **Flask-WTF 验证**：所有邮件字段使用 Flask-WTF 的 `EmailField` 和 `validators.Email()` 自动验证

2. **严格过滤**：在传入 `Message` 前，所有用户输入都经过 CRLF 过滤和邮箱格式验证

3. **数据库来源**：邮箱地址从用户模型查询，用户仅能选择已验证的邮箱

4. **蓝图中间件**：使用路由级别的输入验证装饰器统一处理所有邮件相关输入

5. **仅内部使用**：Flask-Mail 配置的 SMTP 服务器仅用于内部通知，不对外发送邮件
