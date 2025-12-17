# Java_SSTI_Freemarker_Template_Include

**漏洞类型**: FreeMarker 模板引擎中用户输入直接作为模板内容或包含路径

---

## Details

### 代码示例

**易受攻击的代码模式**:
```java
// 用户输入直接作为模板内容
Configuration cfg = new Configuration();
String userTemplate = request.getParameter("template");
Template template = new Template("name", new StringReader(userTemplate), cfg);
template.process(dataModel, out);

// 使用 include 指令且路径用户可控
// 模板中: <#include "${userPath}">
dataModel.put("userPath", request.getParameter("path"));

// getTemplate 方法路径拼接
String templateName = request.getParameter("name") + ".ftl";
Template tmpl = cfg.getTemplate(templateName);

// 数据模型包含危险对象
dataModel.put("exec", new freemarker.template.utility.Execute());
dataModel.put("objectConstructor", new freemarker.template.utility.ObjectConstructor());

// 直接执行用户提交的表达式
String expr = request.getParameter("expr");
dataModel.put("userExpr", expr);  // 模板中: ${userExpr}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板类: `Template`, `Configuration`, `StringTemplateLoader`
- 处理方法: `.process()`, `.getTemplate()`, `new Template()`
- 指令语法: `<#include>`, `<#import>`, `<#assign>`, `${...}`
- 危险工具: `Execute`, `ObjectConstructor`, `JythonRuntime`
- 用户输入: `request.getParameter()`, `@RequestParam`, `@PathVariable`

**L2 跳读定位**:
- 从请求参数追踪到 `new Template()` 或 `getTemplate()`
- 检查模板字符串是否来自用户输入
- 定位数据模型中是否包含危险工具类
- 搜索模板文件中的 `<#include>` 和 `<#import>`  指令
- 关注 Configuration 的安全配置

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 模板白名单: 模板名称白名单验证
- 沙箱模式: `TemplateClassResolver.SAFER_RESOLVER`
- API 版本: `Configuration.setIncompatibleImprovements()`
- 禁用危险功能: `setNewBuiltinClassResolver()`, `setAPIBuiltinEnabled(false)`
- 模板加载器: `ClassTemplateLoader` 限制加载路径

**L3 逐行分析**:
- Configuration 配置:
  - `setTemplateLoader()` 是否限制模板目录
  - `setObjectWrapper()` 包装器安全性
  - `setNewBuiltinClassResolver(TemplateClassResolver.SAFER_RESOLVER)`
  - `setAPIBuiltinEnabled(false)` 禁用 API 访问
- 模板来源:
  - 是否接受用户提交的完整模板字符串
  - getTemplate 的路径是否用户可控
  - TemplateLoader 配置是否限制目录
- 数据模型安全:
  - 是否包含 Execute、ObjectConstructor 等危险类
  - 是否传递了 Request、Response 等 Servlet 对象
  - 变量是否经过白名单验证
- 模板指令检查:
  - include/import 路径是否来自用户输入
  - 是否使用了 `?eval` 动态求值
  - assign 指令是否被滥用

**L4 跨模块追踪**:
- 追踪从 Controller → Service → 模板处理的数据流
- 检查全局 Configuration Bean 的安全配置
- 验证模板文件的存储位置和访问权限
- 检查是否有安全包装器或拦截器
- 追踪数据模型的构建过程

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接用于创建 Template 对象
- 数据模型包含 Execute、ObjectConstructor 等危险工具类
- getTemplate 路径可被用户完全或部分控制
- 模板中使用 include/import 且路径来自用户输入
- 未启用 SAFER_RESOLVER 且可访问任意类

**误报判定**:
- 模板完全预定义，用户仅控制数据模型中的简单值
- 启用了 SAFER_RESOLVER 且禁用了 API builtin
- 模板名称经过严格白名单验证
- 使用 ClassTemplateLoader 限制在 classpath 特定包
- 数据模型仅包含基本类型和安全的业务对象

**代码异味**:
- 模板路径虽验证但使用字符串拼接
- Configuration 版本过低，存在已知漏洞
- 数据模型虽无危险类但包含复杂对象
- 使用黑名单禁止某些类名或方法
- 模板中存在复杂的宏定义和嵌套包含
- ObjectWrapper 配置为 BeansWrapper 暴露所有 getter

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染功能仅限管理员使用
- 需要多重身份验证和授权
- 功能部署在内部系统
- 实施严格的访问控制

**架构设计防护**:
- 启用 TemplateClassResolver.SAFER_RESOLVER
- 设置 APIBuiltinEnabled 为 false
- 使用最新的 FreeMarker 版本
- 模板全部预编译和缓存

**输入与输出保护**:
- 模板名称严格白名单验证
- 数据模型仅包含安全的 DTO 对象
- 禁止在模板中使用 ?eval 等动态求值
- ClassTemplateLoader 限制模板路径

**监控与运行环保**:
- 应用运行在受限环境
- SecurityManager 限制反射和类加载
- 完整的审计日志
- 实时监控异常模板访问
