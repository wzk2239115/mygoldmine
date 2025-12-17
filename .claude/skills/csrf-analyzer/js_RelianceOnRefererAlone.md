# JavaScript 仅依赖 Referer 的 CSRF 防护漏洞

## Details

### 漏洞成因
部分前端应用会在提交敏感请求前检查 `document.referrer`，或服务端仅验证 `Referer`/`Origin` 头以判断请求来源。然而 Referer 可以被浏览器策略、人为清除或部分跨协议场景省略，也可能被中间人篡改。若没有 Anti-CSRF Token 等不可伪造的凭证，攻击者仍能构造请求绕过 Referer 检查并利用受害者会话执行敏感操作。

### 代码示例

**易受攻击的代码：**
```javascript
// protection.js
function isSameOrigin() {
  return document.referrer && document.referrer.startsWith(window.location.origin);
}

function submitTransfer(amount) {
  if (!isSameOrigin()) {
    alert("blocked");
    return;
  }
  fetch("/transfer", {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({ amount }),
  });
}
// 攻击者可通过 meta refresh / window.open 等方式诱导发起请求并绕过
```

**另一个不安全示例（服务端仅校验 Referer）：**
```javascript
// admin.js
axios.post("/admin/delete", { userId })
  .then(() => console.log("deleted"));

// 服务端伪代码
if (!req.headers.referer?.startsWith("https://admin.example.com")) {
  return res.status(403).end();
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 前端：`document.referrer`, `document.origin`, `sameOrigin`
- 后端：`req.get("Referer")`, `request.headers['origin']`
- CSRF Token 字段：`_csrf`, `X-CSRF-Token`（缺失时重点关注）

**定位步骤：**
1. 搜索 Referer/Origin 校验逻辑，确认是否同时存在 Token 验证。
2. 检查浏览器端 JS 是否仅基于 Referer 决策是否发起请求。
3. 跳读（L2）敏感接口的处理函数，看是否缺失其它防护。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **Anti-CSRF Token** 与 Referer 结合使用。
- **SameSite Cookie** 设置为 `Lax/Strict`，降低跨站风险。
- **额外验证步骤**：验证码、MFA、密码确认。

**定位技巧：**
- 确认 Token 是否与会话绑定且随机。
- 分析跨域场景（子域、HTTP↔HTTPS）下 Referer 可能为空。
- 关注 `strict-origin-when-cross-origin` 等浏览器策略变动带来的影响。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Token + Referer 双重防护 | **L0（快速跳过）** | 防护充分 |
| 同源 Token 缺失，依赖 Referer | **L2（跳读）** | 易被绕过 |
| 完全依赖 Referer/Origin | **L3（逐行读）** | 高风险 |
| 子域或跨协议场景复杂 | **L4（跨模块追踪）** | 需检查多环境部署 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 敏感操作的唯一防护是 Referer/Origin 检查。
2. 没有 Token、SameSite、双重提交等额外防护。
3. 请求使用 Cookie 或自动凭证完成认证。

#### 误报
以下情况可判定为误报：
1. Referer 校验与 Token、验证码等多重防护并用。
2. 接口仅通过带外凭证访问（Bearer Token）且无 Cookie。
3. 应用部署在受控内网并结合网络层限制。

#### 代码异味
仍需关注：
1. Referer 校验逻辑对子域、大小写、尾部斜杠处理不一致。
2. Token 存在但可选或在某些情况下被禁用。
3. 仅依赖 JS 层检查，服务端未验证。
4. Referer 校验失败被记录为警告但继续执行。

## Low risk

### 低风险评级场景

#### 1. 管理后台 + VPN
- **场景：** 后台仅可通过 VPN 访问，Referer 用于辅助日志。
- **风险评估：** 风险降低，但仍建议 Token。

#### 2. SameSite=Strict 配置
- **场景：** Cookie 设置 Strict，跨站请求不携带 Cookie。
- **风险评估：** 对部分场景有效，仍需 Token。

#### 3. 敏感操作需二次确认
- **场景：** 触发请求后需短信、硬件令牌确认。
- **风险评估：** 可降低风险，但不替代 Token。

#### 4. 全链路监控
- **场景：** 对 Referer 缺失/异常的请求进行告警与阻断。
- **风险评估：** 提升检测能力，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| VPN/内网限制 | 攻击面小 | 中 |
| SameSite=Strict | 浏览器级缓解 | 低 |
| 二次确认 | 提高成功难度 | 中 |
| 监控告警 | 及时发现异常 | 高（仍需 Token）|

