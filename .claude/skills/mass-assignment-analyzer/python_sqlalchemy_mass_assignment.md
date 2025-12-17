# Python SQLAlchemy 批量赋值漏洞

## Details

### 漏洞成因
SQLAlchemy 提供 `update`, `bulk_update_mappings`, `session.merge`, `session.execute` 等 API，可将字典或 ORM 对象直接映射到数据库列。若应用层直接将 `request.json`/`payload` 传入这些 API，且未过滤敏感字段（如 `role`, `is_admin`, `balance`, `tenant_id`, `status`），攻击者可覆盖敏感列，实现越权修改。批量操作和 `merge` 尤其危险，因为它们会写入所有提供的列。

### 代码示例

**易受攻击的代码：**
```python
@bp.route("/users/<int:user_id>", methods=["PATCH"])
def patch_user(user_id):
    data = request.get_json()  # 可包含 is_admin=True
    db.session.query(User).filter_by(id=user_id).update(data)
    db.session.commit()
    return jsonify({"ok": True})
```

**另一个不安全示例（bulk_update_mappings）：**
```python
def bulk_update_orders(order_updates):
    # order_updates 来自外部输入
    db.session.bulk_update_mappings(Order, order_updates)
    db.session.commit()

# 调用示例
bulk_update_orders([
    {"id": 1001, "status": "PAID", "tenant_id": 2},  # 可跨租户
])
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `session.query(...).update`, `session.merge`, `bulk_update_mappings`
- `Model(**payload)`, `dict_to_model`, `setattr(obj, key, value)`
- `request.get_json()`, `payload`, `data = request.json`
- 蓝图/服务层的批量更新函数

**定位步骤：**
1. 搜索更新 API，检查传入数据来源。
2. 关注 payload 是否直接来自请求或外部服务。
3. 跳读（L2）确认是否进行字段过滤或权限校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单字段：** `allowed = {"email", "phone"}` 并 `data = {k: v for k, v in data.items() if k in allowed}`
- **模型属性控制：** 使用 SQLAlchemy `synonym` 或 `hybrid_property` 将敏感字段设为只读。
- **权限/租户校验：** 更新前确认 `current_user`.
- **数据库触发器/检查约束：** 防止修改敏感列。
- **Schema/DTO 分离：** 使用 Marshmallow/Pydantic 验证并过滤。

**定位技巧：**
- 检查 `session.merge` 是否被用于处理 PATCH/PUT 请求。
- 确认 `bulk_update_mappings` 是否限制字段集合。
- 对 `setattr` 循环，确认是否跳过敏感字段。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 明确白名单过滤 + 权限校验 | **L0（快速跳过）** | 风险低 |
| Schema 验证后再组装更新 | **L2（跳读）** | 检查 Schema 是否完整 |
| `update/merge` 直接使用请求数据 | **L3（逐行读）** | 高风险 |
| 批量更新/跨租户场景 | **L4（跨模块追踪）** | 需分析全链路 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **SQLAlchemy 更新 API** 使用未经筛选的输入。
2. **敏感字段可被覆盖**。
3. **产生越权或关键数据被篡改**。

#### 误报
可视为误报的情况：
1. 输入数据经过严格 Schema 校验并剥离敏感字段。
2. 更新操作仅允许修改当前用户可见字段。
3. 数据库层阻止敏感列被更新。

#### 代码异味
需记录的风险：
1. **黑名单方式过滤字段**，易遗漏新增字段。
2. **`merge` 应用于外部输入**，默认写入全部列。
3. **批量操作缺少逐条权限校验**。
4. **未开启 SQLAlchemy 事件钩子** 检查变更。

## Low risk

### 低风险评级场景

#### 1. 内部后台工具
- **场景：** 接口仅由受信任管理员使用。
- **风险评估：** 攻击面小，但需防账号泄露。

#### 2. 白名单 DTO
- **场景：** 使用 DTO 手动选择字段更新。
- **风险评估：** 风险较低，仍需保持维护。

#### 3. 数据库触发器/权限
- **场景：** 敏感列由触发器/行级安全策略保护。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计日志
- **场景：** 对关键字段更新记录审计并监控。
- **风险评估：** 有助于发现问题，仍需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用接口 | 攻击面有限 | 中 |
| DTO 白名单过滤 | 技术防护完善 | 低 |
| 数据库触发器/权限 | 阻断敏感修改 | 中 |
| 审计监控 | 及时发现异常 | 高（持续改进）|

