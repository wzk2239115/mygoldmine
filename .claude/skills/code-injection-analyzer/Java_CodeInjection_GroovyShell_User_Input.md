# Java GroovyShell 代码执行注入

**漏洞成因**：使用 `groovy.lang.GroovyShell` 执行用户可控的 Groovy 脚本代码，GroovyShell 提供完整的 Groovy 语言支持，攻击者可执行任意 Groovy 代码，包括访问 Java 对象和方法。

---

## Details

**代码示例**：
```java
// 危险：直接执行用户输入的 Groovy 脚本
GroovyShell shell = new GroovyShell();
String userCode = request.getParameter("code");
Object result = shell.evaluate(userCode);

// 危险：脚本与用户输入拼接
String script = "def x = " + userInput + "; x.execute()";
shell.evaluate(script);

// 危险：使用 Binding 传递数据但仍可执行任意代码
Binding binding = new Binding();
binding.setVariable("userValue", userInput);
GroovyShell shell = new GroovyShell(binding);
shell.evaluate("Runtime.getRuntime().exec('cmd')");

// 虚假安全：限制权限（Groovy 仍可绕过）
GroovyShell shell = new GroovyShell();
shell.setVariable("safe", "true");
```

**快速定位核心操作**（L1-L3）：
- 关键词：`GroovyShell`、`.evaluate(`、`Binding`、`groovy.lang`
- 查看脚本来源：用户参数、文件、配置
- 检查是否涉及脚本拼接：字符串+、String.format、StringBuilder
- 追踪数据流：`request.getParameter()`、`request.getInputStream()`

**快速定位保护机制**（L2-L3）：
- 是否存在代码白名单：仅允许特定操作或预定义脚本
- 是否使用了 CompilerConfiguration 限制功能：禁用导入、方法调用
- 是否限制了 Binding 变量：防止访问危险对象
- 是否进行了脚本审计：检查禁止的关键词

**审计等级**：**L2-L4**
- **L2**：跳读 GroovyShell 使用，确认脚本来源
- **L3**：逐行读取 evaluate 及其参数、防护机制
- **L4**：跨模块追踪用户输入到 evaluate 的完整流程

---

## Classify

**确认为漏洞**：
- 用户输入直接或间接参与 Groovy 脚本构造
- 无防护或防护不完整
- 脚本可访问 Java Runtime、ProcessBuilder 等危险类

**误报**：
- 脚本为硬编码常量
- 用户输入被严格限制在安全值
- CompilerConfiguration 禁用了导入和方法调用

**代码异味**：
- GroovyShell 存在但有部分防护
- 权限控制依赖前端验证
- 业务可用静态规则替代

---

## Low Risk

以下情况可评为低风险：
- **严格限制脚本功能**：CompilerConfiguration 禁止导入、方法调用、new 操作
- **权限隔离**：脚本执行在最小权限用户下
- **内网保护**：仅限管理员、开发者
- **白名单脚本**：脚本内容限制在预定义集合
- **审计监控**：脚本执行被完整记录、监控
