# Java_SSTI_Thymeleaf_Expression_Injection

**漏洞类型**: Thymeleaf 模板引擎中用户输入被用于构造表达式，导致 SpEL 表达式注入

---

## Details

### 代码示例

**易受攻击的代码模式**:
```java
// 直接将用户输入作为模板内容
TemplateEngine engine = new TemplateEngine();
String userTemplate = request.getParameter("template");
Context context = new Context();
String result = engine.process(userTemplate, context);

// 使用内联表达式且内容用户可控
String template = "Hello, [[${" + username + "}]]";
templateEngine.process(template, context);

// Fragment 表达式中包含用户输入
String fragmentExpr = "~{fragments/" + request.getParameter("name") + "}";
model.addAttribute("fragmentPath", fragmentExpr);

// 使用 th:utext 输出未转义内容
// 模板中: <div th:utext="${userInput}"></div>
context.setVariable("userInput", request.getParameter("data"));

// SpringEL 表达式直接拼接用户输入
String expr = "${T(java.lang.Runtime).getRuntime().exec('" + cmd + "')}";
parser.parseExpression(expr);
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板引擎: `TemplateEngine`, `SpringTemplateEngine`, `ITemplateEngine`
- 处理方法: `.process()`, `.processThrottled()`, `.createTemplate()`
- 表达式语法: `${}`, `*{}`, `#{}`, `@{}`, `~{}`（片段表达式）
- 内联表达式: `[[...]]`, `[(...)]`
- 用户输入: `request.getParameter()`, `@RequestParam`, `@PathVariable`, `@RequestBody`
- 未转义输出: `th:utext`, `th:inline="javascript"`

**L2 跳读定位**:
- 从 Controller 参数追踪到 `process()` 方法的模板参数
- 检查模板字符串是否通过拼接包含用户输入
- 定位 Context 中设置的变量是否来自外部输入
- 搜索模板文件中 `th:utext` 或内联表达式 `[[${...}]]`
- 关注 Fragment 表达式路径是否用户可控

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入验证: 白名单验证如 `ALLOWED_VIEWS.contains()`
- 安全输出: 使用 `th:text` 代替 `th:utext`（自动转义）
- 模板预定义: 使用 `ClassLoaderTemplateResolver` 限定模板路径
- 表达式限制: `SpringSecurityDialect` 限制可用表达式
- 沙箱模式: 自定义 `IExpressionObjectFactory` 限制可访问对象

**L3 逐行分析**:
- 模板解析器配置:
  - `TemplateResolver.setPrefix()` 和 `setSuffix()` 是否限定路径
  - `setCacheable(true)` 是否启用模板缓存
  - `setCheckExistence(true)` 验证模板文件存在性
- 输出方式检查:
  - `th:text` 会自动 HTML 转义（安全）
  - `th:utext` 输出原始 HTML（危险）
  - 内联文本 `[[...]]` 自动转义，`[(...)` 不转义
- Context 变量安全:
  - 是否限制了可访问的工具类和静态方法
  - 是否禁用了 `#execInfo`, `#request` 等内置对象
  - 变量值是否经过类型检查和验证
- SpEL 表达式控制:
  - 是否禁用了 `T()` 操作符（类型引用）
  - 是否限制了可调用的方法和属性

**L4 跨模块追踪**:
- 追踪 Spring MVC Controller → Service → TemplateEngine 的数据流
- 检查 Spring Security 是否对表达式求值进行了限制
- 验证 `TemplateEngine` Bean 的全局配置
- 检查是否使用了自定义的 `ITemplateResolver`
- 追踪视图名称解析过程，确认是否可被用户控制

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `process()` 的模板参数
- 模板中使用 `th:utext` 输出用户可控变量
- 内联表达式 `[[${userInput}]]` 中包含用户可控的变量名或表达式
- Fragment 路径 `~{...}` 可被用户控制导致任意模板包含
- SpEL 表达式中包含 `T(Runtime).exec()` 等危险调用且参数可控

**误报判定**:
- 模板完全预定义，用户仅控制通过 `th:text` 输出的简单值
- 视图名称虽来自用户但经过严格白名单验证
- 使用了 Spring Security 的表达式安全检查
- 所有用户输入在设置到 Context 前经过类型验证和编码
- 模板解析器严格限定在特定目录且禁止路径遍历

**代码异味**:
- 视图名称通过字符串拼接如 `"user/" + username`
- 使用 `th:fragment` 动态选择片段且参数来自用户
- 模板中存在 `th:inline="javascript"` 且变量未充分验证
- 在 Context 中传递了整个 Request 对象或 ServletContext
- 使用黑名单过滤如禁止 `Runtime` 但未禁止反射调用
- 自定义的 Dialect 引入了额外的表达式求值点

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板选择功能仅限管理员使用，有多重身份验证
- 动态模板渲染仅用于内部报表系统，不对外开放
- 使用了基于角色的访问控制限制视图访问
- 用户提交的模板需经过安全审查流程

**架构设计防护**:
- 使用 `ClassLoaderTemplateResolver` 仅从 classpath 加载模板
- 模板全部预编译且在构建时验证安全性
- 实现了自定义 `IExpressionObjectFactory` 严格限制可用对象
- 启用了 Spring Security 的方法级安全检查

**输入与输出保护**:
- 视图名称经过严格的正则表达式白名单验证
- 所有模板变量强制使用 `th:text` 进行转义
- 禁用了所有内联表达式功能
- Context 中仅包含基本数据类型，不传递对象引用

**监控与运行环保**:
- 应用运行在安全沙箱环境，限制系统调用
- 启用了 SecurityManager 限制反射和类加载
- 部署了 WAF 检测和阻断 SpEL 注入特征
- 完整的审计日志记录所有模板渲染和异常
