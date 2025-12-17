# NodeJS_SSTI_EJS_Unescaped_Input

**漏洞类型**: 使用 EJS 模板引擎时未对用户输入进行转义，直接将用户可控内容嵌入模板渲染

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 直接使用用户输入作为模板内容
const ejs = require('ejs');
const userTemplate = req.query.template;
const result = ejs.render(userTemplate, {data: 'value'});

// 使用 <%- %> 输出未转义内容
const template = '<h1><%- username %></h1>';
ejs.render(template, {username: req.body.name});  // 用户输入直接渲染

// compile 方法接受用户可控模板
const compiled = ejs.compile(req.body.tpl);
const output = compiled({user: userData});

// renderFile 但模板路径用户可控
const path = req.query.template + '.ejs';
ejs.renderFile(path, data, (err, html) => {
    res.send(html);
});

// options 中 escape 被设置为 false
ejs.render(templateString, data, {escape: false});
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板渲染函数: `ejs.render()`, `ejs.compile()`, `ejs.renderFile()`, `ejs.renderString()`
- 未转义标签: `<%- %>` (输出原始 HTML), `<% %>` (执行代码)
- 用户输入源: `req.query`, `req.body`, `req.params`, `req.cookies`, `req.headers`
- 配置项: `options.escape`, `options.async`, `options.compileDebug`
- 文件操作: `renderFile()` 与路径拼接

**L2 跳读定位**:
- 从路由处理函数追踪 `req.*` 到 `ejs.render()` 的数据流
- 关注模板字符串是否来自外部输入或文件读取
- 检查模板中是否使用 `<%- %>` 标签输出用户可控变量
- 搜索 `ejs.compile()` 是否接受动态生成的模板代码
- 定位 `renderFile()` 的路径参数是否包含用户输入

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入验证: 检查是否有白名单验证如 `ALLOWED_TEMPLATES.includes()`
- 转义使用: 查找 `<%= %>` 标签代替 `<%- %>`（自动 HTML 转义）
- 配置检查: `options.escape = true` 或未设置（默认转义）
- 模板预编译: 使用预编译的模板而非动态生成
- 路径限制: `path.basename()` 或白名单验证模板文件名

**L3 逐行分析**:
- 模板来源检查:
  - 是否直接接受用户输入作为模板内容
  - 模板是否从可信的文件系统位置加载
  - 是否存在模板内容的白名单验证
- 输出标签使用:
  - `<%= %>` 自动转义 HTML 特殊字符（安全）
  - `<%- %>` 输出原始内容不转义（危险）
  - `<% %>` 执行代码但不输出（可能危险）
- Options 配置:
  - `escape: true` 启用转义
  - `client: false` 禁止客户端编译
  - `strict: true` 启用严格模式
- 变量上下文:
  - 传入 render 的数据对象是否包含敏感方法
  - 是否限制了可访问的全局变量和函数

**L4 跨模块追踪**:
- 追踪从输入验证中间件 → 路由处理 → 模板渲染的完整流程
- 检查是否有全局 EJS 配置文件限制危险选项
- 验证模板文件的访问权限和目录限制
- 检查是否使用了安全的模板加载器或中间件
- 追踪 Express/Koa 框架的视图引擎配置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `ejs.render()` 或 `ejs.compile()` 的模板参数
- 模板中使用 `<%- %>` 标签输出用户可控变量且无转义
- 使用 `<% %>` 标签执行用户可控的代码逻辑
- `renderFile()` 的路径参数完全或部分由用户输入控制
- 设置 `escape: false` 关闭自动转义且输出用户数据

**误报判定**:
- 模板内容完全预定义，用户仅控制通过 `<%= %>` 输出的变量值
- 使用了严格的白名单验证模板文件名，且路径固定在安全目录
- 所有用户输入在渲染前经过 HTML 实体编码或消毒
- 模板完全静态，仅在构建时生成，运行时不接受用户输入
- 使用了内容安全策略 (CSP) 完全阻止内联脚本执行

**代码异味**:
- 虽使用 `<%= %>` 但模板本身的结构可被用户影响
- 模板路径通过字符串拼接构造如 `'templates/' + req.query.name + '.ejs'`
- 使用黑名单过滤危险字符如禁用 `<script>` 但未处理其他注入点
- 在模板中引入了过多的辅助函数或全局对象
- 使用了过时的 EJS 版本存在已知安全问题
- 条件渲染或循环的控制变量来自用户输入

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染功能仅限管理员或内部用户使用，有强身份验证
- 用户提交的模板需要经过人工审核才能被系统渲染
- 功能部署在隔离的内网环境，无公网访问入口
- 使用基于角色的访问控制限制模板编辑权限

**架构设计防护**:
- 所有模板文件在构建阶段预编译，运行时只加载编译后的函数
- 使用独立的模板渲染服务，与主应用进程隔离
- 实现了完整的内容安全策略 (CSP) 阻止脚本执行
- 模板渲染结果仅用于生成静态文件，不直接返回给用户

**输入与输出保护**:
- 用户输入经过严格的白名单验证，仅允许字母数字
- 即使路径可控，也通过 `path.basename()` + 白名单限制文件访问
- 所有模板变量在渲染时强制使用 `<%= %>` 进行 HTML 转义
- 渲染输出经过二次净化处理，移除潜在的危险标签

**监控与运行环保**:
- 应用运行在受限的容器环境，文件系统只读挂载
- 进程以最低权限用户运行，无系统命令执行权限
- 部署了完整的审计日志记录所有模板渲染请求
- 实时监控异常模板访问和渲染错误，触发告警机制
