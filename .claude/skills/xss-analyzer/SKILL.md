---
name: xss-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 XSS（跨站脚本攻击）漏洞；重点关注检测不安全的用户输入在输出到网页时未经适当编码、转义或过滤，从而导致恶意脚本在用户浏览器中执行；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**  
XSS（跨站脚本）漏洞源于应用程序未对用户可控的输入数据进行充分的输出编码或内容过滤，导致恶意脚本在受害者浏览器中执行。该漏洞通常出现在涉及用户输入展示、富文本处理、动态内容拼接或前端模板渲染的业务模块中，如评论系统、消息通知、用户资料展示、搜索结果页、管理后台日志展示等。

---

**Early exit**  
若项目代码完全不涉及将用户输入或第三方数据直接/间接输出至HTML、DOM或JavaScript上下文（例如纯API后端、无HTML输出的命令行工具、不处理用户输入的底层系统服务），且前端完全由可信静态内容构成，则可快速退出对XSS的审计。

---

## 通用 XSS 漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：用户输入未经转义直接输出到 HTML（反射型/存储型）、DOM 操作中插入未净化数据（绕过技巧详见 [bypassTricks.md - DOM-based XSS利用](bypassTricks.md#dom-based-xss利用)）、模板引擎禁用自动转义、JavaScript 代码拼接用户输入、内联事件处理器和 javascript: URL（绕过技巧详见 [bypassTricks.md - 协议和事件处理器绕过](bypassTricks.md#协议和事件处理器绕过)）、净化和过滤不足（绕过技巧详见 [bypassTricks.md - WAF和过滤器绕过](bypassTricks.md#waf和过滤器绕过)）、特定场景（JSONP/JSON Hijacking/SSTI/富文本编辑器）、多重编码和上下文混淆（绕过技巧详见 [bypassTricks.md - Payload混淆与编码](bypassTricks.md#payload混淆与编码)）

查看详细说明：
- JSON Hijacking 漏洞，详见：[json_hijacking.md](json_hijacking.md)
- XSS 与 SSTI 重叠场景，详见：[xss_ssti_xss_overlap.md](xss_ssti_xss_overlap.md)
- 常见误报场景，详见：[COMMON_FALSE_POSITIVES.md](COMMON_FALSE_POSITIVES.md)

案例研究：
- Java 博客平台 XSS 案例，详见：[CASE_STUDY_Java_BlogPlatform.md](CASE_STUDY_Java_BlogPlatform.md)
- JavaScript 评论系统 XSS 案例，详见：[CASE_STUDY_JavaScript_CommentSystem.md](CASE_STUDY_JavaScript_CommentSystem.md)
- PHP CMS XSS 案例，详见：[CASE_STUDY_PHP_CMS.md](CASE_STUDY_PHP_CMS.md)
- Python Django 论坛 XSS 案例，详见：[CASE_STUDY_Python_DjangoForum.md](CASE_STUDY_Python_DjangoForum.md)
- React 富文本编辑器 XSS 案例，详见：[CASE_STUDY_React_RichEditor.md](CASE_STUDY_React_RichEditor.md)

---
**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言或框架的实现方式相关。根据项目所使用的技术栈，仅需审计对应章节中的漏洞模式。

**JavaScript**  
- 使用 innerHTML、outerHTML、document.write 等方法直接插入未转义的用户输入到 DOM 中，详见:[JavaScript_DOMBasedXSS.md](JavaScript_DOMBasedXSS.md)  
- 在前端模板引擎中直接拼接用户输入或使用不安全的模板语法，详见:[JavaScript_TemplateInjection.md](JavaScript_TemplateInjection.md)  
- 从 URL 参数、hash 或 search 中提取数据后未经处理直接输出到页面，详见:[JavaScript_URLParameterReflection.md](JavaScript_URLParameterReflection.md)

**TypeScript**  
- 在 Angular 中使用 bypassSecurityTrustHtml 等方法绕过内置的安全机制直接信任用户输入，详见:[TypeScript_AngularBypassSecurityTrust.md](TypeScript_AngularBypassSecurityTrust.md)  
- 在 React 中使用 dangerouslySetInnerHTML 属性插入未经过滤的用户数据，详见:[TypeScript_ReactDangerouslySetInnerHTML.md](TypeScript_ReactDangerouslySetInnerHTML.md)  
- 在 Vue 中使用 v-html 指令渲染未经净化的用户内容，详见:[TypeScript_VueVHtmlWithoutSanitization.md](TypeScript_VueVHtmlWithoutSanitization.md)

**PHP**  
- 在模板或视图文件中使用 echo、print 等输出未经 htmlspecialchars/htmlentities 转义的用户输入，详见:[PHP_UnescapedOutputInTemplate.md](PHP_UnescapedOutputInTemplate.md)  
- 搜索功能中将用户查询关键词未经过滤直接回显到页面造成反射型 XSS，详见:[PHP_ReflectedXSSInSearch.md](PHP_ReflectedXSSInSearch.md)  
- 管理后台或评论系统中存储的用户输入在展示时未进行输出编码造成存储型 XSS，详见:[PHP_StoredXSSInAdminPanel.md](PHP_StoredXSSInAdminPanel.md)

**Java**  
- 在 JSP 页面中使用 <%= %> 或 out.println() 直接输出未编码的用户输入，详见:[Java_JSPUnencodedOutput.md](Java_JSPUnencodedOutput.md)  
- 在 Thymeleaf 模板中使用 th:utext 或 [(${...})] 语法渲染未经转义的用户数据，详见:[Java_ThymeleafUnescapedExpression.md](Java_ThymeleafUnescapedExpression.md)  
- 在 Servlet 中通过 response.getWriter().write() 等方法直接返回用户输入到 HTML 响应，详见:[Java_ServletDirectReflection.md](Java_ServletDirectReflection.md)

**Python**  
- 在 Flask 中使用 render_template_string 动态构建模板或 Markup 直接包装用户输入导致未转义，详见:[Python_FlaskUnsafeTemplateRendering.md](Python_FlaskUnsafeTemplateRendering.md)  
- 在 Django 中对用户输入使用 mark_safe() 标记为安全字符串或在模板中使用 |safe 过滤器，详见:[Python_DjangoMarkSafeMisuse.md](Python_DjangoMarkSafeMisuse.md)  
- 在 Jinja2 模板引擎中关闭自动转义（autoescape=False）或手动拼接 HTML 字符串，详见:[Python_Jinja2AutoescapeDisabled.md](Python_Jinja2AutoescapeDisabled.md)

**Go**  
- 使用 text/template 包而非 html/template 包渲染 HTML 页面导致缺少自动转义，详见:[Go_TextTemplateUsedForHTML.md](Go_TextTemplateUsedForHTML.md)  
- 通过 fmt.Sprintf 或字符串拼接手动构造 HTML 响应并插入用户输入，详见:[Go_ManualHTMLConcatenation.md](Go_ManualHTMLConcatenation.md)  
- 在 Gin、Echo 等 Web 框架中使用 c.HTML() 或直接写响应时未对用户输入进行编码，详见:[Go_GinEchoUnescapedResponse.md](Go_GinEchoUnescapedResponse.md)

**C/C++**  
- 在 CGI 程序中使用 printf、sprintf 等直接输出包含用户 GET/POST 参数的 HTML 响应，详见:[C_CGIReflectedXSS.md](C_CGIReflectedXSS.md)  
- 自研 HTTP 服务器或嵌入式 Web 服务中手动拼接响应体时未对用户输入进行 HTML 实体编码，详见:[C_CustomHTTPServerHTMLInjection.md](C_CustomHTTPServerHTMLInjection.md)

**Rust**  
- 在 Actix-web、Rocket 等框架中使用 format! 宏或字符串拼接手动构造 HTML 响应插入用户输入，详见:[Rust_ActixManualHTMLConstruction.md](Rust_ActixManualHTMLConstruction.md)  
- 在 Tera、Handlebars 等模板引擎中使用 safe 过滤器或禁用自动转义渲染用户数据，详见:[Rust_TeraTemplateSafeFilterMisuse.md](Rust_TeraTemplateSafeFilterMisuse.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注用户输入处理和输出展示相关的实现：**

- 查阅项目文档，重点关注用户交互功能和数据展示机制说明
- 理解业务领域和核心功能，识别涉及用户输入和内容展示的场景
- 识别关键组件、模块及其关系，特别是前端渲染模块、模板引擎、API响应处理
- 梳理应用流程（重点：用户输入接收流程、数据处理流程、内容输出渲染流程）
- 识别关键业务功能（评论系统、搜索功能、用户资料展示、消息通知、内容管理等）
- 理解所用技术栈和框架（前端框架如 React/Vue/Angular、后端模板引擎如 Jinja2/Thymeleaf/JSP、Web框架等）
- 查阅配置文件以理解系统行为（模板引擎配置、安全策略如CSP、自动转义设置等）
- 定位用户输入的接收位置（表单提交、URL参数、API请求等）
- 定位用户输入的输出位置（HTML渲染、DOM操作、JavaScript代码拼接等）
- 识别数据流转路径（从输入到存储再到输出的完整链路）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件（例如纯API后端无HTML输出、不处理用户输入、完全静态页面等），可立即退出该漏洞类型的审计，无需继续深入分析。

只有在确认项目涉及用户输入和HTML/DOM输出并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅 XSS 漏洞的参考指南

XSS 漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用 XSS 漏洞模式（所有项目必审）**

在 **通用 XSS 漏洞模式** 章节中，列举了所有 Web 应用都必须审计的 XSS 问题：
- 用户输入未经转义直接输出到 HTML（反射型 XSS、存储型 XSS）
- DOM 操作中插入未净化的用户数据（DOM-Based XSS、URL 参数提取）
  - 绕过技巧详见：[bypassTricks.md - DOM-based XSS利用](bypassTricks.md#dom-based-xss利用)
- 模板引擎中禁用自动转义或使用不安全标记（autoescape=False、mark_safe、dangerouslySetInnerHTML、v-html）
- JavaScript 代码拼接中插入用户输入（eval、Function 构造器、setTimeout）
- 内联事件处理器和 javascript: URL（onclick、href="javascript:"、CSS 注入）
  - 绕过技巧详见：[bypassTricks.md - 协议和事件处理器绕过](bypassTricks.md#协议和事件处理器绕过)
- 净化和过滤不足（黑名单过滤、HTML 净化库配置不当）
  - 绕过技巧详见：[bypassTricks.md - WAF和过滤器绕过](bypassTricks.md#waf和过滤器绕过)
- 特定场景 XSS（JSONP 回调注入、JSON Hijacking、SSTI、富文本编辑器、SVG 和特殊标签）
  - SVG 绕过技巧详见：[bypassTricks.md - SVG和特殊标签](bypassTricks.md#svg和特殊标签)
- 多重编码和上下文混淆（双重编码、上下文切换）
  - 绕过技巧详见：[bypassTricks.md - Payload混淆与编码](bypassTricks.md#payload混淆与编码)

这些问题与编程语言无关，是输出编码和内容过滤设计层面的通用缺陷，任何 Web 应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言和框架组织了各技术栈的特定 XSS 问题：
- 按编程语言/框架分类（JavaScript、TypeScript/React/Vue/Angular、PHP、Java/JSP/Thymeleaf、Python/Flask/Django、Go、C/C++、Rust）
- 列出该语言/框架特定的 XSS 缺陷和对应的参考文档链接

根据项目所用技术栈，仅需查找和审计对应章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用 XSS 漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `xss_reflected_url_parameter.md`、`JavaScript_DOMBasedXSS.md`、`PHP_UnescapedOutputInTemplate.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（不可信输入）→ 处理逻辑 → 危险操作 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护

---

## 审计等级详解

XSS 漏洞审计采用分层的审计等级制度，根据风险程度和代码复杂度来指导审计员的工作深度和时间投入。

### 审计等级定义

| 等级 | 名称 | 操作 | 时间估计 | 何时使用 | 定义 |
|------|------|------|---------|----------|------|
| **L0** | 快速跳过 | 无需深入分析 | 1-2 分钟 | 代码明确无危险操作 | 使用了安全的 API（如 textContent、innerText）或框架默认转义（React JSX、Vue Mustache 默认转义）；代码确定无漏洞风险 |
| **L1** | 快速扫描 | 确认关键词并跳读参数来源 | 3-5 分钟 | 有风险操作但有明显防护 | 存在危险 API（innerHTML、dangerouslySetInnerHTML 等）但已使用可信库净化（DOMPurify、sanitize-html）；输入经过验证或来自受信源 |
| **L2** | 跳读 | 确认防护机制和参数来源 | 5-10 分钟 | 需要验证防护有效性 | 存在危险操作但防护配置需要核实；防护库的配置是否正确（如 DOMPurify 的白名单）；多个处理点是否都有防护 |
| **L3** | 逐行读 | 完整阅读逻辑，追踪数据流 | 15-30 分钟 | 高风险操作或防护不完整 | 直接将用户输入写入 HTML/DOM 无防护；防护机制不足或有绕过可能；需要完整理解数据处理逻辑 |
| **L4** | 跨模块追踪 | 分析完整数据链路，跨文件追踪 | 30-60 分钟 | 链路复杂或多层处理 | 数据链路跨越多个文件、模块、框架边界；涉及数据库存储、API 传输、前后端交互；需要完整的攻击链分析 |

### 快速判断流程

#### 第 1 步：检查是否存在危险操作

扫描代码中是否存在危险 API 或操作：

| 操作类型 | 危险 API/语法 | 风险等级 |
|---------|----------|---------|
| **DOM 操作** | innerHTML, outerHTML, insertAdjacentHTML, document.write | 高风险 |
| **React 特定** | dangerouslySetInnerHTML, HTML 字符串拼接 | 高风险 |
| **Vue 特定** | v-html, v-bind:innerHTML | 高风险 |
| **Angular 特定** | bypassSecurityTrustHtml, bypassSecurityTrustUrl | 高风险 |
| **模板引擎** | Handlebars {{{}}}, EJS <%=, Thymeleaf th:utext | 高风险 |
| **后端输出** | echo, print, response.write 未经编码 | 高风险 |
| **标记为安全** | mark_safe(), Markup(), \|safe, safe 过滤器 | 中等风险 |

**判断：** 如果没有找到上述操作 → **L0 快速跳过**

#### 第 2 步：检查是否有防护机制

| 防护措施 | 等级调整 |
|---------|---------|
| **无防护** | 确定为 L3+（高风险） |
| **框架默认转义** | 降低到 L0（React JSX、Vue Mustache、Django 默认、Thymeleaf 默认） |
| **可信净化库** | 降低到 L1-L2（DOMPurify、sanitize-html、HTML Purifier） |
| **简单替换** | 保持 L3（仅删除特定标签，易绕过，详见 [bypassTricks.md - WAF和过滤器绕过](bypassTricks.md#waf和过滤器绕过)） |
| **自定义过滤** | 保持或升高至 L3-L4（需验证正确性） |

**判断：**
- 有可信防护 → **L1-L2 跳读/确认**
- 无防护或防护不足 → **L3-L4 深度分析**

#### 第 3 步：检查数据流复杂度

| 数据流特征 | 等级调整 |
|-----------|---------|
| **单点直接输出** | L2 或更低 |
| **多个中间处理** | 升高 1 级（如 API 返回 → 模板 → DOM） |
| **跨多个文件** | 升高 1 级（需追踪多文件） |
| **涉及数据库存储** | 升高 1 级（需验证保存和读取点） |
| **多个输出位置** | 升高 1 级（需检查所有输出是否都有防护） |

**判断：**
- 简单直接 → **L2**
- 涉及多个模块/文件 → **L3-L4**

### 各等级的具体操作指南

#### L0：快速跳过（1-2 分钟）

当满足以下条件之一时，可以 L0 处理：

1. 代码只使用安全的 API：
   ```javascript
   // ✅ L0：不需要审计
   element.textContent = userInput;  // textContent 自动转义
   element.innerText = userInput;    // innerText 自动转义
   ReactComponent render 默认转义     // React JSX 默认转义
   v-text 指令                       // Vue v-text 默认转义
   ```

2. 代码使用框架默认转义，未关闭：
   ```tsx
   // ✅ L0：React JSX 默认转义
   return <div>{userInput}</div>;
   ```

3. 输入明确为常量或硬编码：
   ```javascript
   // ✅ L0：没有用户输入
   document.getElementById('banner').innerHTML = '<h1>Welcome</h1>';
   ```

**操作：** 记录为"无漏洞"，继续审计下一部分

---

#### L1：快速扫描（3-5 分钟）

当存在危险操作但有明显防护时：

1. **确认防护库的使用**
   - DOMPurify 是否被导入和使用？
   - 白名单配置是否合理？（检查 ALLOWED_TAGS、ALLOWED_ATTR）

2. **验证参数来源**
   - 确认参数来自何处（URL、用户输入、API）
   - 参数是否经过验证？

3. **快速代码浏览**
   ```jsx
   // ✅ L1：有防护，快速确认配置
   const clean = DOMPurify.sanitize(content, {
     ALLOWED_TAGS: ['b', 'i', 'p']  // 检查白名单
   });
   return <div dangerouslySetInnerHTML={{ __html: clean }} />;
   ```

**操作：** 快速验证防护机制，记录为"有防护措施"或"低风险"

---

#### L2：跳读（5-10 分钟）

当防护机制需要核实时：

1. **定位危险操作**
   ```javascript
   // 搜索以下关键词：
   innerHTML, dangerouslySetInnerHTML, v-html, th:utext, mark_safe
   ```

2. **验证防护配置**
   - DOMPurify 的白名单是否过于宽松？
   - 是否允许了危险属性（onclick、onerror、href="javascript:"）？
   - 多个防护点是否配置一致？

3. **追踪参数来源**
   ```javascript
   // 反向查找参数的来源
   const clean = DOMPurify.sanitize(userContent);
   // userContent 来自哪里？
   // 如果来自用户输入，需要验证 DOMPurify 的配置是否足够
   ```

**操作：** 读一遍防护逻辑，确认没有漏洞，记录风险等级

---

#### L3：逐行读（15-30 分钟）

当存在高风险操作或防护不完整时：

1. **完整阅读逻辑**
   ```javascript
   // 完整理解整个函数，不跳跃阅读
   function renderComment(comment) {
     // 1. 检查 comment 来源
     // 2. 检查中间是否有处理
     // 3. 检查输出时是否有防护
     document.getElementById('comments').innerHTML += comment;
   }
   ```

2. **追踪完整数据流**
   - 输入来自哪里？（URL、表单、API、localStorage）
   - 数据经过了什么处理？（验证、替换、编码）
   - 数据在哪里输出？（多个位置都要检查）
   - 每个输出位置是否都有防护？

3. **验证防护绕过可能性**
   ```javascript
   // ❌ L3：防护不足
   const comment = request.get('content');
   const safe = comment.replace(/<script>/g, '');  // 简单替换，易绕过
   element.innerHTML = safe;

   // 问题：可以使用 <SCRIPT>、<img onerror>、<svg onload> 绕过
   // 详见：bypassTricks.md - WAF和过滤器绕过、协议和事件处理器绕过
   ```

**操作：** 完整分析数据流，确认漏洞，生成具体报告

---

#### L4：跨模块追踪（30-60 分钟）

当数据链路复杂跨越多个文件时：

1. **建立完整的数据流图**
   ```
   用户输入 (URL参数)
     ↓
   前端路由处理 (router.js)
     ↓
   API 请求 (api/comments.js)
     ↓
   后端处理 (server/comments.py)
     ↓
   数据库存储 (db.save())
     ↓
   重新查询 (db.query())
     ↓
   后端返回 (response.json())
     ↓
   前端接收 (fetch().then())
     ↓
   DOM 渲染 (innerHTML += response.data)
   ```

2. **检查每个节点**
   - 输入端：是否有验证？
   - 传输端：是否有编码？
   - 存储端：是否保存了原始值？
   - 输出端：是否有转义？

3. **识别多源拼接风险**
   ```javascript
   // ❌ L4：多源拼接
   const userComment = await api.getComment(id);  // 来自 API
   const userName = props.username;                // 来自 props
   const html = `<div>${userComment}</div>`;      // 拼接
   element.innerHTML = html;                       // 无防护输出
   ```

**操作：** 追踪完整链路，分析每个环节，生成详细报告

### 审计等级的实际应用

在各个 XSS 漏洞文档（如 `JavaScript_DOMBasedXSS.md`）中，每一个都有"审计等级标注"表格，指导审计员快速判断：

```markdown
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 仅使用 textContent | L0 | 无风险 |
| innerHTML + DOMPurify 净化 | L2 | 核实净化策略 |
| 直接 innerHTML 无防护 | L3 | 高风险 |
| 跨模块数据链路 | L4 | 需完整分析 |
```

**使用方式：** 根据代码实际情况选择等级，然后按照等级要求进行审计

## 常见保护机制绕过技巧

详见：[bypassTricks.md](bypassTricks.md)

快速索引：
- **CSP 绕过** → [bypassTricks.md - CSP绕过技术](bypassTricks.md#csp绕过技术)
- **编码混淆绕过** → [bypassTricks.md - Payload混淆与编码](bypassTricks.md#payload混淆与编码)
- **DOM 操作利用** → [bypassTricks.md - DOM-based XSS利用](bypassTricks.md#dom-based-xss利用)
- **Cookie 窃取** → [bypassTricks.md - Cookie获取与外带技术](bypassTricks.md#cookie获取与外带技术)
- **XSS 蠕虫** → [bypassTricks.md - XSS蠕虫与自动传播](bypassTricks.md#xss蠕虫与自动传播)
- **SVG 和特殊标签** → [bypassTricks.md - SVG和特殊标签](bypassTricks.md#svg和特殊标签)
- **WAF 和过滤器绕过** → [bypassTricks.md - WAF和过滤器绕过](bypassTricks.md#waf和过滤器绕过)
- **协议和事件处理器绕过** → [bypassTricks.md - 协议和事件处理器绕过](bypassTricks.md#协议和事件处理器绕过)
- **XSS+CSRF 组合** → [bypassTricks.md - XSS+CSRF组合利用](bypassTricks.md#xss+csrf组合利用)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-xss-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
