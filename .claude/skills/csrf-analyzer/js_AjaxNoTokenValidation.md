# JavaScript Ajax 请求缺少 Token 验证漏洞

## Details

### 漏洞成因
现代 Web 应用常通过 `fetch`、`XMLHttpRequest`、`axios` 等发送 Ajax 请求完成资料更新、订单操作等敏感行为。如果这些请求未携带 Anti-CSRF Token（例如来自 `<meta name="csrf-token">` 或 Cookie），服务端也未强制验证，浏览器会自动在跨站请求中附带认证 Cookie，使得攻击者可以在第三方站点发起伪造的 POST/PUT/DELETE 请求，诱导用户执行非预期操作。

### 代码示例

**易受攻击的代码：**
```javascript
// profile.js
function updateProfile(data) {
  return fetch("/api/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }); // 未添加 CSRF Token 头
}
```

```javascript
// axios 示例
axios.post("/orders/cancel", { orderId })
  .then(() => alert("Cancelled"))
  .catch(console.error); // 默认配置中未注入 X-CSRF-Token
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Ajax 请求：`fetch(`, `axios.post`, `$.ajax`, `XMLHttpRequest`
- 请求头：`headers`, `setRequestHeader`, `X-CSRF-Token`
- Token 来源：`document.querySelector('meta[name="csrf-token"]')`, `localStorage`

**定位步骤：**
1. 搜索发送敏感请求的 JS 模块，确认是否设置 Token 请求头或参数。
2. 查看全局 Ajax 拦截器（如 axios interceptor）是否注入 Token。
3. 跳读（L2）模板或布局文件，确认是否提供 `meta` Token。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **全局请求封装**（如 `apiClient`）在每次请求中注入 Token。
- **Token 同步逻辑**：从 Cookie/DOM 读取并随请求发送。
- **后端响应头**：`X-CSRF-Token` 更新机制。
- **错误处理**：Token 验证失败时提示用户刷新而非静默忽略。

**定位技巧：**
- 关注 SPA 与 SSR 混合应用，确保同一接口在多处调用都附带 Token。
- 检查跨域请求（CORS）处理，是否允许第三方域提交凭证。
- 分析离线缓存、Service Worker 是否绕过 Token 机制。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局拦截器统一附带 Token | **L0（快速跳过）** | 风险低 |
| 个别模块未注入 Token | **L2（跳读）** | 需补齐 |
| 所有 Ajax 请求均缺少 Token | **L3（逐行读）** | 高风险 |
| Ajax 请求跨域且允许凭证 | **L4（跨模块追踪）** | 风险更高，需分析 CORS 配置 |

## Classify

### 研判标准

#### 确认漏洞
判定为漏洞需同时满足：
1. Ajax 请求执行敏感操作（状态修改、资金操作等）。
2. 请求未附带 Anti-CSRF Token 或等效防护。
3. 服务端对 Token 未做验证，或验证可被绕过。

#### 误报
以下情况可视为误报：
1. 接口仅接受同源请求，并通过严格 Origin/Referer 校验。
2. 使用双重提交 Cookie 且实现正确。
3. 请求依赖独立的 Bearer Token/Basic Auth，不使用 Cookie。

#### 代码异味
需记录的风险点：
1. Token 注入逻辑只在 GET -> POST 切换时执行，易遗漏。
2. Token 通过 localStorage 保存，存在 XSS 泄露风险。
3. 失败后自动重试，可能导致多次执行恶意请求。
4. 部分请求使用硬编码 Token，未随会话刷新。

## Low risk

### 低风险评级场景

#### 1. 管理员操作需 MFA
- **场景：** Ajax 操作前要求二次验证。
- **风险评估：** 行为复杂，攻击成本高，但仍应补 Token。

#### 2. 限制凭证发送
- **场景：** `fetch` 默认设置为 `credentials: 'omit'`，不自动附带 Cookie。
- **风险评估：** 可降低风险，但需验证不会破坏功能。

#### 3. SameSite=Strict Cookie
- **场景：** 认证 Cookie 配置为 Strict，跨站不会自动附带。
- **风险评估：** 受浏览器限制，仍建议 Token。

#### 4. 审计日志
- **场景：** 所有状态修改接口记录详细日志。
- **风险评估：** 有助于发现滥用，但不阻止攻击。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 二次验证 / MFA | 提升攻击成本 | 中 |
| 禁止跨站携带 Cookie | 降低 CSRF 成功率 | 中 |
| SameSite=Strict | 浏览器级缓解 | 低 |
| 完整审计与告警 | 提高检测能力 | 高（仍需补 Token）|

