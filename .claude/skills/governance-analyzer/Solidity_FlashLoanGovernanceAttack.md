# Solidity 闪电贷投票攻击

攻击者通过闪电贷临时获取大量治理代币，在单笔交易内操纵投票结果，投票结束后归还代币，从而以极低成本控制治理决策。

## Details

**代码示例：**
```solidity
// ❌ 漏洞示例：基于实时余额的投票权
contract VulnerableGovernor {
    IERC20 public governanceToken;

    struct Proposal {
        uint256 forVotes;
        uint256 againstVotes;
        mapping(address => bool) hasVoted;
    }

    mapping(uint256 => Proposal) public proposals;

    // 使用当前余额作为投票权重
    function vote(uint256 proposalId, bool support) external {
        require(!proposals[proposalId].hasVoted[msg.sender], "Already voted");

        // ❌ 直接读取当前余额，可被闪电贷操纵
        uint256 votes = governanceToken.balanceOf(msg.sender);

        if (support) {
            proposals[proposalId].forVotes += votes;
        } else {
            proposals[proposalId].againstVotes += votes;
        }

        proposals[proposalId].hasVoted[msg.sender] = true;
    }
}

// ✅ 攻击示例
contract FlashLoanAttacker {
    function attack(
        IFlashLoan flashLender,
        VulnerableGovernor governor,
        IERC20 token,
        uint256 proposalId
    ) external {
        // 1. 通过闪电贷借入大量治理代币
        uint256 loanAmount = 10_000_000 * 1e18;
        flashLender.flashLoan(token, loanAmount, "");
        // 在 flashLoan 回调中：
        // 2. 使用借来的代币投票
        // governor.vote(proposalId, true);
        // 3. 归还代币
    }
}

// ✅ 安全示例：使用快照机制
contract SecureGovernor {
    IERC20Snapshot public governanceToken;

    struct Proposal {
        uint256 snapshotId;
        uint256 forVotes;
        uint256 againstVotes;
        mapping(address => bool) hasVoted;
    }

    mapping(uint256 => Proposal) public proposals;

    function propose() external returns (uint256 proposalId) {
        // 创建提案时立即创建余额快照
        uint256 snapshotId = governanceToken.snapshot();

        proposalId = nextProposalId++;
        proposals[proposalId].snapshotId = snapshotId;
    }

    function vote(uint256 proposalId, bool support) external {
        Proposal storage proposal = proposals[proposalId];
        require(!proposal.hasVoted[msg.sender], "Already voted");

        // ✅ 使用快照时的余额，闪电贷无法影响
        uint256 votes = governanceToken.balanceOfAt(
            msg.sender,
            proposal.snapshotId
        );

        require(votes > 0, "No voting power");

        if (support) {
            proposal.forVotes += votes;
        } else {
            proposal.againstVotes += votes;
        }

        proposal.hasVoted[msg.sender] = true;
    }
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索投票权重计算：`balanceOf`、`votingPower`、`getVotes`
- 检查是否使用快照：`snapshot`、`balanceOfAt`、`getPastVotes`
- 定位提案创建函数，查看是否创建快照
- 搜索代币转移限制：`transfer` 是否在投票期间被禁止
- 检查投票锁定机制：是否有 `lock`、`vest`、`lockup` 相关逻辑

**快速定位保护机制技巧（L2-跳读）：**
- 查找 `ERC20Snapshot` 或 `ERC20Votes` 继承
- 搜索 `_snapshot()`、`snapshot()` 函数调用
- 检查 OpenZeppelin Governor 合约的使用
- 查看 `clock()` 和 `CLOCK_MODE()` 实现（EIP-6372）
- 验证是否有投票延迟（`votingDelay`）和投票周期（`votingPeriod`）

## Classify

**漏洞判定：**
- 投票权基于实时余额（`balanceOf(voter)`）而非历史快照
- 提案创建时未记录快照 ID 或区块号
- 缺少投票延迟，提案创建后可立即投票
- 治理代币可在投票期间自由转移且无锁定机制

**误报识别：**
- 使用 `ERC20Snapshot` 或 `ERC20Votes` 标准代币
- 投票权基于委托（`delegates`）且委托关系有延迟生效机制
- 存在足够长的投票延迟（如 1 天），闪电贷无法跨区块持有
- 投票需要提前质押代币且质押有锁定期

**代码异味：**
- 使用普通 ERC20 代币但未实现快照功能
- 快照创建时机不当（投票开始后才创建）
- 投票延迟过短（< 1 个区块）
- 既无快照也无代币锁定机制

## Low risk

**低风险场景：**
- 治理代币流动性极低，闪电贷池无足够代币可借
- 提案执行有长时间锁（如 7 天），社区有时间应对
- 存在链下治理签名验证，单纯代币持有不足以通过提案
- 提案类型仅限参数微调，无法造成严重损害
- 多重防护：快照 + 时间锁 + 多签执行
- 需要达到超高法定人数（如 50%+），闪电贷无法获得足够代币

## 审计专业技巧

### 关键审计清单

**第一阶段：快速扫描（5分钟）**
1. 检查治理代币合约是否继承 `ERC20Snapshot` 或 `ERC20Votes`
2. 搜索 `balanceOf` 在投票逻辑中的使用
3. 确认是否使用 OpenZeppelin Governor 框架（自带保护）
4. 检查提案创建函数是否调用 `snapshot()`

**第二阶段：深度分析（15分钟）**
- 追踪投票权重计算的完整流程
- 验证快照创建时机（必须在投票开始前）
- 检查投票延迟和投票周期设置
- 分析代币转移是否在投票期间受限
- 评估闪电贷可获得的最大代币量 vs 法定人数

**第三阶段：攻击模拟（10分钟）**
- 计算通过闪电贷控制提案所需的代币量
- 检查主流 DEX 的治理代币流动性
- 评估攻击成本 vs 潜在收益
- 模拟攻击交易序列（借贷 → 投票 → 归还）

### 真实漏洞案例

**案例1：Beanstalk DAO (2022-04，$76M)**
```solidity
// Beanstalk 的简化漏洞逻辑
contract BeanstalkGovernor {
    // 使用实时余额投票
    function vote(uint32 proposalId) external {
        uint256 votes = balanceOf(msg.sender); // ❌ 实时余额
        // ... 投票逻辑
    }
}

// 攻击者操作：
// 1. 从 Aave 闪电贷借入大量 BEAN 代币
// 2. 将 BEAN 存入 Beanstalk Silo 获得投票权
// 3. 立即投票通过恶意提案（将资金转给攻击者）
// 4. 提案立即执行（无时间锁）
// 5. 归还闪电贷
// 结果：单笔交易完成攻击，损失 $76M
```

**案例2：Build Finance (2021-02，$470K)**
```solidity
// 类似问题：投票权基于未锁定的代币
contract BuildGovernor {
    function castVote(uint256 proposalId) external {
        uint256 votes = token.balanceOf(msg.sender);
        // 投票后代币可立即卖出，无责任承担
    }
}
```

### 防护最佳实践

**推荐方案1：使用 OpenZeppelin Governor + ERC20Votes**
```solidity
import "@openzeppelin/contracts/governance/Governor.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Votes.sol";

contract MyToken is ERC20Votes {
    constructor() ERC20("MyToken", "MTK") ERC20Permit("MyToken") {}
}

contract MyGovernor is Governor, GovernorSettings, GovernorCountingSimple {
    constructor(IVotes _token)
        Governor("MyGovernor")
        GovernorSettings(
            1 days,    /* voting delay: 1 day */
            1 weeks,   /* voting period: 1 week */
            1000e18    /* proposal threshold: 1000 tokens */
        )
    {}

    // 自动使用 getPastVotes(account, timepoint)
    // 闪电贷无法影响历史投票权
}
```

**推荐方案2：投票代币锁定**
```solidity
contract VoteEscrow {
    struct LockedBalance {
        uint256 amount;
        uint256 end;
    }

    mapping(address => LockedBalance) public locked;

    function createLock(uint256 value, uint256 unlockTime) external {
        // 锁定代币以获得投票权
        token.transferFrom(msg.sender, address(this), value);
        locked[msg.sender] = LockedBalance(value, unlockTime);
    }

    function votingPower(address user) public view returns (uint256) {
        // 投票权基于锁定的代币，闪电贷无法使用
        return locked[user].amount;
    }
}
```

**推荐方案3：多层防护**
```solidity
contract DefenseInDepthGovernor {
    // 1. 快照机制
    function propose() external returns (uint256) {
        uint256 snapshot = token.snapshot();
        // ...
    }

    // 2. 投票延迟（防止提案创建后立即投票）
    uint256 public votingDelay = 1 days;

    // 3. 时间锁（给社区应对时间）
    TimelockController public timelock;

    // 4. 高法定人数（增加攻击成本）
    function quorum() public pure returns (uint256) {
        return totalSupply() * 20 / 100; // 20% 法定人数
    }

    // 5. 提案阈值（防止垃圾提案）
    function proposalThreshold() public pure returns (uint256) {
        return 100_000e18; // 需要持有 10 万代币才能提案
    }
}
```

### 审计检查清单

| 检查项 | 高风险 | 中等风险 | 低风险 |
|--------|--------|----------|--------|
| 快照机制 | 无快照 | 快照时机不当 | 正确使用 ERC20Votes |
| 投票延迟 | < 1 区块 | < 1 天 | ≥ 1 天 |
| 代币锁定 | 无锁定 | 可选锁定 | 强制锁定 |
| 时间锁保护 | 无时间锁 | < 1 天 | ≥ 2 天 |
| 法定人数 | < 5% | 5-15% | > 20% |
| 流动性风险 | 大量代币可借 | 中等流动性 | 代币不可借 |

### 常见误报场景

**场景1：委托投票系统**
```solidity
// ✅ 安全：虽然无快照，但委托关系有延迟
contract DelegateVoting {
    mapping(address => address) public delegates;
    mapping(address => uint256) public delegatedVotes;

    function delegate(address delegatee) external {
        delegates[msg.sender] = delegatee;
        // 委托在下一个区块才生效，闪电贷无法利用
    }
}
```

**场景2：链下签名投票**
```solidity
// ✅ 安全：投票在链下进行，快照由后端控制
contract OffchainVoting {
    function executeProposal(
        bytes[] calldata signatures,
        uint256 snapshotBlock
    ) external {
        // 验证签名是基于历史区块的余额
        // 闪电贷无法伪造历史签名
    }
}
```

### 工具辅助检测

**Slither 检测规则**
```bash
# 检测缺少快照的治理合约
slither . --detect governance-balance-check
```

**自定义 Semgrep 规则**
```yaml
rules:
  - id: flash-loan-governance-risk
    pattern: |
      function $FUNC(...) {
        ...
        $TOKEN.balanceOf($USER)
        ...
      }
    message: "Voting power uses current balance, vulnerable to flash loan attacks"
```

### 历史攻击时间线

| 日期 | 项目 | 损失 | 攻击手法 |
|------|------|------|----------|
| 2022-04 | Beanstalk | $76M | 闪电贷 + 即时投票 + 无时间锁 |
| 2021-10 | Indexed Finance | $16M | 闪电贷操纵治理代币价格 |
| 2021-02 | Build Finance | $470K | 闪电贷投票通过恶意提案 |

**关键洞察**：
- 所有案例都缺少快照机制
- 大多数缺少时间锁保护
- 攻击窗口通常 < 1 小时

---

**参考资料：**
- [OpenZeppelin Governor文档](https://docs.openzeppelin.com/contracts/governance)
- [ERC-20 Votes扩展](https://docs.openzeppelin.com/contracts/api/token/erc20#ERC20Votes)
- [Beanstalk攻击分析](https://rekt.news/beanstalk-rekt/)
- [Curve ve-tokenomics](https://curve.readthedocs.io/dao-vecrv.html)
