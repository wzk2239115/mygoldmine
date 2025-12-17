# Rust ORM 批量赋值漏洞

## Details

### 漏洞成因
Rust ORM 框架（Diesel、SeaORM、SQLx 等）提供将结构体或 `ActiveModel` 写入数据库的能力。如果这些结构体直接来源于用户输入，且未过滤敏感字段（如 `role`, `tenant_id`, `status`, `limit`, `is_admin`），攻击者可覆盖关键数据。Diesel 的 `insert_into`/`update`、SeaORM 的 `ActiveModel::update`, `ActiveModel::insert`, SQLx 的 `query!` 填充结构体时均需谨慎处理。

### 代码示例

**易受攻击的代码（Diesel）：**
```rust
#[derive(Deserialize, AsChangeset)]
#[table_name = "users"]
struct UpdateUser {
    email: Option<String>,
    role: Option<String>, // 未过滤
}

pub fn update_user(conn: &PgConnection, id: i32, payload: UpdateUser) -> QueryResult<usize> {
    diesel::update(users::table.find(id))
        .set(&payload) // payload.role 可被设置为 "admin"
        .execute(conn)
}
```

**另一个不安全示例（SeaORM）：**
```rust
#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Deserialize)]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: i32,
    pub tenant_id: i32,
    pub status: String,
    pub balance: Decimal,
}

pub async fn update_order(db: &DatabaseConnection, payload: Model) -> Result<Model, DbErr> {
    // payload 来自请求体
    payload.update(db).await // 可覆盖 tenant_id、status
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Diesel：`AsChangeset`, `Insertable`, `diesel::update`, `set`, `save_changes`
- SeaORM：`ActiveModel`, `.update`, `.save`, `.insert`
- SQLx：`query_as!`, `FromRow`, `serde_json::from_str`
- 结构体 `derive(Deserialize, AsChangeset)` 等组合

**定位步骤：**
1. 搜索 `AsChangeset`, `ActiveModel`, `update` 等宏/方法。
2. 检查结构体字段是否包含敏感属性。
3. 跳读（L2）确认是否在使用前过滤字段或重写。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段选择：** `set((users::email.eq(payload.email), ...))` 手动列出字段。
- **DTO 分离：** 输入结构体与数据库模型分离。
- **权限校验：** 在更新前验证调用者权限与租户。
- **数据库约束：** 使用触发器/检查约束限制敏感列。
- **默认重写：** 在更新前强制设置 `tenant_id`、`role` 等值。

**定位技巧：**
- 检查 `AsChangeset` 搭配 `Option<T>` 的字段，确认是否允许设置 `NULL`。
- 对 SeaORM，确认 `ActiveModel::from` 是否创建于用户输入。
- 关注批量操作 (`insert_many`, `update_many`)，确认逐条校验。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 手动列出可写字段 + 权限校验 | **L0（快速跳过）** | 风险低 |
| DTO 分离 + 重写敏感字段 | **L2（跳读）** | 验证是否全面 |
| `AsChangeset`/`ActiveModel` 直接来自请求 | **L3（逐行读）** | 高风险 |
| 多租户/批量更新 | **L4（跨模块追踪）** | 需检查租户隔离 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **ORM 更新/插入** 直接使用用户输入的结构体或模型。
2. **敏感字段未过滤**。
3. **导致权限、租户、财务等数据被篡改**。

#### 误报
可视为误报的情况：
1. 手动列出更新字段并排除敏感属性。
2. 结构体在更新前被业务逻辑重写关键字段。
3. 数据库层确保敏感列只可由受控路径修改。

#### 代码异味
需关注的风险：
1. `derive(Deserialize, AsChangeset)` 组合未排除敏感字段。
2. `ActiveModel` 通过 `Set(payload.field)` 直接赋值。
3. 依赖黑名单 `payload.role = None` 的方式过滤。
4. 缺少审计日志监控变更。

## Low risk

### 低风险评级场景

#### 1. 内部 API
- **场景：** 仅内部服务调用，带鉴权。
- **风险评估：** 攻击面有限，但需防滥用。

#### 2. DTO 白名单
- **场景：** 输入 DTO 仅包含允许字段。
- **风险评估：** 风险较低，需保持维护。

#### 3. 数据库约束
- **场景：** 使用触发器或规则阻止敏感列更新。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计日志
- **场景：** 对关键字段更新记录日志并告警。
- **风险评估：** 有助于发现问题，仍需修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 + 强鉴权 | 攻击面有限 | 中 |
| DTO 白名单 + 手动字段 | 技术防护完善 | 低 |
| 数据库约束 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

