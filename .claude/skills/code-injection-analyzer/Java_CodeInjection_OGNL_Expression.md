# Java OGNL 表达式注入

**漏洞成因**：使用 OGNL（Object Graph Navigation Language）解析执行用户输入的表达式，常见于 Struts 框架中，OGNL 支持访问对象属性和调用方法，攻击者可执行任意 OGNL 表达式。

---

## Details

**代码示例**：
```java
// 危险：直接解析用户输入的 OGNL 表达式
String expression = request.getParameter("expr");
Object result = Ognl.getValue(expression, object);

// 危险：在 Struts 标签中使用用户输入
<s:property value="@java.lang.Runtime@getRuntime().exec('cmd')"/>

// 危险：OGNL 拼接用户输入
String userInput = request.getParameter("value");
String expr = "(%23cmd='cal').(%23iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win'))).(%23cmds=(#iswin?{'cmd.exe','/c',#cmd}:{'/bin/bash','-c',#cmd}))";
Ognl.getValue(expr);

// 虚假安全：使用 excludeMethodNames（仍可绕过）
OgnlContext context = new OgnlContext();
context.setMemberAccess(new DefaultMemberAccess(false));
```

**快速定位核心操作**（L1-L3）：
- 关键词：`Ognl.getValue(`、`Ognl.setValue(`、`@`、`()`、`.exec`
- 查看表达式来源：用户参数、标签属性、配置
- 检查是否涉及字符串拼接构造表达式
- 追踪数据流：`request.getParameter()`、Struts 标签

**快速定位保护机制**（L2-L3）：
- 是否禁止了方法调用：`@java.lang.Runtime`
- 是否使用了表达式白名单：仅允许特定表达式
- 是否进行了表达式审计：检查禁止的关键词
- 是否限制了 MemberAccess：访问控制配置

**审计等级**：**L1-L4**
- **L1**：关键词扫描，快速定位 OGNL 使用
- **L2**：跳读确认表达式来源
- **L3**：逐行读取表达式构造及防护机制
- **L4**：跨模块追踪用户输入到表达式的完整流程

---

## Classify

**确认为漏洞**：
- 用户输入直接或间接参与 OGNL 表达式构造
- 无防护或防护可绕过
- 可访问 Runtime、ProcessBuilder 等危险类

**误报**：
- 表达式为硬编码常量
- 使用了严格的表达式白名单
- 用户输入被严格限制在安全值

**代码异味**：
- OGNL 存在但有部分防护
- 权限控制依赖前端验证
- Struts 版本过旧，已有已知漏洞

---

## Low Risk

以下情况可评为低风险：
- **严格的白名单**：仅允许特定的安全表达式
- **权限隔离**：表达式执行在最小权限用户下
- **内网保护**：仅限管理员、内网
- **完全禁用 OGNL**：在不使用 OGNL 的情况下
- **审计监控**：表达式执行被完整记录、监控
