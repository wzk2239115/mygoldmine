# Solidity ERC-721: Missing TokenURI

## Details

### Code Examples

**问题代码示例 1：tokenURI 函数缺失**
```solidity
contract NFT {
    mapping(uint256 => address) public tokenOwner;

    function mint(address to, uint256 tokenId) public {
        tokenOwner[tokenId] = to;
    }

    // ❌ 缺失 tokenURI 函数实现
}
```

**问题代码示例 2：tokenURI 返回空字符串**
```solidity
function tokenURI(uint256 tokenId) public view returns (string memory) {
    // ❌ 无条件返回空字符串
    return "";
}
```

**问题代码示例 3：tokenURI 未验证 tokenId 存在性**
```solidity
function tokenURI(uint256 tokenId) public view returns (string memory) {
    // ❌ 未检查 tokenId 是否存在就返回 URI
    return string(abi.encodePacked("https://metadata.example.com/", tokenId));
}

// 调用者可以为不存在的 tokenId 获取 URI
```

**问题代码示例 4：tokenURI 返回硬编码值**
```solidity
function tokenURI(uint256 tokenId) public view returns (string memory) {
    // ❌ 所有 tokenId 都返回相同的 URI
    return "https://metadata.example.com/default.json";
}
```

### 核心操作定位技巧
- **L1: 关键词扫描** - 搜索 `function tokenURI`，确认函数是否存在且不返回空值
- 检查返回值是否与 `tokenId` 相关（不应该是所有 token 都返回相同的 URI）
- 验证返回的字符串不为空且包含实际的 URI 路径

### 保护机制定位技巧
- **L2: 跳读** - 浏览 tokenURI 函数实现，检查是否有对 tokenId 存在性的验证（require(存在), 或在某个mapping中查找）
- 查看 tokenURI 是否查询了某个存储结构（如 `tokenURIs` mapping）来获取 token 的元数据地址
- **L3: 逐行读** - 逐行验证 tokenURI 对不存在的 tokenId 的处理（应该 revert 或返回有意义的默认值）

---

## Classify

### 漏洞判定标准 (Bug)
- tokenURI 函数完全缺失或不可调用
- tokenURI 对任何 tokenId 都返回空字符串或 null
- tokenURI 返回完全硬编码的值，不区分 token（所有 token 元数据相同）
- tokenURI 对不存在的 tokenId 返回值而不是 revert（应该按 ERC-721 标准 revert）
- tokenURI 返回的 URI 格式错误，无法被标准客户端解析

### 误报排除标准 (False Positive)
- 合约是可升级的代理合约，tokenURI 在实现合约中正确实现
- 合约继承自 OpenZeppelin 或其他标准 ERC-721 库，继承了正确的 tokenURI 实现
- 合约实现了扩展接口（如 IERC721Metadata），满足 tokenURI 的所有要求

### 代码异味 (Code Smell)
- tokenURI 逻辑过于简单，没有对 tokenId 存在性的检查
- tokenURI 返回的 URI 格式不一致（某些 token 是 IPFS 哈希，某些是 HTTP URL）
- tokenURI 调用了可能失败的外部函数（如跨链调用）但没有错误处理

---

## Low Risk

### 应评为低风险的情况
- tokenURI 由中心化的元数据服务提供，合约通过动态构造 URL 访问（如 API gateway）
- 合约在初始阶段未实现 tokenURI，但规划中将添加（在注释或文档中明确说明）
- tokenURI 的实现在子合约或升级版本中完成，当前版本是中间状态
- 合约为 NFT 工厂模式，tokenURI 在子合约中实现而非父合约中

