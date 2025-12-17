# TypeScript TypeORM 批量赋值漏洞

## Details

### 漏洞成因
TypeORM `Repository.save`, `Repository.update`, `createQueryBuilder().update()` 等方法会将输入对象的所有字段写入数据库。若控制器/Service 直接将 `dto` 或 `req.body` 传入这些方法，而 DTO 未排除敏感字段（如 `role`, `status`, `tenantId`, `credit`, `isAdmin`），攻击者可覆盖敏感数据。使用 `preload` 或 `merge` 时也会自动拷贝字段，需要谨慎处理。

### 代码示例

**易受攻击的代码：**
```typescript
@Patch(':id')
async update(@Param('id') id: string, @Body() dto: UpdateUserDto) {
  // dto 可包含 role: 'admin'
  await this.usersRepository.update(id, dto);
  return this.usersRepository.findOneBy({ id });
}
```

**另一个不安全示例（save + merge）：**
```typescript
@Put(':id')
async replace(@Param('id') id: string, @Body() dto: UpdateOrderDto) {
  const order = await this.ordersRepository.preload({ id: Number(id), ...dto });
  // preload 会将 dto 字段复制到实体
  return this.ordersRepository.save(order); // 可覆盖 status, tenantId
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `repository.save`, `repository.update`, `preload`, `merge`, `create`
- `queryBuilder.update`, `set(dto)`
- DTO 中的敏感字段：`role`, `tenantId`, `status`, `price`, `isAdmin`
- `Object.assign(entity, dto)`, `assignDeep`

**定位步骤：**
1. 搜索 TypeORM Repository/QueryBuilder 调用，检查参数。
2. 查看 DTO 定义，识别敏感字段。
3. 跳读（L2）确认是否有字段白名单或权限校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **DTO 白名单：** 使用 `PickType` 或自定义 DTO 仅包含可写字段。
- **字段排除：** 在 Service 层 `delete dto.role`.
- **权限校验：** 在更新前验证调用者角色/租户。
- **数据库约束：** 使用触发器/检查约束限制敏感列。
- **实体配置：** 使用 `@UpdateDateColumn`, `@CreateDateColumn`, `@Column({ update: false })`.

**定位技巧：**
- 检查 `ValidationPipe` 是否启用 `whitelist`.
- 对 `preload`/`merge`，确认第三方字段不会被拼接。
- 关注 `RelationId`, `JoinColumn` 等关联字段是否可被覆盖。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| DTO 白名单 + Service 手动赋值 | **L0（快速跳过）** | 风险低 |
| 使用 `omit`/`pick` 过滤敏感字段 | **L2（跳读）** | 检查是否完整 |
| `update/save` 直接使用 DTO | **L3（逐行读）** | 高风险 |
| 多租户/批量更新 | **L4（跨模块追踪）** | 需检查租户隔离 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **TypeORM 更新操作** 使用未经筛选的输入。
2. **敏感字段能够被覆盖**。
3. **导致越权、数据篡改或租户越界**。

#### 误报
可视为误报的情况：
1. DTO 不包含敏感字段且启用 `whitelist`.
2. Service 在保存前重写或剥离敏感字段。
3. 数据库层阻止敏感列被修改。

#### 代码异味
需关注的风险：
1. `preload`/`merge` 结合外部输入，易忽略字段。
2. 黑名单删除敏感字段，易遗漏新字段。
3. `update` 不触发实体钩子，可能绕过安全逻辑。
4. 异步流程中 DTO 被多处复用，易混淆。

## Low risk

### 低风险评级场景

#### 1. 内部接口
- **场景：** 接口仅对内部服务开放，带鉴权。
- **风险评估：** 攻击面有限，但需防滥用。

#### 2. DTO 白名单 + 手动赋值
- **场景：** Service 手动选择可更新字段。
- **风险评估：** 风险较低，需保持维护。

#### 3. 数据库触发器/约束
- **场景：** 敏感列有数据库级保护。
- **风险评估：** 降低危害，但不替代代码修复。

#### 4. 审计与告警
- **场景：** 对关键字段更新记录审计。
- **风险评估：** 有助于检测异常，仍需修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 + 强鉴权 | 攻击面有限 | 中 |
| DTO 白名单 + whitelist | 技术防护完善 | 低 |
| 数据库约束 | 阻断敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

