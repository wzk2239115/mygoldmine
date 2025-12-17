# Vyper 转账 Revert DoS

批量转账时单个接收方失败导致整批交易回滚，恶意用户可通过部署恶意合约或触发 `__default__` 函数 revert 阻塞资金分发。

## Details

**代码特征**：
```vyper
@external
def distribute_rewards(recipients: DynArray[address, 100], amounts: DynArray[uint256, 100]):
    for i in range(len(recipients)):
        send(recipients[i], amounts[i])  # 单个失败全部回滚
```

**快速定位核心操作（L2：跳读）**：
- 扫描 `for` / `range` + `send` / `raw_call` 组合模式
- 关注 `DynArray[address, ...]` 参数的批量处理逻辑
- 检查 `__default__` 函数是否存在外部调用点

**快速定位保护机制（L3：逐行读）**：
- 是否使用 `raw_call(..., revert_on_failure=False)` 忽略失败
- 是否预先校验接收方类型（`extcodesize` 或白名单）
- 是否采用拉取模式（用户主动 `claim` 而非推送）
- 是否设置单笔操作的 gas 上限（如 `gas=2300`）

## Classify

**漏洞研判**：
- 批量操作中任一失败可阻塞全局状态更新（如分红、奖励发放）
- 攻击者可控制接收方地址（合约部署或参数注入）
- 无重试机制或跳过失败项的容错逻辑

**误报识别**：
- 接收方为已验证的 EOA 地址列表（非合约）
- 循环内仅更新状态而非执行外部调用
- 单次操作有独立事务边界（如事件队列模式）

**代码异味**：
- 批量处理但有完善重试机制或失败补偿
- 循环次数动态且未设置上限（潜在 gas 耗尽 DoS）

## Low risk

**降级场景**：
- 接收方地址由可信管理员预设，用户无法注入恶意合约
- 批量操作仅限管理员调用且有链下监控
- 合约内置接收方白名单且定期审核
- 失败时触发事件记录，管理员可手动重新分配
- 批量操作前强制检查 `extcodesize`，拒绝合约地址

## 审计专业技巧

### 1. 真实漏洞的特征识别

**关键信号**：
- 用户可直接或间接控制接收方列表（参数传入或从公开映射读取）
- 循环内部执行无条件转账：`send()` / `raw_call(..., revert_on_failure=True)`
- 转账后有状态修改（如标记为已分配）但前置检查不足
- 无 try-catch 或错误处理机制，单点失败导致整个交易回滚

**真实案例特征**：
```vyper
# 真实漏洞示例
@external
def batch_transfer(recipients: DynArray[address, 100], amounts: DynArray[uint256, 100]):
    assert len(recipients) == len(amounts)
    for i in range(len(recipients)):
        # 攻击者可在 recipients[i] 部署恶意合约，其 __default__ revert
        send(recipients[i], amounts[i])
        self.distributed[recipients[i]] += amounts[i]  # 永远到不了
```

### 2. 常见误报陷阱与排查方法

**误报案例1：管理员白名单**
- 看似风险：循环遍历接收地址列表
- 关键检查：是否来自 `owner_only` 或 `admin_only` 权限控制
- 排查：追踪列表初始化源，确认非用户可控
```vyper
# 不是漏洞
owner_addresses: public(DynArray[address, 50])

@external
def set_recipients(new_list: DynArray[address, 50]):
    assert msg.sender == self.owner  # 权限检查
    self.owner_addresses = new_list  # 只有 owner 可注入
```

**误报案例2：内部账户转账**
- 看似风险：批量账户余额更新
- 关键检查：是否涉及 ETH/token 真实转账或仅内部账簿更新
- 排查：确认无外部调用，纯粹的状态修改
```vyper
# 不是漏洞（仅内部账簿）
@external
def distribute_internal_credits(accounts: DynArray[address, 100], credits: DynArray[uint256, 100]):
    for i in range(len(accounts)):
        self.balance[accounts[i]] += credits[i]  # 无外部调用，无 revert 风险
```

**误报案例3：预校验机制**
- 看似风险：批量转账
- 关键检查：是否在循环前已检查所有接收方
- 排查：`extcodesize` 或 EIP-1052 检查是否在循环前执行
```vyper
# 安全实现
@external
def safe_batch_transfer(recipients: DynArray[address, 50], amounts: DynArray[uint256, 50]):
    # 前置校验所有接收方
    for i in range(len(recipients)):
        assert extcodesize(recipients[i]) == 0, "No contracts allowed"
    # 再执行转账
    for i in range(len(recipients)):
        send(recipients[i], amounts[i])
```

### 3. 审计检查清单

**第一层（快速判断）**：
- [ ] 是否存在 `for/while` + `send/raw_call` 的组合
- [ ] 接收方是否来自参数、用户输入或公开映射
- [ ] 循环中是否有无条件转账或外部调用

**第二层（深度分析）**：
- [ ] 权限控制：该函数谁可调用（all/owner/whitelisted）
- [ ] 失败处理：转账失败时是否 revert 整个交易
- [ ] 校验时机：是否在循环前预校验接收方
- [ ] 状态一致性：转账失败时余额更新是否会不一致

**第三层（环境验证）**：
- [ ] 该函数在生产环境是否实际被调用
- [ ] 接收方列表是否有历史变更记录
- [ ] 是否有链上/链下监控告警

### 4. 易混淆的边界场景

**场景A：限制循环次数的批量操作**
```vyper
@external
def transfer_to_top_10(recipients: DynArray[address, 10]):  # 固定上限
    for i in range(len(recipients)):  # 最多 10 次
        send(recipients[i], self.balance / 10)
```
- 风险评估：仍是真实漏洞，上限不能消除 revert DoS 威胁

**场景B：失败跳过的实现**
```vyper
@external
def safe_distribute(recipients: DynArray[address, 100]):
    for i in range(len(recipients)):
        # 可以手动实现 try-catch 逻辑
        if raw_call(recipients[i], b"", value=1 ether, revert_on_failure=False):
            self.success_count += 1
        # 失败不 revert，继续下一个
```
- 风险评估：已降级，单个失败不阻塞整体

### 5. 现实审计经验总结

**高风险信号组合**（真实漏洞概率 >80%）：
1. 用户参数 + 无预校验 + 无失败处理 + 状态修改
2. 循环次数动态（DynArray）+ 无上限 + 外部调用
3. 多链合约且跨链 gas 成本差异大（某链易 revert）

**快速降级信号**（误报概率 >70%）：
1. 接收方来自 `self.owner_list` 或经 `onlyOwner` 修饰的初始化
2. 循环前存在显式的 `assert extcodesize(...) == 0` 检查
3. 循环内仅有状态修改，无外部调用（`send/raw_call`）
4. 函数调用频率极低（如年度一次的空投）
