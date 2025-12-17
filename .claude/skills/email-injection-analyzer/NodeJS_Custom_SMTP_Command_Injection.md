# NodeJS Custom SMTP Command Injection

## Details

使用自定义 SMTP 客户端或低级 SMTP 库（如 `net` 模块直接构造 SMTP 命令）时，未对邮件字段进行验证可导致 SMTP 命令注入。攻击者通过在邮箱地址或邮件头中注入 CRLF 和 SMTP 命令，可改变邮件发送行为或执行任意邮件操作。

**代码示例与审计要点**

```javascript
const net = require('net');
const client = net.createConnection(25, 'smtp.example.com');
client.write(`MAIL FROM: <${userEmail}>\r\n`);
client.write(`RCPT TO: <${userTo}>\r\n`);
client.write(`SUBJECT: ${userSubject}\r\n`);
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `net.createConnection()`、`socket.write()`、SMTP 命令构造（`MAIL FROM:`、`RCPT TO:`、`DATA`）
- 定位参数来源：`req.query`、`req.body`、请求头字段
- 查找字符串拼接操作：`\`...${}...\`` 或 `+ userInput +`
- 检查 SMTP 命令是否包含未验证的用户输入

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`replace(/\r\n/g, '')`、`replace(/[\r\n]/g, '')`
- 查找邮箱验证：正则表达式验证 `/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i`
- 检查是否使用了 `email-validator` 库或 `validator` 库的邮箱验证
- 查看是否存在输入白名单或数据库查询限制

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - SMTP 命令通过字符串拼接直接包含用户输入
   - 邮箱地址未通过正则验证或专业验证库验证
   - 邮件头字段（Subject、From 等）直接拼接用户数据
   - 能成功注入 `\r\n` 并执行额外的 SMTP 命令
   - 用户输入来自不可信的外部请求

2. **确认为误报的情况**：
   - 所有邮箱字段都通过严格的正则验证或 `email-validator` 库验证
   - 在构造 SMTP 命令前进行了完整的 CRLF 过滤
   - 邮箱和邮件头值来自数据库白名单
   - 使用了成熟的邮件库（nodemailer、sendgrid）而非低级 SMTP 操作

3. **代码异味判断**：
   - 验证存在但不完整：仅检查 `includes('@')` 而非完整验证
   - 验证在条件分支中，不完全覆盖所有命令拼接
   - CRLF 过滤在验证之后，不能防止已注入的数据

---

## Low risk

**这些情况应给予低风险评级**

1. **严格正则验证**：所有邮箱字段都通过 RFC 5322 兼容的正则验证，且不包含任何特殊字符

2. **专业验证库**：使用 `email-validator` 或 `validator` 库进行邮箱验证，完整检查格式

3. **完整 CRLF 过滤**：在所有 SMTP 命令拼接前进行彻底的 `\r\n` 过滤

4. **白名单机制**：邮箱地址和邮件头值仅来自数据库或预定义配置，不允许用户自由输入

5. **库级防护**：使用 nodemailer、sendgrid 等成熟邮件库，不直接操作 SMTP 命令

