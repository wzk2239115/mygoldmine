# Go_PaymentState_RaceCondition

## Details

**核心漏洞特征**：Go应用中支付状态转换存在竞态条件，并发请求可绕过状态机验证导致非法状态转换。

**代码示例定位**：查找状态转换代码，关键词包括 `order.status`, `Mutex`, `atomic`, `UPDATE ... SET status` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `order.status =` - 检查是否有同步保护
- 搜索 `if order.status ==` - 检查是否原子操作
- 搜索数据库UPDATE - 检查WHERE条件
- 搜索goroutine操作 - 检查并发问题

**快速定位保护机制**（L2: 跳读）：
- 检查是否使用Mutex保护状态
- 检查是否使用数据库事务
- 检查是否使用SELECT ... FOR UPDATE
- 检查是否有乐观锁（版本号）

## Classify

**漏洞判定标准**：
- 状态检查和修改非原子 → **漏洞**
- 无数据库锁保护 → **漏洞**
- UPDATE无WHERE条件 → **漏洞**
- 并发goroutine无同步 → **漏洞**

**误报情况**：
- Mutex保护 + 数据库约束 → 低风险
- 数据库级锁 → 低风险
- 原子操作 → 低风险

**代码异味**：
- 虽有锁但范围不足 → 审计
- 混合使用多种锁机制 → 审计

## Low risk

**低风险评级条件**：
1. **应用层保护**：使用Mutex保护状态访问
2. **数据库保护**：UPDATE ... WHERE status = 'EXPECTED'
3. **行级锁**：SELECT ... FOR UPDATE获取排他锁
4. **事务使用**：状态变化在事务中
5. **并发测试**：有并发场景的单元测试