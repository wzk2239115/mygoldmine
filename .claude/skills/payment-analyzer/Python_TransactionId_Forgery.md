# Python_TransactionId_Forgery

## Details

**核心漏洞特征**：Python应用接受客户端提供的交易ID或允许攻击者伪造有效的交易ID，进行交易冒充。

**代码示例定位**：查找交易ID处理代码，关键词包括 `request.POST['transaction_id']`, `txn_id`, `order_id` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `request.POST['txn_id']` 或 `request.GET['order_id']` - 检查是否接受客户端ID
- 搜索 `db.query(Order).filter(id=txn_id)` - 检查是否直接使用ID
- 搜索UUID或随机生成逻辑 - 检查ID生成方式
- 搜索 `hashlib`, `secrets` 或密码学函数 - 检查是否使用强随机

**快速定位保护机制**（L2: 跳读）：
- 检查是否服务端生成交易ID
- 检查是否有ID格式验证
- 检查是否将ID与用户身份绑定
- 检查是否有ID去重机制

## Classify

**漏洞判定标准**：
- 直接使用客户端提供的交易ID → **漏洞**
- ID生成算法可预测 → **漏洞**
- 无ID与用户的绑定验证 → **漏洞**
- 无ID去重 → **漏洞**

**误报情况**：
- 服务端生成UUID ID → 低风险
- 强验证客户端ID并绑定用户 → 低风险
- 有完整的去重机制 → 低风险

**代码异味**：
- 虽验证ID但无绑定检查 → 审计
- ID生成使用time.time()或简单随机 → 审计

## Low risk

**低风险评级条件**：
1. **服务端生成**：交易ID完全由服务端生成
2. **强随机**：使用secrets或uuid.uuid4()
3. **用户绑定**：交易ID与用户账户绑定验证
4. **去重保障**：数据库约束保证唯一
5. **一次性验证**：交易ID仅能使用一次