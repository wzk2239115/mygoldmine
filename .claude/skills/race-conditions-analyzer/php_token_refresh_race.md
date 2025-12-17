# PHP｜令牌刷新竞态

## Details

### 漏洞成因
刷新访问令牌（Session、JWT、OAuth Token）时，如果多个请求同时触发刷新接口，但后端没有使用互斥锁、唯一约束或 compare-and-set，就可能发生旧令牌被重复发放、刷新结果覆盖等竞态，导致认证绕过或安全策略失效。典型场景包括：单点登录系统的 `refresh_token` 接口、后台批量刷新 session、移动端重复请求刷新。

### 代码示例

**易受攻击示例：**
```php
function refreshToken(PDO $pdo, string $oldToken): string {
    $stmt = $pdo->prepare('SELECT user_id FROM sessions WHERE token = :token');
    $stmt->execute([':token' => $oldToken]);
    $userId = $stmt->fetchColumn();
    if (!$userId) {
        throw new RuntimeException('invalid token');
    }
    $newToken = bin2hex(random_bytes(32));
    $update = $pdo->prepare('UPDATE sessions SET token = :new WHERE user_id = :uid');
    $update->execute([':new' => $newToken, ':uid' => $userId]);
    return $newToken; // 并发请求可能覆盖为不同值
}
```

**安全示例：**
```php
function refreshToken(PDO $pdo, string $oldToken): string {
    $pdo->beginTransaction();
    $stmt = $pdo->prepare('SELECT user_id, token FROM sessions WHERE token = :token FOR UPDATE');
    $stmt->execute([':token' => $oldToken]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$row) {
        $pdo->rollBack();
        throw new RuntimeException('invalid token');
    }
    $newToken = bin2hex(random_bytes(32));
    $update = $pdo->prepare('UPDATE sessions SET token = :new WHERE user_id = :uid AND token = :old');
    $update->execute([':new' => $newToken, ':uid' => $row['user_id'], ':old' => $oldToken]);
    $pdo->commit();
    return $newToken;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `refreshToken`, `regenerate`, `session`, `SET token`, `UPDATE ... WHERE token`, `OAuth`, `JWT`。

**定位步骤：**
1. 搜索刷新令牌或 `session_regenerate_id` 相关逻辑；
2. 跳读（L2）检查是否在数据库/缓存中使用 compare-and-set、唯一约束；
3. 确认是否处理并发请求（分布式锁、队列）。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 数据库事务 + `FOR UPDATE` 或 `WHERE token = oldToken`；
- 唯一索引约束结合受影响行数判断；
- Redis `SETNX` / `GETSET` 原子操作；
- 同一用户刷新时采用互斥锁或请求串行化。

**定位技巧：**
- 逐行读（L3）确认刷新后是否吊销旧 token；
- 检查是否有重复刷新逻辑（移动端重试、后台批量任务）；
- 跨模块追踪（L4）多服务节点是否共享刷新逻辑并使用统一锁。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用事务 + 条件更新 / 唯一索引 | **L0（快速跳过）** | 风险低 |
| 部分路径加锁 | **L2（跳读）** | 需确认遗漏 |
| 无锁刷新或覆盖写 | **L3（逐行读）** | 高风险 |
| 多服务共享刷新但无锁 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 多次刷新时旧 token 依然有效或新 token 被覆盖；
2. 刷新逻辑缺乏原子性，未校验旧 token；
3. 影响认证安全，可被利用进行会话固定或绕过登录。

#### 误报
1. 使用事务 + 条件更新确保只有持有旧 token 的请求成功；
2. 刷新操作受队列或锁保护，每次只允许一个请求；
3. 旧 token 立即吊销并在多节点同步。

#### 代码异味
1. 缺乏对多端登录/多实例的考虑；
2. 依赖短 TTL、客户端重试避免竞态；
3. 刷新失败仅记录日志，不返回错误。

## Low risk

### 低风险评级场景

#### 1. 非敏感令牌
- 场景：token 仅用于非关键业务或临时预览；
- 评估：可降级，但应注明影响范围。

#### 2. 刷新频率极低
- 场景：仅管理员后台偶尔使用，人工可监控；
- 评估：风险较低，但要提示改进。

#### 3. 即将迁移到集中认证服务
- 场景：计划引入统一身份平台或 OAuth 服务；
- 评估：短期可降级，但需跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键业务 | 影响有限 | 低 |
| 低频人工操作 | 可人工兜底 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

