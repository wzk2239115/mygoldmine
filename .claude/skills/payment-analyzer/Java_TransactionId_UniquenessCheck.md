# Java_TransactionId_UniquenessCheck

## Details

**核心漏洞特征**：Java应用中交易ID唯一性检查缺失，无数据库约束也无应用层验证，允许相同ID被重复创建。

**代码示例定位**：查找交易创建代码（DAO层、Service层），关键词包括 `save()`, `insert()`, `persist()`, `transactionService.createTransaction()`, `getById()` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `@Query` 或 `findByTransactionId()` - 检查验证逻辑
- 搜索 `INSERT INTO transactions` - 检查SQL约束
- 搜索 `@Entity` 或 `@Table` - 检查表定义约束
- 搜索 `save()` 前是否有检查

**快速定位保护机制**（L3: 逐行读）：
- 检查是否有 `@Column(unique=true)` 或数据库约束
- 检查INSERT前是否调用 `findByTransactionId()` 检查
- 检查是否使用 `INSERT ... ON DUPLICATE KEY UPDATE`
- 检查是否有数据库事务保证原子性

## Classify

**漏洞判定标准**：
- 无数据库唯一约束 → **漏洞**
- 无应用层唯一性检查 → **漏洞**
- 并发请求可绕过单层检查 → **漏洞**
- 检查与INSERT不在同一事务 → **漏洞**

**误报情况**：
- 数据库UNIQUE约束+异常处理 → 低风险
- 应用层检查+数据库约束 → 低风险
- 数据库事务确保原子性 → 低风险

**代码异味**：
- 仅依赖应用层检查无约束 → 审计
- 异常处理缺失导致错误 → 审计
- 并发未加锁 → 审计

## Low risk

**低风险评级条件**：
1. **数据库约束**：transaction_id有UNIQUE约束
2. **应用层验证**：INSERT前调用SELECT检查
3. **事务保护**：验证和INSERT在同一事务
4. **并发控制**：使用乐观锁或悲观锁
5. **异常处理**：捕获冲突异常返回错误
