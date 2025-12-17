# Java Spring 表达式语言 (SpEL) 用户输入注入

**漏洞成因**：Spring 表达式语言 (SpEL) 是 Spring 框架提供的强大表达式语言，支持对象图导航、方法调用、运算符操作等。当应用将用户输入直接作为 SpEL 表达式内容进行解析时，攻击者可构造恶意表达式访问敏感对象、调用危险方法（如 Runtime.exec）、修改应用状态等，导致远程代码执行。常见于动态权限验证、规则引擎、模板渲染、配置解析等场景。

---

## Details

**代码示例**：
```java
// 危险：直接解析用户输入作为 SpEL 表达式
import org.springframework.expression.Expression;
import org.springframework.expression.ExpressionParser;
import org.springframework.expression.spel.standard.SpelExpressionParser;

String userInput = request.getParameter("expr");
ExpressionParser parser = new SpelExpressionParser();
Expression exp = parser.parseExpression(userInput); // 危险：用户可注入任意表达式
Object value = exp.getValue();

// 危险示例：动态权限校验
@PreAuthorize(request.getParameter("permission")) // 用户可注入表达式
public void sensitiveOperation() { }

// 危险示例：使用 SimpleEvaluationContext 但配置不当
StandardEvaluationContext context = new StandardEvaluationContext();
context.setVariable("user", currentUser);
Expression exp = parser.parseExpression(userInput);
exp.getValue(context); // 攻击者可访问 #user 变量及其方法

// 攻击载荷示例
// T(java.lang.Runtime).getRuntime().exec('calc')
// new java.lang.ProcessBuilder({'calc'}).start()

// 较安全：使用 SimpleEvaluationContext（受限上下文）
SimpleEvaluationContext context = SimpleEvaluationContext.forReadOnlyDataBinding().build();
Expression exp = parser.parseExpression(userInput);
exp.getValue(context); // 禁止类型引用、构造函数调用、方法调用

// 较安全：仅允许白名单表达式
Set<String> allowedExpressions = Set.of("user.name", "user.role", "order.status");
if (!allowedExpressions.contains(userInput)) {
    throw new SecurityException("Invalid expression");
}
```

**快速定位核心操作**：
- 关键词：`SpelExpressionParser`、`parseExpression`、`Expression.getValue`、`StandardEvaluationContext`、`@Value`、`@PreAuthorize`
- 查找 SpEL 解析器的实例化位置：`new SpelExpressionParser()`
- 追踪 `parseExpression()` 的参数来源，判断是否包含用户输入
- 检查是否使用了 `StandardEvaluationContext`（高风险）或 `SimpleEvaluationContext`（受限）
- 关注 Spring 注解：`@Value("${}")`、`@PreAuthorize`、`@PostFilter` 等动态表达式场景
- 搜索 `ExpressionParser` 接口的实现类使用位置

**快速定位保护机制**：
- 是否使用 `SimpleEvaluationContext` 而非 `StandardEvaluationContext`
- 是否禁用了类型引用：检查上下文是否调用 `setTypeLocator(null)` 或使用受限上下文
- 是否禁用了构造函数调用：检查 `ConstructorResolver` 配置
- 是否禁用了方法调用：检查 `MethodResolver` 配置
- 是否使用表达式白名单：验证用户输入是否在预定义的安全表达式集合中
- 是否使用了 SpEL 编译模式（`SpelCompilerMode.OFF`）避免动态编译风险
- Spring Boot 版本是否为 5.3.20+、5.2.24+（修复了部分 SpEL 注入漏洞）

**审计等级**：**L2-L4**
- **L2**：跳读关键 API 调用，识别 SpEL 解析器的使用位置
- **L3**：逐行验证表达式参数来源，确认是否包含用户可控数据
- **L4**：跨模块追踪上下文配置，验证是否使用受限评估环境

---

## Classify

**确认为漏洞**：
- 使用 `StandardEvaluationContext` 解析用户输入的表达式
- Spring 注解（如 `@PreAuthorize`、`@Value`）中的表达式内容来自用户输入
- 表达式上下文中包含敏感对象（如 ApplicationContext、BeanFactory）
- 未对用户输入进行白名单验证或表达式语法限制
- 可通过类型引用 `T(java.lang.Runtime)` 执行系统命令

**误报**：
- 使用 `SimpleEvaluationContext` 且未注册危险的类型定位器或方法解析器
- 表达式内容为硬编码常量，不包含用户输入
- 用户输入经过严格的白名单验证，仅允许安全的属性访问路径
- Spring Security 表达式处于沙箱环境，且已禁用类型引用

**代码异味**：
- 大量使用 SpEL 进行动态逻辑处理，增加攻击面
- 表达式字符串通过字符串拼接构造，易引入注入风险
- 使用 SpEL 处理敏感业务逻辑而非使用编程语言原生控制流
- 表达式上下文中注册了过多的变量和函数

---

## Low Risk

以下情况可评为低风险：
- **受限评估上下文**：使用 `SimpleEvaluationContext` 且未启用类型引用、构造函数、反射等危险功能
- **严格白名单**：用户输入必须匹配预定义的安全表达式模式（如 `^[a-zA-Z0-9._]+$`）
- **只读属性访问**：表达式仅用于访问数据对象的只读属性，不调用方法
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **沙箱隔离**：SpEL 运行在受限的 SecurityManager 或容器沙箱中
- **日志监控**：所有表达式解析操作均记录日志并实时监控异常模式

**注意**：SpEL 注入的危害极高，可直接导致 RCE，即使在受限上下文下也需谨慎评估。
