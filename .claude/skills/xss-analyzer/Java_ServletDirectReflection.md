# Java｜Servlet 直接回显输入导致 XSS

## 基本信息

- **难度等级：** ★★☆☆☆ (初级)
- **审计时间：** 10-25分钟（单个漏洞点）
- **先决知识：** Java Servlet API、HTML 编码基础、StringEscapeUtils 使用
- **复杂度评估：**
  - 简单场景（单点输出）：10-15分钟
  - 复杂场景（多点拼接）：25-40分钟

## 🚀 30秒快速清单

- [ ] 代码中是否存在 `getWriter().write()` 或 `print()` 等响应输出操作？
- [ ] 输出的值是否直接来自 `getParameter()` 等用户输入源？
- [ ] 在输出前是否使用了 `StringEscapeUtils.escapeHtml4()` 或其他编码方法？
- [ ] 是否改用了 JSP、Thymeleaf 等会自动转义的模板引擎？
- [ ] 错误页面、重定向提示等地方是否都进行了编码？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L3 深度分析

## Details

### 漏洞成因
在 Servlet 中使用 `response.getWriter().write()`、`PrintWriter` 或 `ServletOutputStream` 将请求参数直接写入 HTML 响应，未进行编码，会导致反射型 XSS。常见于错误提示、搜索页面、重定向提示、调试接口。

### 代码示例

**易受攻击的代码：**
```java
protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
    String keyword = req.getParameter("q");
    resp.setContentType("text/html;charset=UTF-8");
    PrintWriter out = resp.getWriter();
    out.write("<h1>Search: " + keyword + "</h1>"); // 未编码
}
```

**安全示例：**
```java
protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
    String keyword = req.getParameter("q");
    String safe = StringEscapeUtils.escapeHtml4(keyword == null ? "" : keyword);
    resp.setContentType("text/html;charset=UTF-8");
    PrintWriter out = resp.getWriter();
    out.write("<h1>Search: " + safe + "</h1>");
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `getWriter().write`, `print`, `append`, `sendError`, `sendRedirect`, `resp.write`。

**定位步骤：**
1. 搜索响应写入位置；
2. 跳读（L2）确认拼接的变量来源；
3. 检查是否使用 `StringEscapeUtils.escapeHtml4` 或 JSP/Twig 等模板引擎。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 统一输出编码工具类；
- 改用 JSP/Thymeleaf 模板自动转义；
- 利用 `HtmlUtils.htmlEscape`; 
- 通过 JSON 响应 + 前端渲染（并在前端编码）。

**定位技巧：**
- 逐行读（L3）确认所有输出路径均经过编码；
- 跨模块追踪（L4）多个 Servlet/Filter 是否复用相同逻辑。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 输出统一使用编码工具 | **L0（快速跳过）** | 风险低 |
| 个别响应遗漏编码 | **L2（跳读）** | 快速修补 |
| 大量直接写出用户输入 | **L3（逐行读）** | 高风险 |
| 复杂链路或动态重定向 | **L4（跨模块追踪）** | 需完整审计 |

## 🚨 陷阱识别 - Servlet XSS 的常见误区

### 陷阱 1：只编码了主要输出，忽视了错误页面和日志

**现象：**
```java
protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
  String keyword = req.getParameter("q");

  // 主要输出编码了
  String safe = StringEscapeUtils.escapeHtml4(keyword);
  resp.getWriter().write("<h1>Search: " + safe + "</h1>");

  // 但错误处理中忘记编码
  if (keyword == null) {
    resp.getWriter().write("<p>Error: " + keyword + " is required</p>");  // ❌ 未编码
  }
}
```

**看起来安全，但：**
- 开发者可能会对"主要业务流程"进行编码
- 但对"边界情况"（错误提示、调试信息、日志输出）忽视
- 这些地方仍然会导致 XSS

**定位技巧：**
1. 搜索所有 `getWriter().write()` 或 `print()` 调用
2. 检查每一个调用是否都有编码
3. 特别关注 `if` 语句中的错误处理分支

**研判方法：**
- ❌ 有风险：只有主流程编码，分支处理未编码
- ✅ 安全：所有 `getWriter()` 输出都经过编码
- ✅ 最安全：使用模板引擎，自动处理所有输出

### 陷阱 2：重定向URL中的参数未编码

**现象：**
```java
protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException {
  String redirectUrl = req.getParameter("redirect");

  // 试图验证，但编码不完整
  if (redirectUrl != null && redirectUrl.startsWith("/")) {
    resp.sendRedirect(redirectUrl);  // ❌ 如果 redirectUrl 包含反斜杠、引号等，可能被利用
  }
}
```

**看起来安全，但：**
- HTTP 重定向中的 URL 需要特殊编码
- 虽然检查了 `startsWith("/")，但没有完全编码
- 如果浏览器的某些模式下会解析 URL 中的特殊字符，可能被利用

**定位技巧：**
1. 搜索所有 `sendRedirect` 调用
2. 检查重定向目标是否来自用户输入
3. 验证是否使用了 `URLEncoder.encode()` 或白名单

**研判方法：**
- ❌ 有风险：直接使用 `sendRedirect(userInput)`
- ❌ 有风险：仅检查前缀或简单替换
- ✅ 较安全：使用白名单验证 URL 的来源
- ✅ 最安全：重定向 URL 来自常量或后端生成

### 陷阱 3：JSON 响应中的数据未编码就被用于 HTML

**现象：**
```java
protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
  String keyword = req.getParameter("q");

  // 返回 JSON
  resp.setContentType("application/json");
  resp.getWriter().write("{\"query\":\"" + keyword + "\"}");  // ❌ JSON 中的字符串未转义
}
```

**然后前端代码：**
```javascript
fetch('/api/search').then(r => r.json()).then(data => {
  document.getElementById('result').innerHTML = `<p>Query: ${data.query}</p>`;
});
```

**看起来安全，但：**
- 虽然设置了 JSON Content-Type，但如果浏览器被诱骗以 HTML 方式解析
- JSON 中的特殊字符（如引号）需要转义
- 后端设置了 JSON，但前端用 `innerHTML` 直接渲染也会产生 XSS

**定位技巧：**
1. 搜索 JSON 响应生成的代码
2. 检查是否使用了 JSON 库（如 `JSONObject`、`Gson`）
3. 如果手工拼接 JSON，检查转义情况

**研判方法：**
- ❌ 高风险：手工拼接 JSON 且未转义
- ✅ 较安全：使用 JSON 库自动转义（如 `new JSONObject().put(key, value)`）
- ✅ 最安全：JSON 库自动处理 + 前端也进行适当转义

### 陷阱 4：编码函数选择错误

**现象：**
```java
String keyword = req.getParameter("q");

// ❌ 使用了错误的编码函数
String safe = keyword.replace("<", "&lt;").replace(">", "&gt;");
resp.getWriter().write("<h1>Search: " + safe + "</h1>");

// 或者
String safe2 = URLEncoder.encode(keyword);  // ❌ 这是用于 URL 的编码，不是 HTML
resp.getWriter().write("<h1>Search: " + safe2 + "</h1>");
```

**看起来安全，但：**
- `replace()` 方式容易遗漏字符（如 `"`、`'` 等）
- `URLEncoder.encode()` 是用于 URL 参数的，不是用于 HTML
- 不同的上下文需要不同的编码方式

**定位技巧：**
1. 搜索所有手工转义的代码
2. 检查是否使用了标准库函数
3. 验证编码函数是否与上下文匹配

**研判方法：**
- ❌ 有风险：手工 `replace()` 转义，容易遗漏
- ❌ 有风险：使用了 `URLEncoder`、`Base64` 等错误的编码函数
- ✅ 安全：使用 `StringEscapeUtils.escapeHtml4()` 或 Apache Commons
- ✅ 最安全：使用模板引擎自动处理

### 陷阱 5：字符编码问题导致的绕过

**现象：**
```java
protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
  req.setCharacterEncoding("UTF-8");  // ⚠️ 可能太晚了
  String keyword = req.getParameter("q");

  String safe = StringEscapeUtils.escapeHtml4(keyword);
  resp.setContentType("text/html;charset=UTF-8");
  resp.getWriter().write("<h1>Search: " + safe + "</h1>");
}
```

**看起来安全，但：**
- 如果 `setCharacterEncoding()` 在 `getParameter()` 之前调用，字符可能被错误解析
- 不同的字符编码可能导致某些字符无法被正确编码
- 过时的字符编码（如 GB2312）可能有绕过空间

**定位技巧：**
1. 检查 `setCharacterEncoding()` 的调用位置
2. 查看 `web.xml` 中的字符编码配置
3. 验证编码的一致性

**研判方法：**
- ❌ 有风险：`setCharacterEncoding()` 在 `getParameter()` 后调用
- ❌ 有风险：使用了非标准或过时的字符编码
- ✅ 安全：在请求处理最开始设置 UTF-8 编码
- ✅ 最安全：使用 Filter 统一设置编码

---

### 陷阱总结：Servlet 审计快速检查

看到 Servlet 的 `getWriter().write()` 或 `print()` 输出时，立即检查：

1. **输出的内容来自哪里？**
   - 常量 → L0（无风险）
   - 用户输入参数 → L3+（需要编码）
   - 数据库或外部 API → L2（需要验证编码）

2. **是否使用了编码？**
   - 无编码 → L3（高风险）
   - 手工 `replace()` → L2-L3（检查是否完整）
   - `StringEscapeUtils.escapeHtml4()` → L1（检查上下文）

3. **有没有其他输出路径被遗漏？**
   - 仅检查了主流程 → 检查错误分支
   - 仅编码了搜索结果 → 检查错误提示
   - 仅处理了 HTML → 检查重定向、JSON 等

4. **是否有跨越多个方法的调用？**
   - 多个 Servlet 方法 → L2-L3（检查编码一致性）
   - 涉及 Filter、Interceptor → L3-L4（需要追踪所有输出）
   - 调用了公共工具方法 → 验证工具方法的编码逻辑

5. **是否使用了模板引擎？**
   - 改用 JSP、Thymeleaf → L0-L1（自动转义）
   - 混用 Servlet + 模板 → L2（检查混合点）
   - 仍用原始 Servlet 拼接 → L3+（高风险）

## Classify

### 研判标准

#### 确认漏洞
1. Servlet 直接输出用户可控数据；
2. 无编码或编码不完整；
3. 可利用构造 URL 注入脚本。

#### 误报
1. 输出内容来自常量或已编码；
2. 响应类型非 HTML（JSON/纯文本）且前端安全处理；
3. 页面仅在受控环境使用。

#### 代码异味
1. 使用 `String.format` 拼接 HTML；
2. 在错误页或重定向提示中输出未编码参数；
3. 缺乏统一编码方法，多个类重复实现。

## Low risk

### 低风险评级场景

#### 1. 页面仅内部调试使用
- 攻击面小，可暂降级。

#### 2. 输出仅为日志或低敏信息
- 风险较低，但仍建议编码。

#### 3. 即将迁移到统一模板框架
- 明确计划，可暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部调试 | 攻击面小 | 中 |
| 低敏输出 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
