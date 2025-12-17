# XSS 漏洞审计小抄（通用模式）

**审计范围**：任何涉及用户输入和 HTML/DOM 输出的 Web 应用都需检查以下模式。这些是输出编码和内容过滤层面的通用缺陷，与语言和框架无关。

**快速判断**：搜索代码中是否存在以下关键词并追踪数据源和防护机制。

---

## 1. 用户输入未转义直接输出到 HTML

### 反射型 XSS
- **位置**：搜索功能、错误消息、URL 参数显示等
- **现象**：请求参数直接出现在 HTML 响应中，未经 HTML 实体编码
- **关键词**：echo、print、response.write、`${}`、`{{}}`、`<%=`、`th:utext`、`v-text`
- **验证**：追踪 URL 参数从请求到 HTML 响应的完整路径，确认每个输出点是否都用了 `htmlspecialchars()`、`html()`、`escape()` 或框架的默认转义

### 存储型 XSS
- **位置**：评论、用户资料、帖子、后台日志、操作记录
- **现象**：用户输入存储到数据库，展示时未转义
- **关键词**：评论显示、个人资料页、管理后台
- **验证**：从数据库查询到 HTML 渲染，确认使用了输出编码

---

## 2. DOM 操作中插入未净化数据

### DOM-Based XSS
- **危险 API**：`innerHTML`、`outerHTML`、`insertAdjacentHTML`、`document.write`
- **现象**：`element.innerHTML = userInput;` 这样的代码
- **验证**：
  - 数据来源：追踪变量从哪里来（URL、输入框、API）
  - 防护检查：是否用了 DOMPurify、sanitize-html 等净化库
  - 多点检查：同一个变量是否在多处使用，每处都有防护？

### URL 参数提取
- **危险模式**：`location.search`、`location.hash`、`URLSearchParams` 提取后直接用
- **验证**：确认提取的参数是否经过净化或验证

### JavaScript 动态执行
- **危险 API**：`eval()`、`Function()`、`setTimeout(code, ms)`、`setInterval(code, ms)`（第一个参数为字符串）
- **现象**：用户输入被直接拼接到代码字符串中
- **验证**：通常这些都是严重问题，确认输入来源是否可信

### 动态脚本标签
- **现象**：`createElement('script')` 后 `innerHTML` 赋值用户输入，或 `src` 指向用户可控 URL
- **验证**：非常高风险，需确认是否有必要

---

## 3. 模板引擎不安全配置

### 禁用自动转义
- **关键词**：`autoescape=False`、`autoescape: false`、`{{{}}}`（三层花括号）
- **危险**：模板引擎未对变量进行 HTML 编码
- **验证**：查看配置文件和模板文件，确认是否确实禁用

### 标记为安全（绕过转义）
- **关键词**：`mark_safe()`、`Markup()`、`|safe`、`safe` 过滤器、`bypassSecurityTrust*`、`dangerouslySetInnerHTML`、`v-html`
- **现象**：用户输入被标记为"信任"，绕过转义机制
- **验证**：确认被标记为安全的内容是否真的经过了净化
- **常见误用**：
  ```python
  # 危险：用户输入直接标记为安全
  return mark_safe(user_comment)

  # 安全：先净化再标记
  clean = sanitize(user_comment)
  return mark_safe(clean)
  ```

---

## 4. 不安全的过滤和净化

### 黑名单过滤
- **现象**：`replace('<script>', '')`、`replace('onclick=', '')`
- **问题**：易被绕过（大小写、编码、其他标签）
- **绕过例**：`<SCRIPT>`、`<img onerror>`、`<svg onload>`、`<iframe>`、`expression()`

### 净化库配置不当
- **检查点**：
  - 版本是否过旧？
  - 白名单是否过宽（允许了危险标签或属性）？
  - 多处净化是否配置一致？
  - 净化后是否再次拼接导致二次注入？

---

## 5. 特殊场景

### JSONP 回调注入
- **现象**：`response.text = 'callback(' + userCallback + ')'`
- **问题**：回调函数名未验证
- **验证**：确认回调参数是否用了白名单验证（只允许字母数字下划线点号）

### JSON 通过 Content-Type 欺骗
- **现象**：返回 JSON 但 `Content-Type: text/javascript`
- **问题**：可被 `<script src>` 标签加载，执行为 JavaScript

### SSTI（Server-Side Template Injection）
- **现象**：用户输入直接拼接到 `render_template_string()` 或模板路径由用户控制
- **危险**：攻击者可执行任意代码

### 富文本编辑器
- **检查**：
  - 允许的标签列表是否包含危险标签（`iframe`、`embed`、`object`、`script`）？
  - 允许的属性是否包含事件处理器（`onclick`、`onerror`）或危险协议（`javascript:`）？
  - Markdown 渲染器是否转义了 HTML？

---

## 6. 多重编码和上下文切换

### 多重编码绕过
- **现象**：HTML 实体 + URL 编码 + Base64，解码顺序错误导致绕过防护
- **验证**：追踪数据的所有编码/解码步骤

### 上下文切换
- **现象**：在 HTML 中转义的数据再拼接到 JavaScript 字符串，或反之
- **例**：
  ```javascript
  // 危险：HTML 转义后直接拼接到 JS 字符串
  var msg = "User said: {userInput}";  // userInput 在 HTML 中已转义，但在 JS 中可能没转义
  eval("alert('" + msg + "')");
  ```

---

## 审计要点

1. **追踪数据流**：从输入源（URL、表单、API）→ 处理点（验证、转义、净化）→ 输出点（HTML、DOM、JS）
2. **每个输出点检查**：确认是否都有防护，不要遗漏任何输出位置
3. **防护验证**：使用可信库（DOMPurify、HTML Purifier）比简单替换更安全
4. **配置检查**：即使使用了防护库，配置过宽也会产生漏洞
5. **多个输入源**：同一个输出可能来自多个输入源，都要检查
