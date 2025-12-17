# JavaScript｜路由处理器缺失函数级权限

## Details

### 漏洞成因
Node.js/Express/Koa 等服务通常通过中间件验证 JWT 或 session。如果路由处理器（handler）未进一步验证用户是否具备执行该操作的权限，普通用户即可访问管理员接口。常见于 BFF/SSR 服务、REST API、GraphQL resolver 仅在入口验证 token，而不校验所请求操作。

### 代码示例

**易受攻击示例：**
```js
router.post('/admin/users/:id/reset', authMiddleware, async (req, res) => {
  await userService.resetPassword(req.params.id); // 未检查 req.user.role
  res.sendStatus(204);
});
```

**安全示例：**
```js
router.post('/admin/users/:id/reset', authMiddleware, async (req, res) => {
  if (!req.user || !req.user.permissions.includes('user:reset')) {
    return res.status(403).json({ message: 'forbidden' });
  }
  await userService.resetPassword(req.params.id, req.user);
  res.sendStatus(204);
});
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `router.`, `app.post`, `ctx.body`, `req.user`, `permissions`, `role`。

**定位步骤：**
1. 搜索带 `/admin`, `/manage`, `/settings` 的路由；
2. 跳读（L2）确认 handler 是否访问 `req.user` 权限数据；
3. 检查是否使用 `authorize`, `requireRole` 中间件。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 权限中间件（`authorize('user:reset')`）；
- 服务层执行权限校验；
- API Gateway/Reverse proxy 做 RBAC；
- GraphQL resolver 包含角色判断。

**定位技巧：**
- 逐行读（L3）敏感 handler，确认是否误信任 `req.body.isAdmin`；
- 跨模块追踪（L4）SSR/BFF 是否复用同 handler。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| handler 使用权限中间件 | **L0（快速跳过）** | 安全性好 |
| 部分路由缺少中间件 | **L2（跳读）** | 快速核实 |
| 完全无权限验证 | **L3（逐行读）** | 高风险 |
| 同一 handler 被多入口调用 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. handler 无权限校验；
2. 低权限用户可执行敏感操作；
3. 影响关键数据或系统功能。

#### 误报
1. handler 仅返回公开信息；
2. 上游中间件强制执行权限并不可绕过；
3. handler 仅内部服务调用。

#### 代码异味
1. 依赖客户端传入角色；
2. 将权限分支写在前端；
3. 未记录操作日志。

## Low risk

### 低风险评级场景

#### 1. 操作只影响非敏感数据
- **评估：** 可标低风险。

#### 2. 内部工具接口
- **评估：** 攻击面小。

#### 3. 将迁移到 RBAC 中间件
- **评估：** 暂降级，跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非敏感 | 影响有限 | 低 |
| 内部 | 攻击面低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |
