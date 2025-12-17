# NodeJS_SSTI_Handlebars_User_Content

**漏洞类型**: 使用 Handlebars 模板引擎时用户输入直接作为模板内容进行编译和渲染

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 直接编译用户输入为模板
const Handlebars = require('handlebars');
const userTemplate = req.query.template;
const template = Handlebars.compile(userTemplate);  // 用户输入直接作为模板
const result = template({ name: 'user' });

// 字符串拼接后编译
const userContent = req.body.content;
const tpl = Handlebars.compile('Hello ' + userContent);
const output = tpl({});

// Express 视图引擎配置中使用用户输入
app.set('view engine', 'handlebars');
app.get('/', (req, res) => {
  res.render(req.query.view);  // 用户可控视图名称
});

// 通过 registerPartial 注册用户提供的模板
const userPartial = req.body.partial;
Handlebars.registerPartial('userContent', userPartial);
const template = Handlebars.compile('{{> userContent}}');

// 使用 eval 或动态编译用户提供的模板表达式
const expression = req.query.expr;
const template = Handlebars.compile(`{{${expression}}}`);
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板编译函数: `Handlebars.compile()`, `handlebars()`, `template()`
- 模板渲染方法: `.render()`, `.then()` 链式调用
- 用户输入获取: `req.query`, `req.body`, `req.params`, `req.headers`
- 视图渲染: `res.render()`, `res.view()`, `response.render()`
- 模板注册: `registerPartial()`, `registerHelper()`

**L2 跳读定位**:
- 从用户输入获取点追踪到 `Handlebars.compile()` 的参数
- 检查模板字符串中是否包含用户可控内容
- 关注是否使用了动态视图名称或模板路径
- 搜索是否有模板上下文数据来自用户输入

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入白名单验证: `ALLOWED_TEMPLATES = [...]`, `if (!templates.includes(input))`
- 模板使用限制: 仅编译预定义的模板文件，不接受用户提交的模板代码
- 转义处理: `Handlebars.escapeExpression()`, 对用户输入进行转义
- 沙箱隔离: 使用隔离的模板上下文，限制可访问的变量

**L3 逐行分析**:
- 模板编译方式检查:
  - `Handlebars.compile()` 直接编译字符串 vs `Handlebars.compile(fs.readFileSync(...))`
  - 是否完全控制模板代码或仅控制部分变量
  - 是否使用了 `precompiled` 模式提前编译模板
- 上下文隔离:
  - `template()` 调用时传入的数据是否包含用户可控内容
  - 是否限制了模板可以访问的变量范围
  - 是否配置了严格的变量访问策略
- Helper 函数安全:
  - 是否注册了自定义 Helper，其中是否执行了用户输入
  - `Handlebars.registerHelper()` 中是否存在危险操作
  - 是否禁用了危险的内置 Helper

**L4 跨模块追踪**:
- 追踪用户输入从路由 → 模板处理 → 编译 → 渲染的完整数据流
- 检查中间件层是否做了输入验证
- 验证是否有全局的 Handlebars 安全配置
- 检查框架配置是否限制了模板编译
- 追踪模板 partial 和 layout 的加载方式

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `Handlebars.compile()` 的参数编译为模板
- 用户可以通过注入 `{{}}` 表达式执行任意代码
- 可通过 `{{#if}}`, `{{#each}}` 等控制流指令进行攻击
- 可访问内置对象如 `__proto__`, `constructor` 等进行原型污染
- 动态模板加载时用户可控模板路径，导致任意文件加载

**误报判定**:
- 模板内容完全由后端开发者预定义，用户仅可控模板变量值（如 `Hello {{name}}`）
- 使用了完整的输入白名单验证，仅允许选择预定义的模板文件名
- 用户输入仅用作模板变量值而非模板代码本身
- 所有用户输入都经过 `Handlebars.escapeExpression()` 转义

**代码异味**:
- 虽然编译了预定义模板但模板中直接使用用户输入作为变量名，如 `{{request.args['var_name']}}`
- 动态生成部分模板代码，即使不是全部用户可控
- Helper 函数中执行了用户输入的某些部分
- 使用字符串替换而非白名单过滤用户输入的模板参数
- 模板路径拼接包含用户输入，如 `views/${req.query.template}.hbs`

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板编译和渲染功能仅限管理员或特权用户使用
- 用户提交的模板需经管理员审核才能被使用
- 功能被完全隔离在内部系统，非公网可访问

**架构设计防护**:
- 明确采用预编译的模板方式，所有模板在部署时固定
- 模板内容完全由开发者定义，用户仅控制模板变量值
- 使用严格的模板白名单，用户只能选择预定义的模板
- 配置 Content Security Policy 限制脚本执行

**输入与输出保护**:
- 用户输入被严格白名单验证，仅允许字母数字和特定符号
- 即使用户可控模板名称，也通过文件系统限制模板目录访问
- 所有用户输入在模板中都被强制当作普通变量值而非模板代码
- 使用沙箱环境限制模板可访问的对象和方法

**监控与运行环保**:
- 部署在完全隔离的容器环境，无系统命令执行权限
- 进程以最小权限用户运行，文件系统权限限制严格
- 有完整的审计日志和异常检测机制
- 系统配置禁用了危险操作如 eval、child_process 等
