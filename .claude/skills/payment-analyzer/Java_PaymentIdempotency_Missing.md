# Java_PaymentIdempotency_Missing

## Details

**核心漏洞特征**：Java支付处理无幂等性设计，相同请求被多次处理导致多次扣款，缺少去重或状态检查。

**代码示例定位**：查找支付处理核心逻辑（Service层、Controller层），关键词包括 `processPayment()`, `pay()`, `charge()`, `deductBalance()`, `updateOrderStatus()` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `account.balance -= amount` - 检查状态检查
- 搜索 `if (order.status != PENDING)` - 检查支付前验证
- 搜索 `UPDATE users SET balance` - 检查SQL条件
- 搜索 `@Transactional` - 检查事务管理

**快速定位保护机制**（L2: 跳读）：
- 检查支付前是否验证订单状态为PENDING
- 检查是否有幂等性Key去重
- 检查是否使用 `UPDATE ... WHERE status = 'PENDING'` 原子操作
- 检查是否记录支付历史

## Classify

**漏洞判定标准**：
- 无支付前状态检查 → **漏洞**
- 无幂等性Key或去重 → **漏洞**
- 操作非原子性 → **漏洞**
- 重复请求被多次处理 → **漏洞**

**误报情况**：
- 支付前验证状态为PENDING → 低风险
- 有幂等性Key或去重 → 低风险
- 使用原子操作（UPDATE WHERE） → 低风险

**代码异味**：
- 虽有检查但非原子 → 审计
- Key存在但未真正去重 → 审计

## Low risk

**低风险评级条件**：
1. **状态机设计**：支付前验证为PENDING，完成后为PAID
2. **幂等性Key**：生成唯一Key，检查拒绝重复
3. **原子操作**：UPDATE带WHERE条件
4. **并发控制**：使用乐观或悲观锁
5. **交易日志**：完整的支付日志
