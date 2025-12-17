# **Java LLM Output XSS JSP**

当 Java Web 应用（使用 JSP）将 LLM 输出直接渲染到网页中而不转义，攻击者可以通过提示注入导致 XSS 漏洞。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索 JSP 表达式：`<%= llmOutput %>`、`${llmResponse}`
- 查找标签库：`<c:out>`、`<fn:escapeXml()>`
- 搜索转义配置：`escapeXmlAttribute`、`autoEscape`
- 查找自定义标签：标签实现中的 HTML 输出
- 定位动态内容：从 LLM 输出到 JSP 的流程

**核心操作保护机制（L2: 跳读）**
- 检查是否使用了 `<c:out>` 标签进行自动转义
- 验证是否使用了 `fn:escapeXml()` 函数
- 查看 JSP EL autoescape 是否启用
- 检查自定义标签是否进行了转义
- 查看 Content Security Policy（CSP）

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪 LLM 输出在 JSP 中的使用
- 检查是否使用了 `<%=` 或 `${}` 直接输出
- 审查标签库的使用
- 查看是否有动态生成的 HTML
- 检查属性值中是否使用了 LLM 输出

**数据流追踪（L4: 跨模块追踪）**
- 追踪从 LLM API 到 JSP 渲染的完整路径
- 检查中间处理步骤

## Classify

**确认为漏洞的特征：**
1. 直接使用 `<%= llmOutput %>` 或 `${llmOutput}` 输出
2. 未使用 `<c:out>` 标签
3. 动态生成 HTML 标签包含 LLM 输出
4. 在 HTML 属性值中使用 LLM 输出
5. JSP EL autoescape 被禁用

**误报场景：**
1. 使用 `<c:out>` 标签进行自动转义
2. 使用 `fn:escapeXml()` 函数
3. JSP EL autoescape 启用
4. 输出仅用于文本内容，不在 HTML 属性
5. 有 CSP 头保护

**代码异味（需要深入审查）**
1. 混合使用转义和非转义方式
2. 自定义标签处理 HTML
3. 动态 HTML 构造
4. 条件性的转义

## Low risk

**评级为低风险的场景：**
1. 所有输出都使用 `<c:out>` 标签
2. JSP EL autoescape 启用
3. HTML 属性由应用定义，LLM 输出仅作为文本值
4. 有 CSP 头限制脚本执行
5. 仅输出纯文本，无 HTML 结构
