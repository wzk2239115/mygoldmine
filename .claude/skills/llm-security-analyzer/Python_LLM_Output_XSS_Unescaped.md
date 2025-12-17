# **Python LLM Output XSS Unescaped**

当 Python Web 应用（Flask、Django 等）将 LLM 模型输出未经 HTML 转义直接渲染到网页中，攻击者可以通过提示注入或污染 LLM 输入源，导致生成包含恶意 JavaScript 的输出，在用户浏览器中执行。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索 Flask `render_template_string()`、Django `mark_safe()`、`render_to_string()`
- 查找 `{{ variable }}`、`{{{ triple_brace }}}`（模板变量）的使用
- 定位模板中使用 LLM 输出的位置：`{{ llm_response }}`、`{{ result.content }}`
- 搜索 `escape=False`、`autoescape=False` 等禁用转义的配置
- 查找 `bleach.clean()`、`markupsafe.escape()` 等转义函数是否被使用

**核心操作保护机制（L2: 跳读）**
- 检查 Flask/Django 模板引擎的 autoescape 配置是否启用
- 验证是否使用了 `markupsafe.escape()` 或 `html.escape()` 包装 LLM 输出
- 查看是否使用了白名单库（如 `bleach`）清理 HTML
- 检查响应的 Content-Type 是否正确设置为 `text/html; charset=utf-8`

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪 LLM 输出变量从 API 调用到模板渲染的路径
- 检查 Python 代码中是否有字符串拼接创建 HTML（如 `"<div>" + llm_output + "</div>"`）
- 审查 API 端点返回 JSON 时，前端是否也进行了 XSS 防护
- 查看是否在生成 HTML 属性值时使用了 LLM 输出（高风险）

**数据流追踪（L4: 跨模块追踪）**
- 追踪 LLM 输出的完整路径：API 调用 → 数据库存储 → 模板渲染
- 检查是否有中间的处理步骤（如后处理、过滤）
- 验证错误页面是否也存在 XSS 风险

## Classify

**确认为漏洞的特征：**
1. LLM 输出直接在模板中使用 `{{ variable }}` 而未显式转义
2. 模板引擎的 autoescape 配置被禁用
3. 使用 `mark_safe()` 或类似方法标记 LLM 输出为安全
4. Python 代码使用字符串拼接生成 HTML，将 LLM 输出作为值
5. API 返回 JSON 包含 LLM 输出，前端 JavaScript 未进行转义直接插入 DOM

**误报场景：**
1. LLM 输出仅返回给 API，由现代 JavaScript 框架（React、Vue）处理
2. 模板引擎已启用 autoescape，所有输出都被自动转义
3. 输出仅用于纯文本渲染（如 `<textarea>` 或 `<code>`），不能执行 JavaScript
4. 使用 `html.escape()` 或 `markupsafe.escape()` 明确转义了 LLM 输出

**代码异味（需要深入审查）：**
1. 自定义转义函数而非使用标准库
2. 存在有条件的转义逻辑
3. 部分路径转义，部分不转义
4. 模板中包含 `autoescape=False` 的局部块

## Low risk

**评级为低风险的场景：**
1. LLM 输出仅通过 JSON API 返回，由 React/Vue 等框架自动处理
2. 模板引擎全局启用 autoescape 且正确配置
3. 输出内容来自非用户可控的系统提示
4. 应用仅提供给可信用户（如内部员工），并有充分的监控
5. 输出完全基于结构化数据（如 JSON 对象），不包含用户生成的 HTML
