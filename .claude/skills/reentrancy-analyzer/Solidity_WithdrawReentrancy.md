# Solidity 提取函数重入漏洞

资金提取函数在更新余额前进行外部调用，允许恶意合约在回调中递归调用提取函数，重复提取资金。

## Details

**代码示例：**
```solidity
function withdraw(uint256 amount) external {
    require(balances[msg.sender] >= amount);
    (bool success, ) = msg.sender.call{value: amount}(""); // 外部调用在前
    require(success);
    balances[msg.sender] -= amount; // 状态更新在后
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索 `call`/`send`/`transfer` + `value` 资金转账操作
- 搜索 `delegatecall` 外部代码执行点
- 定位 `balances[xxx] -=` / `balance -= ` 余额扣减语句
- 检查操作顺序：外部调用是否在状态更新之前
- 关注 `withdraw`/`claim`/`redeem` 等资金提取函数

**快速定位保护机制技巧（L2-跳读）：**
- 查找 `nonReentrant` 修饰符（OpenZeppelin ReentrancyGuard）
- 查找 `locked`/`_locked`/`mutex` 锁变量及其检查逻辑
- 验证 CEI 模式（Checks-Effects-Interactions）：状态更新是否先于外部调用
- 搜索 `require(!locked)` / `require(_status != ENTERED)` 等防重入检查
- 查看是否使用 `pull payment` 模式替代直接转账

## Classify

**漏洞判定：**
- 状态更新（余额扣减）发生在外部调用（资金转账）之后
- 无有效重入锁保护且允许递归调用
- 可导致资金被重复提取直至合约余额耗尽

**误报识别：**
- 已正确实施 CEI 模式（状态更新先于外部调用）
- 存在有效的 `nonReentrant` 修饰符保护
- 外部调用目标为可信合约（如 WETH）且不会回调
- 使用 `transfer`（2300 gas 限制）可防止复杂重入，但需注意 EIP-1884 后的兼容性

**代码异味：**
- 虽有重入锁但状态更新顺序不合理
- 依赖 `transfer` gas 限制而非显式保护机制
- 多个外部调用散落在状态更新前后

## Low risk

**低风险场景：**
- 提取金额已在外部调用前清零（如 `amount = balances[msg.sender]; balances[msg.sender] = 0`），即使重入也无可提取余额
- 仅读取状态不修改余额的查询类外部调用
- 提取金额来自函数参数且有独立的 `allowance` 机制约束，重入无法绕过授权额度
- 合约总锁仓量极小（测试合约）或已废弃不再使用
- 重入可能性存在但需额外前置条件（如特定时间窗口、多签授权等）且攻击成本超过收益

## 审计专业技巧

### 关键审计清单

**第一阶段：快速扫描（5分钟）**
1. 全局搜索所有资金转移函数（`withdraw`、`claim`、`redeem`、`transfer`、`burn`）
2. 统计 `.call{value:}` 的出现次数及位置
3. 检查是否存在 `nonReentrant` 或 `ReentrancyGuard` 引入
4. 扫描状态变量声明，查找 `locked`/`_locked`/`_guard` 等互斥锁变量

**第二阶段：深度分析（15分钟）**
- 为每个资金转移函数绘制时序图：检查点 → 效果 → 交互的顺序
- 追踪被调用的外部函数返回值处理（如未检查则存在失败重入的变种）
- 检查跨函数的状态依赖关系（A函数修改状态，B函数在外部调用前读取该状态）

**第三阶段：边界测试（10分钟）**
- 构造特殊的重入合约进行思维模拟
- 考虑多个合约间的调用链重入（外部调用不直接回调提取函数，但通过第三方回调）
- 验证 gas 限制、回退机制对防护的实际作用

### 真实漏洞 vs 误报的区分

**典型误报案例1：Transfer vs Call**
```solidity
// ❌ 被误判为漏洞，但实际是安全的
function withdraw(uint256 amount) external {
    require(balances[msg.sender] >= amount);
    balances[msg.sender] -= amount;  // 状态先更新
    msg.sender.transfer(amount);      // transfer 只传 2300 gas，无法发起重入
}
```
**审计要点：** `transfer` 在 EIP-1884 之前确实安全（2300 gas 不足以执行任何存储写），但现在某些合约（含代理）可能超过这个限制。应检查：
- 接收方是否为代理合约
- 是否有备选路由导致高 gas 消耗

**典型误报案例2：调用可信合约**
```solidity
// ❌ 被误判为漏洞，但 WETH 不会恶意回调
function withdrawViaWETH(uint256 amount) external {
    require(balances[msg.sender] >= amount);
    IWETH(WETH_ADDRESS).withdraw(amount);  // WETH 是审计过的标准合约
    balances[msg.sender] -= amount;
}
```
**审计要点：** 需验证目标地址是否真的是 WETH 官方合约（可能被替换）、是否在已知的安全白名单中。不能仅凭代码审查判断。

**真实漏洞案例：隐藏的重入路径**
```solidity
// ✅ 真实漏洞：通过利息分配函数重入
mapping(address => uint256) public balances;
mapping(address => uint256) public interests;

function withdraw(uint256 amount) external {
    require(balances[msg.sender] >= amount);
    (bool ok, ) = msg.sender.call{value: amount}("");  // 外部调用
    balances[msg.sender] -= amount;                     // 状态更新在后
}

function claimInterest() external {
    // 攻击者在 withdraw 的回调中调用此函数
    uint256 interest = interests[msg.sender];
    interests[msg.sender] = 0;
    (bool ok, ) = msg.sender.call{value: interest}("");
    // 如果 withdraw 尚未扣减 balances，攻击者可再次调用 withdraw
}
```

### 实践审计指标

| 指标 | 高风险 | 中等风险 | 低风险 |
|------|--------|----------|--------|
| CEI 遵循 | 不遵循（外部调用在前） | 部分遵循（多个 call 混乱） | 完全遵循 |
| 重入锁 | 无 | 有但不正确使用 | 有且正确应用 |
| 资金来源 | 用户可控（参数）| 状态变量但有时间依赖 | 参数受 allowance 约束 |
| 防护深度 | 单一防护或无 | 两种防护组合 | CEI+锁+低级操作验证 |

### 常见漏报陷阱

1. **递归 delegatecall**：`delegatecall` 在重入中的危害大于 `call`，需单独标记
2. **跨合约重入**：主合约没问题但调用的库合约有漏洞
3. **View 函数的虚假安全**：标记为 view 的函数被 delegatecall 执行时可修改状态
4. **Fallback 函数陷阱**：合约有 fallback 接收 ETH 时，发送方可在 fallback 中重入
