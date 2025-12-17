# 缺失签名者检查（Rust - Solana/Sui）

**漏洞描述：** 关键指令未验证交易签名者身份或 `is_signer` 标志，导致任意用户可冒充授权账户执行敏感操作

## Details

**对应代码示例：**
```rust
// processor.rs - 风险示例（Native Solana Program）
pub fn process_withdraw(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    amount: u64,
) -> ProgramResult {
    let account_iter = &mut accounts.iter();
    let vault_account = next_account_info(account_iter)?;
    let recipient = next_account_info(account_iter)?;
    let authority = next_account_info(account_iter)?;
    
    // ❌ 未检查 authority.is_signer
    // ❌ 未验证 authority 是否为 vault 所有者
    
    **vault_account.lamports.borrow_mut() -= amount;
    **recipient.lamports.borrow_mut() += amount;
    
    Ok(())
}

// lib.rs - 风险示例（Anchor 框架）
#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut)]
    pub vault: Account<'info, VaultState>,
    /// CHECK: 缺少 Signer 类型约束
    pub authority: AccountInfo<'info>,
    #[account(mut)]
    pub recipient: SystemAccount<'info>,
}

pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
    // ❌ authority 为 AccountInfo 而非 Signer<'info>
    // ❌ 未手动检查 authority.is_signer
    let vault = &mut ctx.accounts.vault;
    vault.balance -= amount;
    Ok(())
}
```

**快速定位核心操作的技巧（L2:跳读）：**  
- **Native 程序：** 扫描 `AccountInfo` 参数列表，定位包含 `lamports.borrow_mut()`、`data.borrow_mut()`、`realloc()` 的状态修改操作
- **Anchor 程序：** 检查 `#[derive(Accounts)]` 结构体中使用 `AccountInfo<'info>` 而非 `Signer<'info>` 的字段，尤其是名为 `authority`、`admin`、`owner` 的参数
- 快速跳读敏感指令：`withdraw`、`transfer`、`close_account`、`set_authority`、`initialize`、`mint`、`burn`
- 定位权限相关字段：通过 `/// CHECK:` 注释标记但无 `Signer` 约束的账户参数

**快速定位保护机制的技巧（L3:逐行读）：**  
- **Native 程序必查项：**
  - `if !authority.is_signer { return Err(ProgramError::MissingRequiredSignature); }`
  - `require_keys_eq!(account.owner, expected_authority)` - 检查账户所有者匹配
  - `account.owner == program_id` - 验证账户归属当前程序
- **Anchor 程序必查项：**
  - 类型约束：`pub authority: Signer<'info>` - 框架自动验证 `is_signer`
  - 账户约束：`#[account(has_one = authority @ ErrorCode::Unauthorized)]` - 关联身份校验
  - 手动校验：`require!(ctx.accounts.authority.key() == expected_key, ErrorCode::InvalidAuthority)`
- **PDA 派生验证：** 涉及 `find_program_address` 或 `seeds` 约束时，确认派生参数中是否包含 signer 公钥
- **跨 CPI 调用：** 检查 `invoke()` 或 `invoke_signed()` 的 AccountMeta 是否正确设置 `is_signer: true`

## Classify

**漏洞判定：**  
- 执行特权操作（资产转移、权限变更、账户关闭、参数修改）时，完全未检查任何账户的 `is_signer` 标志
- Anchor 程序中权限角色使用 `AccountInfo` 而非 `Signer` 类型，且函数内无手动 `require!` 校验
- PDA 派生 seeds 中未包含 signer 公钥，导致任意用户可构造相同 PDA 地址执行操作
- 跨 CPI 调用传递的 signer 权限未在目标程序侧重新验证

**误报判定：**  
- 指令为公开操作（如质押、投票），设计上允许任意用户调用且仅修改调用者自身账户
- Anchor 框架中虽使用 `AccountInfo`，但紧接着通过 `.as_ref().signer_key()` 或 `UncheckedAccount` 进行手动验证
- 账户所有权校验可替代 signer 检查：操作对象为程序自身拥有的 PDA，且 seeds 中包含调用者公钥作为唯一性保证
- 只读查询操作（如 `get_balance`、`view_config`），无状态修改

**代码异味判定：**  
- `/// CHECK:` 注释中说明"需调用者签名"，但代码中无对应 `is_signer` 检查
- 使用 `UncheckedAccount` 类型但验证逻辑分散在多个 helper 函数中，可追踪性差
- Signer 检查存在但位于非关键路径：如在日志记录前检查，但在实际转账前未复查
- 部分指令有签名者验证，同一合约其他敏感指令缺失，缺乏一致性

## Low risk

- **自主账户操作：** 所有修改的账户通过 PDA 派生，seeds 包含 `[signer.key().as_ref(), "user_state"]`，确保用户仅能操作自身数据
- **只读指令：** 指令函数仅读取账户数据返回结果，所有账户参数均无 `mut` 修饰
- **协议层防护：** Solana 运行时账户租金检查、Sui Move 所有权系统等底层机制已提供隔离保护
- **多重签名托管：** 资产存储在多签 PDA 中，单一 signer 缺失检查不构成完整攻击路径（但仍建议修复）
- **受限操作范围：** 指令仅修改元数据或配置参数，不涉及代币转移或权限提升，业务影响可控
