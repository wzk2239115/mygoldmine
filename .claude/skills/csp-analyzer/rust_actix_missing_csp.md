# Rust Actix-web 缺失 CSP 响应头

## Details

Actix-web 应用在渲染 HTML 内容或提供 Web 资源时，若未在 HTTP 响应中设置 `Content-Security-Policy` 响应头，将无法有效限制浏览器加载的资源来源与执行权限，导致 XSS、数据外泄等威胁增大。

**代码示例**：处理 HTML 渲染或静态资源的 HTTP 处理器中，响应头配置通常涉及两个关键路径：
- 手工构造 `HttpResponse` 并设置响应头
- 通过全局或路由级中间件注入 CSP 响应头

**快速定位到核心操作的技巧** `L1:关键词扫描`
- 搜索关键词：`HttpResponse`、`HttpResponseBuilder`、`app.wrap()`、`web::scope()`
- 检查涉及 HTML 模板渲染、API 端点或文件服务的 handler 函数
- 识别通过 `.json()`、`.body()`、`.from_response()` 等方法返回响应的位置
- 在这些位置检查是否存在 `.insert_header("Content-Security-Policy", ...)` 调用

**快速定位到保护机制的技巧** `L2:跳读`
- 按照代码执行流追踪中间件注册：检查 `App::new()` 的链式调用中是否有 `wrap()` 方法使用自定义中间件
- 检查是否引入第三方 CSP 中间件 crate（如 `actix-web-middleware-*` 相关库），关键词 `middleware`、`CSP`、`Security`
- 统计 HTTP handler 数量与显式设置 CSP 响应头的 handler 数量，寻找覆盖差异
- 对于 SPA（单页应用）场景，检查主 HTML 入口文件（通常是 `index.html`）的提供方式，该 handler 最为关键

## Classify

漏洞与误报的研判逻辑：

**认定为漏洞**：
- 应用提供 HTML 内容（包含 `<script>`、`<iframe>`、`<img>` 等标签）且响应头完全缺失 CSP，或 CSP 策略过于宽松（如 `default-src 'unsafe-inline' *`）
- 应用包含用户可控的内容注入点（如模板变量、API 响应嵌入）且无 CSP 约束
- 跨域资源加载（CORS）且无 CSP 限制资源来源

**认定为误报**：
- 应用仅提供 JSON API，不包含 HTML 内容生成，且响应头为 `Content-Type: application/json`
- 页面由前端静态部署且 CSP 在 Web 服务器配置层（nginx/Apache）或 CDN 层实施，而非 Actix 应用层
- CSP 通过其他方式实施，如 HTTP/2 PUSH 配置或浏览器扩展策略

**代码异味**：
- 仅在部分 handler 中设置 CSP，覆盖率不完整
- CSP 策略与实际资源加载不匹配（过度限制导致功能受阻）

## Low risk

以下情况可评定为低风险或接受风险：

- 应用明确为内部网络或专属协议应用（如 WebSocket 长连接服务），其内容由受信源完全控制且不含用户输入
- CSP 实施于 Actix 上游层（反向代理、WAF、CDN），能有效覆盖所有出站响应，审计者可通过网络拓扑确认
- 应用采用 Content Security Policy Level 3 标准的 `require-trusted-types-for 'script'` 或 `script-src-elem` 配合严格的编码实践，在有证据表明不存在 DOM-based XSS 的情况下
- 页面内容完全由后端模板引擎生成且后端已通过参数化查询、模板自动转义等手段完全杜绝注入，CSP 此时作为纵深防护层可选
