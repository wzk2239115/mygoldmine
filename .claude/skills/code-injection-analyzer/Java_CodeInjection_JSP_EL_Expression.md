# Java JSP EL 表达式注入

**漏洞成因**：JSP EL（Expression Language）支持访问对象属性和调用方法，当用户输入作为 EL 表达式或包含在 EL 表达式中时，攻击者可执行任意 EL 表达式，访问对象属性和调用方法。

---

## Details

**代码示例**：
```jsp
<!-- 危险：用户输入作为 EL 表达式 -->
<c:out value="${param.expr}"/>

<!-- 危险：拼接用户输入到 EL 表达式 -->
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %>
<c:out value="${requestScope[param.key]}"/>

<!-- 危险：在 tag 中使用用户输入 -->
<c:forEach var="item" items="${param.list}">
    ${item}
</c:forEach>

<!-- 较安全：使用 JSP 2.1+ 禁用 EL -->
<%@ page isELIgnored="true" %>
```

**快速定位核心操作**（L1-L2）：
- 关键词：`${param.`, `${request`, `${}` 等 EL 表达式
- 查看 EL 中是否包含用户输入：`param`、`header`、`cookie`
- 检查是否使用了动态属性访问：`${map[key]}`
- 追踪模板中的用户输入

**快速定位保护机制**（L1-L2）：
- 是否禁用了 EL：`isELIgnored="true"`
- 是否使用了 JSTL `<c:out>` 进行转义
- 是否限制了可访问的对象：白名单配置
- 是否使用了 EL 函数白名单

**审计等级**：**L1-L3**
- **L1**：关键词扫描，快速定位 EL 表达式和用户输入
- **L2**：跳读确认用户输入是否在 EL 中
- **L3**：逐行读取 EL 构造及其防护机制

---

## Classify

**确认为漏洞**：
- 用户输入直接在 EL 表达式中
- 未禁用 EL，未进行转义
- 可访问危险对象（Runtime、ProcessBuilder）

**误报**：
- 禁用了 EL（`isELIgnored="true"`）
- 使用 `<c:out>` 进行了转义
- 用户输入被严格限制

**代码异味**：
- EL 存在但有部分防护
- 权限控制依赖前端验证

---

## Low Risk

以下情况可评为低风险：
- **完全禁用 EL**：明确设置 `isELIgnored="true"`
- **权限隔离**：EL 执行在最小权限用户下
- **内网保护**：仅限管理员、内网
- **白名单对象**：仅允许访问安全对象
- **审计监控**：EL 执行被完整记录、监控
