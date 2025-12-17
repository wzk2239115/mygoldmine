# Rust Solana CPI Context Confusion（Solana CPI 权限上下文混淆）

## Details

**典型代码模式（Solana CPI）：**

```rust
// 易受攻击的代码模式：CPI 中权限上下文混淆
#[derive(Accounts)]
pub struct TransferViaDelegate<'info> {
    #[account(mut)]
    pub signer: Signer<'info>,
    #[account(mut)]
    pub user_ata: Account<'info, TokenAccount>,  // 用户的 ATA 账户
    #[account(mut)]
    pub vault_ata: Account<'info, TokenAccount>, // 金库的 ATA 账户
    pub token_program: Program<'info, Token>,
    // remaining_accounts 中可能包含任意账户
}

pub fn transfer_via_delegate(
    ctx: Context<TransferViaDelegate>,
    amount: u64,
) -> Result<()> {
    // 1. 检查签名者权限
    require!(ctx.accounts.signer.is_signer, ProgramError::MissingRequiredSignature);

    // 2. 验证 ATA 所有者（但不够完整）
    require_eq!(
        ctx.accounts.user_ata.owner,
        ctx.accounts.signer.key(),
        ProgramError::InvalidAccountOwner
    );

    // 3. 危险点：将 remaining_accounts 原样转发给 Token Program
    // 被调用的 Token Program 可能会访问这些账户
    let ix = spl_token::instruction::transfer(
        &ctx.accounts.token_program.key(),
        &ctx.accounts.user_ata.key(),
        &ctx.accounts.vault_ata.key(),
        &ctx.accounts.signer.key(),
        &[], // 代理权限列表（应该是空的）
        amount,
    )?;

    // 4. CPI 调用（危险点：remaining_accounts 中的所有账户都被传入）
    let account_infos = [
        ctx.accounts.user_ata.to_account_info(),
        ctx.accounts.vault_ata.to_account_info(),
        ctx.accounts.signer.to_account_info(),
        ctx.accounts.token_program.to_account_info(),
        // 这里不应该包含 remaining_accounts，但有时会被不谨慎地包含
    ];

    // 实际风险：某些程序在处理 CPI 时会检查 remaining_accounts
    // 如果 remaining_accounts 中包含敏感账户（如用户的其他 ATA），
    // 被调用程序可能会错误地访问或修改这些账户
    invoke(&ix, &account_infos)?;

    Ok(())
}

// 风险场景：通过 remaining_accounts 传递额外账户
#[derive(Accounts)]
pub struct DangerousTransfer<'info> {
    #[account(mut)]
    pub signer: Signer<'info>,
    #[account(mut)]
    pub source_ata: Account<'info, TokenAccount>,
    #[account(mut)]
    pub dest_ata: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
    // remaining_accounts 可能包含其他 ATA 账户
}

pub fn dangerous_transfer(
    ctx: Context<DangerousTransfer>,
    amount: u64,
) -> Result<()> {
    // 危险：直接转发 remaining_accounts
    let mut account_infos = vec![
        ctx.accounts.source_ata.to_account_info(),
        ctx.accounts.dest_ata.to_account_info(),
        ctx.accounts.signer.to_account_info(),
        ctx.accounts.token_program.to_account_info(),
    ];

    // 将 remaining_accounts 全部加入
    account_infos.extend_from_slice(&ctx.remaining_accounts);

    // CPI 调用时，被调用程序可能会访问这些额外账户
    // 如果恶意构造，可能导致权限提升或资产盗取
    let ix = spl_token::instruction::transfer(...)?;
    invoke(&ix, &account_infos)?;

    Ok(())
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索 `invoke`, `invoke_signed` 关键字，追踪账户列表的构造
- 检查 `remaining_accounts` 是否被原样转发给 CPI 调用
- 识别账户验证的完整性：是否对每个账户进行了 `is_signer`, `is_writable`, `owner` 检查
- 追踪账户的来源：是否来自外部输入（remaining_accounts）或内部定义（#[account(...)]）
- 关注 CPI 调用前后的账户状态变化，是否可能被篡改

**快速定位保护机制技巧（L2-跳读 + L4-跨模块追踪）：**
- **L2** - 检查是否在 Accounts struct 中明确定义了所有需要的账户，避免依赖 remaining_accounts
- **L2** - 验证每个账户的约束条件（is_signer, is_writable, owner, type 等）
- **L2** - 确认 CPI 调用时仅传入必要的账户，不包含额外的 remaining_accounts
- **L4** - 追踪被调用程序（如 SPL Token）对账户的访问模式
- **L2** - 检查是否有账户索引验证，防止重复使用同一账户
- **L2** - 验证是否有权限上下文隔离：调用前后的签名权限是否一致

## Classify

**判定为漏洞：**
- CPI 调用时将 remaining_accounts 原样转发给被调用程序，未进行白名单检查
- 账户验证不完整，仅检查了部分约束条件（如仅检查 owner，未检查 is_writable）
- 被调用程序可能对 remaining_accounts 中的账户进行非预期的操作
- 权限上下文在 CPI 调用中被隐式传递，导致权限提升
- 存在账户别名（aliasing）风险：同一账户以不同身份被多次传入

**判定为误报：**
- CPI 调用已显式指定了所有必需的账户，未使用 remaining_accounts
- 所有账户都在 Accounts struct 中明确定义，带有完整的约束条件
- 被调用程序为系统级程序（Token Program、System Program），其行为已被完全审计
- 存在完整的账户验证链，包括 signer, writable, owner, type 等所有检查
- 权限上下文已被明确隔离，CPI 调用中的签名权限严格受限

**判定为代码异味：**
- CPI 调用的账户列表构造复杂，难以快速验证完整性
- 存在多个 CPI 调用，各自的账户验证标准不一致
- 缺少清晰的注释说明 remaining_accounts 的使用目的和安全性

## Low risk

**以下场景可评为低风险：**
- CPI 调用仅涉及 SPL Token Program 等官方程序，且已完全审计
- 所有账户都在编译时确定，无动态账户传递
- Accounts struct 中所有账户都有完整的约束条件（#[account(...)] 宏）
- 被调用程序无法对 remaining_accounts 进行任何有意义的操作
- CPI 调用明确指定了账户索引，防止了别名问题
- 程序运行在隔离的测试环境中，未涉及真实资产

## Audit Checklist

- [ ] 检查所有 `invoke` 和 `invoke_signed` 调用
- [ ] 验证每个 CPI 调用中的账户来源（Accounts struct vs remaining_accounts）
- [ ] 检查 remaining_accounts 是否被原样转发，是否存在白名单检查
- [ ] 验证每个账户的约束条件（is_signer, is_writable, owner, type）
- [ ] 检查是否存在账户别名（aliasing）风险
- [ ] 追踪权限上下文在 CPI 调用前后的变化
- [ ] 验证被调用程序对账户的访问权限，确认不存在权限提升
- [ ] 执行单元测试，模拟恶意构造 remaining_accounts 的场景
- [ ] 检查 Accounts struct 中是否有遗漏的约束条件

## References

- [Solana CPI Documentation](https://docs.solana.com/developing/programming-on-solana/calling-between-programs)
- [Anchor Framework Accounts](https://www.anchor-lang.com/docs/accounts)
- [Solana Security Best Practices](https://docs.solana.com/developing/programming-on-solana/security)
- [Account Constraints in Anchor](https://www.anchor-lang.com/docs/syntax#accounts)
