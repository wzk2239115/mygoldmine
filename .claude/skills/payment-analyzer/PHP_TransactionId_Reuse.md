# PHP_TransactionId_Reuse

## Details

**核心漏洞特征**：PHP应用中交易ID生成不唯一，允许旧交易ID被重新使用，攻击者可复用已支付的ID进行重放。

**代码示例定位**：查找交易ID生成和验证代码，关键词包括 `generateTxnId()`, `$_POST['transaction_id']`, `SELECT FROM orders WHERE txn_id`, `UPDATE payment SET` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `$txn_id = time()` - 弱ID生成
- 搜索 `SELECT FROM orders WHERE txn_id` - 检查去重
- 搜索 `INSERT INTO orders` 无UNIQUE约束 - 检查保护
- 搜索 `$_POST['txn_id']` - 检查客户端控制

**快速定位保护机制**（L2: 跳读）：
- 检查是否有UNIQUE约束在txn_id字段
- 检查是否验证ID存在且初始状态
- 检查ID生成是否使用UUID或加密随机数
- 检查是否有重复ID检查逻辑

## Classify

**漏洞判定标准**：
- 交易ID无唯一约束 → **漏洞**
- 生成的ID可预测 → **漏洞**
- 处理前未验证ID唯一性 → **漏洞**
- 接受客户端提供的ID → **漏洞**

**误报情况**：
- UUID生成+数据库唯一约束 → 低风险
- 严格状态机+去重验证 → 低风险

**代码异味**：
- 虽有约束但无应用层校验 → 审计
- 验证逻辑未覆盖所有路径 → 审计

## Low risk

**低风险评级条件**：
1. **强随机生成**：使用UUID或密码学随机数
2. **数据库保护**：UNIQUE约束确保全局唯一
3. **应用层验证**：INSERT前验证ID是否存在
4. **防重放设计**：状态机确保已处理交易不可重复
5. **清理机制**：定期清理或归档已完成交易
