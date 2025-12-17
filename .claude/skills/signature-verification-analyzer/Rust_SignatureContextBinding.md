# Rust 签名上下文绑定漏洞

**漏洞类型**: 签名消息未绑定具体交易参数或操作上下文，允许签名被跨操作重用  
**适用场景**: Substrate runtime、Solana program、链下授权、账户代理、跨链消息验证

## Details

### 典型代码示例

```rust
// 漏洞示例：签名仅绑定操作类型，未绑定具体参数
fn verify_transfer_signature(
    signature: &Signature,
    pubkey: &Pubkey,
    operation: &str,  // 仅验证 "transfer"
) -> bool {
    let message = operation.as_bytes();
    signature.verify(message, pubkey)
}

// 调用时未绑定 amount、recipient 等参数
verify_transfer_signature(&sig, &user_key, "transfer");
```

### 快速定位核心操作技巧 **[L2-L3]**

**关键模式识别**:
- **签名验证入口** (L2): 搜索 `verify`、`verify_signature`、`ed25519::verify`、`sr25519::verify`、`secp256k1_recover`
- **消息构造逻辑** (L3): 定位签名验证前的 `message` 构造，逐行检查是否包含所有关键参数（amount、nonce、recipient、deadline）
- **Substrate 特征**: 检查 `Encode::encode()`、`blake2_256`、`sp_io::crypto::*` 调用链
- **Solana 特征**: 关注 `msg!` 前的 `&[u8]` 拼接、`Pubkey::create_program_address` 的 seeds 参数

**红旗信号** (L1):
- 签名消息仅包含常量字符串或枚举类型
- 验证函数参数少于 3 个（签名、公钥、操作类型）
- 缺失 `nonce`、`timestamp`、`chain_id` 等防重放字段

### 快速定位保护机制技巧 **[L1-L4]**

**分层检查策略**:

1. **消息绑定完整性** (L3):
   - 验证签名消息是否包含: `(operation, amount, recipient, nonce/timestamp, chain_id, contract_address)`
   - Substrate: 检查是否使用 `SignedPayload` 或完整的 `Call` 结构体编码
   - Solana: 验证 PDA seeds 是否包含所有操作参数

2. **Nonce/重放保护** (L2):
   - 搜索 `nonce`、`counter`、`used_signatures`、`executed_txs` 等状态存储
   - 检查是否在验证后立即标记已使用: `used_nonces.insert(nonce)` 或 `mark_signature_used(hash)`

3. **上下文隔离** (L4):
   - 跨模块追踪签名是否混用：检查同一签名格式是否被多个 extrinsic/instruction 调用
   - 搜索 `SignedExtension` (Substrate) 或 `instruction_data` 前缀标识 (Solana)
   
4. **域分隔符** (L1):
   - 关键词: `DOMAIN_SEPARATOR`、`chain_id`、`program_id`、`pallet_name`
   - 缺失时标记为高风险

## Classify

**确认为漏洞的条件**:
- 签名消息缺少至少一个可变参数（金额、接收方、时间戳等）且该参数影响操作结果
- 同一签名可被用于不同操作上下文（如授权签名可用于转账、提款、投票）
- 无有效的 nonce 或时间窗口限制，允许签名跨交易重放

**归类为误报**:
- 签名仅用于身份验证（如登录），无关键状态变更操作
- 已通过链上事务机制隔离（Substrate 的 `SignedExtra` 自动绑定 nonce 和 genesis hash）
- 签名验证在只读查询中，不影响状态写入

**代码异味**:
- 签名绑定参数不充分但有外部限制（如时间窗口仅 5 秒）
- 未明确标识签名适用范围，虽当前业务逻辑未触发跨上下文复用

## Low risk

**低风险场景判定**:
- **严格时间限制**: 签名消息包含 `timestamp` 且验证时强制 `now - timestamp < 60s`，配合链上时间戳防篡改
- **单次使用标记**: 虽缺少参数绑定，但通过签名哈希去重（`used_signatures: HashSet<H256>`）且状态持久化
- **受限权限操作**: 签名仅授权低价值操作（如更新昵称、设置头像），经济损失可控
- **链上双重验证**: 签名验证后需经过 DAO 投票或多签确认，形成多层防护
- **封闭环境**: 私有链或测试网，签名者与验证者均为可信内部节点
