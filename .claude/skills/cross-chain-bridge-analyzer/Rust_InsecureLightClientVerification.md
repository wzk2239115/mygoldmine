# 不安全的轻客户端验证 (Insecure Light Client Verification)

**漏洞成因**：跨链桥中轻客户端验证逻辑不完整，允许伪造的区块头、状态证明或共识签名通过验证，导致恶意跨链消息被接受执行。

## Details

**代码示例**（Substrate Pallet）：

```rust
// 漏洞：未验证区块头的父哈希链条连续性
impl<T: Config> Pallet<T> {
    pub fn verify_header(header: &Header) -> bool {
        // ❌ 仅验证签名，未验证区块高度递增、父哈希关联
        Self::verify_signatures(&header.validator_set_id, &header.seal)
    }
    
    pub fn submit_state_proof(proof: Proof, header: Header) {
        ensure!(Self::verify_header(&header), Error::InvalidHeader);
        // ❌ 未验证 proof.root 是否匹配 header.state_root
        Self::apply_cross_chain_message(proof.message);
    }
}
```

**代码示例**（Solana Program）：

```rust
// 漏洞：轻客户端未验证签名者权重阈值
pub fn process_bridge_message(
    accounts: &[AccountInfo],
    header: BlockHeader,
    signatures: Vec<Signature>,
) -> ProgramResult {
    // ❌ 仅计数签名数量，未验证签名者在验证人集合中的权重
    require!(signatures.len() >= 2, BridgeError::InsufficientSignatures);
    // ❌ 未验证 header.slot 必须大于已存储的 last_verified_slot
    bridge_state.last_header = header;
}
```

**快速定位核心操作**（L3:逐行读）：
- 搜索关键函数：`verify_header`、`verify_proof`、`verify_signatures`、`submit_block`、`relay_message`
- 检查项：区块头验证流程是否包含**所有共识必要条件**（高度递增、父哈希连续性、时间戳合理性、签名者集合验证）
- 追踪 `ensure!` / `require!` 宏后的错误路径，确认验证失败是否真正拒绝执行

**快速定位保护机制**（L4:跨模块追踪）：
- 检查是否存在 `ValidatorSet` / `AuthoritySet` 模块，追踪验证人集合**更新逻辑**（是否可被单方面篡改）
- 验证状态证明时，需追踪 `state_root` 是否从**已验证的区块头**中提取（而非外部输入）
- 检查是否实现 `finality gadget`（GRANDPA/Casper）验证，搜索 `justification`、`commit`、`vote` 关键字
- Solana环境需确认 `Sysvar::SlotHashes` 的使用，防止引用未终局化的区块

## Classify

**归类为漏洞**：
- 轻客户端逻辑中任一共识规则缺失（如未验证签名者权重、区块高度可回退、状态根未关联）
- 允许使用未达最终性的区块头作为信任锚点
- 验证人集合更新无需超级多数签名或可被单方面更改

**归类为误报**：
- 代码中存在"验证跳过"逻辑但仅在测试环境(`#[cfg(test)]`)或治理升级紧急预案中启用
- 轻客户端为 Optimistic 模式（乐观验证），但存在欺诈证明挑战窗口期和惩罚机制

**归类为代码异味**：
- 验证逻辑存在但实现在链下中继器中（需评估中继器可信假设是否合理）
- 使用外部预言机提供验证结果（存在中心化风险但在明确信任模型内）

## Low risk

以下场景可给予低风险评级：

1. **验证宽松但有补偿机制**：允许部分无效证明通过，但存在延迟执行期+链上仲裁机制
2. **信任假设明确且可接受**：文档明确说明采用联盟链模式，验证人为KYC实体且数量<10（非去中心化场景）
3. **金额上限控制**：单笔跨链金额有硬编码上限且总锁仓量通过治理严格限制（最小化潜在损失）
4. **测试网或未激活功能**：轻客户端模块存在但桥接功能未在主网激活（需确认无治理提案可单方面激活）
5. **双重验证架构**：链上轻客户端验证宽松，但提款需链下守护者多签批准（实际安全依赖后者）

## 审计专业技巧与经验

### 技巧1: 区分真实漏洞 vs 误报的关键指标

**真实漏洞特征**：
- **验证链条断裂**：验证函数A调用了验证函数B，但B的返回值被忽略或条件检查不完整（如`if verify_header() { }` 但未检查所有返回场景）
- **信息流污染**：外部输入未经验证直接用于关键决策（如`header.state_root` 未从已验证块头关联提取）
- **原子性缺失**：多步验证过程可被中断（如先验证签名再更新状态，中间无锁机制导致竞态条件）
- **回退问题**：区块高度可向后更新（`last_verified_slot = header.slot` 缺少 `slot > last_verified_slot` 检查）

**常见误报陷阱**：
- 看到 `unimplemented!()` 或 `todo!()` 就判定为漏洞，实际该分支仅在测试或特定条件下执行
- 发现验证逻辑在链下中继器中就报告为漏洞，忽视了链上仲裁机制的存在
- 认为简化验证模式就是漏洞，未识别乐观证明+欺诈挑战期的完整安全模型

### 技巧2: 验证人集合操作的深度审计

**审计检查清单**：
1. **变更触发点**：搜索 `ValidatorSet` 赋值操作，确认是否需要链上多签批准
   ```rust
   // ✅ 正确：需要多签和时间锁
   pub fn update_validator_set(new_set: Vec<Validator>) {
       ensure!(Self::verify_multisig_approval(&new_set), Error::Unauthorized);
       ensure!(system::block_number() >= self.set_change_time + LOCK_PERIOD, Error::TooEarly);
       ValidatorSet::<T>::put(new_set);
   }

   // ❌ 漏洞：任何调用者可更新，无安全检查
   pub fn update_validator_set(new_set: Vec<Validator>) {
       ValidatorSet::<T>::put(new_set);
   }
   ```

2. **权重计算**：验证签名者权重总和的计算逻辑是否存在整数溢出或除以零
3. **集合大小约束**：是否存在最小验证人数要求防止单人签名漏洞

### 技巧3: 状态证明与区块头关联性验证

**常见关联漏洞模式**：
```rust
// ❌ 漏洞模式1：proof 来源不可信
pub fn submit_proof(proof: Proof) {
    // proof.block_root 可能来自任意未验证的源
    let state = merkle_verify(&proof.root, &proof.path)?;
    apply_state(state);
}

// ✅ 修正：proof 必须与已验证的块头关联
pub fn submit_proof(proof: Proof, header_hash: H256) {
    ensure!(Self::is_header_finalized(header_hash), Error::NotFinalized);
    let header = VerifiedHeaders::<T>::get(header_hash)?;
    ensure!(header.state_root == proof.root, Error::RootMismatch);
    let state = merkle_verify(&proof.root, &proof.path)?;
    apply_state(state);
}
```

**审计策略**：
- 追踪 `state_root` 来源：必须从已验证块头的字段提取，不能接受外部参数
- 验证 Merkle 路径长度是否与应用场景合理（过长路径可能指示数据污染）

### 技巧4: 共识规则完整性自检表

| 规则项 | 检查方法 | 常见漏洞表现 |
|--------|--------|-----------|
| 块高递增 | `current_height > last_height` | 允许高度向后更新或跳跃验证 |
| 父哈希链 | `header.parent_hash == prev_header.hash` | 断裂块之间无关联性检查 |
| 时间戳单调 | `current_time > last_time` | 允许时间回退（51% 攻击向量） |
| 签名者权重 | `sum(weights) >= threshold` | 仅计数而不考虑权重或重复签名 |
| 最终性 | `justification || supermajority_reach` | 使用未终局块头作为信任锚 |
| 验证人变更 | `multisig_approval && time_lock` | 无多签或时间锁保护 |

### 技巧5: Solana 特定漏洞模式识别

**Solana 轻客户端常见误报区分**：
```rust
// ❌ 初看像漏洞：仅检查签名数量
require!(signatures.len() >= 2/3 * validators.len());

// 但需检查：这些签名者是否已在 Sysvar::SlotHashes 中验证？
// 如果是则可接受，如果签名者身份未验证则是漏洞

// ⚠️ 真实漏洞：使用未确认的 slot
let header = accounts[2].try_borrow_data()?;
require!(header.slot > current_slot); // ❌ 允许未终局化块
```

**正确做法**：
- 必须通过 `Sysvar::SlotHashes` 历史记录验证块哈希（最多 256 个之前的块）
- 不能直接接受未在 `SlotHashes` 中的块引用

### 技巧6: 欺诈证明与乐观验证模式识别

**需要特别考察的场景**：
```rust
// 初看是漏洞，实际可能是合理的乐观模式
pub fn optimistic_relay(message: Message, proofs: Vec<Proof>) {
    // 直接接受，不完全验证
    pending_messages.insert(message);

    // 但需要确认这三点：
    // 1️⃣ 是否存在挑战期？(challenge_period > 0)
    // 2️⃣ 是否有欺诈证明机制？(fraud_proof_handler 可追溯)
    // 3️⃣ 是否有惩罚机制？(slashing_condition 对错误中继者)
}
```

### 技巧7: 链下中继器可信性评估

**关键问题**：
1. 中继器合约地址是否可被治理更改？
2. 中继器私钥管理流程是否有审计报告？
3. 是否存在链上验证机制作为二层防护？
4. 能否绕过中继器直接在链上调用验证函数？

**正确的链下中继架构**：
```rust
// ✅ 链上合约验证不依赖特定中继器
pub fn verify_and_execute(
    message: Message,
    proof: CrossChainProof,
    relayer: AccountInfo, // 仅用于费用支付，非验证
) {
    // 验证逻辑与中继器身份无关
    ensure!(Self::verify_cross_chain_proof(&proof), Error::InvalidProof);
    execute_message(message);
    pay_relayer_fee(relayer);
}
```

### 技巧8: 快速风险分级的实战流程

**5分钟快速判定流程**：
1. **第一步** (30秒)：搜索所有 `verify_*` 函数，数一下有多少个，对比白皮书共识规则数 → 匹配度低则可能有漏洞
2. **第二步** (1分钟)：追踪每个 `verify_*` 的返回值，是否都被 `ensure!` 或 `require!` 检查 → 发现忽视即为漏洞
3. **第三步** (1.5分钟)：搜索 `ValidatorSet`、`state_root` 等关键变量，检查写入前是否需多签验证 → 无验证即为漏洞
4. **第四步** (1.5分钟)：检查是否存在 `finality` 相关代码或时间锁，判定是完全验证还是乐观模式 → 确定风险基线
5. **第五步** (30秒)：查看注释和配置项，确认是否有文档说明采用简化信任模型 → 若有则可能非漏洞

这个流程可在5分钟内将风险从"未知"分类为"确定漏洞"、"需深入审计"或"误报"三类。
