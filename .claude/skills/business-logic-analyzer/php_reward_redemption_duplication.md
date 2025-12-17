# PHP - 奖励兑换重复发放漏洞

**漏洞描述**：奖励兑换或商品购买未实施幂等性控制，重复提交导致资源重复发放

---

## Details

**审计等级**：L3（逐行读）

**代码特征**：
```php
// 典型漏洞代码
function redeemReward($userId, $rewardId) {
    $reward = getReward($rewardId);
    if ($reward['stock'] > 0) {
        // 缺少幂等性检查
        decreaseStock($rewardId);
        grantReward($userId, $rewardId);
        return ['success' => true];
    }
}
```

**快速定位核心操作技巧**：
1. 搜索关键词：`redeem`, `exchange`, `claim`, `purchase`, `buy`, `grant`, `gift`, `coupon`
2. 定位资源变更操作：`INSERT`, `UPDATE stock/balance/points`, `giveReward`, `addCredits`
3. 关注无返回值或仅返回成功状态的兑换接口
4. 查看事务边界：资源检查和扣减是否在同一事务内

**快速定位保护机制技巧**：
1. **幂等性令牌**：`$_POST['token']`, `idempotency_key`, `request_id`, `order_no` 唯一性检查
2. **状态流转**：`redemption_records` 表 + `user_id + reward_id` 唯一索引或查重逻辑
3. **分布式锁**：`Redis::setnx("lock:redeem:{$userId}:{$rewardId}")`, `Memcached::add()`
4. **数据库锁**：`SELECT ... FOR UPDATE`, `WHERE stock > 0 AND ...` 原子更新
5. **消息队列**：异步处理 + 消费端幂等性保证

**审计检查点**：
- 兑换记录表是否有唯一约束（用户+奖励）
- 库存扣减是否使用原子操作（`UPDATE ... WHERE stock >= ?`）
- 并发场景下是否存在 TOCTOU（Time-of-Check Time-of-Use）
- 是否依赖前端防抖/禁用按钮（客户端控制无效）
- 异步回调是否验证请求唯一性

---

## Classify

**确认为漏洞**（高危）：
- 无任何幂等性控制机制
- 库存检查和扣减分离，存在竞态窗口
- 依赖 PHP Session 锁但请求可绕过（不同 SessionID）
- 兑换记录表无唯一索引且代码无查重逻辑
- 使用 `stock = stock - 1` 但未验证 `WHERE stock > 0`

**误报**：
- 幂等性令牌已实施且服务端强制校验
- 数据库唯一约束已生效（测试插入重复数据抛异常）
- 使用事务 + `SELECT ... FOR UPDATE` 锁定记录
- 分布式锁实现正确（注意锁超时和释放逻辑）
- 消息队列处理且消费端已去重

**代码异味**（需人工验证）：
- 锁机制存在但实现可疑（如超时时间过短、锁范围过宽）
- 依赖数据库乐观锁但无重试逻辑
- 异步处理但回调接口无签名验证
- 存在幂等性设计但仅在部分分支生效

---

## Low risk

以下场景可降低风险等级：

1. **资源价值低**：测试环境积分、无实际价值的虚拟徽章
2. **访问受限**：内部管理后台且需多因素认证
3. **业务兜底**：
   - 每日兑换次数有硬限制（数据库约束级别）
   - 用户账户余额/积分上限很低
   - 人工审核流程在资源发放前介入
4. **监控告警**：实时异常检测（同用户短时间多次兑换触发风控）
5. **库存极大**：虚拟商品无库存限制，重复兑换不影响其他用户
6. **已有补偿机制**：定时任务校验并回收异常发放的资源

**注意**：即使评为低风险，仍需在报告中说明潜在危害和建议修复优先级