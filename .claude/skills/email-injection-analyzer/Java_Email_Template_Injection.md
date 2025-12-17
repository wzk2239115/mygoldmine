# Java Email Template Injection

## Details

Java 应用使用模板引擎（如 Freemarker、Velocity、Thymeleaf）渲染邮件内容时，若用户输入直接嵌入模板未经转义，攻击者可注入模板指令。这可能导致服务器端模板注入（SSTI）、敏感信息泄露、远程代码执行或邮件内容篡改。

**代码示例与审计要点**

```java
// 危险：Freemarker 模板注入
Configuration cfg = new Configuration();
Template template = new Template("email",
    "Hello " + userName + ", your code is: ${code}", cfg);
StringWriter out = new StringWriter();
template.process(data, out);
sendEmail(recipient, out.toString());

// 危险：Velocity 用户输入作为模板
VelocityEngine ve = new VelocityEngine();
String templateStr = request.getParameter("emailTemplate");
StringReader reader = new StringReader(templateStr);
Template template = ve.getTemplate(reader);
template.merge(context, writer);

// 危险：Thymeleaf 动态模板
Context ctx = new Context();
ctx.setVariable("name", userInput);
String html = templateEngine.process("email-" + userInput, ctx);
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `freemarker.template.Template`、`org.apache.velocity.Template`、`TemplateEngine`
- 查找模板创建：`new Template(`、字符串拼接到模板
- 定位用户输入：`request.getParameter()`、`@RequestParam`、表单数据
- 检查 `process()`、`merge()`、`evaluate()` 的调用

**快速定位保护机制 (L2: 跳读)**
- 搜索自动转义配置：Freemarker 的 `auto_escaping`、Thymeleaf 的默认转义
- 查找手动转义：`StringEscapeUtils.escapeHtml4()`、`?html` 指令
- 检查模板是否从文件加载：`cfg.setDirectoryForTemplateLoading()`
- 查看沙箱配置：Freemarker 的 `TemplateClassResolver.SAFER_RESOLVER`

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到模板字符串中
   - 允许用户提供完整的模板内容
   - 模板引擎未启用自动转义或使用不安全的解析器
   - 可通过输入 `<#assign ex="freemarker.template.utility.Execute"?new()> ${ex("calc")}` 测试注入
   - 能执行任意 Java 代码或访问敏感对象

2. **确认为误报的情况**：
   - 模板完全从文件系统加载，用户输入仅作为上下文变量
   - Freemarker 使用 `SAFER_RESOLVER` 限制类访问
   - Thymeleaf 使用默认转义，所有变量自动 HTML 转义
   - 用户输入经过严格的 HTML 转义

3. **代码异味判断**：
   - 使用 `?no_esc` 或 `th:utext` 禁用转义
   - 模板中可访问 `class`、`classLoader` 等危险属性
   - 转义仅在部分代码路径中执行

---

## Low risk

**这些情况应给予低风险评级**

1. **静态模板**：所有邮件模板从文件系统加载（`cfg.setDirectoryForTemplateLoading()`），用户输入仅作为数据

2. **安全配置**：Freemarker 使用 `cfg.setNewBuiltinClassResolver(TemplateClassResolver.SAFER_RESOLVER)` 限制类访问

3. **自动转义**：Thymeleaf 使用 `th:text` 而非 `th:utext`，自动 HTML 转义所有变量

4. **输入转义**：所有用户输入在传入模板前都经过 `StringEscapeUtils.escapeHtml4()` 转义

5. **纯文本邮件**：仅发送纯文本邮件，不使用 HTML 模板，模板注入风险降低
