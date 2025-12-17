# Solidity ERC-1155: Invalid BalanceOfBatch

## Details

### Code Examples

**问题代码示例 1：返回数组长度与输入不匹配**
```solidity
function balanceOfBatch(
    address[] calldata accounts,
    uint256[] calldata ids
) public view returns (uint256[] memory) {
    // ❌ 返回数组长度错误（只返回一半）
    uint256[] memory batchBalances = new uint256[](accounts.length / 2);
    for (uint i = 0; i < accounts.length / 2; i++) {
        batchBalances[i] = balances[accounts[i]][ids[i]];
    }
    return batchBalances;
}
```

**问题代码示例 2：未检查数组长度**
```solidity
function balanceOfBatch(
    address[] calldata accounts,
    uint256[] calldata ids
) public view returns (uint256[] memory) {
    // ❌ 未检查数组长度是否匹配
    uint256[] memory batchBalances = new uint256[](accounts.length);

    for (uint i = 0; i < accounts.length; i++) {
        // 可能访问 ids 数组越界
        batchBalances[i] = balances[accounts[i]][ids[i]];
    }
    return batchBalances;
}
```

**问题代码示例 3：返回错误的余额顺序**
```solidity
function balanceOfBatch(
    address[] calldata accounts,
    uint256[] calldata ids
) public view returns (uint256[] memory) {
    // ❌ 返回余额顺序错误（反向）
    uint256[] memory batchBalances = new uint256[](accounts.length);
    for (uint i = 0; i < accounts.length; i++) {
        batchBalances[accounts.length - 1 - i] = balances[accounts[i]][ids[i]];
    }
    return batchBalances;
}
```

### 核心操作定位技巧
- **L1: 关键词扫描** - 搜索 `function balanceOfBatch`，定位函数声明
- 检查函数签名：输入应为 `address[] calldata accounts, uint256[] calldata ids`
- 验证返回值：`uint256[] memory`，且数组长度应等于 `accounts.length`

### 保护机制定位技巧
- **L2: 跳读** - 浏览函数实现，检查是否有长度检查：`require(accounts.length == ids.length)`
- 查看循环边界条件，确认迭代次数与 `accounts.length` 一致
- 验证返回数组的初始化大小是否为 `accounts.length`
- **L3: 逐行读** - 逐行验证数组赋值逻辑，确认循环中索引对应关系正确

---

## Classify

### 漏洞判定标准 (Bug)
- balanceOfBatch 返回数组长度与 accounts.length 不相等
- balanceOfBatch 未检查 accounts.length == ids.length，导致数组越界或不完整查询
- balanceOfBatch 返回的余额顺序与输入地址/id 顺序不对应
- balanceOfBatch 在循环中使用了错误的索引（如使用 ids 数组索引访问 accounts）
- balanceOfBatch 对空数组输入处理不当（应返回空数组，不是 revert）

### 误报排除标准 (False Positive)
- 合约继承自 OpenZeppelin ERC-1155 或其他标准库，balanceOfBatch 正确实现
- 合约实现了长度检查，虽然返回值初始化方式不同但逻辑正确
- balanceOfBatch 是代理合约的函数，实际实现在目标合约中正确处理

### 代码异味 (Code Smell)
- balanceOfBatch 实现中没有明显的长度相等性检查注释或文档说明
- 返回数组初始化使用了硬编码大小而非输入参数
- 循环条件与返回数组大小不一致（如返回数组大小为 N，但循环只迭代 M 次）

---

## Low Risk

### 应评为低风险的情况
- balanceOfBatch 通过 require 显式检查了长度相等性，即使检查位置不在函数开头
- 合约为只读视图函数，返回错误的顺序不影响后续业务逻辑（虽然仍然不规范）
- 合约在前端或第三方库中进行了数组长度匹配验证，后端 balanceOfBatch 实现有缺陷但被补偿
- 返回数组长度略有不同，但合约业务逻辑中自行处理了填充（虽然违反标准但功能完整）

