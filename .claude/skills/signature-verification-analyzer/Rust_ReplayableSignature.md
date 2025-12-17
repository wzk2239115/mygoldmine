# Rust 可重放签名漏洞审计指南

**漏洞描述**  
常出现在基于 Substrate 或 Solana 的链下授权、账户代理、跨链通信等业务逻辑实现中。签名验证逻辑未防止重放攻击，同一签名可被多次使用于不同交易或时间窗口。

## Details

**代码示例场景**：
```rust
// Substrate runtime 中的链下签名验证
pub fn verify_signature(origin, signature: Signature, message: Vec<u8>) {
    ensure!(signature.verify(&message, &signer), Error::InvalidSignature);
    // 缺少 nonce/timestamp/chain_id 等防重放检查
    Self::execute_action(origin, message);
}

// Solana 中未使用 account 状态防重放
pub fn process_instruction(accounts, signature, data) {
    verify_sig(&signature, &data)?;
    // 未标记 signature 已使用，未检查 account 状态
    transfer_tokens(accounts, amount)?;
}
```

**快速定位核心操作**（L2-L3 跳读至逐行）：
- 搜索关键函数：`verify`、`verify_signature`、`ed25519_verify`、`secp256k1_recover`
- Substrate：检查 `validate_unsigned`、`pre_dispatch` 中的签名验证
- Solana：检查 `process_instruction` 入口的签名处理
- 关注 `message`/`data` 构造逻辑，确认是否包含防重放字段
- 追踪签名验证后的状态更新，是否记录签名使用

**快速定位保护机制**（L1-L4 关键词扫描至跨模块追踪）：
- L1：搜索 `nonce`、`sequence`、`timestamp`、`deadline`、`chain_id`、`replay_protection`
- L2：检查签名消息体是否包含 `block_number`、`extrinsic_index`、`transaction_hash`
- L3：验证是否有 `used_signatures` 存储映射或账户状态标记
- L4：跨 pallet/program 追踪 `SignedPayload`、`SignedExtra` 的完整性
- Solana 特定：检查是否使用 `recent_blockhashes`、PDA 状态防重放
- Substrate 特定：检查 `CheckNonce`、`CheckMortality` 等 `SignedExtension` 是否生效

## Classify

**确认为漏洞的条件**：
- 签名验证通过后，未检查任何防重放标识（nonce/timestamp/used_flag）
- 相同签名在不同区块/时间可重复执行业务逻辑
- 签名消息未绑定链 ID、合约地址、特定上下文

**误报场景**：
- 签名用于只读查询操作，无状态变更
- 业务逻辑本身具有幂等性，重复执行无影响（如状态已达终态）
- 上层调用已有防重放保护（需跨模块确认）

**代码异味**：
- 防重放机制存在但逻辑复杂，难以快速验证有效性
- 依赖外部系统（如 indexer）进行重放检测，链上无保障

## Low risk

**以下情况可评为低风险**：
- 签名仅用于权限验证，后续操作有独立 nonce/状态检查
- 业务金额/影响极小，且有速率限制或冷却期
- 重放窗口极短（如仅当前区块有效），攻击成本高于收益
- 测试网环境或未上线功能
- 需多签协同，单一签名重放无法完成攻击

## 审计专业技巧与经验

### 真实漏洞典型特征

**特征 1：状态变更无防重放保护**
```rust
// 真实漏洞：签名验证后直接状态变更，无 nonce 检查
pub fn claim_reward(signer: AccountId, signature: Vec<u8>, amount: u128) {
    let msg = encode(&(signer.clone(), amount));
    ensure!(verify_sig(&signature, &msg), Error::InvalidSig);
    // ❌ 直接转账，无 nonce/已使用标记，同一签名可重复领取奖励
    pallet_balances::transfer(&signer, &self_account(), amount)?;
}
```

**特征 2：交叉 Pallet 导致防重放失效**
```rust
// Pallet A：验证签名后调用 Pallet B 的 extrinsic
pub fn authorize_transfer(sig: Signature, data: Vec<u8>) {
    verify_sig(&sig, &data)?;
    // Pallet B 未包含原始 signed_data，仅接收已解析的参数
    T::Transfer::do_transfer(account_id, amount)?;  // ❌ 上下文丢失
}
```

**特征 3：时间窗口过大**
```rust
// 防重放不完全：仅检查 block_number 范围，但范围设置过大
let current_block = frame_system::Pallet::<T>::block_number();
ensure!(
    signed_at_block >= current_block - 256,  // ❌ 256 块 (~26 分钟)，重放窗口过大
    Error::TxOutdated
);
```

### 常见误报陷阱

**误报 1：混淆"权限验证"与"交易唯一性"**

| 场景 | 判断 | 原因 |
|------|------|------|
| `签名用于验证操作发起者身份，但操作本身由 nonce 保护` | 不是漏洞 | nonce 在签名外层已防重放 |
| `签名验证后执行有状态变更的操作，但无任何防重放` | 是漏洞 | 同一签名可在任意时刻重复执行 |
| `多步流程：签名→验证→检查 nonce→执行` | 检查 nonce 位置 | 若 nonce 检查在签名验证之前可能被绕过 |

**误报 2：低估 Solana PDA 的防重放能力**
```rust
// 错误认为这是漏洞：实际上因为 PDA 状态已被修改，无法重放
pub fn claim_once(account: &AccountInfo, signer: Pubkey, signature: &Signature) {
    verify_sig(signature, &encode(&(signer, CLAIM_SEED)))?;

    let pda = get_pda(&signer, CLAIM_SEED);
    ensure!(!pda.is_initialized, Error::AlreadyClaimed);  // ✓ 状态保护

    pda.data.borrow_mut()[0] = 1;  // 标记已使用
}
```
**诊断**：虽然签名本身无 nonce，但 PDA 初始化后状态变更，重放自动失败。

**误报 3：跨链场景的虚假警报**
```rust
// 不是漏洞：每条链有独立的 chain_id，签名绑定特定链
pub fn verify_cross_chain_sig(sig: Signature, chain_id: u32, data: Vec<u8>) {
    let msg = encode(&(chain_id, data));  // ✓ chain_id 包含在签名消息中
    verify_sig(&sig, &msg)?;
    // 同一签名在另一条链上验证失败（chain_id 不同）
}
```

### 审计实战经验

**技巧 1：追踪完整的消息构造路径**
- 从调用入口开始，记录签名消息体所有成分
- 特别关注：是否包含 `account_id`、`nonce`、`block_number`、`chain_id`
- **关键**：消息中缺少的字段才是重放的"受害者"
- 示例：若消息仅包含 `amount`，则 `nonce` 及 `to_account` 重放风险最高

**技巧 2：区分"防重放责任边界"**
```
L0（最弱）：完全无防重放 → 确定漏洞
L1：签名消息包含防重放字段 → 检查字段有效性
L2：状态记录已使用签名 → 验证存储结构和检查逻辑
L3：上层交易 nonce 防护 → 确认不会被绕过
```

**技巧 3：构造最小化重放 PoC**
```rust
// 如何验证：模拟真实攻击
1. 构造 signed_msg，包含所有原始字段
2. 验证签名成功
3. 执行业务逻辑，修改状态（如余额转账）
4. 使用完全相同的 signed_msg 再次验证
5. ❌ 如果第 4 步仍验证成功且能再次修改状态 → 确认漏洞
```

**技巧 4：识别"隐藏的 nonce"**
- Substrate：`CheckNonce` → 自动递增账户 nonce
- Solana：`recent_blockhash` → 隐式防重放（有限的块范围）
- 自定义：搜索状态变更时序相关的检查

**技巧 5：阈值判断**
```
重放影响评分 = (被重放操作的金额/用户总资产) × (重放窗口/总时间) × (攻击难度倒数)

高危：金额 > 10%，窗口 > 1 小时，容易自动化重放
中危：金额 > 1%，窗口 > 10 分钟，需要多步操作
低危：金额 < 1%，窗口 < 1 分钟，需要外部条件触发
```

### 常见代码模式速查表

| 模式 | 风险等级 | 诊断 |
|------|---------|------|
| `verify_sig() → 直接状态变更` | 🔴 高 | 无防重放，100% 漏洞 |
| `verify_sig() → 检查 used_sigs map → 状态变更` | 🟢 低 | 有明确防重放 |
| `verify_sig() → 上层 nonce 已检查` | 🟡 中 | 需验证 nonce 检查的有效性 |
| `签名用于只读查询` | 🟢 低 | 无状态变更，非漏洞 |
| `PDA 初始化后修改状态` | 🟢 低 | 状态防重放（仅限 Solana）|
| `跨合约调用，内层无防重放` | 🔴 高 | 外层防护不保证内层安全 |
