# Java Hibernate 批量赋值漏洞

## Details

### 漏洞成因
JPA/Hibernate 提供了 `save`, `merge`, `update`, `flush` 等 API，可将实体对象持久化到数据库。当应用层直接将用户提交的实体对象（或 JSON DTO）传入这些 API，而未过滤敏感字段（如 `role`, `creditLimit`, `tenantId`, `status`, `ownerId`），攻击者可覆盖这些字段，造成越权或数据篡改。尤其在开放 `PATCH`/`PUT` 接口时，若使用 `EntityManager.merge` 或 `BeanUtils.copyProperties` 后提交，风险更大。

### 代码示例

**易受攻击的代码：**
```java
@Transactional
public Account updateAccount(Account incoming) {
    Account account = entityManager.find(Account.class, incoming.getId());
    // 未过滤敏感字段
    entityManager.merge(incoming); // incoming 可包含 role = "ADMIN"
    return account;
}
```

**另一个不安全示例（Spring Data JPA）：**
```java
@PutMapping("/orders/{id}")
public Order updateOrder(@PathVariable Long id, @RequestBody Order payload) {
    Order existing = orderRepository.findById(id).orElseThrow();
    BeanUtils.copyProperties(payload, existing); // 未排除 status/tenantId
    return orderRepository.save(existing);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `entityManager.merge`, `entityManager.persist`, `save`, `saveAll`
- `BeanUtils.copyProperties`, `ModelMapper.map`, `DozerBeanMapper`
- Repository 接口 `save`, `saveAndFlush`, `saveAll`
- DTO/实体包含敏感字段，如 `role`, `enabled`, `tenantId`

**定位步骤：**
1. 搜索使用 `merge`/`save` 的业务方法。
2. 检查 DTO/实体字段定义，识别敏感字段。
3. 跳读（L2）确认是否进行了属性过滤或权限校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单映射：** 使用 DTO + 手动赋值允许字段。
- **属性排除：** `BeanUtils.copyProperties(src, dest, "role", "status")`
- **JPA 注解：** `@JsonIgnore`, `@Column(updatable = false)`, `@PreUpdate` 钩子。
- **权限/租户校验：** 在更新前验证当前用户是否允许修改目标实体。
- **乐观锁控制：** 确保更新者拥有最新版本并触发二次检查。

**定位技巧：**
- 检查实体字段是否使用 `@Column(updatable = false)` 或 `insertable=false`.
- 确认服务层是否使用 DTO 分离输入/输出。
- 关注 `@DynamicUpdate`, `@DynamicInsert` 等可能影响字段选择的注解。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| DTO 手动赋值 + 排除敏感字段 | **L0（快速跳过）** | 风险低 |
| 使用 `copyProperties` 但排除敏感字段 | **L2（跳读）** | 验证排除列表完整 |
| `merge/save` 直接使用用户实体 | **L3（逐行读）** | 高风险 |
| 多租户/关联实体同步更新 | **L4（跨模块追踪）** | 需检查租户隔离 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **JPA/Hibernate 更新操作** 直接使用来自客户端的实体或 DTO。
2. **敏感字段未受保护** 或未重写。
3. **可导致越权或关键数据被篡改**。

#### 误报
可视为误报的情况：
1. **实体字段被标记为不可更新**（`updatable=false` 或 `@JsonIgnore`）。
2. **服务层手动覆盖敏感字段**（如 `existing.setRole(existing.getRole())`）。
3. **接口仅对内部可信服务开放并有签名验证**。

#### 代码异味
需关注的风险：
1. 使用 `BeanUtils` 黑名单排除敏感字段。
2. 依赖 `@PreAuthorize`/`@Secured` 但未覆盖所有路径。
3. DTO 与实体共享，后续新增字段时易被遗漏。
4. 批量更新 (`saveAll`) 缺乏逐条校验。

## Low risk

### 低风险评级场景

#### 1. DTO 分层 + 手动赋值
- **场景：** 输入 DTO 只包含安全字段，服务层逐个赋值。
- **风险评估：** 风险较低，但需保持同步。

#### 2. 数据库触发器/约束
- **场景：** 数据库层禁止更新敏感列。
- **风险评估：** 降低危害，但不是根治。

#### 3. 后台管理员专用
- **场景：** 接口仅对已授权管理员开放。
- **风险评估：** 攻击面有限，但需防账号泄露。

#### 4. 审计日志
- **场景：** 对关键字段更新有审计与告警。
- **风险评估：** 有助于监测，但需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| DTO 手动赋值 | 技术防护完善 | 低 |
| 数据库约束 | 阻止敏感更新 | 中 |
| 管理员专用接口 | 攻击面小 | 中 |
| 审计告警 | 及时发现 | 高（持续改进）|

