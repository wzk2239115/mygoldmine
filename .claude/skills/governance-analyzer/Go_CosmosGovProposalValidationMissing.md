# Go Cosmos 治理提案验证缺失

Cosmos SDK 治理模块中提案内容验证不足，允许提交格式错误或恶意的提案导致链停止或状态损坏。

## Details

**代码示例：**
```go
// ❌ 漏洞示例
func (k Keeper) SubmitProposal(
    ctx sdk.Context,
    content Content,
    proposer sdk.AccAddress,
) (Proposal, error) {
    // ❌ 未验证提案内容
    proposal := Proposal{
        Content:  content,
        Proposer: proposer,
    }

    // 直接存储，可能导致问题
    k.SetProposal(ctx, proposal)

    return proposal, nil
}

// ✅ 安全示例
func (k Keeper) SubmitProposal(
    ctx sdk.Context,
    content Content,
    proposer sdk.AccAddress,
) (Proposal, error) {
    // ✅ 验证提案内容
    if err := content.ValidateBasic(); err != nil {
        return Proposal{}, err
    }

    // ✅ 检查提案者有足够的质押
    minDeposit := k.GetDepositParams(ctx).MinDeposit
    if !k.bankKeeper.HasBalance(ctx, proposer, minDeposit) {
        return Proposal{}, errors.New("insufficient deposit")
    }

    // ✅ 验证提案类型在白名单内
    if !k.router.HasRoute(content.ProposalRoute()) {
        return Proposal{}, errors.New("invalid proposal type")
    }

    proposal := Proposal{
        Content:  content,
        Proposer: proposer,
        Status:   StatusDepositPeriod,
    }

    k.SetProposal(ctx, proposal)

    return proposal, nil
}
```

## Classify

**漏洞判定：**
- 提案内容未调用 ValidateBasic()
- 缺少提案者质押检查
- 提案类型无白名单限制

**误报识别：**
- 使用官方 gov module
- 有 ValidateBasic 调用
- 提案类型受router限制

**代码异味：**
- 直接接受任意Content
- 缺少参数范围检查
- 无提案大小限制
