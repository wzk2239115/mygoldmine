# TypeScript CSRF Token 未绑定会话漏洞

## Details

### 漏洞成因
在自定义实现 CSRF 防护时，一些 TypeScript 后端（NestJS、Express、Next.js API）仅生成随机 Token 并返回给客户端，但验证时未将 Token 与用户会话（Session ID、User ID）绑定，而是存储在内存变量、Redis 公共键或仅检验是否存在。攻击者若能获取其它用户的 Token（通过日志、URL、预测等）即可跨会话复用，从而伪造请求。

### 代码示例

**易受攻击的代码：**
```typescript
const csrfTokens = new Set<string>();

app.get("/form", (req, res) => {
  const token = randomBytes(16).toString("hex");
  csrfTokens.add(token);
  res.render("form", { token });
});

app.post("/form", (req, res) => {
  const token = req.body._csrf;
  if (!csrfTokens.has(token)) {
    return res.status(403).send("invalid token");
  }
  // 未校验 token 与当前用户/会话关系，任何用户可复用
  csrfTokens.delete(token);
  res.send("ok");
});
```

**另一个不安全示例（Token 存储在 Redis 公共键）：**
```typescript
await redis.set(`csrf:${token}`, "1", "EX", 600); // 未使用 sessionId 拼接

// 校验时仅检查 token 是否存在
const exists = await redis.exists(`csrf:${req.body._csrf}`);
if (!exists) return res.status(403).send("invalid");
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Token 存储：`Map`, `Set`, `redis.set`, `redis.hset`, `memoryCache`
- 验证逻辑：`if (!tokens.has(token))`, `redis.exists`, `token === req.session.csrfToken`
- 会话信息：`req.session`, `req.user`, `req.cookies.sid`

**定位步骤：**
1. 搜索 Token 生成与存储的代码，确认键是否包含会话标识。
2. 检查验证逻辑是否将 Token 与当前用户或会话关联。
3. 跳读（L2）确认 Token 是否可重复使用、多次提交。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **会话绑定**：Token 存储在 `req.session.csrfToken` 或 `redis.set(sessionId, token)`。
- **一次性 Token**：每次成功使用后失效。
- **双重提交 Cookie**：Token 与 Cookie 同步并验证二者一致。
- **Token 更新**：登录、角色切换时刷新 Token。

**定位技巧：**
- 确认是否存在匿名用户场景（未登录也可获取 Token）。
- 检查 Token 是否通过 URL 传递，存在被记录/分享风险。
- 分析集群环境中 Token 存储是否同步，避免使用全局静态变量。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Token 与 session/user 强绑定 | **L0（快速跳过）** | 风险低 |
| Token 存储但未绑定会话 | **L3（逐行读）** | 高风险 |
| Token 可多次使用或与匿名用户共享 | **L4（跨模块追踪）** | 极易被滥用 |
| 绑定逻辑存在漏洞（大小写、时序） | **L2（跳读）** | 需补齐校验 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. Token 验证未与当前会话/用户绑定。
2. 攻击者可获取或猜测他人 Token 并复用。
3. 服务端依赖 Cookie 认证，缺乏额外防护。

#### 误报
以下情况可视为误报：
1. Token 与会话绑定，并在验证时严格比较。
2. 请求依赖一次性登录码/验证码，不受 CSRF 影响。
3. 接口仅供第三方 API 调用，不依赖浏览器 Cookie。

#### 代码异味
需记录：
1. Token 存储在全局 Map，服务重启即失效导致绕过。
2. 多个 Token 可以同时有效，未设置过期策略。
3. Redis 键缺少租户或环境前缀，可能与其它应用冲突。
4. 验证时先判断空值但未处理相等情况（大小写、trim）。

## Low risk

### 低风险评级场景

#### 1. 管理后台 + MFA
- **场景：** 即便 Token 可复用，也需二次验证。
- **风险评估：** 攻击难度高，但不应依赖此做法。

#### 2. 短期 Token + 监控
- **场景：** Token 有极短有效期，并实时监控重复使用。
- **风险评估：** 可降低窗口期，但建议绑定会话。

#### 3. SameSite=Strict Cookie
- **场景：** Cookie 设置 Strict，跨站请求不携带 Cookie。
- **风险评估：** 较为安全，但存在兼容性问题。

#### 4. 日志审计
- **场景：** 记录 Token 生成与验证日志，及时发现异常。
- **风险评估：** 有助于追踪，但非根治。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| MFA / 二次验证 | 提高攻击成本 | 中 |
| 短期 Token + 监控 | 缩小窗口期 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 审计日志 | 追踪滥用 | 高（仍需会话绑定）|

