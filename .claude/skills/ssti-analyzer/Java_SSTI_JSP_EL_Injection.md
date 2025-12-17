# Java_SSTI_JSP_EL_Injection

**漏洞类型**: JSP 表达式语言（EL）注入，用户输入被解析为 EL 表达式执行

---

## Details

### 代码示例

**易受攻击的代码模式**:
```java
// JSP 页面直接输出用户输入到 EL 表达式
<%-- JSP 文件 --%>
${param.username}  <%-- 用户输入直接求值 --%>

// 字符串拼接后使用 EL
String expr = "${" + request.getParameter("field") + "}";
<%= expr %>

// 使用 ELProcessor 动态求值
ELProcessor elp = new ELProcessor();
String userExpr = request.getParameter("expr");
Object result = elp.eval(userExpr);

// StandardEvaluationContext 用户可控表达式
ExpressionParser parser = new SpelExpressionParser();
String expr = request.getParameter("expression");
Expression exp = parser.parseExpression(expr);
exp.getValue();

// JSP 自定义标签中的 EL 注入
<custom:display value="${param.userInput}" />
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- EL 语法: `${}`, `#{}`, `param.`, `header.`, `cookie.`
- EL 类: `ELProcessor`, `ELContext`, `ValueExpression`, `MethodExpression`
- SpEL 类: `SpelExpressionParser`, `StandardEvaluationContext`
- JSP 指令: `<%=`, `<jsp:expression>`, `<c:out>`
- 用户输入: `param.`, `request.getParameter()`, `@RequestParam`

**L2 跳读定位**:
- 搜索 JSP 文件中的 `${param.}` 和 `${header.}` 模式
- 检查 Java 代码中的 ELProcessor.eval() 调用
- 定位 SpEL 表达式解析器的使用
- 追踪用户输入到表达式求值的数据流
- 关注自定义标签的属性处理

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入验证: 表达式内容白名单检查
- 使用 JSTL: `<c:out>` 默认转义
- 禁用 EL: `<%@ page isELIgnored="true" %>`
- SpEL 配置: 使用 SimpleEvaluationContext 替代 StandardEvaluationContext
- 自定义解析器: 实现受限的 ELResolver

**L3 逐行分析**:
- JSP 配置:
  - `isELIgnored` 是否设置为 true
  - web.xml 中的 `<el-ignored>` 配置
  - JSP 版本是否支持安全特性
- EL 表达式检查:
  - 是否直接使用 `${param.}` 输出用户输入
  - JSTL 标签是否设置 `escapeXml="true"`
  - 表达式是否包含方法调用或复杂逻辑
- ELProcessor 安全:
  - 是否对输入表达式进行验证
  - ELResolver 是否限制了可访问的对象
  - 是否禁用了函数映射和变量解析器
- SpEL 配置:
  - 使用 SimpleEvaluationContext（安全）还是 StandardEvaluationContext（危险）
  - 是否禁用了类型引用 `T()`
  - 是否限制了可调用的方法和属性

**L4 跨模块追踪**:
- 追踪从请求 → JSP 渲染的完整流程
- 检查 web.xml 和 Spring 配置中的全局 EL 设置
- 验证自定义标签库的实现安全性
- 检查是否有过滤器或拦截器进行输入净化
- 追踪 EL 隐式对象的暴露范围

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- JSP 中直接使用 `${param.}` 或 `${header.}` 输出用户输入
- ELProcessor.eval() 接受未验证的用户表达式
- SpEL 使用 StandardEvaluationContext 且表达式可控
- 可通过 EL 访问 Runtime、ClassLoader 等危险类
- 表达式中可调用任意对象的方法

**误报判定**:
- JSP 设置了 `isELIgnored="true"` 完全禁用 EL
- 使用 `<c:out escapeXml="true">` 且仅输出简单值
- SpEL 使用 SimpleEvaluationContext 严格限制功能
- 表达式内容经过严格的白名单验证
- 自定义 ELResolver 仅允许访问安全的属性

**代码异味**:
- 虽使用 JSTL 但 escapeXml 未明确设置
- 表达式内容虽验证但使用黑名单过滤
- SpEL 配置了部分限制但未完全禁用危险功能
- 自定义标签处理属性时未充分验证
- EL 函数映射包含文件操作或命令执行
- 在 JSP 中混用 `<%= %>` 脚本和 EL 表达式

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- JSP 页面仅限管理员访问
- 需要强身份验证和授权
- 功能部署在内部管理系统
- 实施严格的访问控制

**架构设计防护**:
- 全局禁用 EL 或仅在必要页面启用
- 使用 SimpleEvaluationContext 替代 StandardEvaluationContext
- 实现自定义 ELResolver 白名单机制
- 迁移到更安全的模板引擎

**输入与输出保护**:
- 所有用户输入经过严格验证和编码
- 强制使用 `<c:out escapeXml="true">`
- 表达式内容白名单验证
- 禁止在表达式中使用方法调用

**监控与运行环保**:
- 部署 WAF 检测 EL 注入特征
- SecurityManager 限制反射和类加载
- 完整的审计日志
- 实时监控异常表达式求值
