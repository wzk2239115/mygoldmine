# NodeJS_TransactionId_ClientGeneration

## Details

**核心漏洞特征**：NodeJS应用中交易ID由客户端生成，应用直接信任该ID，攻击者可伪造、重复或冒充他人ID进行支付。

**代码示例定位**：查找处理客户端ID的代码（API端点、支付处理函数），关键词包括 `req.body.transactionId`, `req.params.txnId`, `createOrder()` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `const txnId = req.body.txn_id` - 直接使用客户端ID
- 搜索 `db.orders.insert({ txn_id: txnId })` - 无验证INSERT
- 搜索 `UUID.parse()` - 检查最小验证
- 搜索 `req.query` 或 `req.params` 中的ID

**快速定位保护机制**（L2: 跳读）：
- 检查服务端是否生成ID而非信任客户端
- 检查是否有唯一约束限制重复
- 检查是否验证客户端ID格式
- 检查是否绑定用户身份

## Classify

**漏洞判定标准**：
- 交易ID完全由客户端生成 → **漏洞**
- 服务端无ID去重验证 → **漏洞**
- 无用户身份与ID的绑定 → **漏洞**

**误报情况**：
- 服务端生成并分配ID → 低风险
- 客户端ID仅作请求标识，服务端生成实际ID → 低风险
- 完整去重和身份绑定 → 低风险

**代码异味**：
- 使用时间戳或计数器作ID → 审计
- ID格式验证但无去重 → 审计

## Low risk

**低风险评级条件**：
1. **服务端生成**：使用UUID或密码学随机数
2. **去重保障**：UNIQUE约束+应用层验证
3. **绑定验证**：ID与用户账户绑定
4. **一次性使用**：每笔ID仅能使用一次
5. **不可修改**：创建后ID不可更改
