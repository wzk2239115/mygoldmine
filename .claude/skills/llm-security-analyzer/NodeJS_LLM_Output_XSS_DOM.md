# **NodeJS LLM Output XSS DOM**

当 Node.js 服务端返回的 LLM 输出被前端 JavaScript 直接插入到 DOM 中，而未进行 HTML 转义，攻击者可以通过提示注入或污染数据源，在用户浏览器中执行恶意 JavaScript。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索 DOM 操作：`innerHTML =`、`dangerouslySetInnerHTML`、`insertAdjacentHTML()`
- 查找文本设置：`textContent =`、`innerText =`（如果转义不当）
- 搜索 API 端点：`res.json()`、`response.send()`
- 查找前端框架使用：React、Vue、Angular 的变量绑定
- 定位模板库：`EJS`、`Handlebars`、`Pug` 的变量使用

**核心操作保护机制（L2: 跳读）**
- 检查后端是否对 LLM 输出进行了 HTML 转义
- 验证前端是否使用了 `textContent` 而非 `innerHTML`
- 查看是否使用了 React、Vue 等框架的自动转义
- 检查是否有 Content Security Policy（CSP）头
- 查看是否对响应进行了 Content-Type 设置

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪 LLM 输出从 API 返回到 DOM 插入的路径
- 检查后端返回的是 JSON 还是 HTML
- 审查前端代码中 LLM 数据的使用方式
- 查看是否有多个渲染路径
- 检查是否有特殊情况下的不同处理

**数据流追踪（L4: 跨模块追踪）**
- 追踪 LLM 输出从生成到最终渲染的完整链
- 检查是否有中间处理步骤
- 验证模板系统的配置

## Classify

**确认为漏洞的特征：**
1. 使用 `innerHTML` 或 `dangerouslySetInnerHTML` 直接渲染 LLM 输出
2. 前端 JavaScript 未对 API 返回的 LLM 数据进行转义
3. 模板引擎的 autoescape 被禁用
4. 没有 Content Security Policy 保护
5. 可以通过生成包含 `<script>` 标签的输出触发 XSS

**误报场景：**
1. 使用 `textContent` 或现代框架的自动转义机制
2. 后端明确进行了 HTML 转义（`htmlspecialchars()` 等）
3. React、Vue、Angular 等框架正确配置了自动转义
4. 有严格的 Content Security Policy（CSP）头
5. 仅返回 JSON，前端框架处理所有渲染

**代码异味（需要深入审查）**
1. 混合使用不同的 DOM 操作方法
2. 条件性地启用/禁用转义
3. 自定义的 HTML 转义函数
4. 直接的字符串拼接创建 HTML

## Low risk

**评级为低风险的场景：**
1. 使用 `textContent` 或框架的文本绑定，自动转义
2. 后端使用 `htmlspecialchars()` 或等价函数转义所有 LLM 输出
3. 前端框架（React、Vue）正确配置了自动转义
4. 有严格的 CSP 头限制内联脚本执行
5. 输出内容来自非用户可控的系统提示
