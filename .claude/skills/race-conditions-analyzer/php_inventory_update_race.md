# PHP｜库存扣减竞态

## Details

### 漏洞成因
在 Laravel、ThinkPHP 等框架中，多个请求或 worker 同时执行 `UPDATE goods SET stock = stock - ? WHERE id = ?` 时，如果缺乏事务、行锁或乐观锁，就会导致库存被重复扣减或出现负值。常见问题还包括：使用 Redis 预扣库存但未与数据库对账；后台管理与 API 共用库存逻辑却无统一锁；使用旧版 `mysql_*` 函数直接拼接 SQL，缺乏条件约束。

### 代码示例

**易受攻击示例：**
```php
function deductStock(PDO $pdo, int $goodsId, int $qty): bool {
    $stmt = $pdo->prepare('SELECT stock FROM goods WHERE id=:id');
    $stmt->execute([':id' => $goodsId]);
    $stock = (int) $stmt->fetchColumn();
    if ($stock < $qty) {
        return false;
    }
    $update = $pdo->prepare('UPDATE goods SET stock = stock - :qty WHERE id = :id');
    return $update->execute([':qty' => $qty, ':id' => $goodsId]);
}
```

**安全示例：**
```php
function deductStock(PDO $pdo, int $goodsId, int $qty): bool {
    $pdo->beginTransaction();
    $stmt = $pdo->prepare('SELECT stock FROM goods WHERE id = :id FOR UPDATE');
    $stmt->execute([':id' => $goodsId]);
    $stock = (int) $stmt->fetchColumn();
    if ($stock < $qty) {
        $pdo->rollBack();
        return false;
    }
    $update = $pdo->prepare('UPDATE goods SET stock = stock - :qty WHERE id = :id');
    $update->execute([':qty' => $qty, ':id' => $goodsId]);
    return $pdo->commit();
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `stock`, `inventory`, `扣减`, `UPDATE`, `FOR UPDATE`, `transaction`, `锁`。

**定位步骤：**
1. 搜索库存相关 SQL 或 ORM 操作；
2. 跳读（L2）判断是否开启事务并使用 `FOR UPDATE` 或版本号；
3. 检查是否有多处入口调用同一扣减函数（前台下单、后台修改、脚本任务）。

#### 保护机制定位（审计等级：L2-L4）
**检查是否存在：**
- 数据库事务 + 行级锁；
- 乐观锁字段（`version`、`updated_at` 比较）；
- Redis/Etcd 分布式锁；
- 串行化任务队列或库存中心服务；
- Redis 预扣后写库时的 Lua 校验。

**定位技巧：**
- 逐行读（L3）确认更新语句是否附带条件（`WHERE stock >= :qty`）；
- 若使用 Redis 预扣，检查是否在失败时回滚；
- 跨模块追踪（L4）库存逻辑是否被 worker、cron、后台同时调用且缺乏统一锁。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 事务 + 行锁/乐观锁健全 | **L0（快速跳过）** | 风险小 |
| 部分入口有锁 | **L2（跳读）** | 需确认遗漏 |
| 无锁扣减或只在应用层判断 | **L3（逐行读）** | 高风险 |
| 多系统共享库存无统一策略 | **L4（跨模块追踪）** | 全链路分析 |

## Classify

### 研判标准

#### 确认漏洞
1. 库存扣减缺乏事务/锁，读取与写入分离；
2. 并发请求可导致超卖、库存负值、重复扣费；
3. 涉及订单、券、配额等核心业务。

#### 误报
1. 所有扣减都在事务中进行并加行锁；
2. 使用 `UPDATE ... WHERE stock >= ?` 并检查受影响行数；
3. 通过队列串行扣减或使用库存中心。

#### 代码异味
1. 依赖 Redis 预扣但无数据库校验；
2. 使用短 TTL 或延时任务兜底；
3. 扣减失败时记录日志但未回滚缓存。

## Low risk

### 低风险评级场景

#### 1. 库存仅为统计字段
- 场景：库存不会驱动业务流程，错误只影响展示；
- 评估：可降级，但记录潜在问题。

#### 2. 并发量极低
- 场景：人工审核、线下发货，每次操作人工确认；
- 评估：短期风险小，但需说明依赖人工。

#### 3. 正在引入库存中心
- 场景：已有迁移计划到统一库存服务；
- 评估：可作为低风险保留，跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非核心统计 | 影响有限 | 低 |
| 人工审批 | 可人工纠错 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

