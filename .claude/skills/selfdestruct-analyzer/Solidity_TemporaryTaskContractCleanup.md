# Solidity - 临时任务合约清理 (Temporary Task Contract Cleanup)

**漏洞成因**：一次性任务合约执行完毕后调用 `selfdestruct` 自毁，但在销毁前未妥善处理剩余资金、未完成的状态转移或对外部合约的依赖关系，导致资金锁死、状态不一致或逻辑中断。

## Details

**代码示例**：
```solidity
contract TemporaryTask {
    address public owner;
    mapping(address => uint256) public deposits;
    bool public taskCompleted;
    
    function completeTask() external {
        // 执行任务逻辑
        taskCompleted = true;
        selfdestruct(payable(owner)); // 直接自毁，未退还用户deposits
    }
}
```

**快速定位核心操作（L2 跳读）**：
- 搜索 `selfdestruct` 关键词，定位销毁调用点
- 向上追溯触发条件：检查是否有任务完成标志位（如 `taskCompleted`、`isFinished`）
- 向下检查销毁前操作：是否清空所有映射、数组等状态变量
- 查看 `selfdestruct` 接收地址：是否为 `owner`/`creator`/固定地址，资金流向是否合理

**快速定位保护机制（L3 逐行读）**：
- 检查销毁前是否有资金分配逻辑：遍历所有债权人/存款人执行退款
- 确认余额检查：`require(address(this).balance == 0)` 或 `require(allFundsDistributed)`
- 验证状态清零：关键映射是否通过循环或批量操作清空
- 查找事件日志：`event SelfDestructed(address recipient, uint256 amount)` 记录销毁详情
- 检查时间锁或冷静期：是否有延迟销毁机制防止误操作

## Classify

**漏洞判定**：
- 合约持有用户资金（deposits、staking、escrow）且销毁时未全部退还 → **高危漏洞**
- 外部合约依赖该合约地址进行回调或状态查询，销毁后导致外部合约功能失效 → **中危漏洞**
- 销毁时机可被非授权角色触发，或触发条件未充分验证（如任务实际未完成） → **高危漏洞**

**误报判定**：
- 合约设计为单次使用且明确声明不接收资金（无 payable、无 receive/fallback）
- 销毁前已通过多笔交易完成所有资金清算，链上可验证余额为零
- 合约仅作为临时数据存储，无外部依赖且状态不影响其他合约

**代码异味**：
- 虽然有退款逻辑但依赖用户主动提取（withdraw模式），销毁时未强制推送剩余资金
- 缺少销毁事件日志，无法链下追踪资金去向
- 销毁逻辑与业务逻辑耦合在同一函数，未做权限隔离

## Low risk

**低风险场景**：
- 合约生命周期明确（如众筹失败后7天销毁），且在销毁窗口期内用户有充足时间取回资金
- 销毁接收地址为预设的公共金库或慈善地址，资金去向透明且有治理机制
- 合约仅处理微小金额（如测试币、积分），即使资金遗留也不构成经济损失
- 存在平行的备份合约或状态迁移方案，销毁不影响系统整体可用性
- 销毁操作需多签或DAO投票，且有公示期和应急取消机制

## 审计专业技巧与区分指南

### 1. **真实漏洞的三大特征识别**

**特征A：多层级资金持有无清算路径**
```solidity
// 【真实漏洞】嵌套映射未清空导致资金永久锁死
contract VulnerableVault {
    mapping(address => mapping(uint256 => uint256)) public stakes;

    function liquidateAll() external onlyOwner {
        selfdestruct(payable(owner));  // stakes 映射未清空！
    }
}

// 【正确做法】循环清算或分布式清零
function liquidateAll() external onlyOwner {
    // 方案1：调用方负责逐个提取
    // 方案2：销毁前强制清算所有持有者
    for (uint i = 0; i < activeUsers.length; i++) {
        (bool success, ) = activeUsers[i].call{value: stakes[activeUsers[i]][lastEpoch]}("");
        require(success, "Refund failed");
        delete stakes[activeUsers[i]][lastEpoch];
    }
    selfdestruct(payable(owner));
}
```

**特征B：触发权限控制不足导致抢跑**
```solidity
// 【真实漏洞】任何人可提前触发销毁
contract RaceCondition {
    bool public taskDone;

    function completeAndDestroy() external {
        require(taskDone, "Task not done");
        selfdestruct(payable(msg.sender));  // 高危！msg.sender 可随意指定
    }
}

// 【区分方法】检查销毁前的 require 条件强度
// - require(msg.sender == owner) ✓ 安全
// - require(taskDone && block.timestamp > deadline) ✓ 相对安全
// - require(taskDone) ✗ 不足（taskDone 可被攻击者提前设置）
```

**特征C：外部合约依赖导致级联崩溃**
```solidity
// 【真实漏洞】Aggregator 依赖 Oracle 地址不变
contract Aggregator {
    address public oracle;

    function fetchPrice() external returns (uint) {
        return IOracle(oracle).getPrice();  // 如果 oracle 被 selfdestruct，此调用失败
    }
}

contract VulnerableOracle {
    function selfDestructAndRefund() external {
        selfdestruct(payable(owner));  // Aggregator 将崩溃
    }
}

// 【审计方法】
// 1. 搜索所有外部调用该合约的地址：etherscan API / on-chain analysis
// 2. 检查依赖方是否做了地址变更预案（proxy pattern）
// 3. 评估销毁事件是否有足够公示期通知依赖方
```

### 2. **常见误报vs真实漏洞的对比案例**

| 场景 | 初判 | 关键检查点 | 最终判定 |
|------|------|---------|--------|
| 合约有 `selfdestruct` | ⚠️ 可疑 | 是否接收用户资金？销毁前是否清空所有state? | ✓ 安全（无资金持有） |
| 销毁时 `msg.sender == beneficiary` | ⚠️ 可疑 | beneficiary 是否 == owner 或通过 multisig 控制？ | ✓ 安全（权限足够） |
| 销毁接收 `address(this).balance` 的某个钱包 | ⚠️ 可疑 | 这个钱包是否是DAO金库或明确的受益人？是否可变？ | ✗ 高危（如可变且未授权） |
| 合约代码中有 `withdrawAll()` + `selfdestruct` | ⚠️ 中等 | withdrawAll 是 pull 还是 push 模式？有没有 fallback? | ✗ 高危（pull模式+无fallback） |

### 3. **链上验证技巧（实战审计必备）**

**技巧1：验证资金流向可追溯性**
```bash
# 对于已执行的 selfdestruct，检查：
1. etherscan / 区块链浏览器：查询该合约地址的最后交易
2. 搜索 Destroyed 标签：确认销毁时间和接收地址
3. 追踪接收地址的后续转账：是否流向明确账户（交易所/多签）
4. 检查是否有 "Contract destroyed" 的官方公告事件日志
```

**技巧2：多签/DAO 控制验证**
```solidity
// 审计检查清单：
// ✓ selfdestruct 调用者是否受 onlyOwner 保护？
// ✓ owner 是否为 Timelock / GnosisSafe / DAO Governor?
// ✓ 是否存在 timelock 延迟（如 48 小时公示期）？
// ✓ 是否有在野的 governance 提案记录证明用户事先知晓？

contract SafeSelfdestruct {
    address public governance;
    uint public destructionProposedAt;
    uint constant TIMELOCK = 2 days;

    function proposeDestruction() external {
        require(msg.sender == governance);
        destructionProposedAt = block.timestamp;
    }

    function executeDestruction(address recipient) external {
        require(block.timestamp >= destructionProposedAt + TIMELOCK, "Timelock not expired");
        selfdestruct(payable(recipient));
    }
}
```

### 4. **误报排除的上下文规则**

**规则1：单次使用合约（Factory模式）**
```solidity
// 【通常安全】：临时合约只用一次，立即销毁，不持有资金
contract OneTimeTask {
    constructor(address target, bytes calldata data) {
        (bool ok, ) = target.call(data);
        require(ok);
        selfdestruct(payable(msg.sender));  // 立即销毁，资金未曾进入
    }
}
```

**规则2：测试网络特定合约**
```solidity
// 【排除误报】检查：
// 1. 代码注释中是否明确标注 "only for testnet"？
// 2. 是否在 mainnet 部署？（Etherscan 标签）
// 3. 是否设有 testnet-only 标志？
if (block.chainid == 5) {  // Goerli testnet only
    selfdestruct(payable(owner));  // 非误报，合理设计
}
```

**规则3：资金已提前清算的批准期**
```solidity
// 【区分关键】：检查销毁日志前的历史交易
event UserRefunded(address indexed user, uint amount);

function liquidate() external {
    // 已通过多笔交易完成所有用户退款（链上可验证）
    // block.timestamp 前 7 天内所有用户都已 withdraw
    require(lastUserWithdrawTime + 7 days <= block.timestamp);
    selfdestruct(payable(treasury));  // 安全：余额已为零
}
```

### 5. **审计工作流（快速决策树）**

```
发现 selfdestruct ⬇
│
├─ 合约接收资金吗？
│  ├─ NO → 检查销毁权限 ⬇ （很可能安全）
│  └─ YES ⬇
│
├─ 销毁前完整清算所有资金？
│  ├─ YES ⬇ 检查清算逻辑是否完备
│  │  ├─ 完备（遍历所有债权人） → 检查销毁权限
│  │  └─ 不完备（只清算部分） → 【真实漏洞】
│  └─ NO ⬇
│     ├─ 是否 pull 模式（用户主动提取）→ 检查是否有 fallback
│     │  ├─ 有 fallback → 【可能误报】检查公示期
│     │  └─ 无 fallback → 【真实漏洞】
│     └─ 是否 push 模式（合约主动转账） → 【真实漏洞】
│
└─ 销毁权限充分吗？
   ├─ onlyOwner 且 owner 是 multisig → 【较安全】
   ├─ onlyGovernance + timelock → 【安全】
   └─ 条件较弱或权限可绕过 → 【漏洞】
```

### 6. **审计报告中的表述规范**

**误报说明模板**：
```
本项标记为"信息" 而非"漏洞"，原因：
1. 合约未接收用户资金，selfdestruct 仅用于代码清理
2. 销毁操作受到 2 位多签 gnosis safe 控制，需要 48 小时 timelock
3. 链上记录显示销毁前所有用户已完成资金提取
4. 建议：在销毁事件中记录最终日志以增强可追踪性
```

**漏洞说明模板**：
```
【高危】合约销毁时用户资金未完整清算：
1. 合约接收用户通过 deposit() 存入的资金
2. destroy() 函数直接 selfdestruct(owner) 不检查余额
3. 用户如未及时提取，资金将永久锁死在销毁地址
4. 攻击场景：owner 恶意加速销毁、用户网络拥堵无法提取
5. 修复：销毁前 require(address(this).balance == 0) 或循环退款
```
