# Solidity 委托投票劫持

委托投票机制存在缺陷，允许攻击者控制他人的投票权、委托关系被恶意修改、或委托链过长导致Gas攻击。

## Details

**代码示例：**
```solidity
// ❌ 漏洞示例
contract VulnerableDelegation {
    mapping(address => address) public delegates;

    function delegate(address delegatee) external {
        // ❌ 未检查delegatee有效性
        delegates[msg.sender] = delegatee;
    }

    function votingPower(address account) public view returns (uint256) {
        address current = account;
        uint256 power = balanceOf(account);

        // ❌ 无限委托链，可能Gas攻击
        while (delegates[current] != address(0)) {
            current = delegates[current];
            power += balanceOf(current);
        }

        return power;
    }
}

// ✅ 安全示例
contract SecureDelegation {
    using Checkpoints for Checkpoints.History;

    mapping(address => address) private _delegates;
    mapping(address => Checkpoints.History) private _delegateCheckpoints;

    function delegate(address delegatee) public {
        require(delegatee != address(0), "Invalid delegatee");
        require(delegatee != msg.sender, "Self-delegation");

        // ✅ 禁止循环委托
        require(
            _delegates[delegatee] != msg.sender,
            "Circular delegation"
        );

        address oldDelegate = _delegates[msg.sender];
        _delegates[msg.sender] = delegatee;

        _moveDelegates(oldDelegate, delegatee, balanceOf(msg.sender));

        emit DelegateChanged(msg.sender, oldDelegate, delegatee);
    }

    function _moveDelegates(
        address from,
        address to,
        uint256 amount
    ) private {
        if (from != to && amount > 0) {
            if (from != address(0)) {
                _delegateCheckpoints[from].push(
                    _subtract,
                    amount
                );
            }
            if (to != address(0)) {
                _delegateCheckpoints[to].push(
                    _add,
                    amount
                );
            }
        }
    }
}
```

## Classify

**漏洞判定：**
- 允许委托给零地址或合约地址
- 未检测循环委托（A→B→A）
- 委托链无长度限制导致Gas耗尽
- 委托操作未记录检查点，可被实时操纵

**误报识别：**
- 使用 ERC20Votes 标准实现
- 委托关系通过检查点记录
- 禁止自委托和循环委托
- 有最大委托链深度限制

**代码异味：**
- 递归或循环遍历委托链
- 委托可指向EOA和合约地址
- 缺少委托变更事件

## Low risk
- 委托需要链下授权
- 委托数量有硬性上限
- 委托仅影响链下治理

---

**参考：** [Compound COMP Token](https://github.com/compound-finance/compound-protocol/blob/master/contracts/Governance/Comp.sol)
