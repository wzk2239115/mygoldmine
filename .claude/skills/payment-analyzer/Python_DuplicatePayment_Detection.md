# Python_DuplicatePayment_Detection

## Details

**核心漏洞特征**：Python应用中缺少重复支付检测机制，允许同一笔交易被重复扣款。

**代码示例定位**：查找支付处理代码，关键词包括 `pay()`, `charge()`, `deductBalance()`, `duplicate`, `check` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `SELECT ... WHERE txn_id` - 检查是否检查重复交易
- 搜索 `INSERT INTO payments` - 检查INSERT前是否验证
- 搜索 `UPDATE ... WHERE` - 检查是否有幂等性设计
- 搜索异常处理 - 检查重复错误处理

**快速定位保护机制**（L2: 跳读）：
- 检查是否有UNIQUE约束
- 检查是否在INSERT前检查重复
- 检查是否使用请求ID去重
- 检查是否记录重复支付日志

## Classify

**漏洞判定标准**：
- 无重复交易检测 → **漏洞**
- 无UNIQUE约束 → **漏洞**
- 检查和INSERT非原子 → **漏洞**
- 异常处理未考虑重复 → **漏洞**

**误报情况**：
- UNIQUE约束+异常处理 → 低风险
- 原子操作 → 低风险
- 完整的去重逻辑 → 低风险

**代码异味**：
- 虽有约束但无应用层检查 → 审计
- 检查逻辑分散 → 审计

## Low risk

**低风险评级条件**：
1. **数据库约束**：交易ID有UNIQUE约束
2. **应用检查**：INSERT前SELECT检查重复
3. **原子操作**：检查和INSERT在事务中
4. **异常处理**：UNIQUE冲突异常被正确处理
5. **审计日志**：重复支付尝试有日志