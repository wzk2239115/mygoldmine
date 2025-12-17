# NodeJS Express Email Injection

## Details

Express 应用中处理邮件发送时，若未对用户输入进行充分验证和过滤，可能导致多种邮件注入漏洞。常见场景包括：联系表单、用户注册、密码重置等。Express 本身不提供邮件功能，通常配合 Nodemailer 等库使用，需要在路由处理器中实现输入验证。

**代码示例与审计要点**

```javascript
const express = require('express');
const nodemailer = require('nodemailer');
const app = express();

// 危险：未验证的联系表单
app.post('/contact', (req, res) => {
    transporter.sendMail({
        from: req.body.email,  // 用户输入
        to: 'admin@example.com',
        subject: req.body.subject,  // 用户输入
        text: req.body.message
    });
});

// 危险：密码重置邮件
app.post('/reset-password', (req, res) => {
    const email = req.body.email;
    // 未验证邮箱格式
    sendPasswordResetEmail(email, resetToken);
});
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `app.post()`、`router.post()` 中包含邮件发送逻辑的路由
- 查找 `sendMail()`、`send_mail()`、`emailService` 等邮件发送调用
- 定位 `req.body`、`req.query`、`req.params` 用于邮件参数的位置
- 检查联系表单、注册、密码重置等典型场景

**快速定位保护机制 (L2: 跳读)**
- 搜索验证中间件：`express-validator`、`joi`、`yup`
- 查找验证链：`check('email').isEmail()`、`body('email').normalizeEmail()`
- 检查 CRLF 过滤函数
- 查看是否有全局错误处理和输入清理中间件

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 路由处理器直接使用 `req.body` 等用户输入发送邮件
   - 未使用 `express-validator` 或类似验证库
   - 邮箱地址、主题等字段未经验证和过滤
   - 能通过 POST 请求注入恶意邮件头或内容
   - 缺少速率限制，可被滥用发送垃圾邮件

2. **确认为误报的情况**：
   - 使用 `express-validator` 的 `check('email').isEmail()` 验证所有邮箱字段
   - 路由前使用验证中间件，验证失败时拒绝请求
   - 所有字段都经过白名单验证或格式限制
   - 实现了邮件发送速率限制（如 `express-rate-limit`）

3. **代码异味判断**：
   - 验证存在但不完整（仅验证部分字段）
   - 验证错误未正确处理，仍继续执行
   - 某些路由缺少验证中间件

---

## Low risk

**这些情况应给予低风险评级**

1. **Express-Validator**：使用 `express-validator` 的完整验证链验证所有邮件相关输入

2. **验证中间件**：在所有邮件相关路由前应用统一的验证中间件

3. **速率限制**：使用 `express-rate-limit` 限制邮件发送频率，防止滥用

4. **CSRF 保护**：使用 `csurf` 中间件防止跨站请求伪造导致的邮件滥用

5. **内部系统**：邮件发送功能仅限内部管理员使用，不对公众开放
