# Rust Serde 批量赋值漏洞

## Details

### 漏洞成因
Rust Web 框架（Actix Web、Rocket、Axum 等）常使用 Serde 将 JSON 请求反序列化为结构体。如果结构体未使用 `#[serde(skip_deserializing)]`, `#[serde(default)]`、`#[serde(deny_unknown_fields)]` 控制字段，攻击者可在 payload 中加入敏感字段（如 `role`, `is_admin`, `tenant_id`, `status`, `limit`），并通过直接保存结构体或与 ORM 结合更新数据库，实现批量赋值。默认情况下，Serde 会接受 payload 中存在的所有字段。

### 代码示例

**易受攻击的代码：**
```rust
#[derive(Deserialize)]
struct UpdateUser {
    email: String,
    display_name: Option<String>,
    is_admin: Option<bool>, // 未跳过反序列化
}

async fn update_user(Json(payload): Json<UpdateUser>, state: AppState) -> impl Responder {
    // payload.is_admin 可被设置
    state.repo.update_user(payload).await;
    HttpResponse::Ok()
}
```

**另一个不安全示例（缺少 deny_unknown_fields）：**
```rust
#[derive(Deserialize)]
struct OrderUpdate {
    product_id: i32;
    quantity: i32;
    #[serde(default)]
    status: Option<String>; // 未 skip，默认允许
}

// payload 可增加 tenant_id 字段，因未 deny_unknown_fields
async fn patch_order(Json(payload): Json<OrderUpdate>) {
    repository.update_order(payload).await;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `#[derive(Deserialize)]`, `#[serde(deserialize_with = ...)]`
- 控制器函数参数：`Json<T>`, `Form<T>`, `Query<T>`
- 结构体中敏感字段：`role`, `tenant_id`, `status`, `is_admin`, `limit`
- 缺少 `skip_deserializing` 或 `deny_unknown_fields`

**定位步骤：**
1. 搜索所有反序列化结构体，检查敏感字段。
2. 查看控制器/handler 是否直接使用结构体更新数据库。
3. 跳读（L2）确认是否存在字段白名单或重写逻辑。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段跳过：** `#[serde(skip_deserializing)]`
- **禁止未知字段：** `#[serde(deny_unknown_fields)]`
- **只读字段：** 在业务逻辑中重写或忽略敏感字段。
- **权限校验：** 在使用结构体前验证调用者。
- **DTO 分离：** 输入结构体不包含敏感字段。

**定位技巧：**
- 检查 `default` 属性是否导致敏感字段可选写入。
- 对嵌套结构体，确认内层也应用 `skip`/`deny_unknown_fields`.
- 确认反序列化器返回的结构体是否在持久化前进一步过滤。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 DTO 且 `skip_deserializing` 敏感字段 | **L0（快速跳过）** | 风险低 |
| 部分字段保护 + `deny_unknown_fields` | **L2（跳读）** | 检查覆盖范围 |
| 直接反序列化并保存 | **L3（逐行读）** | 高风险 |
| 多租户/批量更新场景 | **L4（跨模块追踪）** | 需分析全链路 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **Serde 反序列化结构体** 包含敏感字段或允许未知字段。
2. **结构体直接用于更新模型/数据库**。
3. **敏感字段实际可被覆盖**。

#### 误报
可视为误报的情况：
1. 使用 `skip_deserializing` 避开敏感字段。
2. `deny_unknown_fields` 结合 DTO 白名单，拒绝额外字段。
3. 在更新前业务逻辑重写敏感字段。

#### 代码异味
需关注的风险：
1. 依赖自定义验证器移除字段，但缺少编译器约束。
2. 使用 `Option<T>` 接受字段，默认 `None` 也可能覆盖为 `null`.
3. 同一结构体用于内部与外部调用，逻辑混杂。
4. 没有日志记录，难以追踪滥用。

## Low risk

### 低风险评级场景

#### 1. 内部 API
- **场景：** 接口仅供内部服务使用且有鉴权。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. DTO 白名单
- **场景：** 输入结构体仅包含可写字段。
- **风险评估：** 风险较低，需保持维护。

#### 3. 数据库约束
- **场景：** 数据库阻止敏感列修改。
- **风险评估：** 降低危害，但非根治。

#### 4. 审计日志
- **场景：** 对敏感字段更新记录日志并告警。
- **风险评估：** 有助于检测异常，仍需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部受控接口 | 攻击面有限 | 中 |
| DTO 白名单 + skip | 技术防护完善 | 低 |
| 数据库约束 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

