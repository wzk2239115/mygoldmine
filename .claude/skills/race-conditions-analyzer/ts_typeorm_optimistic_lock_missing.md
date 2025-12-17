# TypeScript｜TypeORM 乐观锁缺失

## Details

### 漏洞成因
TypeORM 的实体默认不会自动处理并发写。当多个请求通过 `repository.save()` 或 `createQueryBuilder().update()` 修改同一行数据时，如果未启用 `@VersionColumn`、`@UpdateDateColumn` 校验或事务行锁，就可能出现后写覆盖先写，导致状态回退。常见于订单状态更新、余额、配置表写入等业务。

### 代码示例

**易受攻击示例：**
```ts
// Order entity 没有 version 字段
await this.orderRepository.save({
  id: orderId,
  status: OrderStatus.PAID,
  updatedBy: userId,
});
```

两个请求几乎同时读取旧状态，先后写回，导致最后一次写入覆盖前一次修改。

**安全示例：**
```ts
@Entity()
export class Order {
  @PrimaryGeneratedColumn()
  id: number;

  @VersionColumn()
  version: number;

  @Column()
  status: OrderStatus;
}

await this.orderRepository.save(order, { data: { action: 'update-status' } });
// TypeORM 会在 UPDATE 时带上 version，version 不一致抛出 OptimisticLockVersionMismatchError
```

或使用查询构建器：
```ts
await this.orderRepository
  .createQueryBuilder()
  .update(Order)
  .set({ status: OrderStatus.PAID })
  .where('id = :id', { id: orderId })
  .andWhere('version = :version', { version: currentVersion })
  .execute();
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `repository.save`, `update`, `createQueryBuilder().update`, `@VersionColumn`, `optimisticLock`。

**定位步骤：**
1. 搜索实体定义，确认是否存在 `@VersionColumn` 或 `@UpdateDateColumn`；
2. 跳读（L2）判断更新逻辑是否传入版本或条件；
3. 检查是否在事务中结合 `FOR UPDATE`。

#### 保护机制定位（审计等级：L2-L4）
**检查是否存在：**
- `@VersionColumn` 或 `optimisticLock` 配置；
- 事务 + `QueryRunner` + `FOR UPDATE`；
- 使用 `setLock('optimistic', version)` 或 `setLock('pessimistic_write')`；
- 应用层比较 `updatedAt` 是否变化。

**定位技巧：**
- 逐行读（L3）确认 `save` 时是否只传入部分字段导致覆盖；
- 若使用 `preload`，确认是否保留版本；
- 跨模块追踪（L4）多个 service 是否共享同一实体更新逻辑。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 启用乐观锁或事务锁 | **L0（快速跳过）** | 风险低 |
| 部分接口加锁 | **L2（跳读）** | 确认遗漏 |
| 无任何锁或版本控制 | **L3（逐行读）** | 高风险 |
| 多服务更新同一实体 | **L4（跨模块追踪）** | 全链路分析 |

## Classify

### 研判标准

#### 确认漏洞
1. 同一实体被多个请求并发更新；
2. 未启用乐观锁、悲观锁或事务；
3. 能复现状态回退、重复扣费等问题。

#### 误报
1. 实体启用 `@VersionColumn` 和 `optimisticLock`；
2. 更新操作只在单线程 worker 中执行；
3. 数据仅用于审计日志，覆盖影响小且有其他校验。

#### 代码异味
1. 注释说明“TODO: 加版本字段”但迟迟未实现；
2. 依赖外部服务序列化请求但缺乏兜底；
3. 使用 `save` 更新时未指定字段，导致覆盖默认值。

## Low risk

### 低风险评级场景

#### 1. 数据非关键
- 场景：记录仅用于缓存或统计；
- 评估：可降级，但需记录影响范围。

#### 2. 并发概率低
- 场景：系统由人工触发，短时间不会出现并发；
- 评估：风险较低，但需提醒。

#### 3. 正在引入乐观锁
- 场景：已有任务添加版本字段或使用消息队列；
- 评估：可标低风险，跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键数据 | 影响有限 | 低 |
| 低并发场景 | 触发概率低 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

