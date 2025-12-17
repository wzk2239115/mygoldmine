# Vyper_FlashLoan_TokenBalanceAssumption

## 漏洞简述
Vyper 协议假设代币余额在单笔交易内保持相对稳定，未考虑闪电贷可在同一交易中瞬间注入/抽离巨额资金，导致基于余额计算的逻辑（如份额铸造、价格计算、奖励分配）被操纵。

## Details

**典型代码模式：**
```vyper
@external
def deposit():
    # 漏洞：直接读取当前余额计算份额
    current_balance: uint256 = ERC20(token).balanceOf(self)
    shares: uint256 = amount * total_shares / current_balance
    # 攻击者可在此前用闪电贷操纵 current_balance
```

**快速定位核心操作技巧（L3 逐行读）：**
- 搜索 `balanceOf(self)` 且用于除法/比例计算的位置
- 关注 `deposit/withdraw/swap/claim` 函数中的余额读取时机
- 检查余额是否在 `@external/@payable` 函数入口即快照
- 排查是否存在"余额差值"计算但缺少起始快照

**快速定位保护机制技巧（L2 跳读）：**
- 检查函数顶部是否有 `snapshot: uint256 = self.balance` 或 `ERC20.balanceOf(self)` 的缓存变量
- 搜索 `@nonreentrant` 装饰器（注意：仅防重入不防闪电贷）
- 查找 TWAP/Oracle 使用而非即时余额（如 `price_oracle.get_twap()`）
- 验证是否使用"转账前后差值"模式：`bal_before = balanceOf(self)` → `transfer` → `bal_after = balanceOf(self)`

## Classify

**漏洞判定标准：**
- 余额读取与价值计算直接关联且无时间加权/预言机校验
- 外部可通过闪电贷在同一交易内影响该余额读取结果
- 可导致实际经济损失（套利/超额铸造/抽干池子）

**误报场景：**
- 余额仅用于事件日志或视图函数，不影响状态变更
- 该函数已有 reentrancy guard 且协议设计明确禁止单交易多次调用
- 余额用于"最小阈值"检查而非精确计算（如 `require balance > MIN_LIQUIDITY`）

**代码异味：**
- 余额读取在非关键路径但存在潜在组合调用风险
- 有保护但实现不完整（如仅缓存代币A余额未缓存代币B）

## Low risk

- 余额假设仅影响 gas 优化或次要展示逻辑
- 池子总价值低于闪电贷操纵成本（如测试网/小型池）
- 存在其他硬约束限制单笔收益（如提款手续费 >5% 或单笔上限）
- 余额波动影响被限制在可接受范围内（如滑点保护兜底）

## 审计专业技巧与真实案例区分

### 真实漏洞的典型特征识别

**特征1：份额/价格直接基于瞬时余额**
```vyper
# 真实漏洞案例（USDC/USDT 双代币池）
def exchange_rate() -> uint256:
    usdc_balance: uint256 = ERC20(USDC).balanceOf(self)
    usdt_balance: uint256 = ERC20(USDT).balanceOf(self)
    return usdc_balance * 10**18 / usdt_balance  # 闪电贷可瞬时改变比例
```
**攻击路径**：闪电贷注入1000万 USDT → 执行 exchange_rate() → 获得套利额度 → 归还闪电贷
**经济损失**：10-50% 的流动性可在单笔交易内被掏空

**特征2：份额铸造/销毁缺少起始快照**
```vyper
# 易被忽视的漏洞（常见于初级审计报告误报）
def deposit(amount: uint256):
    # 错误思路：这里没有 balanceOf 调用，不是漏洞？
    # 实际：Vyper 的 ERC20 转账后 self.balance 自动更新
    response: bool = ERC20(token).transferFrom(msg.sender, self, amount)
    assert response

    # 关键：下一行计算时 self.balance 已被污染（可能包含闪电贷资金）
    new_shares = amount * self.total_shares / self.balance
    self.balances[msg.sender] += new_shares
```
**为什么这是真漏洞**：使用者以为 `amount` 等于实际入金，但闪电贷可在转账前后注入资金
**正确修复**：`bal_before = ERC20(token).balanceOf(self)` → `transfer` → 计算 `delta = ERC20(token).balanceOf(self) - bal_before`

### 常见的误报场景和区分方法

**误报案例1：View 函数中的余额读取**
```vyper
# 错误标记为漏洞（实际是误报）
@view
def get_current_ratio() -> uint256:
    return ERC20(tokenA).balanceOf(self) * 10**18 / ERC20(tokenB).balanceOf(self)
```
**为什么是误报**：View 函数不改变状态，即使被闪电贷污染也不影响协议安全性
**区分方法**：搜索该函数的所有调用点 (`--grep "get_current_ratio"`），检查返回值是否用于 state-change 逻辑

**误报案例2：存储变量缓存的双重保护**
```vyper
# 常被误判为漏洞（实际受保护）
def deposit(amount: uint256):
    self.last_balance = ERC20(token).balanceOf(self)
    response: bool = ERC20(token).transferFrom(msg.sender, self, amount)
    assert response

    # 虽然使用瞬时余额，但后续检验限制了损害
    delta = ERC20(token).balanceOf(self) - self.last_balance
    assert delta >= amount * 99 / 100  # 滑点保护：接受最多1%损失
    new_shares = amount * self.total_shares / self.total_supply
```
**为什么受保护**：即使闪电贷攻击，delta 滑点检查会拦截异常行为
**审计判定**：此时漏洞 Severity 从 CRITICAL 降至 LOW（取决于滑点阈值是否合理）

**误报案例3：预言机缓存已过期但函数仍可用**
```vyper
# 易被误判的场景
def claim_rewards():
    price: uint256 = self.cached_price  # 5分钟前缓存的价格
    current_balance: uint256 = ERC20(reward_token).balanceOf(self)

    # 虽然使用瞬时余额，但价格缓存 + 时间延迟共同限制操纵空间
    user_reward = current_balance * self.user_share * price / 10**18
```
**区分方法**：
- 检查价格更新频率 vs 交易包含时间（若 < 12秒差异则实际风险低）
- 验证 `cached_price` 是否通过 `@nonreentrant` 函数保护
- 计算攻击成本（闪电贷费率 0.09% + Gas）vs 可获利空间

### 审计工具链与检验流程

**第1步：自动化快速扫描（5分钟）**
```bash
# 关键词覆盖：识别90%的候选位置
grep -n "balanceOf(self)" src/contracts/*.vy | grep -E "(divide|mul|share|price|rate)"
grep -rn "\.balance\s*[*/]" src/contracts/  # 查找 Vyper 原生 balance 参与计算
```

**第2步：上下文确认（15分钟）**
- 对每个命中点：向上检查 3-5 行是否有"起始快照"
- 向下检查是否立即用于 state mutation （`self.xxx = `）或仅用于事件/查询
- 标记是否已有 `@nonreentrant` 或 `cached_price` 等防护

**第3步：经济可行性评估（10分钟）**
```python
# 计算每个候选漏洞的攻击成本
闪电贷成本 = 池子大小 * 0.09% + Gas(~50万)
可获利空间 = balanceOf 操纵幅度 * 协议利差 * 池子大小

若 可获利空间 < 闪电贷成本 * 1.5 → 实际风险 LOW
若 已有滑点保护且保护比 > 1% → 最多降级为 MEDIUM
```

**第4步：真漏洞的确认标记**
- [ ] 直接读取代币/原生余额用于比例/份额计算
- [ ] 无起始快照或起始快照与实际转账不对应
- [ ] 无时间加权或预言机校验
- [ ] 无滑点/价格保护机制
- [ ] 攻击成本 < 可获利空间 * 0.5

若以上 4 项以上满足 → CRITICAL/HIGH
若 3 项满足但有部分防护 → MEDIUM
其他情况 → LOW/误报

### 易被遗漏的变体

**变体1：间接余额操纵（ERC777/ERC1155 Hooks）**
```vyper
# 隐蔽的漏洞：代币转账触发 callback
def deposit():
    ERC20(token).transferFrom(msg.sender, self, amount)  # 如果 token 是 ERC777
    # 转账过程可能调用 tokensReceived hook，攻击者在 hook 中执行闪电贷归还逻辑
    new_shares = amount * total_shares / self.balance  # 此时 self.balance 已被污染！
```
**审计检验**：在处理代币时强制验证代币类型，或在 transferFrom 后立即快照余额

**变体2：多步骤余额污染**
```vyper
# 分布式攻击：多个函数共同被污染
def deposit(): pass  # 使用 self.balance
def swap(): pass     # 使用 self.balance
def withdraw(): pass # 使用 self.balance

# 攻击者可在单笔交易中同时调用这三个函数，每个函数都读取被污染的余额
```
**防御**：在交易入口使用全局的 `tx_snapshot`，或为每个涉及余额的函数添加独立的 `@nonreentrant`
