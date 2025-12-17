# Python SMTP Header CRLF Injection

## Details

Python 标准库 `smtplib` 和 `email` 模块在构建 SMTP 命令和邮件头时，若用户输入包含 CRLF 字符（`\r\n`）未被过滤，攻击者可注入额外的邮件头或 SMTP 命令。这可能导致邮件头伪造、垃圾邮件发送或 SMTP 命令注入。

**代码示例与审计要点**

```python
import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg['From'] = user_from  # 危险：直接使用用户输入
msg['To'] = user_to
msg['Subject'] = user_subject
msg.set_content(body)

# 危险：自定义头部拼接用户输入
msg['X-Custom-Header'] = user_header

server = smtplib.SMTP('localhost')
server.send_message(msg)
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `smtplib.SMTP`、`EmailMessage`、`email.message.Message`
- 查找头部设置：`msg['From']`、`msg['To']`、`msg['Subject']`、`msg.add_header()`
- 定位 `send_message()`、`sendmail()` 调用
- 检查是否使用 `email.parser` 解析用户提供的邮件内容

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`replace('\r', '')`、`replace('\n', '')`、`splitlines()[0]`
- 查找邮箱验证：`email.utils.parseaddr()`、`re.match()` 正则验证
- 检查头部值的白名单验证或字符限制
- 查看是否使用 `email.policy.SMTP` 或 `email.policy.default` 的严格策略

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接赋值给 `msg['From']`、`msg['Subject']` 等头部字段
   - 自定义头部值包含未过滤的用户数据
   - 未进行 CRLF 字符过滤
   - 能通过注入 `\r\n` 添加额外的邮件头或修改邮件结构
   - 可能通过头部注入绕过 SPF/DKIM 验证

2. **确认为误报的情况**：
   - 所有头部值都经过 CRLF 过滤或仅允许单行内容
   - 使用 `email.policy.SMTP` 严格策略自动验证头部格式
   - 邮箱地址通过 `email.utils.parseaddr()` 解析并验证
   - 用户输入仅用于邮件正文，不涉及头部字段

3. **代码异味判断**：
   - 验证不完整：仅检查是否包含 `@` 而未验证完整格式
   - 过滤不彻底：仅过滤 `\n` 未过滤 `\r`
   - 在某些代码路径中缺少验证

---

## Low risk

**这些情况应给予低风险评级**

1. **严格策略**：使用 `email.policy.SMTP` 或 `email.policy.default` 策略，自动拒绝包含 CRLF 的头部值

2. **CRLF 过滤**：所有用户输入在赋值给头部字段前，都进行 `replace('\r\n', '')`、`replace('\r', '')`、`replace('\n', '')` 过滤

3. **邮箱解析验证**：使用 `email.utils.parseaddr()` 解析并验证邮箱格式，拒绝格式不正确的地址

4. **白名单验证**：头部值仅来自预定义列表或数据库查询，用户无法输入任意内容

5. **仅正文输入**：用户输入仅用于邮件正文内容（`set_content()`），不影响任何头部字段
