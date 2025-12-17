# Vyper ERC-20: Incomplete Interface

## Details

Vyper ERC-20 代币合约未完整实现 ERC-20 标准接口的所有必需函数，或已实现的函数存在参数不完整、返回类型错误等问题。此缺陷导致合约与标准钱包、DEX 和交易所不兼容，影响代币流动性和可用性。

### 典型表现

**缺失核心函数**
```vyper
# 缺失 approve 函数，无法授权第三方代币转账
@external
def transfer(to: address, amount: uint256) -> bool:
    self.balances[msg.sender] -= amount
    self.balances[to] += amount
    return True

# 缺失 transferFrom 函数，无法实现代币授权转账
# 缺失 approve 函数，无法实现授权机制
```

**参数不完整**
```vyper
# balanceOf 缺少参数
@external
def balanceOf() -> uint256:
    return self.balances[msg.sender]

# transfer 参数不完整
@external
def transfer(to: address) -> bool:
    # amount 参数缺失
    pass
```

**返回类型错误**
```vyper
# totalSupply 应返回 uint256
@external
def totalSupply() -> bool:
    return True

# approve 返回类型错误
@external
def approve(spender: address, amount: uint256) -> uint256:
    self.allowance[msg.sender][spender] = amount
    return self.allowance[msg.sender][spender]
```

**函数签名不匹配**
```vyper
# transferFrom 参数顺序错误
@external
def transferFrom(amount: uint256, from_addr: address, to: address) -> bool:
    pass

# allowance 返回类型错误
@external
def allowance(owner: address, spender: address) -> bool:
    pass
```

## Classify

**风险等级**: HIGH

**影响范围**:
- 钱包集成失败
- DEX 兼容性问题
- 交易所上市困难
- 代币授权机制失效

**审计关键词**:
- `def totalSupply` - 检查返回类型是否为 uint256
- `def balanceOf` - 检查是否接收 address 参数
- `def transfer` - 检查参数(to, amount)是否完整
- `def approve` - 检查是否存在及返回类型
- `def transferFrom` - 检查是否存在及参数顺序
- `def allowance` - 检查返回类型是否为 uint256
- `@external` - 验证所有公开函数声明

## Low risk

此缺陷属于结构性问题，不存在低风险情形。任何 ERC-20 接口不完整都会导致合约不可用。

建议立即修正所有缺失函数和错误的函数签名，确保与标准完全一致。
