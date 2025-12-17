# Solidity 投票权重计算错误

投票权重计算使用当前余额而非快照，或计算逻辑存在缺陷，允许代币在投票期间转移以重复投票，或通过其他方式操纵投票权重。

## Details

**代码示例：**
```solidity
// ❌ 漏洞示例：代币可转移以重复投票
contract VulnerableGovernor {
    mapping(uint256 => mapping(address => bool)) public hasVoted;

    function vote(uint256 proposalId, bool support) external {
        require(!hasVoted[proposalId][msg.sender], "Already voted");

        uint256 weight = token.balanceOf(msg.sender);
        // ... 记录投票

        hasVoted[proposalId][msg.sender] = true;
    }
}

// ✅ 攻击场景：代币循环转移
contract Attacker {
    address[] public puppets; // 10个傀儡账户

    function multiVote(uint256 proposalId) external {
        uint256 tokens = 1000 * 1e18;

        // 1. 用 1000 代币在账户0投票
        token.transfer(puppets[0], tokens);
        governor.vote(proposalId, true); // puppets[0] 投票

        // 2. 转给账户1，再投一次
        token.transferFrom(puppets[0], puppets[1], tokens);
        governor.vote(proposalId, true); // puppets[1] 投票

        // 3. 重复 10 次 = 用 1000 代币获得 10000 投票权
    }
}

// ✅ 安全示例：使用检查点快照
contract SecureGovernor {
    using Checkpoints for Checkpoints.History;

    struct Proposal {
        uint256 snapshot; // 快照区块号
        mapping(address => bool) hasVoted;
    }

    function vote(uint256 proposalId, bool support) external {
        Proposal storage proposal = proposals[proposalId];
        require(!proposal.hasVoted[msg.sender], "Already voted");

        // ✅ 使用快照时的余额，转移代币无效
        uint256 weight = token.getPastVotes(
            msg.sender,
            proposal.snapshot
        );

        require(weight > 0, "No voting power");
        // ... 记录投票
    }
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索投票权计算：`balanceOf`、`votingPower`、`getVotes`
- 检查是否使用历史数据：`getPastVotes`、`getPastTotalSupply`
- 查找代币转移限制：投票期间是否禁止 `transfer`
- 检查委托机制：`delegates`、`delegate` 函数
- 验证重复投票保护：`hasVoted` 映射的键是否包含地址

**快速定位保护机制技巧（L2-跳读）：**
- 查找 `ERC20Votes`、`ERC20Snapshot` 接口
- 检查 `Checkpoints` 库的使用
- 搜索 `_snapshot()`、`clock()` 函数
- 验证投票记录的键设计（proposalId + voter）
- 查看代币合约是否有 `_beforeTokenTransfer` 钩子

## Classify

**漏洞判定：**
- 投票权基于实时余额，代币可在投票期间自由转移
- 缺少快照机制或快照未被使用
- 投票记录仅基于地址，未考虑代币转移
- 委托投票权重可被实时操纵
- 存在算术错误导致权重计算不准确（如溢出）

**误报识别：**
- 使用 `ERC20Votes.getPastVotes()` 获取历史投票权
- 代币在投票期间被锁定（通过质押或冻结机制）
- 投票需要提前注册且注册时记录快照
- 委托关系有延迟生效机制
- 使用 Checkpoints 库管理历史数据

**代码异味：**
- 同时存在快照和实时余额两种计算方式
- 快照创建在投票开始后
- 投票权重依赖可变的外部合约数据
- 代币 decimals 不一致导致精度问题

## Low risk

**低风险场景：**
- 单次投票成本极高（如需要销毁代币）
- 代币流动性极低，无法快速转移
- 投票窗口极短（< 1 区块），无法在期间转移
- 存在 Sybil 攻击成本（如需要 KYC）
- 投票结果仅供参考，不直接执行链上操作

## 审计专业技巧

### 真实案例

**案例：重复投票攻击**
```solidity
// 简化的真实漏洞
function vote(uint256 proposalId, bool support) external {
    require(!voted[proposalId][msg.sender]); // ✅ 有检查

    uint256 votes = balanceOf(msg.sender); // ❌ 但使用实时余额

    if (support) {
        proposals[proposalId].yesVotes += votes;
    } else {
        proposals[proposalId].noVotes += votes;
    }

    voted[proposalId][msg.sender] = true;
}

// 攻击方式：
// 用户A持有1000代币
// 1. A投票（1000票支持）
// 2. A将代币转给B
// 3. B投票（1000票支持）
// 结果：1000代币获得2000票
```

### 防护最佳实践

**方案1：ERC20Votes标准**
```solidity
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Votes.sol";

contract GovernanceToken is ERC20Votes {
    constructor() ERC20("Gov", "GOV") ERC20Permit("Gov") {}

    // 自动维护检查点，支持 getPastVotes()
}

contract Governor {
    function vote(uint256 proposalId, bool support) external {
        Proposal storage p = proposals[proposalId];

        // ✅ 使用提案创建时的快照
        uint256 votes = token.getPastVotes(msg.sender, p.snapshot);
        require(votes > 0, "No voting power");

        // 投票逻辑...
    }
}
```

**方案2：质押锁定机制**
```solidity
contract StakedVoting {
    struct Stake {
        uint256 amount;
        uint256 lockedUntil;
    }

    mapping(address => Stake) public stakes;

    function stakeForVoting(uint256 amount, uint256 lockDuration) external {
        token.transferFrom(msg.sender, address(this), amount);

        stakes[msg.sender] = Stake({
            amount: stakes[msg.sender].amount + amount,
            lockedUntil: block.timestamp + lockDuration
        });
    }

    function vote(uint256 proposalId) external {
        uint256 votes = stakes[msg.sender].amount;
        require(votes > 0, "No staked tokens");

        // 代币被锁定，无法转移以重复投票
    }

    function unstake() external {
        Stake storage s = stakes[msg.sender];
        require(block.timestamp >= s.lockedUntil, "Still locked");

        token.transfer(msg.sender, s.amount);
        delete stakes[msg.sender];
    }
}
```

**方案3：双重验证机制**
```solidity
contract DoubleCheckGovernor {
    function vote(uint256 proposalId, bool support) external {
        Proposal storage p = proposals[proposalId];

        // 检查1：地址未投过票
        require(!p.hasVoted[msg.sender], "Already voted");

        // 检查2：使用快照余额
        uint256 historicalBalance = token.balanceOfAt(
            msg.sender,
            p.snapshotBlock
        );

        // 检查3：当前余额 >= 快照余额（防止投票后卖出）
        uint256 currentBalance = token.balanceOf(msg.sender);
        require(
            currentBalance >= historicalBalance,
            "Token sold after snapshot"
        );

        // 使用历史余额作为投票权重
        uint256 votes = historicalBalance;

        p.hasVoted[msg.sender] = true;
        // 记录投票...
    }
}
```

### 检查清单

| 检查项 | 高风险 | 中等风险 | 低风险 |
|--------|--------|----------|--------|
| 权重来源 | balanceOf(current) | 自定义计算 | getPastVotes |
| 代币转移 | 无限制 | 部分限制 | 投票期锁定 |
| 快照机制 | 无快照 | 有但未使用 | 正确使用 |
| 重复保护 | 仅检查地址 | 地址+代币量 | 地址+快照 |
| 委托机制 | 实时生效 | 延迟1区块 | 快照时确定 |

---

**参考资料：**
- [ERC-20 Votes扩展标准](https://docs.openzeppelin.com/contracts/api/token/erc20#ERC20Votes)
- [Checkpoints库文档](https://docs.openzeppelin.com/contracts/api/utils#Checkpoints)
