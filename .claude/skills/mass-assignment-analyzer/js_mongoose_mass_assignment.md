# JavaScript (Node.js) Mongoose 批量赋值漏洞

## Details

### 漏洞成因
使用 Mongoose 操作 MongoDB 时，常见模式是将 `req.body` 直接传递给 `Model.create`, `updateOne`, `findByIdAndUpdate`, `Model.set`. 如果 Schema 未开启 `strict` 或未对敏感字段设置 `select: false`, `immutable: true`, `private`，攻击者可以提交额外字段（如 `role`, `isAdmin`, `credits`, `status`, `tenant`) 以覆盖数据库中的值，从而实现越权或数据篡改。`$set`, `$setOnInsert` 等操作符也会写入所有提供的字段。

### 代码示例

**易受攻击的代码：**
```javascript
// user.model.js
const userSchema = new mongoose.Schema({
  email: String,
  password: String,
  role: String,      // 未限制
  isActive: Boolean,
});

// controller
router.patch("/users/:id", async (req, res) => {
  const user = await User.findByIdAndUpdate(req.params.id, req.body, { new: true });
  res.json(user); // req.body 可传 { role: "admin" }
});
```

**另一个不安全示例（updateMany）：**
```javascript
app.post("/orders/bulk-update", async (req, res) => {
  const updates = req.body; // [{ _id, status, tenant }]
  await Order.updateMany({ _id: { $in: updates.map(u => u._id) } }, updates);
  res.sendStatus(200);
});
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `Model.create`, `Model.updateOne`, `Model.updateMany`, `findByIdAndUpdate`, `findOneAndUpdate`
- `doc.set(req.body)`, `Object.assign(doc, req.body)`
- Schema 配置：`strict`, `select`, `immutable`, `private`, `toJSON`
- 中间件/钩子：`pre('save')`, `pre('findOneAndUpdate')`

**定位步骤：**
1. 搜索控制器中直接使用 `req.body` 的 Mongoose 调用。
2. 检查 Schema 是否包含敏感字段及其访问控制。
3. 跳读（L2）确认是否有字段白名单（`pick`、`lodash`）或 `omit`.

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **Schema 严格模式：** `strict: true`, `strictQuery: true`.
- **字段保护：** `select: false`, `immutable: true`, `default`.
- **白名单：** 控制器使用 `pick` 指定可更新字段。
- **中间件：** `pre('save')` 重写敏感字段（如从 session 获取）。
- **权限校验：** 校验当前用户是否可更新目标字段。

**定位技巧：**
- 检查是否使用 `lean()`，导致中间件失效。
- 确认 `runValidators: true` 是否启用，防止非法值写入。
- 对 `updateMany`/`bulkWrite` 关注批量逻辑是否缺乏校验。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| `pick` 白名单 + schema 保护 | **L0（快速跳过）** | 风险低 |
| Schema 部分字段 `immutable/select:false` | **L2（跳读）** | 检查全面程度 |
| 直接 `req.body` 传入更新 | **L3（逐行读）** | 高风险 |
| 批量/多租户更新 | **L4（跨模块追踪）** | 需检查租户隔离 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **Mongoose 更新操作** 直接使用可控输入。
2. **敏感字段未受 Schema 或代码限制**。
3. **可篡改权限/状态/租户等关键数据**。

#### 误报
可视为误报的情况：
1. 控制器对 `req.body` 做了白名单过滤。
2. Schema 将敏感字段设为 `select: false` 或 `immutable`.
3. 更新逻辑在保存前重写敏感字段。

#### 代码异味
需关注的风险：
1. 依赖 `delete req.body.role` 等黑名单方式。
2. 未启用 `runValidators`，导致非法值写入。
3. 使用 `updateMany` 处理用户输入且无逐条校验。
4. 允许 `$set` 以外的操作符写入（如 `$push` 嵌套数据）。

## Low risk

### 低风险评级场景

#### 1. 内部受控 API
- **场景：** 接口仅供内部服务访问，带签名认证。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. DTO 白名单映射
- **场景：** 使用 DTO/Service 层手动指定字段。
- **风险评估：** 风险较低，但需保持一致。

#### 3. 数据库权限限制
- **场景：** 使用 MongoDB 权限/Schema Validation 限制字段。
- **风险评估：** 降低危害，但不替代代码修复。

#### 4. 审计监控
- **场景：** 对关键字段更新记录审计并告警。
- **风险评估：** 有助于发现问题，但仍需修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 + 强鉴权 | 攻击面有限 | 中 |
| DTO/白名单 | 技术防护完善 | 低 |
| 数据库权限/Schema 校验 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

