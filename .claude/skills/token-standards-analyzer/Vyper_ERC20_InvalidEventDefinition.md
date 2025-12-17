# Vyper ERC-20: Invalid Event Definition

## Details

Transfer 和 Approval 事件参数定义与 ERC-20 标准不匹配，导致链下索引服务和前端应用无法正确解析事件，影响交易追踪和用户界面显示。

### 典型表现

**参数类型错误**
```vyper
# Transfer 事件中 from/to 类型错误
event Transfer:
    indexed: uint256
    indexed: uint256
    value: uint256

# Approval 事件参数类型不符
event Approval:
    owner: uint256
    spender: uint256
    value: address
```

**参数顺序错误**
```vyper
# Transfer 标准顺序应为: from, to, value
event Transfer:
    indexed: address
    value: uint256
    indexed: address

# Approval 标准顺序应为: owner, spender, value
event Approval:
    spender: address
    owner: address
    value: uint256
```

**参数缺失**
```vyper
# Transfer 缺少 value 参数
event Transfer:
    indexed: address
    indexed: address

# Approval 缺少关键参数
event Approval:
    indexed: address
    indexed: address
```

**拼写错误或命名不符**
```vyper
# 事件名称错误
event Trasfer:  # 应为 Transfer
    indexed: address
    indexed: address
    value: uint256

# 参数名称不符标准
event Transfer:
    indexed: address
    indexed: address
    amount: uint256  # 应为 value
```

**indexed 修饰符不符**
```vyper
# value 被错误标记为 indexed
event Transfer:
    indexed: address
    indexed: address
    indexed: uint256

# owner 未被标记为 indexed
event Approval:
    owner: address
    indexed: address
    value: uint256
```

## Classify

**风险等级**: HIGH

**影响范围**:
- 链上数据索引失败
- Block explorer 无法解析交易
- 钱包应用无法追踪转账
- 第三方服务无法监听事件
- DEX 流动性管理失效

**审计关键词**:
- `event Transfer` - 验证参数为 (indexed address, indexed address, uint256)
- `event Approval` - 验证参数为 (indexed address, indexed address, uint256)
- `indexed` - 确认 address 类型参数被正确标记
- 参数顺序 - from → to → value 或 owner → spender → value
- 参数名称 - value 而非 amount

## Low risk

此缺陷属于结构性问题，不存在低风险情形。任何事件定义不符都会导致事件索引失败。

建议立即修正所有事件定义，确保参数类型、顺序和修饰符与标准一致。
