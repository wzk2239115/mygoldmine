# NodeJS_SSTI_Mustache_User_Variable

**漏洞类型**: Mustache 模板引擎中用户可控变量直接渲染，可能导致注入攻击

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 用户输入作为模板内容
const Mustache = require('mustache');
const template = req.body.template;
const rendered = Mustache.render(template, {data: userData});

// 模板字符串拼接用户输入
const tpl = "Hello {{" + req.query.varName + "}}";
const output = Mustache.render(tpl, context);

// 使用三重大括号输出未转义内容
const template = "Welcome {{{username}}}";
Mustache.render(template, {username: req.body.name});

// 用户控制部分模板路径
const partial = req.params.template;
Mustache.render(mainTemplate, data, {partial: fs.readFileSync(partial, 'utf8')});

// Lambda 函数中执行用户输入
const view = {
    execute: function() {
        return eval(req.query.code);  // 危险的 eval
    }
};
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 渲染函数: `Mustache.render()`, `Mustache.parse()`, `Mustache.compile()`
- 未转义标签: `{{{ }}}` (三重大括号)、`{{& }}`
- 用户输入: `req.query`, `req.body`, `req.params`, `req.cookies`
- 模板配置: `Mustache.tags`, `partials`
- Lambda 函数: 模板中的函数调用

**L2 跳读定位**:
- 追踪用户输入到 `render()` 第一个参数（模板）
- 检查模板字符串是否通过拼接构造
- 定位 `{{{ }}}` 三重大括号的使用位置
- 搜索 partials 配置中是否包含用户可控路径
- 关注 view 对象中的 lambda 函数实现

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入验证: 模板白名单如 `TEMPLATES.includes(templateName)`
- 安全标签: 使用 `{{ }}` 双大括号（自动转义）
- 模板预编译: 使用 `Mustache.parse()` 提前编译模板
- Partials 限制: 仅从可信目录加载部分模板
- 禁用 Lambda: 不在 view 中传递函数

**L3 逐行分析**:
- 模板来源:
  - 模板是否从文件系统预定义位置加载
  - 是否接受用户提交的完整模板内容
  - 模板名称是否经过白名单验证
- 输出方式:
  - `{{ }}` 双大括号自动 HTML 转义（安全）
  - `{{{ }}}` 三重大括号输出原始 HTML（危险）
  - `{{& }}` 也输出未转义内容（危险）
- View 对象安全:
  - 是否包含用户可控的函数或方法
  - Lambda 函数是否执行外部输入
  - 是否限制了可访问的对象属性
- Partials 配置:
  - 部分模板是否从固定路径加载
  - 是否验证 partial 名称和路径

**L4 跨模块追踪**:
- 追踪完整的请求处理流程：路由 → 控制器 → 模板渲染
- 检查是否有全局 Mustache 配置限制危险特性
- 验证模板加载中间件的安全策略
- 检查框架层面是否有输入过滤机制
- 追踪 view 对象的构造过程，确认数据来源

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `Mustache.render()` 的模板参数
- 模板中使用 `{{{ }}}` 输出用户可控变量且无验证
- View 对象中的 lambda 函数执行用户输入代码
- Partials 路径或内容可被用户控制
- 模板标签分隔符被用户输入修改

**误报判定**:
- 模板完全预定义，用户仅控制通过 `{{ }}` 输出的值
- 模板名称虽可选择但经过严格白名单验证
- 所有用户输入在传入 view 前经过编码和验证
- Partials 完全从可信的静态文件加载
- 使用了 CSP 策略阻止脚本执行

**代码异味**:
- 模板路径通过拼接构造如 `'views/' + name + '.mustache'`
- 虽用 `{{ }}` 但模板结构本身可被用户影响
- View 对象包含过多方法或引用了全局对象
- 使用黑名单过滤如禁止 `<script>` 标签
- Partials 名称可被用户部分控制
- 在模板中使用 sections 且迭代数据未验证

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板选择功能仅限认证管理员使用
- 自定义模板需要经过审核流程
- 功能部署在内部网络，无公网暴露
- 实施了严格的基于角色的访问控制

**架构设计防护**:
- 所有模板在构建时预编译和验证
- 使用独立的模板渲染微服务
- 实现了完整的 CSP 策略
- 模板输出仅用于邮件等非 Web 场景

**输入与输出保护**:
- 用户输入经过严格的类型和格式验证
- 模板名称白名单验证且路径固定
- 强制所有变量使用 `{{ }}` 双大括号
- 输出前进行二次 HTML 净化处理

**监控与运行环保**:
- 运行在受限容器环境，文件系统只读
- 进程以低权限用户运行
- 完整的请求审计和异常监控
- 实时检测模板注入攻击特征
