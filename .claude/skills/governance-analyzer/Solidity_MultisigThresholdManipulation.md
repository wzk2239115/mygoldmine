# Solidity 多签阈值操纵

多签钱包的签名者管理或阈值修改存在漏洞，允许少数签名者降低阈值控制整个钱包，或添加/删除签名者的权限控制不当。

## Details

**代码示例：**
```solidity
// ❌ 漏洞示例
contract VulnerableMultisig {
    address[] public owners;
    uint256 public required;

    // ❌ 任何owner可降低阈值
    function changeRequirement(uint256 _required) external {
        require(isOwner(msg.sender));
        required = _required; // 可设为1
    }

    // ❌ 单个owner可添加新owner
    function addOwner(address owner) external {
        require(isOwner(msg.sender));
        owners.push(owner);
    }
}

// ✅ 安全示例
contract SecureMultisig {
    address[] public owners;
    uint256 public required;

    function changeRequirement(uint256 _required) external {
        // ✅ 必须通过多签执行
        require(msg.sender == address(this));
        require(_required > 0 && _required <= owners.length);

        // ✅ 不能降低到过低阈值
        require(_required >= owners.length / 2);

        required = _required;
    }

    function addOwner(address owner) external {
        require(msg.sender == address(this));
        require(owner != address(0));
        require(!isOwner(owner));

        owners.push(owner);

        // ✅ 添加owner后检查阈值是否需要调整
        if (required > owners.length) {
            required = owners.length;
        }
    }

    function removeOwner(address owner) external {
        require(msg.sender == address(this));
        require(isOwner(owner));
        require(owners.length - 1 >= required);

        // 移除owner逻辑...
    }
}
```

## Classify

**漏洞判定：**
- 阈值可被单个owner修改
- 阈值可降至1（失去多签意义）
- 添加owner不需要其他owner批准
- 移除owner后未检查阈值是否仍有效

**误报识别：**
- 使用 Gnosis Safe 等审计过的多签
- 阈值修改需要通过多签提案
- 有最小阈值限制（如 ≥50%）
- Owner管理需要多数同意

**代码异味：**
- required为public可写
- Owner数组可被直接操作
- 缺少Owner变更事件

## Low risk
- 多签仅用于测试
- Owners均为高信任实体
- 有链下监控和告警

---

**参考：** [Gnosis Safe](https://github.com/safe-global/safe-contracts)
