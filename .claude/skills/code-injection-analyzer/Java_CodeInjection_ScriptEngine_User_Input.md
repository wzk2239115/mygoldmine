# Java ScriptEngine 代码执行注入

**漏洞成因**：使用 `javax.script.ScriptEngine` 执行用户可控的脚本代码，常见于规则引擎、动态脚本执行、数据验证等场景。攻击者可通过构造恶意脚本在 ScriptEngine 中执行任意代码。

---

## Details

**代码示例**：
```java
// 危险：直接执行用户输入的脚本
ScriptEngineManager manager = new ScriptEngineManager();
ScriptEngine engine = manager.getEngineByName("JavaScript");
String userScript = request.getParameter("script");
engine.eval(userScript);

// 危险：脚本与用户输入拼接
String script = "result = " + userInput + ";";
engine.eval(script);

// 危险：执行多行脚本
String scriptCode = "var x = " + userInput + ";" +
                    "var y = x * 2;" +
                    "result = y;";
engine.eval(scriptCode);

// 虚假安全：限制命名空间（仍可绕过）
Bindings bindings = engine.createBindings();
bindings.put("__builtins__", null);
engine.eval(userScript, bindings);
```

**快速定位核心操作**（L1-L3）：
- 关键词：`ScriptEngine`、`ScriptEngineManager`、`.eval(`、`getEngineByName(`
- 查看脚本来源：用户请求参数、表单、文件上传
- 检查是否涉及脚本拼接：字符串+、StringBuilder、String.format
- 追踪数据流：`request.getParameter()`、`request.getInputStream()`

**快速定位保护机制**（L2-L3）：
- 是否存在脚本白名单：仅允许特定的预定义脚本
- 是否限制了脚本引擎：使用受限的脚本语言（如仅计算表达式）
- 是否存在脚本语法检查：AST 验证、语句审计
- 是否限制了 Bindings 访问：禁止访问危险类和方法

**审计等级**：**L2-L4**
- **L2**：跳读 ScriptEngine 使用，确认脚本来源
- **L3**：逐行读取 eval 及其参数、防护机制
- **L4**：跨模块追踪用户输入到 eval 的完整数据流

---

## Classify

**确认为漏洞**：
- 用户输入直接或间接参与脚本构造
- 无防护或防护可绕过
- 脚本执行环境允许访问危险类（如 Runtime、ProcessBuilder）

**误报**：
- 脚本为硬编码常量
- 用户输入被严格限制在安全值集合
- 脚本引擎仅支持表达式计算，不支持代码执行

**代码异味**：
- ScriptEngine 存在但有部分防护
- 权限控制依赖前端验证
- 业务可用静态规则替代动态脚本

---

## Low Risk

以下情况可评为低风险：
- **受限脚本环境**：脚本引擎禁止访问外部类、文件系统、网络
- **权限隔离**：脚本执行在最小权限用户下
- **内网保护**：仅限管理员、开发者访问
- **严格白名单**：脚本内容限制在预定义集合
- **审计监控**：脚本执行被完整记录、监控
