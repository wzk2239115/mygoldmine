# JavaScript (Node.js) Sequelize/Prisma 批量赋值漏洞

## Details

### 漏洞成因
Sequelize、Prisma 等 ORM 支持直接将请求体对象传入 `Model.update`, `Model.create`, `upsert`, `Client.user.update`, `Client.order.updateMany` 等 API。如果未使用 `fields`, `attributes`, `select`, `omit` 控制可写字段，攻击者可以提交额外字段（如 `role`, `status`, `tenantId`, `creditLimit`, `isAdmin`）覆盖数据库值。Prisma 默认会写入所有提供的字段，除非显式排除。

### 代码示例

**易受攻击的代码（Sequelize）：**
```javascript
// PATCH /users/:id
router.patch("/users/:id", async (req, res) => {
  const [count, rows] = await User.update(req.body, {
    where: { id: req.params.id },
    returning: true,
  });
  res.json(rows[0]); // req.body 可包含 role: "admin"
});
```

**另一个不安全示例（Prisma）：**
```javascript
// PUT /accounts/:id
app.put("/accounts/:id", async (req, res) => {
  const account = await prisma.account.update({
    where: { id: Number(req.params.id) },
    data: req.body, // 包含 balance、tenantId 等
  });
  res.json(account);
});
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Sequelize：`Model.update`, `Model.create`, `Model.upsert`, `bulkCreate`
- Prisma：`prisma.user.update`, `updateMany`, `create`, `upsert`
- 字段控制参数：`fields`, `attributes`, `select`, `omit`
- Service/controller 层将 `req.body`/`input` 直接传入 ORM

**定位步骤：**
1. 搜索 ORM 更新/创建调用，检查数据来源。
2. 查看模型字段定义，识别敏感字段。
3. 跳读（L2）确认是否使用白名单筛选字段。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单：** `User.update(req.body, { fields: ["name", "email"] })`
- **黑名单（谨慎）：** 手动删除敏感字段。
- **DTO/Service 层映射：** 先构造允许字段对象。
- **权限校验：** 根据当前用户角色/租户限制更新内容。
- **数据库约束：** 触发器或 CHECK 限制。

**定位技巧：**
- 检查 `updateMany` 是否结合 `where` 过滤同一租户。
- 对 Prisma，确认是否启用中间件处理敏感字段。
- 查看 `include`/`select` 是否暴露了敏感字段给客户端。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| DTO 白名单 + `fields/select` 控制 | **L0（快速跳过）** | 风险低 |
| 黑名单过滤 + 权限校验 | **L2（跳读）** | 检查是否完善 |
| `req.body` 直接传入 ORM | **L3（逐行读）** | 高风险 |
| 批量/跨租户更新操作 | **L4（跨模块追踪）** | 需验证隔离性 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **ORM 更新/创建操作** 直接使用外部输入。
2. **缺乏字段控制**，允许敏感字段写入。
3. **造成权限/租户/金额等关键数据被篡改**。

#### 误报
可视为误报的情形：
1. `fields/select` 精确限定可写字段。
2. 控制层手动构建数据对象，仅包含安全字段。
3. 接口仅对受信系统开放并有额外验证（签名、mTLS）。

#### 代码异味
需关注的风险：
1. 依赖黑名单删除敏感字段，易遗漏。
2. 使用 `updateMany` 接受客户端列表更新。
3. Prisma 中允许 `include` 返回敏感数据，易与更新混用。
4. 缺少事务/钩子导致绕过业务校验。

## Low risk

### 低风险评级场景

#### 1. 内部服务接口
- **场景：** 服务间调用，带鉴权与签名。
- **风险评估：** 攻击面小，但需防内部滥用。

#### 2. DTO 白名单策略
- **场景：** 仅允许 DTO 中定义的字段写入。
- **风险评估：** 风险较低，需确保覆盖完整。

#### 3. 数据库约束/触发器
- **场景：** 敏感列有数据库级限制。
- **风险评估：** 降低危害，但不替代代码修复。

#### 4. 审计告警
- **场景：** 对关键字段变更记录日志并告警。
- **风险评估：** 有助于检测异常，仍需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 + 强鉴权 | 攻击面有限 | 中 |
| DTO 白名单 + `fields/select` | 技术防护完善 | 低 |
| 数据库约束 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

