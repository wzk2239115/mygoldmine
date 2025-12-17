# Java_SSTI_Velocity_User_Controlled_Variable

**漏洞类型**: Velocity 模板引擎中用户可控的模板变量或模板内容

---

## Details

### 代码示例

**易受攻击的代码模式**:
```java
// 用户输入直接作为模板内容
VelocityEngine ve = new VelocityEngine();
String userTemplate = request.getParameter("template");
StringReader reader = new StringReader(userTemplate);
ve.evaluate(context, writer, "template", reader);

// 模板字符串拼接用户输入
String tpl = "#set($name = " + request.getParameter("value") + ")";
ve.evaluate(context, writer, "test", tpl);

// Context 中包含危险对象
VelocityContext context = new VelocityContext();
context.put("runtime", Runtime.getRuntime());
context.put("class", Class.class);

// 用户可控的模板文件路径
String templatePath = request.getParameter("template") + ".vm";
Template template = ve.getTemplate(templatePath);

// 使用反射或方法调用
// 模板中: $user.class.forName("java.lang.Runtime")
context.put("user", userObject);  // userObject 方法可被调用
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Velocity 类: `VelocityEngine`, `VelocityContext`, `Template`
- 方法调用: `.evaluate()`, `.getTemplate()`, `.merge()`
- 模板语法: `$variable`, `#set`, `#foreach`, `#include`, `#parse`
- 工具对象: `ClassTool`, `FieldTool`, `MethodTool`
- 用户输入: `request.getParameter()`, `@RequestParam`, `@PathVariable`

**L2 跳读定位**:
- 从请求参数追踪到 `evaluate()` 或 `merge()` 的模板参数
- 检查模板字符串是否包含用户输入拼接
- 定位 VelocityContext 中设置的对象类型
- 搜索模板文件中的 `#include` 和 `#parse` 指令
- 关注 getTemplate() 的路径参数来源

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 模板白名单: 模板名称白名单验证
- Context 限制: 仅放入基本类型和安全 DTO
- 禁用内省: `introspector.restrict.classes` 配置
- 模板加载器: `ClasspathResourceLoader` 限制路径
- 方法访问限制: `SecureUberspector` 或自定义 Uberspector

**L3 逐行分析**:
- VelocityEngine 配置:
  - `resource.loader` 是否限制加载路径
  - `introspector.restrict.classes` 是否配置黑名单
  - `introspector.restrict.packages` 是否限制包访问
  - `runtime.introspector.uberspect` 是否使用安全实现
- 模板来源:
  - 是否接受用户提交的完整模板字符串
  - getTemplate 路径是否用户可控
  - ResourceLoader 配置是否安全
- Context 对象:
  - 是否包含 Runtime、Class、ClassLoader 等危险类
  - 是否传递了 HttpServletRequest 等 Servlet 对象
  - 对象的公共方法是否存在安全风险
- 模板指令:
  - `#include` 和 `#parse` 路径是否可控
  - `#set` 是否被用于动态代码生成
  - `#evaluate` 是否用于二次求值

**L4 跨模块追踪**:
- 追踪从 Controller → Service → Velocity 渲染的数据流
- 检查全局 VelocityEngine Bean 配置
- 验证模板文件存储位置和权限
- 检查是否有安全包装器限制方法访问
- 追踪 Context 对象的构造过程

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 evaluate() 的模板参数
- Context 包含 Runtime、Class 等危险对象
- getTemplate 路径可被用户完全或部分控制
- 模板中可通过反射访问任意类
- 未配置 introspector 限制且对象方法可任意调用

**误报判定**:
- 模板完全预定义，用户仅控制基本类型变量
- 配置了严格的 introspector.restrict 限制
- 使用 SecureUberspector 限制方法访问
- 模板名称经过白名单验证
- Context 仅包含不可变的安全对象

**代码异味**:
- 模板路径虽验证但使用字符串拼接
- introspector 配置了黑名单但不完整
- Context 包含复杂业务对象但未评估风险
- 使用了自定义 Uberspector 但安全性未知
- 模板中存在复杂的宏和嵌套指令
- Velocity 版本过低存在已知漏洞

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染功能仅限管理员使用
- 需要多重身份验证
- 功能部署在内部系统
- 实施严格访问控制

**架构设计防护**:
- 配置完善的 introspector.restrict 黑名单
- 使用 SecureUberspector 限制方法访问
- 模板全部预编译和缓存
- ClasspathResourceLoader 限制模板路径

**输入与输出保护**:
- 模板名称严格白名单验证
- Context 仅包含简单 DTO 对象
- 禁止使用 #evaluate 等动态求值指令
- 模板文件权限严格控制

**监控与运行环保**:
- SecurityManager 限制反射
- 完整审计日志
- 实时监控异常模板访问
- WAF 检测 Velocity 注入特征
