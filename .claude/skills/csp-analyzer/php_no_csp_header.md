## PHP 应用缺失 CSP 响应头漏洞审计指南

### 漏洞本质

应用在生成 HTTP 响应时未通过 `header()` 函数设置 `Content-Security-Policy` (CSP) 响应头，导致浏览器无法通过该安全策略机制对页面中的脚本、样式、图片等资源加载进行约束，增大 XSS 攻击的易利用性。

### Details

#### 核心操作特征

典型代码示例：

```php
// 缺失 CSP 头的情况
<?php
header('Content-Type: application/json');
echo json_encode($data);  // 无 CSP 头
?>

// 存在 CSP 头的情况
<?php
header('Content-Security-Policy: default-src \'self\'; script-src \'self\' trusted-cdn.com');
header('Content-Type: text/html; charset=utf-8');
echo $html_content;
?>
```

**快速定位核心操作** (L1: 关键词扫描)
- 搜索所有包含 `header(` 的位置，特别是响应初始化的入口函数（如 `Controller::render()`、`View::output()` 等）
- 在每个输出 HTML/JSON 的分支路径中检查是否存在 `Content-Security-Policy` 相关的 header 调用
- 注意 `header()` 函数必须在任何输出之前调用，检查是否有提前的 echo/print 导致 header 失效

**快速定位保护机制** (L2: 跳读)
- 查找全局中间件或框架级的 Response 类（如 Laravel 的 Response 类、自定义中间件层）
- 检查是否有统一的 CSP 头设置逻辑，追踪通过依赖注入的 Response 对象如何生成最终的 HTTP 头
- 定位问题：若所有的响应输出均通过统一的 Response 对象或中间件，仅需在该单点检查；若存在多个独立的输出路径，需逐个核查

#### 审计深度指标

| 代码形态 | 审计等级 | 说明 |
|---------|---------|------|
| 纯 API 端点（仅返回 JSON） | L0 | 若确认该端点不涉及 HTML 模板渲染、仅返回结构化数据，可快速跳过 |
| HTML 模板直接输出 | L3 | 需逐行读取，检查每个输出 HTML 的位置，追踪数据来源是否经过充分的上下文转义 |
| MVC 框架使用（含模板继承链） | L3 | 跨读模板继承链，检查基模板是否设置了 CSP，子模板是否可能覆盖 |
| 多渠道响应（同一页面可能通过不同控制器、Ajax、同步渲染输出） | L4 | 需跨模块追踪，确保所有响应路径均配置了一致的 CSP 策略 |

### Classify

#### 漏洞与误报的研判标准

**确认为真实漏洞的条件：**
1. 应用在 HTTP 响应中输出了 HTML 内容（检查 `Content-Type: text/html`）
2. 该 HTML 页面包含第三方脚本、样式或其他可动态加载的资源
3. 响应头中完全缺失 `Content-Security-Policy` 或 `Content-Security-Policy-Report-Only` 头
4. 应用代码对用户输入的处理存在反射点（即使经过转义，也建议使用 CSP 作为纵深防御）

**判定为误报的情况：**
- 仅输出 JSON、XML 等结构化数据格式，无 HTML 上下文
- 该端点被明确标记为内部系统服务（如内部监控接口），风险承受度已在业务级别评估
- 响应头由反向代理或 WAF 统一注入，应用层不需单独设置（但应在审计报告中标注此依赖）

**代码异味的判定：**
- CSP 策略过于宽松（`default-src *` 或大量使用 `unsafe-inline`）应降级为"低风险"处理，不视为漏洞
- 存在条件性 CSP 设置（某些请求路径有，某些没有）应标注为"不一致风险"

### Low risk

#### 低风险评级的场景

1. **纯数据接口**：该端点的响应仅包含 JSON/XML，不包含 HTML 构建、脚本标签、样式注入点，且不被视为网页应用入口

2. **内部系统通道**：确认该应用部署环境中，所有 HTTP 响应均经过网关级或代理级的统一安全策略注入（如 Nginx/Apache 全局 header 配置、API 网关中间件），应用层可不单独配置

3. **降级策略**：应用通过 `Content-Security-Policy-Report-Only` 头进行非强制策略监控，虽未完全限制资源加载，但已具备数据收集能力，可作为过渡方案

4. **其他资源端点**：若该响应被确认为静态资源服务（如图片、CSS 文件等），技术上不涉及脚本执行风险，可标为低风险

5. **框架内置防护**：某些 PHP 框架（如 Symfony、Laravel 等）的模板引擎提供了内置的上下文感知转义机制，且该应用的所有用户输入均经过该机制验证；在这种情况下，CSP 缺失的严重程度可降低（仍应在纵深防御层面指出缺陷）
