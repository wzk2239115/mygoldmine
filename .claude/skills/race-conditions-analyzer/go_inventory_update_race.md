# Go｜库存更新竞态

## Details

### 漏洞成因
库存或配额扣减流程中若未使用数据库事务、行锁或乐观锁，HTTP 请求、定时任务、异步队列可能同时读取旧库存并写回，导致超卖或库存负值。常见写法是 `UPDATE goods SET stock = stock - ? WHERE id = ?`，缺少 `WHERE stock >= ?` 或版本号校验，或在 Redis 预扣库存但后续写主库时未校验。

### 代码示例

**易受攻击示例：**
```go
func DeductStock(ctx context.Context, id int64, qty int) error {
    var current int
    err := db.QueryRowContext(ctx, "SELECT stock FROM goods WHERE id=?", id).Scan(&current)
    if err != nil {
        return err
    }
    if current < qty {
        return errors.New("insufficient")
    }
    _, err = db.ExecContext(ctx, "UPDATE goods SET stock = stock - ? WHERE id = ?", qty, id)
    return err
}
```

**安全示例：**
```go
func DeductStock(ctx context.Context, id int64, qty int) error {
    tx, err := db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
    if err != nil {
        return err
    }
    defer tx.Rollback()

    var current int
    if err := tx.QueryRowContext(ctx, "SELECT stock FROM goods WHERE id=? FOR UPDATE", id).Scan(&current); err != nil {
        return err
    }
    if current < qty {
        return ErrInsufficient
    }
    if _, err := tx.ExecContext(ctx, "UPDATE goods SET stock = stock - ? WHERE id = ?", qty, id); err != nil {
        return err
    }
    return tx.Commit()
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `stock`, `inventory`, `UPDATE ... SET ... -`, `cron`, `worker`, `transaction`, `FOR UPDATE`。

**定位步骤：**
1. 搜索库存相关 SQL 或 Redis 操作；
2. 跳读（L2）判断是否使用事务、行锁或条件更新；
3. 检查是否存在多个入口（HTTP、Cron、队列）调用相同逻辑。

#### 保护机制定位（审计等级：L2-L4）
**检查是否存在：**
- 数据库事务 + `SELECT ... FOR UPDATE`；
- 乐观锁列（version）+ 比较更新；
- 分布式锁（Redis、Etcd）、队列串行化；
- Redis 预扣 + Lua 保证一致性。

**定位技巧：**
- 逐行读（L3）确认写入 SQL 是否校验受影响行数；
- 如果启用缓存预扣，检查与主库一致性；
- 跨模块追踪（L4）库存更新是否在不同 service/worker 间同步。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用事务 + 行锁/乐观锁 | **L0（快速跳过）** | 风险低 |
| 仅部分路径使用锁 | **L2（跳读）** | 需确认遗漏 |
| 无锁扣减 / 仅靠读取判断 | **L3（逐行读）** | 高风险 |
| 多入口写入且无统一策略 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 读库存与写库存分离，无锁或版本控制；
2. 并发请求可复现超卖、库存为负或重复扣减；
3. 影响核心业务（订单、支付、配额）。

#### 误报
1. 采用 `SELECT ... FOR UPDATE` 或 `UPDATE ... WHERE stock >= ?` 并检查受影响行数；
2. 所有扣减通过单线程队列或分布式锁串行执行；
3. 库存只是统计字段，实际扣减在其他系统完成。

#### 代码异味
1. 依赖 Redis 缓存扣减但缺少主库校验；
2. 仅靠延迟补偿或定时任务对账；
3. 未处理扣减失败时的 rollback/重试。

## Low risk

### 低风险评级场景

#### 1. 库存非关键
- 场景：库存仅用于展示（例：浏览量），错误影响小；
- 评估：可降级，但仍应提示缺陷。

#### 2. 人工复核流程
- 场景：订单极少，并有人工审批；
- 评估：风险降低，但需记录依赖人工。

#### 3. 正在迁移到统一库存服务
- 场景：已有计划使用库存中心或消息队列；
- 评估：暂标低风险，跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非核心展示 | 影响有限 | 低 |
| 人工复核 | 可控补救 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

