# Rust Diesel 记录访问 IDOR

## 漏洞成因
通过请求参数中的ID直接使用Diesel进行数据库查询，缺乏角色或所有权验证，导致用户可访问未授权的数据记录。

## Details

### 代码示例

```rust
// 易受攻击的代码
#[get("/user/<user_id>")]
async fn get_user(user_id: i32, conn: DbConn) -> Result<Json<User>, Status> {
    conn.run(move |c| {
        users::table
            .filter(users::id.eq(user_id))
            .first::<User>(c)
    }).await
    .map(Json)
    .map_err(|_| Status::NotFound)
}

// 直接从路径/查询参数获取ID进行查询
#[post("/order/<order_id>")]
async fn view_order(order_id: i32, db: DbConn) -> Json<Order> {
    db.run(move |conn| {
        orders::table.find(order_id).first(conn).unwrap()
    }).await
}
```

### 快速定位核心操作（L1-L2）

**关键词扫描（L1）：**
- `table.filter()`、`find()`、`first()`、`get_result()`
- 路由参数：`<user_id>`、`<id>`、`<record_id>`
- 查询方法链：`users::table.filter(users::id.eq(...))`

**跳读定位（L2）：**
1. 定位路由函数入口（`#[get]`、`#[post]`等宏）
2. 追踪参数来源：是否直接来自路径/查询参数
3. 查看查询语句：`filter()`、`find()` 等条件是否仅基于用户输入的ID
4. 快速扫描函数体内是否有 `WHERE` 或 `filter()` 添加额外约束

### 快速定位保护机制（L2-L4）

**跳读检查（L2）：**
- 函数签名中是否有认证参数：`AuthUser`、`Claims`、`Session`
- 查询条件是否包含当前用户过滤：`.filter(user_id.eq(current_user))`
- 是否调用权限检查函数：`can_access()`、`check_permission()`

**逐行审计（L3）：**
- 检查查询后是否有所有权验证：比较 `record.owner_id` 与 `current_user.id`
- 检查是否有角色判断：`if user.role == Role::Admin`
- 确认 JOIN 子句是否添加了访问控制条件

**跨模块追踪（L4）：**
- 追踪中间件/守卫实现：查看 `FromRequest` trait 是否包含权限逻辑
- 检查 Diesel schema 定义中是否有 RLS（行级安全）相关逻辑
- 追踪自定义提取器（extractor）的实现代码
- 查看是否存在全局查询拦截器或作用域（scoped queries）

## Classify

**判定为漏洞：**
- 用户可控ID参数直接用于查询，无任何所有权或角色验证
- 查询结果直接返回，未校验当前用户与记录的关联关系
- 认证存在但授权缺失（已登录但未验证访问权限）

**判定为误报：**
- 查询条件中已包含当前用户约束（如 `.filter(owner_id.eq(session.user_id))`）
- 查询后立即进行所有权校验并返回403
- 中间件/守卫层已实现完整的访问控制逻辑
- 该接口为公开数据接口（需确认业务逻辑）

**判定为代码异味：**
- 权限检查逻辑存在但不完整（仅检查部分角色）
- 使用字符串比较等弱验证方式
- 权限逻辑分散在多处，难以维护
- 依赖前端传递的权限标识而非服务端查询

## Low risk

以下情况可评为低风险：

- **公开只读资源**：接口返回的是公开信息（如公开文章、产品列表），无敏感数据泄露风险
- **受限的ID空间**：ID范围极小且全部为当前用户可见资源（如用户仅能访问自己的3条记录）
- **脱敏数据**：返回数据已充分脱敏，即使越权访问也无实质危害
- **辅助表查询**：查询的是配置表、字典表等无隐私关联的辅助数据
- **读操作且数据价值低**：仅限查看且数据不涉及PII、财务、业务机密
- **需要额外条件触发**：需要同时满足其他复杂条件才能成功越权（如需要token+时间戳+签名校验）

**注意**：低风险不等于无风险，仍需在报告中标注并建议修复。