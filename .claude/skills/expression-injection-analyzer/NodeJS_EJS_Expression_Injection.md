# Node.js EJS 模板表达式注入

**漏洞成因**：EJS 模板引擎中未对用户输入进行充分转义或沙箱化处理，攻击者可通过模板标签（`<%`, `<%-`, `<%=`, `<%%=` 等）在模板中注入代码片段，导致服务端代码执行或信息泄露。常见于用户可自定义模板、动态生成报告或邮件等场景。

---

## Details

**代码示例**：
```javascript
// 危险：直接使用用户输入作为模板
const ejs = require('ejs');
const template = req.body.template;  // 用户提供的模板
const html = ejs.render(template, data);

// 危险：模板中可注入表达式
// template = "<%=  process.env.DATABASE_URL %>"
// 用户可访问 process 对象及环境变量

// 较安全：使用 renderFile 并配置选项
const ejs = require('ejs');
const templatePath = '/safe/templates/template.ejs';
ejs.renderFile(templatePath, data, { escape: true }, (err, html) => {
    // 响应 html
});

// 较安全：限制模板功能，禁用危险分隔符
ejs.render(template, data, {
    openDelimiter: '{{',
    closeDelimiter: '}}',
    escape: true,
    client: false
});
```

**快速定位核心操作**：
- 关键词：`ejs.render`、`renderFile`、`<%-`、`<%=`、`<%`、用户模板处理
- 查看模板来源是否为用户可控（文件上传、请求参数、数据库字段）
- 检查是否使用了内置的转义函数或沙箱化配置
- 追踪模板中可访问的全局对象和函数
- 关注是否存在 `include` 或 `require` 功能被滥用

**快速定位保护机制**：
- 是否使用了安全的分隔符（自定义分隔符替代 `<%` 和 `%>`）
- 是否启用了 `escape` 选项进行输出转义
- 是否限制了模板可访问的数据作用域
- 是否禁用了 `include`、`require` 等危险功能
- 是否对模板内容进行了白名单验证

**审计等级**：**L2-L3**
- **L2**：跳读模板处理代码，识别用户可控模板源
- **L3**：逐行分析 EJS 配置选项和变量上下文

---

## Classify

**确认为漏洞**：
- 用户输入直接用作 EJS 模板内容
- EJS 处理函数的配置未启用转义或沙箱化
- 模板上下文中暴露了 process、require、fs 等危险对象
- 模板支持 `include` 等功能且路径由用户控制

**误报**：
- 模板完全由应用内部定义，不接收用户输入
- 所有用户输入都通过 `locals` 对象传递且被转义
- 模板仅包含硬编码的内容和数据绑定

**代码异味**：
- EJS 配置选项不规范，暴露过多上下文对象
- 模板处理逻辑复杂，难以追踪变量来源
- 支持用户模板但缺少预处理或验证

---

## Low Risk

以下情况可评为低风险：
- **完全沙箱化**：模板仅能访问预定义的 locals 对象，无法访问全局对象
- **用户模板受限**：用户不能直接编辑模板内容，仅能提供数据参数
- **分隔符自定义**：使用非标准分隔符，减少误触发注入的风险
- **内网编辑器**：模板仅由内部管理员编辑，普通用户无权限
- **静态模板**：所有模板都是静态文件，由开发者维护，运行时不修改

**注意**：EJS 的灵活性高，安全配置需要多层防护。
