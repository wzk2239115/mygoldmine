# Solidity - 跨链签名绕过

**漏洞类型**：跨链消息签名验证逻辑缺陷，允许伪造签名通过验证  
**常见场景**：跨链资产桥接、通用消息传递、NFT 跨链迁移、跨链治理投票

## Details

### 代码示例

```solidity
// 易受攻击模式 1: ecrecover 零地址未检查
function relayMessage(bytes memory message, bytes memory signature) external {
    bytes32 hash = keccak256(message);
    address signer = ecrecover(hash, v, r, s);
    require(signer == trustedRelayer, "Invalid signer"); // signer 可能为 0x0
    _executeMessage(message);
}

// 易受攻击模式 2: 签名未绑定目标链 ID
function bridgeAsset(uint256 amount, bytes calldata proof) external {
    bytes32 msgHash = keccak256(abi.encode(msg.sender, amount));
    address validator = _recoverSigner(msgHash, proof);
    require(validators[validator], "Invalid validator");
    _mint(msg.sender, amount); // 可在多条链上重放
}

// 易受攻击模式 3: Merkle 证明未验证叶子内容
function claimAsset(bytes32[] calldata proof, bytes calldata leafData) external {
    bytes32 leaf = keccak256(leafData);
    require(MerkleProof.verify(proof, merkleRoot, leaf), "Invalid proof");
    // 未解析 leafData 内容，攻击者可控制解析逻辑
    (address to, uint256 amount) = abi.decode(leafData, (address, uint256));
    _mint(to, amount);
}

// 易受攻击模式 4: 多签阈值计算错误
function submitCrossChainTx(bytes calldata data, bytes[] calldata sigs) external {
    bytes32 hash = keccak256(data);
    uint256 validSigs;
    for (uint i = 0; i < sigs.length; i++) {
        address recovered = _recover(hash, sigs[i]);
        if (guardians[recovered]) validSigs++; // 未去重，同一签名可重复计数
    }
    require(validSigs >= threshold, "Not enough signatures");
    _execute(data);
}
```

### 快速定位核心操作（**审计等级：L3-逐行读**）

**关键函数特征**：
- `ecrecover` / `ECDSA.recover` / `SignatureChecker.isValidSignatureNow`
- `verify` / `verifyProof` / `MerkleProof.verify`
- `relayMessage` / `executeMessage` / `bridgeAsset` / `claimFromSource`
- 包含 `signature` / `proof` / `witness` 参数的外部函数

**定位步骤**：
1. 全局搜索 `ecrecover`、`recover`、关键字查找所有签名验证点
2. 定位跨链入口函数（通常标记 `onlyRelayer`、`whenNotPaused`、注释含 `cross-chain`）
3. 追踪签名哈希构造逻辑（`keccak256(abi.encode(...))`、`_hashTypedDataV4`）
4. 检查签名验证后的权限提升操作（`_mint`、`transfer`、状态变更）

### 快速定位保护机制（**审计等级：L4-跨模块追踪**）

**必查项**：
- **零地址检查**：`ecrecover` 返回值是否判空（`!= address(0)`）
- **域分隔符**：签名哈希是否包含 `chainId` / `block.chainid` / `domainSeparator`
- **Nonce 绑定**：是否存在 `nonces[user]++` 或全局递增计数器
- **重放保护**：是否记录已处理的 `messageHash` / `txId`（`processedMessages[hash] = true`）
- **签名去重**：多签场景中是否检查 `recovered > lastRecovered` 或使用 `EnumerableSet`
- **证明完整性**：Merkle 证明验证后是否解析并校验叶子数据的业务字段

**跨模块追踪要点**：
1. 签名验证函数是否为内部库（如自实现的 `SignatureValidator`），需深入检查实现
2. 哈希构造是否调用抽象函数（如 `_getMessageHash`），需检查继承链中的实现
3. 验证器地址来源（`trustedRelayer` / `validators[addr]`）的更新权限是否过度中心化
4. 跨链消息是否依赖外部预言机（如 Chainlink），需审查预言机数据刷新机制

## Classify

### 漏洞
- **签名返回零地址未拦截**：`ecrecover` 失败返回 `0x0`，若 `trustedRelayer` 可被设为零地址或未初始化，构成高危漏洞
- **缺失链 ID 绑定**：签名消息未包含 `chainId`，可在测试网/分叉链重放，造成资产双花
- **Nonce 未递增**：允许历史签名重复使用，可无限次触发跨链操作
- **多签去重缺失**：同一签名被重复计数达到阈值，单个恶意验证者可控制多签系统
- **Merkle 证明伪造**：仅验证证明路径，未校验叶子内容的业务逻辑字段（如 `recipient`、`amount`）

### 误报
- **签名验证在上层合约**：当前合约标记 `onlyBridge` 修饰器，实际验证逻辑在调用方已完成
- **链下签名为辅助功能**：签名仅用于 Gas 代付（元交易），不涉及权限提升
- **测试/模拟模式**：合约标记 `testnet` 或存在 `skipVerification` 开关（需确认生产环境不可触发）

### 代码异味
- **自实现签名验证库**：未使用 OpenZeppelin 的 `ECDSA` 库，建议替换以避免实现错误
- **硬编码验证器地址**：验证者地址写死在代码中，缺乏动态更新机制
- **签名有效期过长**：签名消息未包含 `deadline` 参数，历史签名可在未来任意时刻使用

## Low risk

### 低风险场景判定

**业务隔离性充分**：
- 签名仅控制用户自身资产（如用户为自己跨链转账），攻击者伪造签名仅影响自己
- 操作可回滚或有争议期（如 Optimistic Rollup 的 7 天挑战期）

**经济损失受限**：
- 单笔跨链金额存在硬编码上限（如 `amount <= maxBridgeAmount`）
- 受攻击资产池隔离（如测试代币池，与主资产池分离）

**攻击成本显著**：
- 需控制 N/M 多签中的绝对多数（如 7/10），且验证者为知名机构
- 签名验证依赖硬件安全模块（HSM）或 TEE 环境，伪造需突破物理隔离

**已有外部监控**：
- 存在链下监控服务实时对比源链和目标链状态，异常交易可被暂停
- 集成去中心化预言机网络（如 Chainlink OCR），单点伪造无法通过共识

**注意**：即使满足低风险条件，仍需在报告中标注潜在风险点，建议添加防御性检查。
