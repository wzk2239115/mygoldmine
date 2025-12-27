# 短地址攻击（Solidity）

**漏洞描述：** ERC20 代币 transfer/transferFrom 函数未验证地址参数的有效性，攻击者可通过提供长度不足的地址（如以0x00结尾的地址）利用Solidity对calldata的处理特性，导致参数被错误解析，进而改变实际转账金额或其他敏感参数

## Details

**短地址攻击的技术原理：**

Solidity 在编码函数参数时使用固定的 calldata 布局：
- 每个参数占用 32 字节（256 位）
- address 类型实际占 20 字节，通常被补零为 32 字节
- 当地址长度不足 20 字节时，EVM 会在参数末尾补零

当攻击者提供一个以 0x00 结尾的短地址时：
1. calldata 中该地址只占 19 字节（而不是 20 字节）
2. 后续参数的 calldata 偏移量错位
3. 原本用于后一个参数的数据被解析为前一个参数的一部分
4. 导致参数值被意外改变

**对应代码示例：**

```solidity
// ❌ 易受攻击的 ERC20 实现
pragma solidity ^0.4.11;

contract VulnerableToken {
    mapping (address => uint) public balances;

    // 无地址验证的 transfer 函数
    function transfer(address _to, uint _value) public returns (bool) {
        require(balances[msg.sender] >= _value);
        balances[msg.sender] -= _value;
        balances[_to] += _value;
        return true;
    }

    // 无地址验证的 transferFrom 函数
    function transferFrom(address _from, address _to, uint _value) public returns (bool) {
        require(balances[_from] >= _value);
        balances[_from] -= _value;
        balances[_to] += _value;
        return true;
    }
}

// 攻击示例：
// 正常调用：transfer(0x1234567890123456789012345678901234567890, 100)
// 攻击调用：transfer(0x123456789012345678901234567890123456ab00, 100)
//           ↑ 短地址（末尾为00）
//
// 由于补零，amount 参数会被解析为:
// 0x100 (256 in decimal) << 8 * (32 - 19) = 0x100 * 2^104
// 导致转账金额大幅增加


// ✅ 安全的 ERC20 实现（使用 OpenZeppelin）
pragma solidity ^0.6.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract SafeToken is ERC20 {
    constructor() ERC20("Safe Token", "SAFE") {
        _mint(msg.sender, 1000000 * 10 ** 18);
    }

    // OpenZeppelin 已内置地址验证和参数检查
    // transfer 函数已安全实现
}

// 或者显式验证地址长度（虽然不如使用标准库优雅）
contract TokenWithValidation {
    mapping (address => uint) public balances;

    // ✅ 添加地址验证
    function transfer(address _to, uint _value) public returns (bool) {
        require(_to != address(0), "Invalid address");
        require(balances[msg.sender] >= _value, "Insufficient balance");

        balances[msg.sender] -= _value;
        balances[_to] += _value;
        return true;
    }
}
```

**快速定位核心操作的技巧（L1: 函数扫描）：**
- 扫描关键函数名：`transfer`, `transferFrom`, `approve`, `mint`, `burn`, `send`, `receive`, `execute`, `call`, `delegatecall`
- 查找所有包含 `address` 类型参数的 `external`/`public` 函数
- 特别关注 ERC20/ERC721 标准接口的实现
- 检查 interface 和合约实现是否一致

**快速定位保护机制的技巧（L2: 验证检查）：**
- 检查函数开始是否有 `require(_to != address(0))` 或类似的地址验证
- 查找是否显式检查了地址长度：如 `require(_to.code.length >= 0)`
- 检查是否使用了标准库（OpenZeppelin）或其他审计过的库函数
- 查看是否有注释说明地址验证策略
- 检查是否在使用 `call`, `delegatecall` 等低级调用时进行了额外的参数验证

**参数操纵的具体案例：**

```solidity
// 攻击场景 1：单次转账金额改变
contract VulnerableToken {
    mapping(address => uint) balances;

    function transfer(address to, uint amount) public {
        balances[msg.sender] -= amount;
        balances[to] += amount;  // ← 这里的 amount 被改变
    }
}

// 攻击交易数据（伪代码）：
// 函数签名: 0xa9059cbb (transfer)
// 参数 1 (to):     0x0000...00ab00  <- 19字节短地址，末位为00
// 参数 2 (amount): 0x0000000000000000000000000000000000000000000000000000000000000064 (100)
//
// 由于补零，实际解析：
// to:     0xabXXXX... (错误解析)
// amount: 0x6400... (被改变，值大幅增加)


// 攻击场景 2：批量转账中多个参数串联篡改
contract VulnerableAirdrop {
    function batchTransfer(address[] recipients, uint[] amounts) public {
        for (uint i = 0; i < recipients.length; i++) {
            transfer(recipients[i], amounts[i]);
        }
    }
}

// 如果 recipients[i] 是短地址，会影响 amounts[i] 的解析


// 攻击场景 3：transferFrom 中的地址混淆
contract VulnerableTransferFrom {
    function transferFrom(address from, address to, uint amount) public {
        // ← 如果 to 是短地址，from 或 amount 可能被篡改
        balances[from] -= amount;
        balances[to] += amount;
    }
}
```

## Classify

**漏洞判定：**
- ERC20 transfer/transferFrom 函数不验证地址参数有效性
- 函数接受地址参数但未检查地址格式或长度
- 使用了自定义地址处理逻辑，未实施标准库提供的保护

**误报判定：**
- 函数使用了 OpenZeppelin 或其他审计过的标准库实现
- 函数为 `internal`/`private`，不接收外部地址参数
- 函数使用硬编码地址常数，不接收参数
- 函数包含显式的地址验证：如 `require(to != address(0))`（虽然不完全防护，但已是基础保护）
- 合约不涉及 ERC20/ERC721 代币转账逻辑

**代码异味判定：**
- 地址验证不一致：transfer 有验证但 transferFrom 没有
- 注释标注"防止短地址"但实现不完整或无验证代码
- 直接操作 calldata 或使用低级调用处理地址参数而未验证
- 同一合约中，不同函数对地址参数的处理方式不同

## Low risk

- **使用标准库：** 合约继承自 OpenZeppelin ERC20/ERC721 或其他审计过的标准库，使用标准库提供的 transfer 等函数
- **明确的防护：** 函数实现了明确的地址长度检查或使用了 `require(to != address(0))` 等基础防护
- **仅内部调用：** 函数标记为 `internal` 或 `private`，不接收外部传入的地址参数
- **常数地址：** 函数使用硬编码的地址，不接收动态地址参数
- **已验证部署：** 合约已在主网长期运行（>1年）且大量用户交易中未见异常，社区已验证无短地址风险
- **合约停用：** 合约已停用或升级至新版本，当前版本不再处理转账

---

## 检查清单

当发现潜在的短地址攻击时，按以下清单验证：

- [ ] 函数是否接受 `address` 类型参数？
- [ ] 函数是否为 `external` 或 `public`？
- [ ] 函数是否修改了状态（涉及资产转移或权限变更）？
- [ ] 函数是否验证了地址参数的有效性？
- [ ] 是否使用了标准库的安全实现？
- [ ] 是否有测试用例覆盖短地址场景？
- [ ] 是否有明确的注释说明地址验证策略？

---

## 修复建议

**推荐方案（按优先级）：**

1. **使用标准库（最佳）**
```solidity
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract SafeToken is ERC20 {
    // 使用 OpenZeppelin 的 transfer 实现，已内置安全检查
}
```

2. **添加地址验证**
```solidity
function transfer(address to, uint amount) public returns (bool) {
    require(to != address(0), "Invalid recipient");
    require(balances[msg.sender] >= amount, "Insufficient balance");

    balances[msg.sender] -= amount;
    balances[to] += amount;
    return true;
}
```

3. **使用 `call` 代替直接转移**
```solidity
function transfer(address to, uint amount) public returns (bool) {
    require(to != address(0), "Invalid recipient");
    require(balances[msg.sender] >= amount, "Insufficient balance");

    balances[msg.sender] -= amount;
    balances[to] += amount;

    // 使用 call 实现安全的资产转移
    (bool success, ) = payable(to).call{value: amount}("");
    require(success, "Transfer failed");

    return true;
}
```

---

## 参考资源

- [短地址攻击分析（外部链接）](https://ericrafaloff.com/analyzing-the-erc20-short-address-attack/)
- [Solidity 官方文档 - 参数编码](https://docs.soliditylang.org/en/latest/abi-spec.html)
- [OpenZeppelin ERC20 实现](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/ERC20.sol)
