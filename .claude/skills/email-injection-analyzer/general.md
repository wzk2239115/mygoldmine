# Email Injection - 通用审计指南

## Details

邮件注入漏洞是指攻击者通过在邮件相关输入中注入特殊字符（如 CRLF、特殊邮件头、模板指令等），篡改邮件结构、头部或内容的安全漏洞。此类漏洞可能导致垃圾邮件发送、邮件欺骗、信息泄露、模板注入（SSTI）等风险。

**主要漏洞类型**

1. **SMTP/邮件头 CRLF 注入**：通过注入 `\r\n` 字符添加额外的邮件头或修改现有头部
2. **邮件地址验证绕过**：通过特殊构造的邮箱地址绕过验证逻辑
3. **邮件模板注入**：在模板引擎中注入模板指令导致 SSTI 或信息泄露
4. **SMTP 命令注入**：在自定义 SMTP 客户端中注入额外的 SMTP 命令
5. **邮件内容篡改**：通过未转义的用户输入篡改邮件正文或 HTML 内容

**代码示例与审计要点**

```
# 通用危险模式（跨语言）

# 1. CRLF 注入
email_header = "To: " + user_input + "\r\n"
subject = "Subject: " + user_subject + "\r\n"

# 2. 验证绕过
if "@" in email and "." in email:  # 过于简单
    send_email(email)

# 3. 模板注入
template = "Hello " + user_name + ", your code is: {{code}}"
render(template, context)

# 4. 命令注入
smtp_cmd = "MAIL FROM:<" + user_email + ">\r\n"
socket.send(smtp_cmd)
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮件发送函数：`send_mail`、`sendMail`、`send`、`smtp`、`mail(`
- 查找邮件库导入：`javax.mail`、`smtplib`、`nodemailer`、`net/smtp`、`lettre`
- 定位用户输入使用：邮箱地址、主题、发件人、抄送、邮件内容
- 检查模板渲染：`render`、`compile`、`Template`、`execute`

**快速定位保护机制 (L2: 跳读)**
- 搜索验证函数：`validate_email`、`isEmail`、`EmailValidator`、`filter_var`
- 查找 CRLF 过滤：`replace("\r", "")`、`replace("\n", "")`、`replaceAll`
- 检查模板转义：`autoescape`、`escape()`、`htmlspecialchars()`
- 查看是否使用成熟的邮件库（较新版本通常有内置保护）

---

## Classify

**理论研判标准**

### 1. 确认为漏洞的标志

**CRLF 注入**：
- 用户输入直接拼接到邮件头字段（To、From、Subject、Cc、Bcc）
- 自定义头部值包含未过滤的用户数据
- 未进行 CRLF（`\r\n`）字符过滤
- 能通过注入 `\r\n` 添加额外的邮件头

**验证绕过**：
- 仅检查 `@` 和 `.` 符号存在
- 正则表达式不完整，允许换行符、空格等特殊字符
- 未验证邮箱的本地部分和域名部分格式
- 允许连续点号、多个 `@` 符号

**模板注入**：
- 用户输入直接拼接到模板字符串中
- 允许用户提供完整的模板内容
- 模板引擎未启用自动转义
- 可执行任意代码或访问敏感对象

**命令注入**：
- 用户输入直接拼接到 SMTP 命令中
- 使用低级 API 手动构建 SMTP 命令
- 未进行命令参数验证和特殊字符过滤

### 2. 确认为误报的情况

**充分验证**：
- 使用标准库的邮箱验证函数（如 `filter_var(FILTER_VALIDATE_EMAIL)`、`EmailValidator.isValid()`）
- 正则表达式符合 RFC 5322 标准
- 额外验证域名 MX 记录

**安全过滤**：
- 所有用户输入都经过 CRLF 过滤
- 使用较新版本的邮件库（通常有内置保护）
- 邮件头通过严格策略自动验证

**模板安全**：
- 模板完全从文件系统加载，用户输入仅作为数据
- 使用沙箱模板环境或自动转义
- 所有用户输入经过 HTML 转义

**白名单机制**：
- 邮箱地址仅来自数据库查询或配置文件
- 用户只能从预定义列表中选择，无法输入任意值

### 3. 代码异味判断

- 验证存在但不完整（仅检查部分字符或格式）
- 过滤不彻底（仅过滤 `\n` 未过滤 `\r`）
- 验证在某些代码路径或条件分支中缺失
- 使用不安全的字符串函数（C 语言中的 `sprintf`、`strcpy`）
- 验证后未使用验证结果，仍使用原始输入

---

## Low risk

**这些情况应给予低风险评级**

### 1. 标准库验证
使用语言标准库或框架提供的邮箱验证功能：
- Python: `django.core.validators.validate_email()`, `email-validator`
- PHP: `filter_var($email, FILTER_VALIDATE_EMAIL)`
- Java: `EmailValidator.getInstance().isValid()`, `@Email` 注解
- Node.js: `validator.isEmail()`, `express-validator`
- Go: `mail.ParseAddress()`
- Rust: `email_address` crate, `Mailbox::new()`

### 2. 成熟邮件库
使用维护良好的邮件库，较新版本通常有内置保护：
- Python: Django Mail, Flask-Mail (配合验证)
- PHP: PHPMailer 6.0+, SwiftMailer 6.0+
- Java: Spring Mail, Commons Email 1.5+
- Node.js: Nodemailer 6.0+
- Go: gomail, github.com/jordan-wright/email
- Rust: Lettre 0.10+

### 3. 严格输入过滤
所有邮件相关输入都经过多层过滤：
- CRLF 过滤：`replace('\r\n', '').replace('\r', '').replace('\n', '')`
- 邮箱格式验证
- 长度限制检查
- 特殊字符白名单

### 4. 模板安全
- 静态模板从文件系统加载
- 启用自动转义（autoescape）
- 使用沙箱模板环境
- 仅发送纯文本邮件（不使用 HTML 模板）

### 5. 环境隔离与访问控制
- SMTP 服务器仅限内部使用，不对外发送
- 邮件功能仅限管理员使用，不对公众开放
- 实现速率限制防止滥用
- 白名单域名或收件人地址

### 6. 代码质量保证
- 代码通过静态分析工具检查（无缓冲区溢出、注入警告）
- 单元测试覆盖邮件注入测试用例
- 安全代码审查通过
- 使用现代编程语言的类型系统保护（Rust、TypeScript）

---

## 审计流程建议

1. **快速扫描 (L1)**：使用关键词搜索定位所有邮件发送代码
2. **验证检查 (L2)**：跳读检查是否有邮箱验证和 CRLF 过滤
3. **深度分析 (L3)**：对缺少保护的代码逐行分析数据流
4. **跨模块追踪 (L4)**：追踪用户输入从接收到邮件发送的完整流程
5. **模板审查**：特别关注邮件模板渲染代码，检查 SSTI 风险
6. **库版本检查**：确认使用的邮件库版本是否有已知漏洞

---

## 常见绕过技巧（审计时需注意）

1. **编码绕过**：URL 编码、Unicode 编码的 CRLF 字符
2. **换行符变体**：`\r`、`\n`、`\r\n`、`%0d%0a`
3. **长邮箱地址**：超长邮箱地址可能导致缓冲区溢出
4. **国际化域名**：IDN homograph 攻击
5. **邮箱注释**：RFC 5322 允许的注释语法 `user(comment)@domain.com`
6. **折叠头部**：多行头部通过空格或制表符连接

---

## 参考标准

- RFC 5321: Simple Mail Transfer Protocol
- RFC 5322: Internet Message Format
- OWASP Email Injection
- CWE-93: Improper Neutralization of CRLF Sequences
- CWE-74: Improper Neutralization of Special Elements
- CWE-1336: Improper Neutralization of Special Elements in Template Engines
