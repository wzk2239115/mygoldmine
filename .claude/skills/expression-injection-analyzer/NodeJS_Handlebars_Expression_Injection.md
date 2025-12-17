# Node.js Handlebars 模板表达式注入

**漏洞成因**：Handlebars 模板引擎中用户输入直接嵌入模板表达式，或通过 Handlebars helper 函数执行用户代码，导致模板注入或任意代码执行。常见于邮件模板、动态报告生成、用户自定义模板等场景。

---

## Details

**代码示例**：
```javascript
// 危险：用户输入作为模板内容
const Handlebars = require('handlebars');
const userTemplate = req.body.template;
const template = Handlebars.compile(userTemplate);
const result = template({ data: userData });

// 危险：模板注入载荷
// userTemplate = "{{#if (constructor.prototype.constructor('return process.env')())}}...{{/if}}"

// 较安全：白名单 helper 函数
const Handlebars = require('handlebars');
Handlebars.registerHelper('safe_helper', (context) => {
    // 仅执行预定义的安全操作
    return context.value.toUpperCase();
});

// 较安全：使用预编译模板
const fs = require('fs');
const template = Handlebars.compile(fs.readFileSync('safe.hbs', 'utf8'));
const result = template(userData);  // 模板由应用内部维护
```

**快速定位核心操作**：
- 关键词：`Handlebars.compile`、`registerHelper`、`{{}}` 表达式、用户模板处理
- 查看模板来源是否为用户可控
- 检查已注册的 helper 函数是否存在危险操作
- 追踪模板中可访问的上下文对象
- 关注是否存在访问对象原型链的表达式

**快速定位保护机制**：
- 是否使用预编译和预定义的模板
- 是否限制了可用的 helper 函数
- 是否禁用了原型链访问和反射调用
- 是否对用户输入进行了 HTML 转义
- 是否使用了自定义的安全编译选项

**审计等级**：**L2-L3**
- **L2**：跳读模板编译和 helper 注册代码
- **L3**：逐行分析模板上下文和 helper 实现

---

## Classify

**确认为漏洞**：
- 用户输入直接用作 Handlebars 模板内容
- 注册的 helper 函数包含危险操作（eval、require、system 调用等）
- 模板可访问构造函数或原型链对象
- 不存在对模板语法的限制

**误报**：
- 模板完全由应用内部定义和维护
- 所有用户输入都通过数据上下文传递且被转义
- 仅允许预定义的安全 helper 函数

**代码异味**：
- Helper 函数实现不规范，包含过多业务逻辑
- 模板处理逻辑复杂，难以追踪变量来源

---

## Low Risk

以下情况可评为低风险：
- **预定义模板**：所有模板都是静态文件，由开发者维护
- **限制的上下文**：模板仅能访问预定义的数据对象
- **安全的 helper**：仅暴露白名单中的 helper 函数
- **内网应用**：仅由内部可信用户使用
- **输出转义**：所有输出都进行了 HTML 转义

**注意**：Handlebars 的表达式功能强大，需要多层防护。
