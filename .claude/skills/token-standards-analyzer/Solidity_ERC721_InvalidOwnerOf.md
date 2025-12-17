# Solidity ERC-721: Invalid OwnerOf

## Details

### Code Examples

**问题代码示例 1：ownerOf 对不存在的 tokenId 返回 address(0)**
```solidity
mapping(uint256 => address) public tokenOwner;

function ownerOf(uint256 tokenId) public view returns (address) {
    // ❌ 应该 revert，而不是返回零地址
    return tokenOwner[tokenId];  // 不存在时返回 address(0)
}
```

**问题代码示例 2：ownerOf 返回错误的 owner 地址**
```solidity
mapping(uint256 => address) public tokenOwner;

function ownerOf(uint256 tokenId) public view returns (address) {
    // ❌ 访问了错误的 mapping
    return tokenApproved[tokenId];  // 应该返回 tokenOwner，不是 tokenApproved
}
```

**问题代码示例 3：ownerOf 对已销毁的 NFT 仍返回原 owner**
```solidity
mapping(uint256 => address) public tokenOwner;
mapping(uint256 => bool) public tokenBurned;

function burn(uint256 tokenId) public {
    tokenBurned[tokenId] = true;
    // ❌ 未清除 tokenOwner
}

function ownerOf(uint256 tokenId) public view returns (address) {
    // ❌ 没有检查 tokenBurned 状态
    return tokenOwner[tokenId];  // 已销毁 token 仍返回 owner
}
```

### 核心操作定位技巧
- **L1: 关键词扫描** - 搜索 `function ownerOf`，定位函数定义和返回语句
- 检查函数签名是否正确：`returns (address)`
- 验证函数对不存在 tokenId 的处理：应该包含 `require`、`revert` 或异常检查

### 保护机制定位技巧
- **L2: 跳读** - 浏览 ownerOf 函数的完整实现，寻找 tokenId 有效性验证逻辑
- 检查是否存在 `require(tokenId exists)` 或类似的守卫条件
- 查看 token burn 逻辑，确认 ownerOf 在 token 被销毁后能正确处理
- **L3: 逐行读** - 逐行验证返回语句，确认返回的是正确的 owner mapping，而非其他变量

---

## Classify

### 漏洞判定标准 (Bug)
- ownerOf 对不存在的 tokenId 返回值（address(0)）而不是 revert
- ownerOf 返回错误的地址（查询了错误的 mapping 或变量）
- ownerOf 对已销毁的 token 返回旧 owner 而不是 revert
- ownerOf 没有任何有效性检查，返回未初始化的 mapping 值
- ownerOf 在某些分支返回值，在其他分支 revert，导致行为不一致

### 误报排除标准 (False Positive)
- 合约继承自 OpenZeppelin ERC-721 或其他标准库，ownerOf 正确实现
- 合约实现了自定义的 token 有效性验证机制（虽然与标准不同，但逻辑一致）
- ownerOf 是代理合约的函数，实际实现在目标合约中正确处理

### 代码异味 (Code Smell)
- ownerOf 逻辑过于简单，没有明确的 require 或 assert 语句
- ownerOf 返回结果后，对 token 的 burn 操作无法改变已返回的结果
- ownerOf 实现中存在多个返回路径，某些路径可能遗漏验证

---

## Low Risk

### 应评为低风险的情况
- ownerOf 基于中心化的数据库或 off-chain 来源，合约只是反映当前状态
- 合约明确标注为非标准 ERC-721（如自定义 NFT 实现），ownerOf 行为与业务逻辑一致
- ownerOf 实现在代理的实现合约中正确处理，当前合约是接口层
- 合约提供了替代的所有权查询函数（balanceOf 等），补偿了 ownerOf 的缺陷

