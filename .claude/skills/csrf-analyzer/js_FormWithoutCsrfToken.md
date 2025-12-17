# JavaScript 表单缺少 CSRF Token 漏洞

## Details

### 漏洞成因
在采用传统表单提交的 Web 应用中（如基于 jQuery、Vanilla JS 的前端），如果敏感操作（密码修改、账户删除、资金转账等）的表单页面未生成并携带不可预测的 Anti-CSRF Token，浏览器又会在跨站请求中自动附带用户的认证 Cookie，攻击者即可构造恶意页面诱导受害者浏览，从而在受害者不知情的情况下提交相同表单完成敏感操作。

### 代码示例

**易受攻击的代码：**
```html
<!-- account.html -->
<form id="update-profile" action="/account/update" method="POST">
  <input type="text" name="email" value="user@example.com">
  <button type="submit">Save</button>
</form>
<!-- 未包含任何隐藏的 CSRF Token 字段 -->
```

```javascript
// account.js
document.getElementById("update-profile").addEventListener("submit", (ev) => {
  ev.target.submit(); // 简单提交，不附带任何 Token
});
```

**另一个不安全示例（多步骤流程忽略 Token）：**
```html
<!-- reset_password.html -->
<form action="/users/reset_password" method="POST">
  <input type="password" name="newPassword">
  <input type="password" name="confirmPassword">
  <button type="submit">Reset</button>
</form>
<!-- 首次请求得到页面后，服务端并未注入 Token，后续步骤仍缺乏 Token 校验 -->
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- HTML 模板：`<form`, `method="post"`, `action="/..."`
- JavaScript 表单提交：`form.submit()`, `axios.post`, `fetch` 发送 `application/x-www-form-urlencoded`
- Token 字段：`name="_csrf"`, `meta[name="csrf-token"]`, `X-CSRF-Token`

**定位步骤：**
1. 搜索所有处理敏感操作的表单模板，确认是否存在隐藏 Token 字段。
2. 检查页面是否在 `<head>` 中注入 `meta` Token，并在提交时写入请求头。
3. 跳读（L2）相关 JS 文件，确认表单提交时是否读取并传递 Token。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **后端生成 Token 并写入模板**（例如 `input type="hidden" name="_csrf"`）。
- **前端读取 meta/header 并设置请求头**（如 `X-CSRF-Token`）。
- **表单序列化库**是否自动包含 Token。
- **Token 验证失败时的异常处理**（显示错误提示而非静默放行）。

**定位技巧：**
- 验证是否存在多个表单共用一个 Token，且 Token 是否随会话或请求轮换。
- 检查 SPA 与传统页面混用场景，确保所有入口均带 Token。
- 分析模板继承/布局文件，确认 Token 注入逻辑是否在所有分支生效。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 模板统一注入 Token + 服务端校验严格 | **L0（快速跳过）** | 可快速确认无风险 |
| 大部分表单有 Token，个别页面缺失 | **L2（跳读）** | 易遗漏，需补齐 |
| 敏感表单完全缺少 Token | **L3（逐行读）** | 高风险，需追踪会话绑定 |
| 表单缺 Token 且配合额外脚本执行 | **L4（跨模块追踪）** | 需检查跨页面调用链 |

## Classify

### 研判标准

#### 确认漏洞
满足以下条件可判定为 CSRF 漏洞：
1. 提交敏感操作的表单未包含不可预测的 Anti-CSRF Token。
2. 服务端对该接口未实施其它等价防护（如双重提交 Cookie、Origin 校验）。
3. 请求依赖 Cookie 等自动凭证完成身份识别。

#### 误报
可视为误报的情况：
1. 表单仅用于非敏感只读操作或依赖一次性验证码。
2. 接口仅接受同源请求且通过严格 Origin/Referer 校验。
3. 应用采用双重提交 Cookie 或 SameSite=Strict，并确认场景允许。

#### 代码异味
仍需记录的隐患：
1. Token 存在但跨多个页面共享且长期不刷新。
2. Token 仅在前端生成，未与会话或服务端存储绑定。
3. 依赖框架默认 Token，但在局部模板被手动移除。
4. Token 验证失败被前端忽略或静默重试。

## Low risk

### 低风险评级场景

#### 1. 管理后台限定
- **场景：** 表单仅管理员使用，配合 MFA 与 IP 白名单。
- **风险评估：** 攻击面小，但仍建议补齐 Token。

#### 2. 二次确认机制
- **场景：** 提交敏感操作后需短信/验证码确认。
- **风险评估：** 可降低风险，但不应替代 Token。

#### 3. SameSite=Strict Cookie
- **场景：** 应用确认所有敏感操作均依赖严格 SameSite Cookie。
- **风险评估：** 浏览器兼容性有限，仍需监控。

#### 4. 人工审计日志
- **场景：** 所有敏感操作记录审计并可追溯。
- **风险评估：** 有助于发现滥用，但无法阻止攻击。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 仅管理员/内部使用 | 攻击面有限 | 中 |
| 二次确认或验证码 | 增强防护 | 中 |
| SameSite=Strict Cookie | 部分浏览器有效 | 低 |
| 完整审计与告警 | 提升检测能力 | 高（仍需补齐 Token）|

