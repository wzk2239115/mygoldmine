# Token Standards Implementation Audit Guide

代币标准实现审计确保智能合约正确实现所声称的代币标准。本指南提供快速定位和研判标准实现缺陷的审计方法论。

## 核心审计方法

### L0: 快速资格确认（3分钟）

**关键词扫描**
- 搜索代币标准声明：`ERC-20`, `ERC-721`, `ERC-1155`, `IERC`, `interface`
- 搜索标准函数：`transfer`, `mint`, `burn`, `approve`, `balanceOf`, `totalSupply`
- 搜索事件定义：`event Transfer`, `event Approval`
- 搜索对应语言库：Rust (SPL Token, CW20), Move (Coin), Vyper, Go (Cosmos)

**快速判断**：无代币合约声明 + 无代币转账逻辑 + 无标准接口 = 快速退出

### L1: 关键词扫描（5-10分钟）

**Solidity ERC-20 核心函数**
- `totalSupply()` 返回 uint256
- `balanceOf(address)` 返回 uint256
- `transfer(address, uint256)` 返回 bool
- `allowance(address, address)` 返回 uint256
- `approve(address, uint256)` 返回 bool
- `transferFrom(address, address, uint256)` 返回 bool

**Solidity ERC-721 核心函数**
- `balanceOf(address)` 返回 uint256
- `ownerOf(uint256)` 返回 address（不存在应 revert）
- `name()` 返回 string
- `symbol()` 返回 string
- `tokenURI(uint256)` 返回非空 string

**Solidity ERC-1155 核心函数**
- `balanceOf(address, uint256)` 返回 uint256
- `balanceOfBatch(address[], uint256[])` 返回 uint256[]（长度需匹配）
- `safeTransferFrom(address, address, uint256, uint256, bytes)` 必须实现
- `safeBatchTransferFrom()` 批量转账逻辑

### L2: 跳读验证（10-20分钟）

**返回值检查**
- bool 返回：`transfer` 和 `approve` 必须显式返回 true/false
- 数组返回：`balanceOfBatch` 数组长度必须等于输入长度
- 地址返回：`ownerOf` 对不存在 tokenId 应 revert

**事件定义检查**
- ERC-20 Transfer：`event Transfer(address indexed from, address indexed to, uint256 value)`
- ERC-20 Approval：`event Approval(address indexed owner, address indexed spender, uint256 value)`
- ERC-721 Transfer：`event Transfer(address indexed from, address indexed to, uint256 indexed tokenId)`
- 检查每个修改操作是否发出事件

**接口实现检查**
- 是否声明了标准接口（`is IERC20` 等）
- 函数签名是否完全匹配标准定义
- 所有函数都为 public 或 external（不能是 internal/private）

### L3: 逐行验证（20-40分钟）

**转账逻辑完整性**
- 转账失败是否 revert（不是返回 false）
- 是否验证金额 > 0 和余额充足
- 是否禁止转账到 address(0)
- 是否实现 check-effects-interactions 模式

**授权机制正确性**
- approve 后 allowance 是否正确更新
- transferFrom 是否扣减 allowance
- 是否实现对 race condition 的防护（approve 零值）

**批量操作**
- ERC-1155 balanceOfBatch 数组长度是否验证
- ERC-721 Enumerable 函数是否处理索引越界

### L4: 跨模块追踪（40+分钟）

- 追踪完整的代币转账流程（mint → transfer → burn）
- 验证状态更新的原子性
- 检查重入保护和权限控制
- 验证跨合约调用的安全性

## 研判标准

### 漏洞判定（Bug）

✓ 合约声称实现标准但缺少核心函数
✓ 返回值类型错误或缺失
✓ 事件定义不符合标准
✓ 逻辑漏洞导致标准函数无法使用
✓ 与标准工具（DEX、钱包、索引器）不兼容

### 误报排除（False Positive）

✗ 合约不声称实现标准
✗ 函数名相似但签名完全不同
✗ 合约明确说明是自定义实现
✗ 代码有 TODO 注释且未部署

### 代码异味（Code Smell）

⚠ 函数存在但实现为空
⚠ 缺失 emit 事件
⚠ 非标准的参数顺序或命名
⚠ 缺少最佳实践（重入保护等）

## 低风险评定

以下情况应评为低风险：
- 合约明确文档声明偏离标准的原因
- 在完整实现标准基础上增加额外功能
- 多标准支持且清晰区分各版本
- 开发阶段合约（代码中有 TODO 注释）
- 代理模式中核心函数在代理合约实现

## 常见陷阱检查表

| 漏洞 | 表现 | 快速识别 |
|------|------|---------|
| 缺失 indexed | 索引器无法查询 | 搜索 `event Transfer` 检查 indexed |
| 返回值缺失 | transfer 返回 void | 搜索 `function transfer` 确认返回 bool |
| allowance 未扣减 | 无限制重复转账 | 搜索 `allowance[...] -= amount` |
| ownerOf 返回零地址 | 无法判断 NFT 存在性 | 搜索 `ownerOf` 的 require 条件 |
| 批量数组长度错误 | balanceOfBatch 结果错误 | 搜索数组处理检查长度匹配 |
| tokenURI 缺失 | NFT 无元数据 | 搜索 `function tokenURI` 检查返回值 |
| safeTransferFrom 缺失 | ERC-1155 不安全转账 | 确认 onERC1155Received 调用 |

## 语言特定检查

### Solidity / Vyper
- interface 完整性、返回值类型、event 定义

### Rust (SPL Token / CW20)
- instruction 类型完整性、account 结构字段、QueryMsg 处理

### Move (Coin)
- resource 结构定义、function 签名、泛型约束

### Go (Cosmos)
- message handler 完整性、query interface 实现、metadata 验证
