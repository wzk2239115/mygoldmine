# Python FastAPI/Pydantic 批量赋值漏洞

## Details

### 漏洞成因
FastAPI 默认使用 Pydantic `BaseModel` 将请求体映射为 Python 对象，并支持 `.dict()`/`.model_dump()` 转为字典。当模型未设置 `Config.extra = 'forbid'`、`Field(..., exclude=True)` 或 `readOnly=True` 时，攻击者可以在 JSON 中加入敏感字段（如 `is_admin`, `user_role`, `tenant_id`, `status`）并通过 `payload.dict()` 传入数据库更新，从而实现批量赋值。GraphQL/REST 接口共享同一模型时也可能受到影响。

### 代码示例

**易受攻击的代码：**
```python
from fastapi import FastAPI
from pydantic import BaseModel

class UserIn(BaseModel):
    email: str
    fullname: str
    is_admin: bool = False  # 未设为只读

app = FastAPI()

@app.put("/users/{user_id}")
def update_user(user_id: int, payload: UserIn):
    # payload.dict() 包含 is_admin
    db.users.update({"id": user_id}, payload.dict())
    return {"ok": True}
```

**另一个不安全示例（Config.extra = 'allow'）：**
```python
class OrderUpdate(BaseModel):
    product_id: int
    quantity: int

    class Config:
        extra = "allow"  # 允许额外字段

@app.patch("/orders/{order_id}")
def patch_order(order_id: int, payload: OrderUpdate):
    data = payload.dict()  # 可包含 status="SHIPPED"
    db.orders.update({"id": order_id}, data)
    return {"ok": True}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Pydantic 模型：`BaseModel`, `model_dump`, `.dict()`
- `extra = "allow"`、`Config.orm_mode = True`、`populate_by_name = True`
- 路由函数中直接 `payload.dict()`/`payload.model_dump()`
- 业务逻辑函数 `update`, `bulk_update`, `crud.update`

**定位步骤：**
1. 搜索 `.dict()`、`.model_dump()` 调用，检查是否传入 `exclude`。
2. 查看模型 `Config`，确认是否限制额外字段。
3. 跳读（L2）检查更新数据库时是否过滤敏感字段。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段白名单：** `payload.model_dump(include={"name", "email"})`
- **字段只读：** `Field(default=False, exclude=True)`、`computed_field`.
- **额外字段禁止：** `extra = "forbid"`、`model_config = {"extra": "forbid"}`。
- **权限校验：** 更新前验证 `current_user`.
- **DTO 分离：** 输入模型与数据库模型隔离。

**定位技巧：**
- 检查 `model_dump` 是否使用 `exclude_unset`；即使未设置字段，也可能默认值写入。
- 对 `orm_mode` 模式，确认敏感字段不会出现在输入模型。
- 留意 `alias`/`populate_by_name` 允许通过别名覆盖字段。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 模型 `extra = "forbid"` + `include` 白名单 | **L0（快速跳过）** | 风险低 |
| 设置只读字段但未涵盖全部敏感项 | **L2（跳读）** | 检查遗漏 |
| `payload.dict()` 直接传入更新 | **L3（逐行读）** | 高风险 |
| 多模型/GraphQL 共用同一 DTO | **L4（跨模块追踪）** | 需检查所有使用点 |

## Classify

### 研判标准

#### 确认漏洞
判定为漏洞需满足：
1. **Pydantic 模型** 允许用户提交敏感字段。
2. **更新逻辑直接使用 `.dict()`/`.model_dump()`**。
3. **导致敏感字段被覆盖**（权限/状态/租户等）。

#### 误报
以下情况可视为误报：
1. 使用 `include` 指定白名单字段。
2. 模型 `extra = "forbid"`，敏感字段无法提交。
3. 更新前手动剥离敏感字段。

#### 代码异味
需记录的风险：
1. 模型默认值允许覆盖（如 `is_admin: bool = False`），应设为只读。
2. `extra = "ignore"` 仅忽略额外字段但不报错，易被绕过。
3. GraphQL/REST 共用模型，易出现意外字段泄露。
4. 所有字段可被别名覆盖 (`populate_by_name=True`).

## Low risk

### 低风险评级场景

#### 1. 内部受控接口
- **场景：** 接口仅对内部服务开放，附带签名认证。
- **风险评估：** 攻击面小，但需防内部滥用。

#### 2. DTO 白名单映射
- **场景：** 使用 `include`/`exclude` 精准控制可写字段。
- **风险评估：** 风险较低，需保持一致。

#### 3. 数据库触发器
- **场景：** 敏感列由触发器/存储过程拒绝修改。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计与监控
- **场景：** 对关键字段修改记录审计并告警。
- **风险评估：** 有助于检测异常，但仍需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部 API + 强鉴权 | 攻击面有限 | 中 |
| 模型白名单/只读字段 | 技术防护完善 | 低 |
| 数据库约束 | 阻断敏感更新 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

