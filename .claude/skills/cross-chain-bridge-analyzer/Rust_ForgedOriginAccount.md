# Rust_ForgedOriginAccount - 伪造来源账户

**Rust**  
常出现在基于 Substrate 或 Solana 的跨链中继器、状态验证器或桥接 pallet 实现中。攻击者通过伪造跨链消息的来源账户身份，绕过权限检查执行未授权操作。

## Details

### 典型代码模式

**Substrate Pallet 场景：**
```rust
// 漏洞示例：直接信任来源账户，未验证跨链证明
pub fn handle_cross_chain_message(
    origin: OriginFor<T>,
    source_chain: ChainId,
    source_account: AccountId,  // ⚠️ 未验证
    payload: Vec<u8>
) -> DispatchResult {
    let sender = ensure_signed(origin)?;
    // 直接使用 source_account 进行权限操作
    Self::execute_privileged_action(source_account, payload)?;
    Ok(())
}
```

**Solana 程序场景：**
```rust
// 漏洞示例：未校验 cross_program_invocation 的来源
pub fn process_bridge_message(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    data: &[u8]
) -> ProgramResult {
    let source_account = next_account_info(accounts)?;
    // ⚠️ 未验证 source_account 是否为合法跨链账户
    invoke_signed(&instruction, &[source_account.clone()], &[])?;
    Ok(())
}
```

### 快速定位核心操作 **[L2-L3]**

**关键函数入口：**
- Substrate: `handle_*`, `process_*`, `relay_*`, `execute_cross_chain_*`
- Solana: `process_instruction`, `invoke_cross_chain`

**核心操作点：**
1. **L2** - 跳读查找账户提取逻辑：`ensure_signed()`, `next_account_info()`, `from_account_info()`
2. **L3** - 逐行追踪账户使用：权限检查前的 `source_account/origin_account` 赋值
3. **L3** - 验证是否存在：`verify_proof()`, `check_consensus()`, `validate_merkle_path()`

**高危操作标志：**
- 权限提升：`ensure_root()`, `is_signer`, `SystemProgram::transfer()`
- 资产转移：`T::Currency::transfer()`, `token::transfer()`
- 状态修改：`<Storage>::insert(source_account, ...)`

### 快速定位保护机制 **[L3-L4]**

**必查验证链：**
1. **L3** - 来源证明验证：
   - `verify_message_proof(merkle_root, proof)` - 是否验证消息哈希
   - `check_validator_signatures(signatures)` - 多签验证是否充分
   - `ensure_consensus_finality(block_height)` - 是否等待最终性

2. **L4** - 跨模块追踪账户映射：
   - 查找 `AccountMapping<ChainId, RemoteAccount, LocalAccount>` 存储
   - 验证 `get_local_account(source_chain, source_account)` 是否存在且调用
   - 追踪 `Origin::Signed` 与远程账户的绑定关系

3. **L3** - 上下文隔离检查：
   - `ensure_xcm_origin()` - XCM 来源校验
   - `check_relayer_authority(relayer)` - 中继器白名单
   - `validate_call_context(origin)` - 调用上下文是否可信

**审计检查点：**
```rust
// ✅ 安全模式
ensure!(Self::is_valid_remote_account(source_chain, &source_account), Error::InvalidOrigin);
let local_account = Self::map_remote_to_local(source_chain, source_account)?;
ensure_signed(origin)? == local_account  // 双重校验
```

## Classify

### 漏洞研判标准

**确认为漏洞：**
- 跨链消息处理函数直接使用未验证的 `source_account` 参数进行权限操作
- 缺失跨链证明验证（Merkle proof、多签、共识证明）直接信任中继器提交的账户信息
- 账户映射机制存在但未在关键路径调用，或映射表可被任意写入
- Origin 提升未校验远程账户与本地签名者的绑定关系

**误报情形：**
- `source_account` 仅用于日志记录或事件发射，不影响状态
- 函数内部已通过 `ensure_signed()` 完整验证了调用者身份，`source_account` 为冗余参数
- 上层已有 `ensure_root()` 或白名单校验，当前函数为内部辅助函数

**代码异味：**
- 验证逻辑存在但不完整（如仅验证签名格式未验证签名权重）
- 账户映射依赖链下预言机，存在时间窗口攻击风险
- 跨链消息重放保护缺失，虽不能伪造账户但可重复执行

### 验证维度

1. **数据流追踪**：从参数入口 → 验证点 → 使用点的完整路径
2. **权限等级**：操作的敏感度（资产转移 > 状态修改 > 查询）
3. **信任边界**：本地签名 > 多签证明 > 单一中继器 > 直接信任

## Low risk

### 低风险评级场景

**有限影响范围：**
- 伪造账户仅能修改非关键业务数据（如昵称、元数据），不涉及资产或权限
- 操作受严格金额/频率限制，单次攻击收益低于 Gas 成本

**多重防护机制：**
- 虽某层验证缺失，但存在经济惩罚机制（Slash 保证金 > 攻击收益）
- 多签门槛设置合理（2/3 或更高），且签名者为独立实体
- 存在延迟执行 + 挑战期机制，恶意消息可被撤销

**受限攻击条件：**
- 需预先通过KYC或质押机制成为白名单中继器
- 需同时控制源链和目标链的特定账户
- 依赖源链出现 51% 攻击等极端场景

**实际约束：**
- 仅影响测试网络或隔离环境
- 功能已标记为 deprecated 且无实际使用
- 代码路径需触发多个低概率条件组合（如特定区块高度 + 特定账户状态）

**注意**：即使评为低风险，仍需在报告中说明潜在风险路径和建议加固方案。
