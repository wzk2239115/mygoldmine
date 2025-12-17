# Solidity_UnboundSignerContext

**漏洞类型：** 签名者上下文未绑定  
**常见场景：** 授权委托、跨链消息验证、治理投票、元交易、多签钱包

## Details

**代码特征：**
```solidity
// 漏洞示例：签名消息缺少关键上下文
function executeWithSignature(address target, bytes calldata data, bytes memory signature) external {
    bytes32 hash = keccak256(abi.encodePacked(target, data)); // 缺少 address(this), msg.sender, nonce 等
    address signer = ECDSA.recover(hash, signature);
    require(hasRole(AUTHORIZED_ROLE, signer), "Unauthorized");
    target.call(data);
}
```

**快速定位核心操作（L2-L3）：**
- 搜索签名验证函数：`ecrecover`、`ECDSA.recover`、`verify`、`_verifySignature`
- 追踪签名哈希构造：`keccak256(abi.encodePacked(...))`、`keccak256(abi.encode(...))`、`_hashTypedDataV4`
- 检查 `abi.encode*` 内包含的字段是否完整（合约地址、调用者、nonce、chainId、业务参数）

**快速定位保护机制（L3-L4）：**
- 检查哈希构造是否包含 `address(this)` 防止跨合约重放
- 检查是否包含 `chainId` 或使用 EIP-712 的 `domainSeparator` 防止跨链重放
- 检查是否包含 `nonce` 或时间戳防止同合约内重放
- 检查是否包含 `msg.sender` 或调用者信息防止权限提升
- 检查是否包含 `functionSelector` 或操作类型防止跨功能重用
- 追踪 nonce 管理：`mapping(address => uint256) nonces` 及其自增逻辑
- 追踪签名时效：`deadline`、`validUntil`、`block.timestamp` 校验

## Classify

**确认为漏洞的条件：**
- 签名消息缺少 `address(this)` 且同一签名人在多个合约中具有相同权限
- 签名消息缺少 `chainId` 且合约部署在多条链上
- 签名消息缺少 `nonce` 且业务逻辑不可重复执行（转账、权限变更等）
- 签名消息缺少调用者身份但该身份在业务逻辑中被隐式依赖
- 签名消息缺少操作类型标识但同一合约有多个签名验证函数共用相同 signer 角色

**误报情况：**
- 签名仅用于一次性授权且合约有其他机制防止重放（如状态标记位）
- 业务逻辑本身幂等且允许重复执行（如查询类操作、只读验证）
- 合约设计为单链单例且无跨链部署计划

**代码异味：**
- 签名包含上下文但缺少文档说明签名格式
- 签名验证代码分散在多处且不统一
- 使用自定义哈希方案而非 EIP-712 标准

## Low risk

- 签名功能仅在受控环境使用（如测试合约、内部工具）
- 签名重放的影响可逆或可通过链下协调解决
- 缺失的上下文字段在当前部署环境下不可能导致实际攻击（如单链部署但缺少 chainId）
- 存在外层防护机制显著降低风险（如白名单、时间锁、多重签名）
- 业务逻辑设计上允许签名重用（如许可证验证、身份证明）

## 审计专业技巧

### 1. 真实漏洞识别三步法

**第一步：追踪签名数据流**
- 从 `ecrecover()` 或 `ECDSA.recover()` 的输入向上回溯
- 记录哈希构造时包含的所有字段：`abi.encode(field1, field2, ...)`
- 对比合约的状态变量、参数和链环境（chainId、block等）
- 识别缺失字段对应的攻击场景

**第二步：验证重放防护链**
- 确认是否存在明确的重放检查：`nonces[signer]++` 或 `usedSignatures[hash] = true`
- 检查重放防护是否在签名验证之前（错误示例：先执行操作再检查）
- 验证状态变更和重放防护是否原子性更新

**第三步：评估实际攻击可能性**
- 判断缺失字段是否导致真实攻击路径（不是假设性威胁）
- 验证攻击者是否能控制缺失字段或其衍生值
- 确认是否存在业务逻辑对该操作的限制

### 2. 真实漏洞案例

**案例1：跨链重放导致的双花（真实漏洞）**
```solidity
// 问题：缺少 chainId
function permitTransferFrom(address to, uint256 amount, bytes memory sig) external {
    bytes32 hash = keccak256(abi.encode(to, amount, nonce[msg.sender]++));
    require(signer == ECDSA.recover(hash, sig), "Invalid sig");
    token.transfer(to, amount);
}
// 攻击：同一签名在主网和 Arbitrum 上都能执行，导致双倍转账
```
**识别特征**：多链部署 + 相同签名人角色 + 不可逆操作

**案例2：权限提升通过签名重用（真实漏洞）**
```solidity
// 问题：缺少 functionSelector
function executeWithSignature(bytes calldata data, bytes memory sig) external {
    bytes32 hash = keccak256(abi.encode(data, msg.sender));
    require(governors[ECDSA.recover(hash, sig)], "Not governor");
    (bool success,) = address(this).call(data);
}
// 攻击：签署 "transfer governance" 的签名被用于执行 "drain pool" 调用
```
**识别特征**：多个签名验证函数 + 同一签名人 + 签名格式不包含操作类型

### 3. 常见误报及如何区分

**误报1：声称缺少 chainId 但项目声明单链**
- 验证方法：查看部署记录、合约构造函数注释、官方文档
- 真实情况：如果项目未来有多链扩展计划，仍应视为风险
- 区分标准：看是否存在跨链桥接合约或官方部署列表中的多链地址

**误报2：声称缺少 nonce 但签名只用一次**
```solidity
function claimReward(bytes32 merkleRoot, bytes memory signature) external {
    require(!claimed[msg.sender], "Already claimed");
    bytes32 hash = keccak256(abi.encode(merkleRoot, msg.sender));
    require(verifier == ECDSA.recover(hash, signature), "Invalid");
    claimed[msg.sender] = true;
}
// 误报：看似缺少 nonce，但 claimed[msg.sender] 标记位防止了重放
// 真实风险：即使缺少 nonce，业务逻辑本身防止了重放
```
**区分方法**：检查是否存在其他防重放机制且顺序正确

**误报3：声称缺少 address(this) 但合约自有权限检查**
```solidity
function executeProposal(bytes calldata data, bytes memory sig) external {
    bytes32 hash = keccak256(abi.encode(data));
    require(ECDSA.recover(hash, sig) == proposer, "Invalid");
    require(msg.sender == governance, "Not governance"); // 额外权限校验
}
// 虽缺少 address(this)，但调用者权限检查限制了跨合约重放的实际危害
```
**区分方法**：评估攻击者是否能同时满足所有条件

### 4. 审计检查清单

```
□ 签名验证 - 包含地址绑定
  □ abi.encode/abi.encodePacked 包含 address(this)
  □ 或使用 EIP-712 domainSeparator 自动包含地址和 chainId

□ 重放保护 - 包含至少一种机制
  □ nonce 递增：mapping(address => uint256) 且每次验证后自增
  □ 一次性标志：mapping(bytes32 => bool) usedSignatures
  □ 时间戳限制：deadline 不超过 1 天
  □ 幂等检查：业务逻辑本身不可重复执行

□ 多链考虑
  □ 如部署多链，chainId 必须包含在签名数据中
  □ 若使用 EIP-712，自动处理 chainId

□ 操作标识
  □ 若多个函数共用签名验证，必须包含 functionSelector
  □ 或为每个函数维护独立的签名方案

□ 代码审查
  □ 签名验证在所有业务逻辑前执行
  □ 重放防护更新与业务操作原子执行
  □ 签名格式有清晰注释或遵循 EIP-712 标准
```

### 5. 工具辅助审计

**推荐搜索模式**
- 搜索所有 `ecrecover` 和 `ECDSA.recover` 出现位置
- 对每处找到 `keccak256(abi.encode*(...))` 的完整参数列表
- 使用 AST 分析工具查看哈希构造的完整表达式树
- 对比 OpenZeppelin EIP-712Helper 的标准实现

**常见代码审计陷阱**
- nonce 定义为 `uint64` 可能导致溢出（十年后回绕）
- 签名验证后才进行重放检查导致 gas 浪费或重入
- 使用 `abi.encodePacked` 而非 `abi.encode` 导致碰撞可能性
