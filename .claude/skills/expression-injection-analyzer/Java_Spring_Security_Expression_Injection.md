# Java Spring Security 表达式注入

**漏洞成因**：Spring Security 支持在权限校验注解（如 `@PreAuthorize`、`@PostAuthorize`、`@Secured`）中使用 SpEL 表达式进行动态权限判断。当这些表达式的内容来自用户输入或可被用户操控时，攻击者可构造恶意表达式绕过权限检查、访问敏感数据、执行任意代码等。常见于动态权限配置、多租户系统、基于表达式的访问控制等场景。

---

## Details

**代码示例**：
```java
// 危险：注解中的表达式内容来自外部配置或用户输入
import org.springframework.security.access.prepost.PreAuthorize;

// 危险示例1：表达式从配置文件读取
@PreAuthorize("#{permissionConfig.getUserPermission()}") // 如果配置可被篡改则存在风险
public void sensitiveOperation() { }

// 危险示例2：表达式包含用户可控的变量
@PreAuthorize("#userRole == '" + request.getParameter("role") + "'") // 表达式注入
public void adminOperation() { }

// 危险示例3：动态构造表达式字符串
String permExpr = "hasRole('" + userInput + "')"; // 用户输入拼接到表达式中
@PreAuthorize(permExpr) // 无法在注解中使用变量，但运行时评估可能存在风险

// 危险示例4：使用 SecurityExpressionRoot 评估用户输入
SecurityExpressionRoot root = new SecurityExpressionRoot(authentication) {};
ExpressionParser parser = new SpelExpressionParser();
Expression exp = parser.parseExpression(userInput);
exp.getValue(root); // 危险：用户可访问 authentication 对象

// 攻击载荷示例
// T(java.lang.Runtime).getRuntime().exec('calc')
// #this.getClass().forName('java.lang.Runtime').getRuntime().exec('calc')

// 较安全：使用硬编码的表达式
@PreAuthorize("hasRole('ADMIN')") // 表达式内容固定
public void adminOperation() { }

// 较安全：使用方法参数的属性访问（不是用户直接提供的表达式）
@PreAuthorize("hasPermission(#order, 'read')") // order 是方法参数，不是表达式
public void viewOrder(Order order) { }

// 较安全：使用 SimpleEvaluationContext
SimpleEvaluationContext context = SimpleEvaluationContext.forReadOnlyDataBinding().build();
Expression exp = parser.parseExpression(safeExpression);
exp.getValue(context);
```

**快速定位核心操作**：
- 关键词：`@PreAuthorize`、`@PostAuthorize`、`@PreFilter`、`@PostFilter`、`SecurityExpressionRoot`、`hasRole`、`hasPermission`
- 查找 Spring Security 注解的使用位置，重点关注表达式内容
- 检查表达式是否包含变量、方法调用、类型引用
- 追踪表达式中变量的来源，判断是否可被用户控制
- 检查配置文件中的权限表达式定义（如 `application.properties`、`security.xml`）
- 搜索 `ExpressionBasedPreInvocationAdvice`、`MethodSecurityExpressionHandler` 的配置

**快速定位保护机制**：
- 注解表达式是否为硬编码常量（如 `hasRole('ADMIN')`）
- 是否使用了 Spring Security 的内置表达式函数（相对安全）
- 是否自定义了 `MethodSecurityExpressionHandler` 限制表达式能力
- 是否使用 `SimpleEvaluationContext` 评估表达式
- 是否对表达式中的变量进行了输入验证
- 是否禁用了类型引用和构造函数调用
- Spring Security 版本是否为最新稳定版（5.7+、6.0+）

**审计等级**：**L2-L4**
- **L2**：跳读 Spring Security 注解，识别包含复杂表达式的位置
- **L3**：逐行分析表达式内容，确认变量来源和表达式复杂度
- **L4**：跨模块追踪配置和上下文，验证表达式评估环境的安全性

---

## Classify

**确认为漏洞**：
- Spring Security 注解中的表达式内容来自用户输入或可被用户篡改
- 表达式通过字符串拼接构造，包含用户可控的部分
- 使用 `StandardEvaluationContext` 评估包含用户输入的表达式
- 表达式中可访问敏感对象或调用危险方法
- 可通过类型引用 `T()` 执行任意代码

**误报**：
- 注解表达式为硬编码常量，不包含动态内容
- 表达式中的变量来自方法参数（Spring 自动绑定），而非用户直接提供的表达式字符串
- 使用 `SimpleEvaluationContext` 且禁用了类型引用和方法调用
- 自定义的 `MethodSecurityExpressionHandler` 已限制表达式能力

**代码异味**：
- 大量使用复杂的 SpEL 表达式进行权限判断
- 表达式中包含大量的逻辑运算和方法调用
- 从配置文件或数据库动态加载权限表达式
- 使用字符串拼接构造表达式，即使当前变量不可控

---

## Low Risk

以下情况可评为低风险：
- **硬编码表达式**：所有 Spring Security 注解中的表达式均为硬编码常量
- **内置函数**：仅使用 Spring Security 内置的安全函数（如 `hasRole`、`hasPermission`）
- **方法参数绑定**：表达式访问方法参数的属性，而非用户提供的表达式字符串
- **受限上下文**：使用 `SimpleEvaluationContext` 评估表达式
- **表达式白名单**：动态表达式必须匹配预定义的安全模式
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **日志监控**：所有权限校验失败和异常表达式均记录日志

**注意**：Spring Security 表达式注入虽然不如直接 SpEL 注入常见，但一旦存在则危害极高，必须确保表达式内容不可被用户操控。
