# NodeJS Nodemailer Header CRLF Injection

## Details

Nodemailer 是 Node.js 最流行的邮件发送库。当用户输入直接传入邮件头字段（`to`、`from`、`subject`、`cc` 等）或自定义头部（`headers`）未经验证和过滤时，攻击者可注入 CRLF 字符（`\r\n`）改变邮件头结构，导致邮件欺骗、垃圾邮件发送或 SMTP 命令注入。

**代码示例与审计要点**

```javascript
const nodemailer = require('nodemailer');
const transporter = nodemailer.createTransport({...});

// 危险：直接使用用户输入
transporter.sendMail({
    from: req.body.from,
    to: req.body.to,
    subject: req.body.subject,
    text: req.body.body,
    cc: req.body.cc,
    headers: {
        'X-Custom-Header': req.body.customHeader
    }
});
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `nodemailer.createTransport`、`transporter.sendMail()`
- 查找邮件选项对象：`{from:`, `to:`, `subject:`, `cc:`, `bcc:`
- 定位用户输入来源：`req.body`、`req.query`、`req.params`
- 检查 `headers` 对象的自定义头部

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`replace(/[\r\n]/g, '')`、`replace(/\r|\n/g, '')`
- 查找邮箱验证：`validator.isEmail()`、正则验证
- 检查是否使用验证中间件：`express-validator`
- 查看 Nodemailer 版本（较新版本有内置保护）

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接传给 `sendMail()` 的 `to`、`from`、`subject` 等字段
   - `headers` 对象值包含未过滤的用户输入
   - 未进行 CRLF 字符过滤
   - 能通过注入 `\r\n` 添加额外的邮件头
   - 可能绕过 SPF/DKIM 验证或注入恶意邮件内容

2. **确认为误报的情况**：
   - 使用 Nodemailer 6.0+ 版本（自动验证和清理头部）
   - 所有邮箱地址通过 `validator.isEmail()` 验证
   - 头部值经过 CRLF 过滤
   - 用户输入仅用于邮件正文，不涉及头部字段

3. **代码异味判断**：
   - 验证不完整：仅检查字符串非空
   - 过滤不彻底：仅过滤 `\n` 未过滤 `\r`
   - 某些代码路径缺少验证

---

## Low risk

**这些情况应给予低风险评级**

1. **新版本 Nodemailer**：使用 Nodemailer 6.0 或更高版本，内置头部验证和 CRLF 清理

2. **CRLF 过滤**：所有用户输入在传入 `sendMail()` 前都经过 `replace(/[\r\n]/g, '')` 过滤

3. **邮箱验证**：使用 `validator.isEmail()` 或 `express-validator` 验证所有邮箱地址

4. **白名单验证**：邮箱地址来自数据库查询或预定义列表，用户无法输入任意内容

5. **仅正文输入**：用户输入仅影响邮件正文（`text`、`html`），不影响任何头部字段
