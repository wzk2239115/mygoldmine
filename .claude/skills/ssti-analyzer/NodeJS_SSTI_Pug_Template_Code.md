# NodeJS_SSTI_Pug_Template_Code

**漏洞类型**: Pug 模板中用户输入作为模板代码或未转义输出

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 用户输入作为模板内容
const pug = require('pug');
const userTemplate = req.body.template;
const fn = pug.compile(userTemplate);
const html = fn({data: 'value'});

// 使用 != 输出未转义内容
const template = `p!= username`;
pug.render(template, {username: req.query.name});

// 模板路径用户可控
const tmplFile = req.params.template + '.pug';
const compiledFunction = pug.compileFile(tmplFile);

// 在模板中执行代码
// Pug 模板: - var code = userInput
pug.render(template, {userInput: req.body.code});

// 内联 JavaScript
// Pug 模板: script= userScript
pug.render(template, {userScript: req.query.js});
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 编译函数: `pug.compile()`, `pug.compileFile()`, `pug.render()`, `pug.renderFile()`
- 未转义输出: `!=`, `!{}`
- 代码执行: `-`, `=`（变量定义和赋值）
- 内联代码: `script.`, `style.`
- 用户输入: `req.body`, `req.query`, `req.params`, `req.cookies`

**L2 跳读定位**:
- 从用户输入追踪到 `compile()` 或 `render()`
- 检查模板字符串是否包含用户输入
- 搜索 `!=` 和 `!{}` 未转义输出
- 定位 compileFile 路径是否可控
- 关注模板中的 `-` 代码执行行

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 转义输出: 使用 `=` 和 `#{}` 代替 `!=` 和 `!{}`
- 模板白名单: 模板名称白名单验证
- 模板预编译: 构建时预编译模板
- 路径限制: basedir 选项限制包含路径
- 禁用功能: pretty 选项和 debug 模式

**L3 逐行分析**:
- 编译选项:
  - `basedir` 是否限制模板目录
  - `filename` 是否固定或验证
  - `compileDebug` 是否禁用（生产环境）
- 模板来源:
  - 是否接受用户提交的完整模板字符串
  - compileFile 路径是否用户可控
  - 是否仅从可信目录加载
- 输出方式:
  - `=` 和 `#{}` 自动转义（安全）
  - `!=` 和 `!{}` 不转义（危险）
  - 缓冲代码 `-` 可执行任意 JS
- 模板语法:
  - 是否使用 `-` 执行用户可控代码
  - include/extends 路径是否可控
  - mixin 定义是否安全

**L4 跨模块追踪**:
- 追踪从路由 → 控制器 → 模板渲染的数据流
- 检查全局 Pug 配置
- 验证模板文件存储位置和权限
- 检查 Express 视图引擎配置
- 追踪自定义过滤器和函数

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `compile()` 参数
- 模板中使用 `!=` 或 `!{}` 输出用户数据
- compileFile 路径可被用户控制
- 模板中使用 `-` 执行用户可控代码
- 内联 script/style 包含用户输入

**误报判定**:
- 模板完全预定义，用户仅控制通过 `=` 输出的值
- 模板名称经过严格白名单验证
- basedir 限制且路径经过验证
- 所有用户输入在传入前已转义
- 模板在构建时预编译

**代码异味**:
- 虽用 `=` 但模板结构可被用户影响
- 模板路径通过拼接构造
- 大量使用 `!=` 未转义输出
- 在模板中使用复杂的 JavaScript 逻辑
- 未设置 basedir 限制
- 使用旧版 Pug 存在已知漏洞

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染仅限管理员使用
- 需要强身份验证
- 功能部署在内网
- 严格访问控制

**架构设计防护**:
- 所有模板在构建时预编译
- 设置严格的 basedir 限制
- 禁用 debug 和 pretty 选项
- 实现 CSP 策略

**输入与输出保护**:
- 模板名称严格白名单验证
- 强制使用 `=` 和 `#{}` 转义
- 禁止在模板中使用 `-` 执行代码
- 路径规范化后检查前缀

**监控与运行环保**:
- 模板文件权限严格控制
- 完整审计日志
- 实时监控异常模板访问
- 容器环境文件系统只读
