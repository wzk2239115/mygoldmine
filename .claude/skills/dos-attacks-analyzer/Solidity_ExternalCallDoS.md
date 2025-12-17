# Solidity - 外部调用 DoS (External Call DoS)

**漏洞简介**  
依赖外部调用成功才能继续执行业务逻辑，恶意合约可通过 revert、gas 耗尽或拒绝接收等方式阻止整个流程。常见于批量转账、奖励分发、退款机制、治理投票等场景。

## Details

**典型代码模式：**
```solidity
function distributeRewards(address[] memory recipients) external {
    for (uint i = 0; i < recipients.length; i++) {
        recipients[i].call{value: rewards[i]}("");  // 依赖外部调用成功
        require(success, "Transfer failed");  // 任意接收者失败导致整批失败
    }
}
```

**快速定位核心操作（L3-逐行读）：**
- 搜索关键词：`call{value:`、`transfer()`、`send()`、`delegatecall`、接口调用（`IERC20.transfer`、`callback`）
- 检查循环体内的外部调用：`for/while` + 外部地址交互
- 关注状态依赖：`require(success)`、`if (!success) revert`
- 追踪地址来源：用户可控地址数组、动态成员列表

**快速定位保护机制（L2-跳读）：**
- 拉取而非推送模式：是否采用 `withdraw()` 而非批量 `transfer()`
- 异常隔离：`try-catch` 包裹外部调用、记录失败但继续执行
- Gas 限制：`.call{gas: X}` 明确限制 Gas（防止恶意消耗）
- 白名单机制：外部地址受信任列表校验
- 失败补偿：失败时记录债权、允许后续重试

## Classify

**确认为漏洞：**
- 用户可控地址 + 循环批量调用 + 无异常处理 → 单点失败导致全部回滚
- 关键业务流程（清算、拍卖结算）被阻塞后无替代路径
- 受限于 Gas Limit 的大数组遍历外部调用

**归类为误报：**
- 外部调用对象为可信合约（官方代理、系统合约）且无用户可控输入
- 已采用拉取模式，用户自行触发提取
- 异常已妥善处理（try-catch + 失败记录）且不影响主流程

**代码异味：**
- 理论上存在 DoS 风险但业务场景中数组长度可控（< 10 且受管理员限制）
- 有保护机制但实现不完善（如 Gas 限制值设置不当）

## Low risk

- **受信地址集**：接收者列表为预设白名单（如核心团队多签地址）且数量极少
- **非关键路径**：被阻塞的功能有其他等价替代方案（如紧急暂停后管理员可手动分发）
- **Gas 优化场景**：批量操作仅为 Gas 优化，单笔操作接口同样开放
- **时间窗口限制**：外部调用对象为即将废弃的临时合约
- **金额可忽略**：涉及资金量极小且有上限保护（如积分而非主币）

## 审计专业技巧

### 1. 真实漏洞vs误报区分方法

**真实漏洞的三要素确认：**
1. **外部调用失败可导致回滚** - `require(success)` 或 `assert()`存在
2. **调用目标地址可被恶意控制** - 参数来自用户输入或未授权修改的状态
3. **无替代路径/后续补偿** - 失败后无 try-catch、无债权记录、无重试机制

示例识别真实漏洞：
```solidity
// ❌ 真实漏洞：三个条件全满足
address[] memory winners = getWinners();  // 用户可控
for (uint i = 0; i < winners.length; i++) {
    payable(winners[i]).transfer(prize);  // 无try-catch，transfer失败自动revert
}
// 若winners[i]为恶意合约拒收，整个分发失败
```

**误报常见场景：**
- 外部调用对象受严格授权（仅核心合约）
- 已实现 try-catch 但审计员未仔细检查
- 失败被记录到映射表允许后续重试（实际已补偿）

### 2. 实际案例对比分析

**案例A：Compound 清算 DoS（真实漏洞）**
- 清算人调用 `liquidateBorrow()` 并指定接收担保品的地址
- 若接收地址为恶意合约的回调陷阱，整个清算交易失败
- **风险**：清算队列堆积，坏账无法处理
- **修复**：使用 try-catch 捕获接收失败，分离清算与接收逻辑

**案例B：Uniswap V2 路由分发（非漏洞）**
- 批量转账使用 `safeTransfer()`（ERC20 库函数已包含异常处理）
- 转账目标为授权白名单合约
- **原因**：库函数内部 revert，但目标地址受控
- **结论**：实际风险可控

### 3. 审计检查清单

| 检查项 | 验证方法 | 风险等级判定 |
|--------|----------|------------|
| **循环体内外部调用** | 检查 for/while + call/transfer | 高优先级 |
| **地址来源** | trace 用户输入、合约参数、授权流程 | 决定是否真漏洞 |
| **失败处理** | 搜索 try-catch、require(success)、if(!success) | 决定是否可继续 |
| **数组长度上界** | 检查 require(arr.length <= MAX) | 评估 DoS 严重性 |
| **重入保护** | 检查 Mutex/ReentrancyGuard | 复合风险评估 |
| **Gas 消耗估算** | block.gaslimit - current.gas 与数组大小关系 | 实际可行性 |

### 4. 代码审查核心要点

**寻找隐藏的 require 失败点：**
```solidity
// 不仅直接 require 会导致 revert
address token = tokens[i];
uint amount = IERC20(token).balanceOf(address(this));
// 若 balanceOf 的 call 失败（低级别调用），同样回滚
```

**区分 Low-Level Call vs 接口调用：**
- `addr.call{value: x}("")` - 失败返回 false（需手动 require）
- `IERC20.transfer()` - 失败自动 revert（无需 require）
- `ITrusted(addr).safeOp()` - 取决于实现

**验证补偿机制有效性：**
```solidity
// ✅ 真实补偿：允许后续重试
if (!success) {
    pendingTransfers[addr] += amount;  // 记录债权
    emit TransferFailed(addr, amount);
}
// 提供独立提取函数
function claimPending() external {
    uint amount = pendingTransfers[msg.sender];
    delete pendingTransfers[msg.sender];
    payable(msg.sender).transfer(amount);  // 用户自行提取
}
```

### 5. 特殊场景误判防止

**场景1：批量操作中的单点失败**
- 误判为 Critical，实际 Medium：若只有 1 个失败而其他 99 个成功，但整体 revert
- 审计建议：检查交易原子性是否为业务需求

**场景2：Gas Limit 下的隐形 DoS**
- 审计易忽视：明面无 revert，但 OOG（Out of Gas）导致失败
- 检查方法：估算单次调用 gas、数组最大长度、block.gaslimit
- `expectedGas = baseGas + (arrayLength × gasPerCall) > blockGasLimit`？

**场景3：依赖链的风险传播**
```solidity
// A合约调用B合约，B再调用C
// 若C失败，B的异常处理可能掩盖真实失败
// 审计需追踪完整调用链
```

## 审计报告示例模板

```
# External Call DoS 审计发现

## 漏洞地址
[contract.sol:lineNumber]

## 严重程度判定
HIGH: ✓ 用户可控地址 ✓ 无异常处理 ✓ 关键路径
MEDIUM: ✓ 用户可控地址 ✗ 无异常处理 - 非关键 / 数组有上界
LOW: ✗ 用户可控地址 或 ✓ 完整异常处理

## 验证清单
- [ ] 追踪参数来源是否真正可控
- [ ] 确认 try-catch/require 的准确位置
- [ ] 验证失败补偿是否完整可用
- [ ] 估算实际可利用的参数范围
- [ ] 评估业务影响（关键路径 vs 边缘功能）

## 结论
真实漏洞 / 误报 / 低风险
```
