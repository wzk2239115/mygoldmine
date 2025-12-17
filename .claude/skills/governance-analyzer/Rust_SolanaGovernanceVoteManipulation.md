# Rust Solana 治理程序投票操纵

Solana 治理程序中投票账户验证不足，允许伪造投票记录、重复计票或操纵投票权重，导致治理决策被少数人控制。

## Details

**代码示例：**
```rust
// ❌ 漏洞示例
use anchor_lang::prelude::*;

#[program]
pub mod vulnerable_governance {
    pub fn cast_vote(ctx: Context<CastVote>, vote: bool) -> Result<()> {
        let proposal = &mut ctx.accounts.proposal;

        // ❌ 未验证投票账户的所有权
        let voter_token_account = &ctx.accounts.voter_tokens;

        // ❌ 直接使用账户余额，可被闪电贷操纵
        let vote_weight = voter_token_account.amount;

        if vote {
            proposal.yes_votes += vote_weight;
        } else {
            proposal.no_votes += vote_weight;
        }

        Ok(())
    }
}

#[derive(Accounts)]
pub struct CastVote<'info> {
    #[account(mut)]
    pub proposal: Account<'info, Proposal>,

    // ❌ 未验证token账户所有权
    pub voter_tokens: Account<'info, TokenAccount>,

    pub voter: Signer<'info>,
}

// ✅ 安全示例
#[program]
pub mod secure_governance {
    pub fn cast_vote(ctx: Context<CastVote>, vote: bool) -> Result<()> {
        let proposal = &mut ctx.accounts.proposal;
        let vote_record = &mut ctx.accounts.vote_record;

        // ✅ 验证投票记录未被使用
        require!(!vote_record.has_voted, ErrorCode::AlreadyVoted);

        // ✅ 使用快照时的余额
        let vote_weight = ctx.accounts.voter_token_snapshot.amount;

        require!(vote_weight > 0, ErrorCode::NoVotingPower);

        if vote {
            proposal.yes_votes += vote_weight;
        } else {
            proposal.no_votes += vote_weight;
        }

        vote_record.has_voted = true;
        vote_record.vote = vote;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct CastVote<'info> {
    #[account(mut)]
    pub proposal: Account<'info, Proposal>,

    // ✅ 验证投票记录PDA
    #[account(
        init_if_needed,
        payer = voter,
        space = 8 + VoteRecord::LEN,
        seeds = [
            b"vote-record",
            proposal.key().as_ref(),
            voter.key().as_ref()
        ],
        bump
    )]
    pub vote_record: Account<'info, VoteRecord>,

    // ✅ 使用快照账户
    #[account(
        constraint = voter_token_snapshot.owner == voter.key(),
        constraint = voter_token_snapshot.mint == proposal.governance_token
    )]
    pub voter_token_snapshot: Account<'info, TokenSnapshot>,

    #[account(mut)]
    pub voter: Signer<'info>,

    pub system_program: Program<'info, System>,
}
```

## Classify

**漏洞判定：**
- 投票权重基于实时token余额
- 未验证token账户所有权
- 缺少投票记录PDA防止重复投票
- 投票账户约束不严格

**误报识别：**
- 使用 SPL Governance 标准程序
- 投票权基于快照账户
- 有PDA防止重复投票
- 账户约束完整

**代码异味：**
- 直接读取token amount
- 缺少seeds约束
- 未使用init_if_needed
