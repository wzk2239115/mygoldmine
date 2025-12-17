# Java 优惠券/积分/奖励重复使用漏洞

## Details

### 漏洞成因
优惠券、积分、代金券等可复用资源在兑换/核销时缺乏去重机制，导致同一凭证可被多次使用、并发重放，或绕过单次使用限制。

### 代码示例

```java
// 典型漏洞：仅查询未标记已使用
@Transactional
public void applyCoupon(String couponCode, Long userId) {
    Coupon coupon = couponRepo.findByCode(couponCode);
    if (coupon != null && coupon.isValid()) {  
        // 无状态检查：未验证 coupon.used 或使用次数
        applyDiscount(userId, coupon.getAmount());
        // 危险：标记已使用在业务逻辑后，存在时间窗口
        coupon.setUsed(true);  
        couponRepo.save(coupon);
    }
}
```

```java
// 并发竞态：检查与标记非原子
public void redeemPoints(Long userId, int points) {
    User user = userService.get(userId);
    if (user.getPoints() >= points) {        // T1: 并发请求同时通过
        // 时间窗口：多个线程可同时执行到这里
        processReward(userId);                // T2: 业务逻辑
        user.setPoints(user.getPoints() - points);  // T3: 扣减（可能多次执行）
        userService.save(user);
    }
}
```

```java
// 缺乏唯一性约束：允许同一用户多次使用同一优惠券
@PostMapping("/use-coupon")
public void useCoupon(@RequestParam String code) {
    // 危险：未检查 userId+couponId 历史使用记录
    couponService.deduct(code);  
    orderService.applyDiscount(code);
}
```

### 快速定位核心操作
- **关键词扫描**：`coupon`, `voucher`, `redeem`, `apply`, `deduct`, `points`, `reward`, `credit`, `discount`
- **业务模式**：兑换接口、核销接口、优惠应用、积分消费、红包使用
- **高危结构**：
  - `if (exists && isValid)` 后直接扣减，无历史使用检查
  - 查询 → 业务逻辑 → 更新状态（三步非原子）
  - 缺少 `used` 字段或 `usageCount` 计数
- **数据流追踪**：优惠券码/ID从请求参数到数据库操作的全链路，检查去重点

### 快速定位保护机制
- **数据库层**：
  - 唯一索引：`UNIQUE(user_id, coupon_id)` 或 `UNIQUE(coupon_code, order_id)`
  - 悲观锁：`SELECT ... FOR UPDATE`
  - 乐观锁：`UPDATE ... WHERE version=? AND used=false`
- **应用层**：
  - 分布式锁：Redis `SETNX`、Redisson、Zookeeper
  - 幂等表：`CouponUsageLog` 记录每次使用，插入前检查
  - 状态检查：`if (coupon.getUsed())` 在业务前
  - 原子操作：`@Transactional(isolation = SERIALIZABLE)`
- **框架防护**：
  - 幂等中间件：统一拦截器基于 `requestId` 去重
  - 防重放 token：一次性 token 绑定优惠券使用

### 审计等级判定

| 等级 | 场景 | 审计策略 |
|------|------|----------|
| **L0** | 仅查询展示优惠券列表，无核销操作 | 跳过 |
| **L1** | 有明确 `UNIQUE` 约束且异常处理完善 | 关键词确认约束覆盖所有使用场景 |
| **L2** | 使用分布式锁但无业务状态检查 | 跳读验证锁粒度与业务事务边界 |
| **L3** | 状态检查与更新分离，或仅依赖应用层校验 | 逐行追踪并发窗口、事务边界、异常回滚 |
| **L4** | 跨服务调用、异步任务、缓存与数据库双写 | 跨模块追踪一致性、补偿机制、MQ重试逻辑 |

---

## Classify

### 确认漏洞（需满足以下条件）
1. **可重复触发**：同一优惠券码/积分可通过重放请求或并发请求多次生效
2. **无有效去重**：缺少以下任一机制：
   - 数据库唯一约束
   - 幂等表记录
   - 分布式锁保护完整事务
   - 状态原子性更新（CAS/乐观锁）
3. **业务影响**：可导致资金损失、超额优惠、积分凭空增加

**典型漏洞特征**：
- 优惠券核销前未查询 `used` 状态或使用历史
- `UPDATE coupon SET used=1` 在业务逻辑后，存在时间窗口
- 仅校验优惠券有效期/金额，不校验使用次数
- 并发场景下 `CHECK-THEN-ACT` 模式无原子保护
- 异步处理（MQ消费）时缺少消息去重

### 误报排除
- ✗ 优惠券设计为"多次使用"（需确认次数上限且有准确计数）
- ✗ 数据库已有 `UNIQUE(user_id, coupon_id)` 且应用正确处理 `DuplicateKeyException`
- ✗ 使用分布式锁覆盖整个兑换事务，且锁粒度正确（按 userId+couponId）
- ✗ 幂等表 `INSERT IGNORE` 或先查询再插入且在同一事务
- ✗ 仅内部管理员可手动核销（需确认无对外API）

### 代码异味（需进一步验证）
- △ 状态更新依赖 `@Transactional` 但隔离级别为 `READ_COMMITTED`（默认级别无法防并发）
- △ 有 `used` 字段但未在 WHERE 条件中使用（如 `UPDATE ... WHERE id=?`）
- △ 前端防重复提交但后端无防护
- △ 使用 Redis 锁但未处理锁超时、续期、异常释放

---

## Low Risk

### 给予低风险评级的场景

1. **金额极小且有总量监控**
   - 单次优惠 <1元，且有实时异常检测告警
   - 每日总优惠额度有硬上限（数据库或风控拦截）

2. **业务自带幂等保护**
   - 优惠券关联订单ID，订单本身有唯一性约束
   - 下游支付系统会二次验证优惠合法性

3. **攻击成本高**
   - 需要实名认证且单用户优惠券数量极少
   - 并发窗口极短（<10ms）且需精准时序配合

4. **影响范围可控**
   - 测试环境优惠券或内部员工福利券
   - 仅影响单用户自身权益（如积分兑换虚拟商品）

5. **有异常恢复机制**
   - 定时任务对账扣减异常使用
   - 人工审核环节（如大额优惠需审批）
   - 已有风控规则检测单用户异常兑换频次

6. **技术债且即将重构**
   - 旧版本系统且使用量极低
   - 已有新版本使用分布式事务保护

**评级建议**：即使低风险，应在报告中注明缺陷并建议优先修复，避免营销活动期间被规模化利用。