# Solidity ERC-1155: Missing SafeTransferFrom

## Details

### Code Examples

**问题代码示例 1：safeTransferFrom 函数缺失**
```solidity
contract SimpleERC1155 {
    mapping(address => mapping(uint256 => uint256)) public balances;

    function transferFrom(address from, address to, uint256 id, uint256 amount) public {
        // ❌ 这是非安全转账，缺失 safeTransferFrom
        balances[from][id] -= amount;
        balances[to][id] += amount;
    }

    // ❌ 缺失 safeTransferFrom 和 safeBatchTransferFrom
}
```

**问题代码示例 2：safeTransferFrom 未调用接收方 hook**
```solidity
function safeTransferFrom(
    address from,
    address to,
    uint256 id,
    uint256 amount,
    bytes calldata data
) public {
    balances[from][id] -= amount;
    balances[to][id] += amount;
    // ❌ 未检查 to 是否为合约，未调用 onERC1155Received
    emit TransferSingle(msg.sender, from, to, id, amount);
}
```

**问题代码示例 3：safeBatchTransferFrom 实现错误**
```solidity
function safeBatchTransferFrom(
    address from,
    address to,
    uint256[] calldata ids,
    uint256[] calldata amounts,
    bytes calldata data
) public {
    // ❌ 未检查数组长度
    // ❌ 未调用接收方的 onERC1155BatchReceived hook
    for (uint i = 0; i < ids.length; i++) {
        balances[from][ids[i]] -= amounts[i];
        balances[to][ids[i]] += amounts[i];
    }
    emit TransferBatch(msg.sender, from, to, ids, amounts);
}
```

### 核心操作定位技巧
- **L1: 关键词扫描** - 搜索 `function safeTransferFrom` 和 `function safeBatchTransferFrom`
- 检查是否有对接收方 hook 的调用：`onERC1155Received` 和 `onERC1155BatchReceived`
- 查找 `onERC1155Received` 字符串或 selector 常量定义

### 保护机制定位技巧
- **L2: 跳读** - 浏览 safeTransferFrom 的完整实现，检查是否有对接收者合约的判断逻辑
- 查找 hook 调用时的 selector 检查（应该验证返回值等于特定的 selector）
- 检查是否使用了 ERC165 接口检查 `supportsInterface`
- **L3: 逐行读** - 逐行验证 hook 调用和返回值检查的完整性，确认 selector 匹配逻辑正确

---

## Classify

### 漏洞判定标准 (Bug)
- safeTransferFrom 函数完全缺失
- safeBatchTransferFrom 函数完全缺失或不可调用
- safeTransferFrom 实现中完全缺少 onERC1155Received hook 调用
- safeBatchTransferFrom 未检查输入数组长度匹配
- safeTransferFrom/safeBatchTransferFrom 调用了 hook 但未验证返回值（返回的 selector）
- 无法识别接收地址是否为合约（缺少 isContract 或类似检查）

### 误报排除标准 (False Positive)
- 合约继承自 OpenZeppelin ERC-1155 或其他标准库，safeTransferFrom 正确实现
- 合约是代理合约，safeTransferFrom 在实现合约中正确实现
- 合约同时提供了非安全转账和安全转账接口，两者都正确实现

### 代码异味 (Code Smell)
- safeTransferFrom 实现了 hook 调用但未完整检查返回值（如只检查长度，未检查 selector）
- safeBatchTransferFrom 实现正确但未说明是否支持部分回滚
- hook 调用存在但错误处理简陋（如发送失败直接 revert 而非日志记录）
- 对接收地址的合约检查不完善（如使用了过时的 isContract 实现）

---

## Low Risk

### 应评为低风险的情况
- safeTransferFrom 存在且实现了 hook 调用，虽然缺少某些可选的优化检查
- 合约明确标注为内部使用或私有，不声称完整 ERC-1155 兼容性
- safeBatchTransferFrom 实现基本正确，虽然某些边界情况处理简化
- 合约通过充分的测试验证，与主流 NFT 钱包和交易所兼容
- hook 返回值检查存在但位置不在函数体最后（虽然不规范但功能完整）

