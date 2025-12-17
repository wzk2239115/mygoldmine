# Java MVEL 表达式引擎注入

**漏洞成因**：MVEL (MVFLEX Expression Language) 是 Java 平台上的动态表达式语言和运行时，支持属性访问、方法调用、脚本执行等功能。当应用将用户输入作为 MVEL 表达式进行编译或执行时，攻击者可构造恶意表达式访问 Java 类、调用危险方法（如 Runtime.exec）、修改对象状态等，导致远程代码执行。常见于规则引擎（如 Drools）、模板渲染、动态配置、表达式求值等场景。

---

## Details

**代码示例**：
```java
// 危险：直接执行用户输入的 MVEL 表达式
import org.mvel2.MVEL;

String userInput = request.getParameter("expr");
Object result = MVEL.eval(userInput); // 危险：用户可注入任意代码

// 危险示例：使用编译模式
Serializable compiled = MVEL.compileExpression(userInput);
Object result = MVEL.executeExpression(compiled, context);

// 危险示例：带上下文执行
Map<String, Object> context = new HashMap<>();
context.put("user", currentUser);
context.put("request", httpRequest);
Object result = MVEL.eval(userInput, context); // 攻击者可访问上下文对象

// 攻击载荷示例
// Runtime.getRuntime().exec("calc")
// java.lang.ProcessBuilder.("calc").start()
// Class.forName("java.lang.Runtime").getMethod("exec",String.class).invoke(null,"calc")

// 较安全：使用 ParserContext 限制表达式能力
import org.mvel2.ParserContext;
import org.mvel2.integration.impl.ClassImportResolverFactory;

ParserContext ctx = new ParserContext();
ctx.setStrongTyping(true); // 启用强类型检查
ctx.setStrictTypeEnforcement(true);
// 移除默认的导入类
ctx.setResolverFactories(new ClassImportResolverFactory());

// 较安全：仅允许白名单表达式
Set<String> allowedExpressions = Set.of("user.name", "order.total");
if (!allowedExpressions.contains(userInput)) {
    throw new SecurityException("Invalid expression");
}
```

**快速定位核心操作**：
- 关键词：`MVEL.eval`、`MVEL.compileExpression`、`MVEL.executeExpression`、`ParserContext`、`org.mvel2`
- 查找 MVEL 类的静态方法调用位置：`MVEL.eval()`、`MVEL.evalToString()`
- 追踪表达式字符串的来源，判断是否包含用户输入
- 检查是否使用了 `ParserContext` 配置表达式解析上下文
- 关注 Drools 规则引擎中的 MVEL 表达式使用
- 搜索依赖：`org.mvel:mvel2`、`org.drools:drools-mvel`

**快速定位保护机制**：
- 是否使用 `ParserContext` 配置强类型检查：`setStrongTyping(true)`
- 是否禁用了类导入功能：检查 `ClassImportResolverFactory` 配置
- 是否限制了方法调用：检查 `MethodAccessor` 配置
- 是否使用表达式白名单：验证用户输入是否在预定义的安全表达式集合中
- 是否设置了 SecurityManager 限制运行时权限
- 上下文对象是否包含敏感对象（如 Runtime、ProcessBuilder、File）
- MVEL 版本是否已修复已知的安全漏洞（如 CVE-2020-13956）

**审计等级**：**L2-L4**
- **L2**：跳读关键 API 调用，识别 MVEL 表达式的执行位置
- **L3**：逐行验证表达式参数来源，确认是否包含用户可控数据
- **L4**：跨模块追踪 ParserContext 配置和上下文对象，验证安全限制

---

## Classify

**确认为漏洞**：
- 直接使用 `MVEL.eval()` 执行用户输入的表达式
- 未使用 `ParserContext` 或配置不当（未启用强类型检查）
- 表达式上下文中包含危险对象（如 Runtime、ClassLoader）
- 未对用户输入进行白名单验证或语法限制
- 可通过反射或类加载机制执行任意代码

**误报**：
- 表达式内容为硬编码常量或配置文件中的预定义值
- 使用了严格的 `ParserContext` 配置，禁用类导入和方法调用
- 用户输入经过白名单验证，仅允许简单的属性访问表达式
- MVEL 运行在受限的沙箱环境中

**代码异味**：
- 大量使用 MVEL 进行动态逻辑处理，增加攻击面
- 表达式字符串通过字符串拼接构造，易引入注入风险
- 使用 MVEL 处理敏感业务逻辑而非使用 Java 原生代码
- 上下文对象中注册了过多的变量和函数

---

## Low Risk

以下情况可评为低风险：
- **严格 ParserContext**：启用强类型检查、禁用类导入、限制方法调用
- **表达式白名单**：用户输入必须匹配预定义的安全表达式模式
- **只读上下文**：上下文对象仅包含不可变的数据对象，不包含方法调用能力
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **沙箱隔离**：MVEL 运行在受限的 SecurityManager 或容器沙箱中
- **日志监控**：所有表达式执行操作均记录日志并实时监控异常模式
- **版本更新**：使用最新版本的 MVEL，已修复已知的安全漏洞

**注意**：MVEL 的表达式能力极强，即使配置了 ParserContext 也可能存在绕过风险，建议优先使用更安全的替代方案。
