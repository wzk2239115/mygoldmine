# Solidity 提案执行权限绕过

提案执行函数缺少足够的权限检查、投票验证或时间锁保护，允许未经投票通过或未达到法定人数的提案被直接执行，导致协议参数被恶意修改或资金被盗。

## Details

**代码示例：**
```solidity
// ❌ 漏洞示例：执行函数缺少权限检查
contract VulnerableGovernor {
    enum ProposalState { Pending, Active, Defeated, Succeeded, Executed }

    struct Proposal {
        address[] targets;
        bytes[] calldatas;
        uint256 forVotes;
        uint256 againstVotes;
        ProposalState state;
    }

    mapping(uint256 => Proposal) public proposals;

    // ❌ 任何人都可以调用执行函数
    function execute(uint256 proposalId) external {
        Proposal storage proposal = proposals[proposalId];

        // ❌ 只检查状态，未验证投票结果
        require(proposal.state == ProposalState.Succeeded, "Not succeeded");

        proposal.state = ProposalState.Executed;

        // 执行提案中的所有调用
        for (uint256 i = 0; i < proposal.targets.length; i++) {
            (bool success, ) = proposal.targets[i].call(proposal.calldatas[i]);
            require(success, "Execution failed");
        }
    }

    // ❌ 状态转换逻辑缺失或可被绕过
    function setProposalState(uint256 proposalId, ProposalState newState) external {
        // 缺少访问控制，任何人可修改状态
        proposals[proposalId].state = newState;
    }
}

// ✅ 安全示例：完整的执行验证
contract SecureGovernor {
    ITimelock public timelock;
    uint256 public quorumNumerator = 4; // 4%

    struct Proposal {
        uint256 id;
        address proposer;
        address[] targets;
        uint256[] values;
        bytes[] calldatas;
        uint256 startBlock;
        uint256 endBlock;
        uint256 forVotes;
        uint256 againstVotes;
        bool executed;
        mapping(address => bool) hasVoted;
    }

    mapping(uint256 => Proposal) public proposals;

    function state(uint256 proposalId) public view returns (ProposalState) {
        Proposal storage proposal = proposals[proposalId];

        if (proposal.executed) {
            return ProposalState.Executed;
        }

        if (block.number <= proposal.endBlock) {
            return ProposalState.Active;
        }

        // ✅ 验证法定人数和投票结果
        uint256 totalSupply = token.totalSupplyAt(proposal.startBlock);
        uint256 quorum = (totalSupply * quorumNumerator) / 100;

        if (proposal.forVotes <= proposal.againstVotes ||
            proposal.forVotes < quorum) {
            return ProposalState.Defeated;
        }

        return ProposalState.Succeeded;
    }

    function execute(uint256 proposalId) external payable {
        // ✅ 严格验证提案状态
        require(state(proposalId) == ProposalState.Succeeded, "Not succeeded");

        Proposal storage proposal = proposals[proposalId];

        // ✅ 防止重复执行
        require(!proposal.executed, "Already executed");
        proposal.executed = true;

        // ✅ 通过时间锁执行（增加延迟，给用户退出时间）
        bytes32 txHash = timelock.hashOperationBatch(
            proposal.targets,
            proposal.values,
            proposal.calldatas,
            0,
            keccak256(bytes(proposal.id))
        );

        require(timelock.isOperationReady(txHash), "Timelock not ready");

        timelock.executeBatch(
            proposal.targets,
            proposal.values,
            proposal.calldatas,
            0,
            keccak256(bytes(proposal.id))
        );

        emit ProposalExecuted(proposalId);
    }
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索执行函数：`execute`、`executeProposal`、`queue`
- 检查状态验证：`require(state == Succeeded)`
- 查找投票结果验证：法定人数、支持率计算
- 定位时间锁集成：`timelock.execute`、`schedule`
- 搜索重复执行保护：`executed` 标志或状态检查

**快速定位保护机制技巧（L2-跳读）：**
- 查找 `TimelockController` 或 `Timelock` 合约引用
- 检查 `onlyGovernance` 或类似修饰符
- 验证状态机实现：Pending → Active → Succeeded → Queued → Executed
- 搜索 `quorum`、`proposalThreshold` 的计算
- 查看事件发射：`ProposalExecuted`、`ProposalQueued`

## Classify

**漏洞判定：**
- 执行函数缺少投票结果验证（未检查 forVotes > againstVotes）
- 未验证法定人数是否达标
- 缺少时间锁延迟，提案通过后可立即执行
- 状态转换逻辑可被绕过（如直接修改 state 变量）
- 缺少重复执行保护

**误报识别：**
- 使用 OpenZeppelin Governor 框架（内置完整验证）
- 执行函数正确调用 `state()` 并验证返回值
- 存在时间锁且 delay > 0
- 有独立的投票计数验证逻辑
- 提案执行通过可信的多签或时间锁合约

**代码异味：**
- 状态检查依赖可变的外部数据
- 投票期结束判断不准确（如使用 timestamp 而非 block.number）
- 时间锁延迟过短（< 1 天）
- 法定人数设置过低（< 1%）

## Low risk

**低风险场景：**
- 提案只能调用白名单内的安全函数（如参数微调）
- 执行需要多签批准，单一漏洞无法利用
- 存在紧急暂停机制，可在执行前阻止
- 时间锁延迟足够长（7+ 天），社区有时间应对
- 提案内容在执行前需要额外的链下审核
- 测试网合约或无实际资产的合约

## 审计专业技巧

### 关键审计清单

**第一阶段：快速扫描（5分钟）**
1. 定位 `execute` 函数的位置和访问控制
2. 检查是否使用 OpenZeppelin Governor（已审计框架）
3. 搜索 `Timelock` 合约的使用
4. 确认是否有 `onlyGovernance` 或 `onlyTimelock` 修饰符

**第二阶段：深度分析（15分钟）**
- 追踪提案状态转换的完整生命周期
- 验证法定人数和投票结果的计算逻辑
- 检查时间锁延迟设置（delay 值）
- 分析提案执行的权限链（谁可以调用、有哪些检查）
- 评估状态变量是否可被非法修改

**第三阶段：攻击模拟（10分钟）**
- 尝试构造绕过验证的攻击路径
- 检查是否可直接修改提案状态
- 验证是否可重复执行同一提案
- 测试边界条件（如投票数相等时的处理）

### 真实漏洞案例

**案例1：Tornado Cash Governor (2023-05，治理权被劫持)**
```solidity
// 简化的漏洞逻辑
contract TornadoGovernor {
    function execute(uint256 proposalId) external {
        Proposal storage proposal = proposals[proposalId];

        // ❌ 状态检查不严格
        require(proposal.state == ProposalState.AwaitingExecution);

        // 执行提案
        for (uint256 i = 0; i < proposal.targets.length; i++) {
            proposal.targets[i].call(proposal.calldatas[i]);
        }
    }

    // ❌ 漏洞：可通过其他方式修改状态
    function emergencyStop(uint256 proposalId) external {
        // 缺少权限检查，攻击者可将恶意提案设为 AwaitingExecution
        proposals[proposalId].state = ProposalState.AwaitingExecution;
    }
}
```

**案例2：自定义 Governor 缺少法定人数检查**
```solidity
// ❌ 危险实现
function execute(uint256 proposalId) external {
    Proposal storage proposal = proposals[proposalId];

    require(block.number > proposal.endBlock, "Voting not ended");

    // ❌ 只检查支持票是否大于反对票，未检查法定人数
    require(proposal.forVotes > proposal.againstVotes, "Not passed");

    // 攻击者可以用极少的票（如 1 票）通过提案
    _executeProposal(proposal);
}
```

### 防护最佳实践

**推荐方案1：使用 OpenZeppelin Governor + TimelockController**
```solidity
import "@openzeppelin/contracts/governance/Governor.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorTimelockControl.sol";

contract MyGovernor is Governor, GovernorTimelockControl {
    TimelockController private _timelock;

    constructor(TimelockController timelockAddress)
        Governor("MyGovernor")
        GovernorTimelockControl(timelockAddress)
    {
        _timelock = timelockAddress;
    }

    // 继承的 execute 函数已包含完整验证：
    // 1. 检查提案状态 (state() == Succeeded)
    // 2. 验证时间锁已准备好
    // 3. 防止重复执行
    // 4. 正确的事件发射

    function quorum(uint256 blockNumber)
        public
        view
        override
        returns (uint256)
    {
        // 设置合理的法定人数（如 4%）
        return (token.getPastTotalSupply(blockNumber) * 4) / 100;
    }
}
```

**推荐方案2：多层状态验证**
```solidity
contract DefenseInDepthGovernor {
    function execute(uint256 proposalId) external {
        Proposal storage proposal = proposals[proposalId];

        // 1. 检查提案未被执行
        require(!proposal.executed, "Already executed");

        // 2. 检查投票期已结束
        require(block.number > proposal.endBlock, "Voting active");

        // 3. 验证投票结果
        require(
            proposal.forVotes > proposal.againstVotes,
            "Proposal defeated"
        );

        // 4. 验证法定人数
        uint256 quorum = _quorum(proposal.startBlock);
        require(proposal.forVotes >= quorum, "Quorum not reached");

        // 5. 检查时间锁延迟
        require(
            block.timestamp >= proposal.eta,
            "Timelock delay not met"
        );

        // 6. 标记为已执行
        proposal.executed = true;

        // 7. 执行提案
        _execute(proposal);

        emit ProposalExecuted(proposalId);
    }

    function _execute(Proposal storage proposal) internal {
        for (uint256 i = 0; i < proposal.targets.length; i++) {
            (bool success, bytes memory returndata) = proposal.targets[i].call{
                value: proposal.values[i]
            }(proposal.calldatas[i]);

            // 验证每个调用都成功
            require(success, string(returndata));
        }
    }
}
```

**推荐方案3：使用专用的 Timelock**
```solidity
contract ProposalTimelock {
    uint256 public constant MINIMUM_DELAY = 2 days;
    uint256 public constant MAXIMUM_DELAY = 30 days;

    struct QueuedProposal {
        uint256 eta; // 最早执行时间
        bool executed;
    }

    mapping(bytes32 => QueuedProposal) public queuedProposals;

    function queueProposal(
        address[] memory targets,
        bytes[] memory calldatas,
        uint256 delay
    ) external onlyGovernor returns (bytes32) {
        require(delay >= MINIMUM_DELAY, "Delay too short");
        require(delay <= MAXIMUM_DELAY, "Delay too long");

        bytes32 txHash = keccak256(
            abi.encode(targets, calldatas)
        );

        require(
            queuedProposals[txHash].eta == 0,
            "Already queued"
        );

        uint256 eta = block.timestamp + delay;
        queuedProposals[txHash] = QueuedProposal(eta, false);

        emit ProposalQueued(txHash, eta);
        return txHash;
    }

    function executeProposal(
        address[] memory targets,
        bytes[] memory calldatas
    ) external onlyGovernor {
        bytes32 txHash = keccak256(abi.encode(targets, calldatas));
        QueuedProposal storage queued = queuedProposals[txHash];

        require(queued.eta != 0, "Not queued");
        require(!queued.executed, "Already executed");
        require(block.timestamp >= queued.eta, "Timelock not expired");

        queued.executed = true;

        for (uint256 i = 0; i < targets.length; i++) {
            (bool success, ) = targets[i].call(calldatas[i]);
            require(success, "Call failed");
        }

        emit ProposalExecuted(txHash);
    }
}
```

### 审计检查清单

| 检查项 | 高风险 | 中等风险 | 低风险 |
|--------|--------|----------|--------|
| 状态验证 | 无验证或可绕过 | 简单验证 | 完整状态机 |
| 法定人数 | 无检查 | < 1% | ≥ 4% |
| 投票结果 | 未验证 | 简单比较 | 严格计算 |
| 时间锁 | 无时间锁 | < 1 天 | ≥ 2 天 |
| 重复执行保护 | 无保护 | 状态检查 | executed 标志 + 状态 |
| 权限控制 | 任何人可调用 | 简单检查 | 多层验证 |

### 工具辅助检测

**Slither 检测**
```bash
slither . --detect missing-timelock
slither . --detect unprotected-execute
```

**Mythril 符号执行**
```bash
myth analyze governance.sol --execution-timeout 90
```

---

**参考资料：**
- [OpenZeppelin TimelockController](https://docs.openzeppelin.com/contracts/api/governance#TimelockController)
- [Compound Governor Bravo](https://github.com/compound-finance/compound-protocol/blob/master/contracts/Governance/GovernorBravoDelegate.sol)
- [治理攻击案例集](https://github.com/ComposableSecurity/SCSVS)
