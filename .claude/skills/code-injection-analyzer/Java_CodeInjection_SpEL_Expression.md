# Java Spring EL (SpEL) 表达式注入

**漏洞成因**：使用 Spring 的 EL 表达式语言（SpEL）解析和执行用户输入的表达式，SpEL 支持访问 Java 对象和方法，攻击者可通过 SpEL 执行任意方法。

---

## Details

**代码示例**：
```java
// 危险：直接解析用户输入的 SpEL 表达式
String expression = request.getParameter("expr");
ExpressionParser parser = new SpelExpressionParser();
Expression exp = parser.parseExpression(expression);
Object result = exp.getValue();

// 危险：SpEL 拼接用户输入
String userInput = request.getParameter("value");
String expr = "T(java.lang.Runtime).getRuntime().exec('" + userInput + "')";
parser.parseExpression(expr).getValue();

// 危险：在 @Value 注解中使用用户输入
@Value("#{request.getParameter('expr')}")
private String userValue;

// 虚假安全：使用 SimpleEvaluationContext（仍可绕过）
SimpleEvaluationContext context = SimpleEvaluationContext.forReadOnlyDataBinding().build();
```

**快速定位核心操作**（L1-L3）：
- 关键词：`SpelExpressionParser`、`parseExpression(`、`@Value`、`T(`
- 查看表达式来源：用户参数、配置、注解
- 检查是否涉及字符串拼接构造表达式
- 追踪数据流：`request.getParameter()`、`@Value` 注解

**快速定位保护机制**（L2-L3）：
- 是否使用了 `SimpleEvaluationContext.forReadOnlyDataBinding()`：更严格的上下文
- 是否禁止了类型转换和方法调用：`T()` 等
- 是否使用了表达式白名单：仅允许特定的表达式
- 是否进行了表达式审计：检查禁止的关键词

**审计等级**：**L1-L4**
- **L1**：关键词扫描，快速定位 SpEL 使用
- **L2**：跳读确认表达式来源
- **L3**：逐行读取表达式构造及防护机制
- **L4**：跨模块追踪用户输入到表达式的完整流程

---

## Classify

**确认为漏洞**：
- 用户输入直接或间接参与 SpEL 表达式构造
- 使用了 `StandardEvaluationContext`（无限制）
- 无防护或防护不完整

**误报**：
- 表达式为硬编码常量
- 使用了 `SimpleEvaluationContext.forReadOnlyDataBinding()`
- 用户输入被严格限制在安全值

**代码异味**：
- SpEL 存在但有部分防护
- 权限控制依赖前端验证

---

## Low Risk

以下情况可评为低风险：
- **严格的评估上下文**：使用 SimpleEvaluationContext 并禁用危险操作
- **权限隔离**：表达式执行在最小权限用户下
- **内网保护**：仅限管理员、内网
- **表达式白名单**：严格限制允许的表达式
- **审计监控**：表达式执行被完整记录、监控
