# Vyper_MissingMemoryCaching

## 概述
未使用内存变量缓存存储值，导致重复的昂贵存储读取操作。常见于代币授权、治理提案执行、收益再投资等业务逻辑中。

## Details

**代码示例：**
```vyper
# 问题代码：同一存储变量被多次读取
@external
def transfer_with_fee(receiver: address, amount: uint256):
    fee: uint256 = amount * self.fee_rate / 10000  # SLOAD 1
    assert self.balances[msg.sender] >= amount + fee  # SLOAD 2
    self.balances[msg.sender] -= (amount + fee)  # SLOAD 3
    self.balances[receiver] += amount
    self.balances[self.fee_collector] += fee  # SLOAD 4

# 优化代码：使用内存缓存
@external
def transfer_with_fee(receiver: address, amount: uint256):
    sender_balance: uint256 = self.balances[msg.sender]  # 缓存
    fee_collector: address = self.fee_collector  # 缓存
    fee: uint256 = amount * self.fee_rate / 10000
    assert sender_balance >= amount + fee
    self.balances[msg.sender] = sender_balance - (amount + fee)
    self.balances[receiver] += amount
    self.balances[fee_collector] += fee
```

**快速定位核心操作技巧（L2:跳读）：**
- 扫描 `self.` 前缀的存储变量访问
- 重点关注函数内同一存储变量的多次引用
- 查找循环体内的存储读取 `for i in range(n): ... self.xxx ...`
- 注意条件分支中的重复存储访问 `if self.xxx > 0: ... self.xxx ...`

**快速定位保护机制技巧（L1:关键词扫描）：**
- 检查是否存在局部变量声明并赋值为存储变量
- 查找 `: uint256 = self.` 或 `: address = self.` 等缓存模式
- 确认临时变量在后续逻辑中替代了存储访问
- 注意：Vyper 无内置自动优化，需手动缓存

## Classify

**漏洞研判：**
- 同一函数内对同一存储变量读取 ≥3 次，且无修改操作时，为明确的 Gas 浪费漏洞
- 循环内每次迭代都读取相同存储变量，为高优先级优化点

**误报识别：**
- 存储变量在两次读取间被修改（写入），缓存会导致逻辑错误
- 跨合约调用后的存储读取（外部调用可能改变状态）
- 存储变量仅被访问 1-2 次，优化收益不明显

**代码异味：**
- 读取次数为 2 次但函数 Gas 消耗不高的场景
- 只读视图函数中的重复读取（view 函数不消耗 Gas）

## Low risk

**低风险评级条件：**
1. **低频调用场景**：管理员函数、初始化函数等低频操作
2. **优化收益小**：仅重复读取 2 次，节省约 100 Gas（1 次 SLOAD ~100 Gas）
3. **可读性权衡**：缓存操作会显著降低代码可读性，且该函数逻辑复杂度高
4. **历史遗留代码**：使用旧版本 Vyper 编写，重构成本高于收益
5. **非关键路径**：错误处理分支、罕见条件分支内的重复读取

**注意**：即使为低风险，在高频交易函数（transfer、swap 等）中仍应修复。

---

## 审计专业技巧与实战经验

### 真实漏洞判断清单

**情景1：循环内的存储读取（100% 真实漏洞）**
```vyper
# 高风险：循环每次迭代都读取存储变量
@external
def batch_approve(spenders: DynArray[address, 100], amount: uint256):
    for spender in spenders:
        self.allowance[msg.sender][spender] = amount  # 每次都读取 amount？
        # 实际业务中可能读取 self.total_supply 或其他状态
```
**判断依据**：循环内每次迭代读取相同存储变量，且迭代次数不可预测，Gas 成本呈 O(n) 增长。建议在循环外缓存。

**情景2：跨外部调用的存储读取（多数为误报）**
```vyper
# 看似重复读取，实际不能缓存
@external
def execute_transaction(target: address, data: Bytes32):
    require_tx: uint256 = self.required_confirmations  # 读取1
    confirmed: uint256 = self._count_confirmations()   # 外部逻辑可能改变状态
    assert confirmed >= require_tx                      # 读取2
    # 第二次读取不能缓存，因为 _count_confirmations() 可能触发其他写入
```
**误报识别**：跨函数调用前后的存储读取通常无法安全缓存，除非能证明该存储变量不被其他调用修改。

**情景3：条件分支中的小范围重复（常见误报）**
```vyper
# 假阳性案例
@external
def check_balance(addr: address) -> bool:
    bal: uint256 = self.balances[addr]  # 读取1
    if bal > 0:
        return self.balances[addr] > 100  # 读取2（但条件分支内只有1次重复）
```
**判断标准**：同一存储变量仅在条件分支内重复 1-2 次，优化价值 < 50 Gas，列为低优先级。

### 误报陷阱识别技巧

**陷阱1：状态修改隐藏在函数调用中**
```vyper
# 危险的"优化"示例
@external
def risky_optimization(recipient: address, amount: uint256):
    balance: uint256 = self.balances[msg.sender]  # 缓存
    self.balances[msg.sender] = balance - amount
    self._notify_event()  # 隐藏的修改：可能修改 balance 关联字段
    assert self.balances[recipient] >= 0  # 使用缓存值会出错
```
**防范方案**：在缓存后、使用前检查是否有内部调用（即使是 internal 函数）；若有调用，需在调用后重新读取关键状态。

**陷阱2：数组/Map 索引变化的误识别**
```vyper
# 误识别为重复读取
balances: public(HashMap[address, uint256])

@external
def complex_transfer(addrs: DynArray[address, 10], amount: uint256):
    for addr in addrs:
        bal: uint256 = self.balances[addr]      # 不同的 addr，不是重复！
        self.balances[addr] = bal - amount
```
**判断要点**：HashMap/Array 访问的索引不同时，不算重复读取；仅当索引和存储变量都相同才是真重复。

**陷阱3：view/pure 函数中的"重复读取"**
```vyper
@view
def calculate_fees(amount: uint256) -> uint256:
    rate1: uint256 = self.fee_rate  # 读取1
    rate2: uint256 = self.fee_rate  # 读取2
    return amount * (rate1 + rate2) / 10000
```
**为何是误报**：view 函数不消耗额外 Gas 成本（仅查询），优化意义极小。审计时通常标记为 Info/QA 级别。

### 实战审计工作流

**第1步：快速扫描期（3分钟）**
1. 使用搜索工具扫描 `self.` 出现 ≥3 次的函数
2. 排除 view/pure 函数（0 优化价值）
3. 排除管理员级别函数（调用频率低）

**第2步：深度分析期（10分钟）**
1. 逐行追踪存储变量：每次读取是否在缓存变量后；缓存后是否存在外部调用
2. 计算潜在 Gas 节省：重复次数 × 100 Gas/SLOAD
3. 评估逻辑风险：缓存会否导致状态不一致

**第3步：优先级分类期（5分钟）**
- **High**：循环内多次读取，节省 >500 Gas
- **Medium**：函数内 3+ 次读取，无外部调用风险，节省 200-500 Gas
- **Low**：仅 2 次读取，或低频调用函数

### 常见审计误区

| 误区 | 正确判断 |
|------|--------|
| "所有重复读取都是 Gas 浪费" | 需考虑外部调用、状态修改风险 |
| "缓存到局部变量就万无一失" | 缓存后的外部调用可能导致状态不同步 |
| "view 函数中的重复读取也要优化" | view 函数无 Gas 成本，优化无意义 |
| "DynArray 遍历中的相同变量都该缓存" | 需区分：索引相同 vs 索引不同 |
| "每个 SLOAD 都是 100 Gas" | 冷读取 2100 Gas，热读取 100 Gas，需考虑上下文 |

### 报告示例

**真实漏洞报告**
```
标题：循环内重复读取 max_withdrawal 导致 Gas 浪费
位置：contract.vy:245 - batch_withdraw() 函数
描述：在循环内每次迭代都读取 self.max_withdrawal，
      循环100次时额外消耗 ~10,000 Gas
修复：在循环外缓存 max_withdrawal 为局部变量
```

**误报示例**
```
标题：重复读取 balances[addr] ❌ 不建议报告
原因：每次循环中 addr 变量不同，访问的 Map 键值不同，
      不属于重复读取同一状态的情况
```
