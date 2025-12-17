# NodeJS Email Template Injection

## Details

Node.js 邮件系统使用模板引擎（如 Handlebars、Pug、EJS、Mustache）渲染邮件内容时，若用户输入直接嵌入模板未经转义，攻击者可注入模板指令。这可能导致服务器端模板注入（SSTI）、敏感信息泄露或邮件内容篡改。

**代码示例与审计要点**

```javascript
const Handlebars = require('handlebars');
const nodemailer = require('nodemailer');

// 危险：用户输入直接拼接到模板字符串
const templateStr = `Hello \${req.body.name}, your code is: {{code}}`;
const template = Handlebars.compile(templateStr);
const html = template({code: secretCode});

// 危险：允许用户提供模板内容
const userTemplate = req.body.emailTemplate;
const template = Handlebars.compile(userTemplate);
const html = template(data);

transporter.sendMail({to: email, subject: 'Test', html: html});
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `Handlebars.compile()`、`pug.compile()`、`ejs.render()`、`mustache.render()`
- 查找模板字符串：`\`...\${...}\``、字符串拼接
- 定位用户输入来源：`req.body`、`req.query`、`req.params`
- 检查 `sendMail()` 的 `html` 或 `text` 参数

**快速定位保护机制 (L2: 跳读)**
- 搜索转义函数：`escapeExpression()`、`htmlEscape()`、`validator.escape()`
- 查找模板选项：`{noEscape: false}`、`{autoescape: true}`
- 检查是否从文件加载模板：`fs.readFile()`、`path.join(__dirname, 'templates')`
- 查看是否使用安全的模板引擎配置

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到模板字符串中
   - 允许用户提供完整模板内容
   - 使用不安全的模板引擎选项（如 `noEscape: true`）
   - 可通过输入 `{{constructor.constructor('return process')()}}` 等测试注入
   - 能执行任意 JavaScript 代码或访问敏感对象

2. **确认为误报的情况**：
   - 模板完全从文件系统加载，用户输入仅作为上下文数据
   - 使用自动转义的模板引擎（如 Handlebars 默认转义 HTML）
   - 模板引擎配置为严格模式，禁止访问原型链
   - 所有用户输入经过 HTML 转义后才传入模板

3. **代码异味判断**：
   - 使用 `{{{triple-stash}}}` 语法禁用转义
   - 模板中使用 `@root`、`this.constructor` 等危险访问器
   - 转义仅在部分代码路径中执行

---

## Low risk

**这些情况应给予低风险评级**

1. **静态模板**：所有邮件模板从文件系统加载，用户输入仅作为数据变量传入，不影响模板结构

2. **自动转义**：使用 Handlebars、Pug 等默认启用 HTML 转义的模板引擎，且未禁用转义

3. **严格模式**：模板引擎配置为沙箱模式或严格模式，限制对原型链和全局对象的访问

4. **输入转义**：所有用户输入在传入模板前都经过 `validator.escape()` 或类似函数转义

5. **纯文本邮件**：仅发送纯文本邮件，不使用 HTML 模板，模板注入风险降低
