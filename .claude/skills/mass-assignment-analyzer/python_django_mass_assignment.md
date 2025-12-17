# Python 批量赋值漏洞

## Details

### 漏洞成因
Python Web 框架（Django、Flask + Marshmallow/Pydantic、FastAPI、Sanic 等）通常通过序列化器、`ModelForm` 或 `BaseModel` 将请求体自动转换为模型对象。若未显式指定 `fields`、`exclude`、`read_only_fields`、`extra = 'forbid'`，攻击者可提交额外字段覆盖敏感属性，如 `is_staff`, `is_superuser`, `tenant_id`, `credit_limit`, `status`。此外，直接使用 `Model.objects.update(**request.data)`、`session.bulk_update_mappings` 等批量更新 API，也会引入越权风险。

### 代码示例

**易受攻击的代码：**
```python
# Django REST Framework Serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"  # 包含 is_staff, is_superuser

    def update(self, instance, validated_data):
        # validated_data 可含 is_superuser=true
        return super().update(instance, validated_data)
```

```python
@api_view(["POST"])
def update_profile(request, user_id):
    data = request.data  # 直接使用未经筛选的 payload
    User.objects.filter(id=user_id).update(**data)  # 可覆盖 balance/status
    return Response({"ok": True})
```

**另一个不安全示例（FastAPI + Pydantic）：**
```python
class Order(BaseModel):
    product_id: int
    quantity: int
    price: float
    status: str = "pending"
    owner_id: int

@app.put("/orders/{order_id}")
def update_order(order_id: int, payload: Order):
    # payload 可包含 status="PAID", owner_id=其他用户
    db.update_order(order_id, payload.dict())
    return {"ok": True}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Django：`ModelSerializer`, `ModelForm`, `fields = "__all__"`, `update(**request.data)`
- Flask/FastAPI：`BaseModel`, `schema.load`, `model(**data)`, `Session.bulk_update_mappings`
- ORM：`update`, `bulk_update`, `dict_to_model`, `setattr(obj, key, value)`
- 序列化配置：`extra = 'ignore'/'allow'`, `allow_population_by_field_name`

**定位步骤：**
1. 搜索所有 Serializer/Form/Schema 定义，检查 `fields`/`exclude` 设置。
2. 查找视图函数中直接使用 `request.data`, `request.json`, `payload.dict()` 更新数据库的逻辑。
3. 跳读（L2）确认是否剥离敏感字段或进行权限校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段白名单：** `fields = ('name', 'email')`, `extra = 'forbid'`
- **只读/写保护：** `read_only_fields`, `allow_mutation = False`
- **权限控制：** 更新前校验 `request.user` 是否具备操作权限
- **二次验证：** 在 `perform_update`/`save` 重写时剥离不允许字段
- **数据层约束：** 数据库触发器/约束阻止越权修改

**定位技巧：**
- 确认 `extra_kwargs` 是否设置 `read_only=True` 对敏感字段生效。
- 检查 `serializer.save()` 前是否手动移除字段（`validated_data.pop`）。
- 对 FastAPI，关注 `Config.extra` 与 `dict(exclude=...)` 是否使用。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用字段白名单 + 只读字段 | **L0（快速跳过）** | 自动绑定受控 |
| 自动绑定但覆盖敏感字段为只读 | **L2（跳读）** | 确认配置完整 |
| 直接 `update(**request.data)` / ModelSerializer `__all__` | **L3（逐行读）** | 高风险 |
| 多租户/跨用户批量更新 | **L4（跨模块追踪）** | 需验证租户隔离 |

## Classify

### 研判标准

#### 确认漏洞
判定为漏洞需满足：
1. **自动绑定或批量更新** 接受未经筛选的输入。
2. **敏感字段可被用户控制**。
3. **产生实质影响**（权限提升、账户篡改、跨租户访问等）。

#### 误报
可视为误报的情况：
1. **Serializer/Form 显式限制字段** 并忽略其他字段。
2. **视图层手动剥离敏感字段** 或重写 `update` 逻辑。
3. **接口仅用于可信内部系统** 且有签名/密钥校验。

#### 代码异味
需要关注的模式：
1. **`fields = "__all__"`** 但依赖文档约束不发送敏感字段。
2. **黑名单过滤**，容易遗漏新增字段。
3. **`allow_population_by_field_name = True`** 未限制前端使用别名覆盖。
4. **使用 `setattr` 遍历 payload**，未过滤属性。

## Low risk

### 低风险评级场景

#### 1. 内部受控 API
- **场景：** API 仅供内部服务调用，使用 mTLS 或签名。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. DTO 与模型分离
- **场景：** 输入 DTO 只含允许字段，保存时手动映射。
- **风险评估：** 低风险，仍需检查未来改动。

#### 3. 数据库行级权限
- **场景：** 使用 Row-Level Security 限制租户访问。
- **风险评估：** 可降低影响，但仍需避免字段覆盖。

#### 4. 审计告警
- **场景：** 对敏感字段更新触发日志/告警。
- **风险评估：** 有助于及时发现问题，不替代修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部 API + 强鉴权 | 攻击面小 | 中 |
| DTO 白名单 + 只读字段 | 技术防护完善 | 低 |
| 数据层行级权限 | 限制影响范围 | 中 |
| 审计监控 | 及时发现 | 高（继续改进）|

