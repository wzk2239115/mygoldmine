# Vyper ERC-721: Missing Enumerable

## Details

NFT 合约未实现 totalSupply、tokenByIndex、tokenOfOwnerByIndex 等枚举功能，不符合 ERC-721 Enumerable 扩展标准。缺少枚举接口导致无法遍历代币、查询所有权分布，影响钱包展示和市场运营。

### 典型表现

**缺失 totalSupply 函数**
```vyper
# 无法查询合约中总代币数量
interface ERC721Enumerable:
    def tokenByIndex(index: uint256) -> uint256: view
    def tokenOfOwnerByIndex(owner: address, index: uint256) -> uint256: view
    # 缺失 totalSupply

@external
def balanceOf(owner: address) -> uint256:
    return self.balance[owner]
```

**缺失 tokenByIndex 函数**
```vyper
# 无法按索引遍历所有代币
@external
def totalSupply() -> uint256:
    return self.total_supply

# 缺失 tokenByIndex(uint256) 函数
```

**缺失 tokenOfOwnerByIndex 函数**
```vyper
# 无法遍历单个地址的所有代币
@external
def balanceOf(owner: address) -> uint256:
    return self.balance[owner]

# 缺失 tokenOfOwnerByIndex(owner, index) 函数
```

**枚举函数错误实现**
```vyper
# tokenByIndex 实现错误，越界未处理
@external
def tokenByIndex(index: uint256) -> uint256:
    return self.tokens[index]  # 无界限检查

# tokenOfOwnerByIndex 返回类型错误
@external
def tokenOfOwnerByIndex(owner: address, index: uint256) -> address:
    return self.owned_tokens[owner][index]  # 应返回 uint256
```

**索引追踪不完整**
```vyper
# 缺少所有权索引映射
owner_tokens: public(HashMap[address, DynArray[uint256, 1000]])
# 缺少全局代币索引
all_tokens: DynArray[uint256, 10000]

@external
def mint(to: address, token_id: uint256):
    # 未更新 owner_tokens 和 all_tokens 映射
    pass
```

## Classify

**风险等级**: MEDIUM

**影响范围**:
- 钱包无法显示完整 NFT 列表
- NFT 市场无法高效查询数据
- 链上数据分析困难
- DeFi 集成受限
- 批量操作无法实现

**审计关键词**:
- `def totalSupply` - 检查是否存在
- `def tokenByIndex` - 验证参数和返回类型
- `def tokenOfOwnerByIndex` - 验证实现完整性
- 索引数据结构 - owner_tokens、all_tokens 映射
- 边界检查 - mint/burn 时的索引更新
- 返回类型 - uint256 而非 address

## Low risk

**部分实现情况**:
- 如果合约明确声明不支持枚举扩展，可接受缺失
- 如果提供替代的链下索引机制，风险可降低
- 但应在文档中明确声明不兼容 ERC-721 Enumerable

建议评估项目是否需要枚举功能，若需要应完整实现所有接口函数。
