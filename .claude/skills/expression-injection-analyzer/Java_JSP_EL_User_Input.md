# Java JSP 表达式语言 (EL) 用户输入注入

**漏洞成因**：在 JSP 页面中将用户输入直接嵌入 EL 表达式（`${}`、`#{}`），JSP 容器执行这些表达式时会进行动态求值，导致用户可通过精心构造的表达式访问对象属性、调用方法或执行代码。常见于动态页面生成、用户数据展示、条件渲染等场景。

---

## Details

**代码示例**：
```jsp
<!-- 危险：直接在 EL 表达式中使用用户输入 -->
<%= request.getParameter("name") %>
<h1>${param.name}</h1>
<h1>#{userInput}</h1>

<!-- 危险：构造复杂表达式 -->
<%
    String userExpr = request.getParameter("expr");
    pageContext.setAttribute("userExpr", userExpr);
%>
<p>${userExpr}</p>  <!-- 如果 userExpr="user.role", 则访问 user 对象的 role 属性 -->

<!-- 较安全：进行输出编码 -->
<%@ taglib uri="http://java.sun.com/jsp/jstl/functions" prefix="fn" %>
<h1>${fn:escapeXml(param.name)}</h1>

<!-- 较安全：使用表达式语言的安全方式 -->
<c:out value="${param.name}" escapeXml="true" />
```

**快速定位核心操作**：
- 关键词：`${}`、`#{}`、`request.getParameter`、`pageContext.getAttribute`、JSP EL 表达式
- 查看 JSP 页面中是否存在直接使用请求参数或用户数据的 EL 表达式
- 追踪用户输入来源（request.getParameter、session、cookies、header）
- 检查是否存在输出编码或表达式转义
- 关注 JSP 容器版本（较新版本可能有 EL 限制）

**快速定位保护机制**：
- 是否使用了 `fn:escapeXml()` 或 `c:out` 进行输出编码
- 是否在 `web.xml` 中禁用了 EL 表达式（`<el-ignored>true</el-ignored>`）
- 是否使用了 JSP 2.1+ 的 deferred 表达式而非立即表达式
- 是否存在对 EL 函数的黑名单或白名单限制

**审计等级**：**L2-L3**
- **L2**：跳读 JSP 页面中的 EL 表达式，识别用户输入的使用位置
- **L3**：逐行验证是否存在输出编码和表达式安全处理

---

## Classify

**确认为漏洞**：
- JSP 页面中存在 `${request.getParameter(...)}` 或 `#{request.getParameter(...)}`
- 用户输入被直接放入 EL 表达式而未进行转义
- 表达式允许访问对象属性、调用方法或执行函数
- 页面未设置 CSP 或其他防护头

**误报**：
- EL 表达式仅用于显示硬编码的常量值
- 所有用户输入都经过 `fn:escapeXml()` 或 `c:out escapeXml="true"` 处理
- JSP 容器版本较新且已默认禁用 EL 或限制表达式能力

**代码异味**：
- JSP 页面中存在大量 EL 表达式，逻辑复杂
- 使用了 JSTL 库但未正确使用编码标签
- EL 表达式包含复杂的属性链访问

---

## Low Risk

以下情况可评为低风险：
- **输出编码完整**：所有用户数据都通过 `fn:escapeXml()` 或 `c:out` 进行了 HTML 编码
- **EL 表达式受限**：容器配置禁用了 EL 或限制了表达式的执行上下文
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **只读展示**：用户输入仅用于展示，不涉及敏感操作或数据处理

**注意**：EL 注入的影响取决于表达式上下文中可访问的对象。
