# NodeJS_SSTI_Nunjucks_Unfiltered_Input

**漏洞类型**: Nunjucks 模板渲染时用户输入未过滤直接嵌入模板

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 用户输入作为模板内容
const nunjucks = require('nunjucks');
const userTemplate = req.body.template;
const res = nunjucks.renderString(userTemplate, {data: 'value'});

// 使用 safe 过滤器输出未转义内容
const template = '{{ username | safe }}';
nunjucks.renderString(template, {username: req.query.name});

// 禁用自动转义
const env = nunjucks.configure({autoescape: false});
env.renderString(templateStr, context);

// 模板路径用户可控
const tmplPath = req.params.template + '.html';
nunjucks.render(tmplPath, data);

// include/extends 路径来自用户输入
// 模板中: {% include userPath %}
nunjucks.renderString(template, {userPath: req.query.include});
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 渲染函数: `nunjucks.renderString()`, `nunjucks.render()`, `nunjucks.compile()`
- 配置方法: `nunjucks.configure()`, `new nunjucks.Environment()`
- 过滤器: `| safe`, `| escape`
- 标签: `{% include %}`, `{% extends %}`, `{% import %}`
- 用户输入: `req.body`, `req.query`, `req.params`, `req.cookies`

**L2 跳读定位**:
- 从用户输入追踪到 `renderString()` 或 `compile()`
- 检查模板字符串是否包含用户输入
- 搜索 `| safe` 过滤器的使用
- 定位 autoescape 配置是否为 false
- 关注 include/extends 路径是否可控

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 自动转义: `autoescape` 是否启用（默认启用）
- 模板白名单: 模板名称白名单验证
- 模板预编译: 使用 `precompile()` 提前编译
- 路径限制: FileSystemLoader 限制目录
- 安全过滤器: 避免使用 `| safe`

**L3 逐行分析**:
- Environment 配置:
  - `autoescape` 设置（默认 true 为安全）
  - `throwOnUndefined` 是否启用
  - loader 配置是否安全
- 模板来源:
  - 是否接受用户提交的完整模板字符串
  - render() 的模板名是否用户可控
  - FileSystemLoader 路径是否受限
- 过滤器使用:
  - 是否使用 `| safe` 输出用户数据
  - 是否自定义了不安全的过滤器
  - 默认 escaping 是否被绕过
- 标签安全:
  - include/extends 路径是否可控
  - 是否使用了 call 或 macro 执行代码
  - 自定义标签实现是否安全

**L4 跨模块追踪**:
- 追踪从路由 → 控制器 → 模板渲染的数据流
- 检查全局 Nunjucks 配置
- 验证模板文件存储位置和权限
- 检查中间件的输入过滤
- 追踪自定义扩展和过滤器

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `renderString()` 参数
- 设置 `autoescape: false` 禁用自动转义
- 使用 `| safe` 过滤器输出用户可控数据
- 模板名称可被用户完全或部分控制
- include/extends 路径来自用户输入

**误报判定**:
- 模板完全预定义，用户仅控制变量值
- 启用 autoescape 且无 `| safe` 使用
- 模板名称经过严格白名单验证
- FileSystemLoader 限制在安全目录
- 所有用户输入在传入前已转义

**代码异味**:
- 虽启用 autoescape 但大量使用 `| safe`
- 模板路径通过拼接构造
- 自定义过滤器未经安全审计
- 在模板中使用复杂的宏和调用
- Nunjucks 版本过低存在已知漏洞
- 模板变量名可被用户影响

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染仅限管理员使用
- 需要强身份验证
- 功能部署在内网
- 严格访问控制

**架构设计防护**:
- 强制启用 autoescape
- 模板全部预编译
- FileSystemLoader 限制目录
- 实现 CSP 策略

**输入与输出保护**:
- 模板名称严格白名单验证
- 禁止使用 `| safe` 过滤器
- 所有变量强制转义
- 路径规范化后检查前缀

**监控与运行环保**:
- 模板文件权限严格控制
- 完整审计日志
- 实时监控异常模板访问
- WAF 检测注入特征
