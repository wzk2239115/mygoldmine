# Solidity 签名重放攻击 (Signature Replay)

**漏洞类型**: 签名验证缺陷  
**常见场景**: 授权委托、跨链消息验证、治理投票、元交易、许可证功能

## Details

**典型代码模式**:
```solidity
function executeWithSignature(address user, uint256 amount, bytes memory signature) external {
    bytes32 messageHash = keccak256(abi.encodePacked(user, amount));
    address signer = recoverSigner(messageHash, signature);
    require(signer == user, "Invalid signature");
    // 执行操作
    _transfer(user, msg.sender, amount);
}
```

**定位核心操作 (L2-跳读)**:  
- 查找 `ecrecover` / `ECDSA.recover` / `recoverSigner` 调用点
- 定位签名消息构造: `keccak256(abi.encodePacked(...))` 或 `_hashTypedDataV4`
- 检查消息内容是否包含: `nonce`、`deadline`、`chainId`、`address(this)` 等上下文绑定字段
- 关注状态变更操作（转账、权限修改、铸造等）是否依赖签名验证

**定位保护机制 (L3-逐行读)**:  
- **nonce 机制**: 搜索 `nonces[user]++` 或 `mapping(address => uint256) nonces`，确认每次使用后递增
- **deadline 检查**: 查找 `require(block.timestamp <= deadline)` 或 `deadline` 参数
- **chainId 绑定**: 检查 `block.chainid` 是否参与签名哈希计算（EIP-712 中的 domain separator）
- **合约地址绑定**: 确认 `address(this)` 是否包含在消息哈希中
- **签名标记**: 查找 `usedSignatures[hash] = true` 或类似的已使用签名记录

**审计关键点**:
- 若消息哈希仅包含业务参数（如 `amount`、`to`），无任何防重放字段 → **High**
- 若存在 nonce 但未递增或可被攻击者控制 → **High**
- 若缺少 chainId 且项目可能部署多链 → **Medium**

## Classify

**确认为漏洞**:
- 签名可在同一合约不同交易中重复使用（缺少 nonce/唯一标识）
- 签名可在不同链上重放（缺少 chainId）
- 签名可在不同合约实例间重放（缺少 address(this)）
- nonce 机制存在但实现有缺陷（如先执行后递增，存在重入风险）

**判定为误报**:
- 签名消息包含完整的 EIP-712 domain separator（包含 chainId + address(this) + version）
- 存在严格的 nonce 自增机制且无法绕过
- 使用 EIP-2612 / EIP-3009 等标准实现，且遵循规范
- 签名仅用于只读查询或无状态操作（无实际风险）

**代码异味**:
- nonce 使用非连续方式（如时间戳），但在业务逻辑上可接受
- 仅使用 deadline 而无 nonce，但在特定场景下风险可控（如一次性凭证）

## Low risk

**以下情况可降级为 Low**:
- 签名操作仅影响签名者自身资产，且签名者有明确意愿重复执行（如用户授权自己多次提取奖励）
- 存在外部约束使重放无实际收益（如重放后合约状态已变更，操作失败或无效）
- 重放窗口极短（如 deadline 为 1 个区块）且业务场景下重放无意义
- 签名用于链下验证或日志记录，不触发状态变更
- 合约在单链部署且无跨链计划，缺少 chainId 但有其他充分防重放措施

## 审计专业技巧

### 真实漏洞识别经验

**1. 多层防御缺失时优先级判定**
- **Single protection failure**: 仅缺少 nonce 但有 chainId + deadline → High（可跨时间同链重放）
- **Multiple protection missing**: 同时缺少 nonce、chainId、address(this) → Critical（可跨链、跨合约、无时间限制重放）
- **Protection bypass**: nonce 存在但实现缺陷（如 `unchecked`、条件判断错误、状态回滚漏洞）→ Critical

**2. 实际案例对标**
- **Ronin Bridge (2022)**: 缺少足够的验证者签名验证 + 签名消息缺少 nonce，导致资金可被多次取出
  - 教训：即使有多签机制，如果签名消息不含唯一标识仍可被利用
- **Poly Bridge (2021)**: 跨链验证缺少目标链 chainId 绑定，签名可跨链重放
  - 教训：多链部署时 domain separator 必须包含 chainId

**3. 常见的隐藏防重放机制**
- 搜索 `mapping(bytes32 => bool) executedTxs` 或 `mapping(bytes => bool) usedSignatures`
- 检查 `mapping(address => uint256) lastBlockUsed` 是否实现序列化（不是真正的 nonce）
- 注意 EIP-712 中的 salt 字段可能实现唯一性
- OpenZeppelin 的 Nonces 库：`_useNonce(nonce)` 会自动检查并递增

### 误报与真漏洞的区分技巧

**识别特征表**:

| 场景 | 是否是漏洞 | 理由 |
|------|----------|------|
| 有 nonce 机制 + deadline + chainId（EIP-712 标准实现）| 否 | 三重保护足以防重放 |
| 仅有 nonce，无 deadline 或 chainId | 是 | 虽然 nonce 可防同链重放，但无法防跨链；deadline 缺失导致过期签名仍可用 |
| 有 deadline（如 1 小时）但无 nonce | 是 | 时间窗口内可多次重放，且跨链时无防护 |
| 签名消息含 `mapping key` 或 `contract state hash` | 否 | 虽非标准防重放，但状态变化可破坏条件 |
| 使用 `msg.sender` 替代 nonce | 误报概率高 | 需核实：是否存在 delegatecall；是否允许 flashloan 攻击；是否真正验证 msg.sender == signer |
| 仅有 amount 和 recipient | 是 | 典型重放漏洞，可在同一交易多次执行 |

**审计检查清单**:

1. **消息哈希构造审查**
   ```
   ✓ 包含 nonce（每个用户独立，递增可靠）？
   ✓ 包含 deadline（block.timestamp 验证）？
   ✓ 包含 chainId（从 EIP-712 domain separator）？
   ✓ 包含 address(this)（EIP-712 domain separator）？
   ✓ 是否使用 EIP-712 而非原始 keccak256？
   ```

2. **nonce 机制深度检查**
   - 搜索 nonce 的定义和更新：`mapping(address => uint256) nonces`
   - 验证递增逻辑：`require(nonce == nonces[user]); nonces[user]++;` vs `nonces[user]++`（后者易出错）
   - 检查是否存在重入漏洞：nonce 是否在状态变更前验证
   - 确认 nonce 值是否可被外部参数控制或可预测

3. **deadline 边界测试**
   ```solidity
   // 危险：deadline 可被操纵
   require(block.timestamp <= deadline); // deadline = MAX_UINT256 时无限期有效

   // 安全：deadline 有合理约束
   require(block.timestamp <= deadline && deadline - block.timestamp <= MAX_DURATION);
   ```

4. **跨链场景判定**
   - 若合约部署在多链（如 Ethereum + Arbitrum + Polygon）
   - 检查 domain separator 是否 hardcoded（危险）或动态获取 `block.chainid`（正确）
   - 对于跨链桥接合约：验证签名消息是否包含目标链 chainId

5. **权限与影响范围分析**
   - 签名验证的操作是否涉及转账、铸造、权限变更？
   - 是否存在 AccessControl / onlyOwner 等额外防护？
   - 若签名仅用于辅助验证（如 Oracle 数据）而非核心资产操作 → 可降级风险

**常见误判案例**:
- **假阳性 1**: 存在 `uint256 deadline` 参数但未使用（代码中无 `require(block.timestamp <= deadline)`）→ 确认这是真实漏洞，非误报
- **假阳性 2**: nonce 在合约中存在但签名消息中不包含 → 检查是否通过其他机制（如 mapping 查询）间接验证
- **假阳性 3**: 使用了 EIP-712 但 domain separator 配置错误（version 字段不对）→ 仍是漏洞，影响跨版本重放

### 实际审计工作流

1. **快速判定** (5 分钟)：签名消息包含 nonce + deadline + chainId？是 → 继续深度检查，否 → 高风险
2. **深度审计** (15 分钟)：逐行验证 nonce 递增、deadline 检查、EIP-712 配置
3. **场景分析** (10 分钟)：考虑多链、跨合约、flash loan、重入等攻击向量
4. **风险定级**：根据漏洞组合、影响范围、修复难度综合评分
