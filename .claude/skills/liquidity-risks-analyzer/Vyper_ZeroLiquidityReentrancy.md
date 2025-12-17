# Vyper 零流动性重入漏洞（Zero Liquidity Reentrancy）

## Details

**代码示例：**
```python
@external
@nonreentrant("lock")
def remove_liquidity(amount: uint256):
    # 流动性检查缺失
    self.balanceOf[msg.sender] -= amount
    send(msg.sender, amount)  # 外部调用
    # 余额为零时未暂停后续操作

@external
def swap(token_in: address, amount_in: uint256):
    # 当 total_supply == 0 时仍可执行
    price: uint256 = self.reserve_out / self.reserve_in  # 零除风险
    send(msg.sender, amount_out)
```

**快速定位核心操作（L2: 跳读）：**
- 搜索 `remove_liquidity`、`withdraw`、`burn` 等流动性销毁函数
- 关注外部调用（`send`、`raw_call`）前后的状态变更顺序
- 检查 `self.total_supply` 或 `self.reserve_*` 归零场景的处理逻辑
- 扫描带有 `@external` + 循环/回调的流动性操作组合

**快速定位保护机制（L3: 逐行读）：**
- 验证是否存在 `assert self.total_supply > MIN_LIQUIDITY` 类型的前置检查
- 确认 `@nonreentrant` 装饰器的锁范围是否覆盖完整操作链
- 追踪 `self.paused` 或 `self.emergency_stop` 标志位在零流动性时的启用逻辑
- 检查 CEI 模式（Checks-Effects-Interactions）是否严格执行：状态更新需在外部调用前完成
- 核查 Vyper 版本 < 0.3.4 的合约是否存在装饰器失效问题（已知漏洞 CVE-2023-XXXX）

## Classify

**漏洞判定标准：**
- 存在 `total_supply == 0` 或 `reserve == 0` 时的可重入路径，且攻击者可控制执行流
- 缺少流动性阈值检查导致除零错误或价格操纵
- `@nonreentrant` 锁作用域不足，未覆盖回调链

**误报场景：**
- 已通过 `assert` 或 `require` 强制 `MIN_LIQUIDITY > 0`（如 Uniswap 的 1000 wei 最小流动性）
- 外部调用目标为可信白名单合约且无回调能力
- 协议设计允许零流动性状态但已隔离高危操作（如只读查询）

**代码异味：**
- 流动性检查存在但位置不当（在外部调用后检查）
- 依赖 `balance` 而非 `reserve` 计算价格（闪电贷可绕过）
- 使用 `>=` 而非 `>` 导致边界值绕过

## Low risk

**降级为低风险的条件：**
- 仅影响价格查询/展示功能，不涉及资金转移
- 需要攻击者预先持有大量流动性份额才能触发（经济成本过高）
- 零流动性状态仅在初始化阶段存在且有时间锁保护
- 已部署的合约总锁仓量（TVL）< $10k 且无升级计划
- 存在其他保护层（如前端禁用、多签审批）可限制实际利用

## 审计专业技巧（Pro Tips）

### 1. 区分真实漏洞 vs 误报的关键指标

**真实漏洞的三层验证法：**
```python
# 危险模式 1: 缺乏状态先行检查
@external
def remove_liquidity(amount: uint256):
    self.balances[msg.sender] -= amount  # ⚠️ 效果立即发生
    log Transfer(msg.sender, empty(address), amount)
    send(msg.sender, amount)  # 外部调用触发回调
    # 攻击者在回调中调用 swap，此时 total_supply 已减少但尚未持久化

# 正确做法：先检查后转账
@external
@nonreentrant("lock")
def remove_liquidity(amount: uint256):
    assert self.total_supply > MIN_LIQUIDITY, "Insufficient"  # 前置守卫
    assert self.balances[msg.sender] >= amount, "Balance"

    new_supply: uint256 = self.total_supply - amount
    self.balances[msg.sender] -= amount
    self.total_supply = new_supply
    send(msg.sender, amount)  # 此时状态已安全更新
```

**危险模式 2: 零除问题隐藏在算术操作中**
```python
# 误报：这可能不是漏洞
price: uint256 = self.reserve_out / self.reserve_in
# 如果在交易执行前已通过 require(self.reserve_in > 0) 验证

# 真实漏洞：条件检查存在但位置错误
def swap(amount_in: uint256) -> uint256:
    amount_out: uint256 = amount_in * self.reserve_out / self.reserve_in  # 零除可能
    self.reserve_in += amount_in
    self.reserve_out -= amount_out
    assert self.reserve_out > 0  # ⚠️ 检查在使用之后！
    return amount_out
```

### 2. 实战技巧：真实案例分析

**案例 1: Curve StableSwap 的安全设计（教学参考）**
- Curve 通过恒定乘积结合 0 流动性检查成功避免漏洞
- 关键：`assert total_supply != 0` 在 `add_liquidity` 后立即执行
- 启示：阈值检查的位置与时机至关重要

**案例 2: Uniswap V2 的最小流动性锁定**
```python
# Uniswap V2 策略（Vyper 等价实现）
MIN_LIQUIDITY: constant(uint256) = 1000  # 永久锁定的份额

@external
def mint(to: address) -> uint256:
    if self.totalSupply == 0:
        liquidity: uint256 = sqrt(balance0 * balance1) - MIN_LIQUIDITY
        self._mint(empty(address), MIN_LIQUIDITY)  # 销毁第一批流动性
    # ...此后 total_supply 永不为零
```
这种设计使得即使持有 99.9% 流动性的攻击者销毁头寸，也无法触发零流动性重入。

### 3. 审计工具与自动化检测

**静态检查清单：**
1. 扫描所有 `@external` 且包含 `send`/`raw_call` 的函数对
2. 统计 `assert`/`require` 对 `total_supply` 和 `reserve_*` 的检查位置
3. 验证 `@nonreentrant` 覆盖范围是否包裹整个 CEI 链
4. 检测是否存在条件分支绕过流动性检查的路径

**动态测试建议：**
```python
# Foundry/Brownie 测试框架伪代码
def test_zero_liquidity_reentrancy():
    # 第一步：正常操作建立状态
    contract.add_liquidity(1000e18)

    # 第二步：提取所有流动性（触发零流动性）
    contract.remove_liquidity(contract.totalSupply())

    # 第三步：在回调中发起二次操作
    attack_contract.trigger_callback_attack()

    # 验证：检查余额、总供应量是否一致
    assert contract.totalSupply() == 0
    assert sum(contract.balances.values()) >= 0
```

### 4. 常见误报陷阱

**陷阱 1: 误判流动性检查的有效性**
- ❌ 错误：看到 `assert` 就认定安全
- ✅ 正确：验证 `assert` 作用于关键路径且无分支绕过

**陷阱 2: 忽视 Vyper 版本差异**
- Vyper < 0.3.4 的 `@nonreentrant` 存在已知漏洞（重入保护可被绕过）
- 需要检查 `compiler_version` 在合约首行的声明

**陷阱 3: 混淆"零流动性"与"低流动性"**
- 零流动性：`total_supply == 0`（极端情况，往往是漏洞）
- 低流动性：`total_supply < MIN_THRESHOLD`（常见状态，可能有额外保护）

### 5. 报告建议

**高风险判定的证据链：**
1. 演示清晰的攻击序列（步骤化描述）
2. 量化经济影响（最坏情况下可窃取金额）
3. 验证是否需要特殊条件（如初始化状态）
4. 提供修复建议（具体代码行）

**低风险/误报的充分理由：**
1. 列举所有可能的防护措施
2. 证明流动性检查的不可绕过性
3. 分析攻击成本 vs 收益比率
4. 指出协议设计中的自洽性
