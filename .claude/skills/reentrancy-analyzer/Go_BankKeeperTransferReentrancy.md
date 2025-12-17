# Go Bank Keeper Transfer Reentrancy（银行模块转账重入）

## Details

**典型代码模式（Cosmos SDK Bank Module）：**

```go
// 易受攻击的代码模式：Bank Keeper 钩子中的重入
func (k Keeper) SendCoins(ctx sdk.Context, fromAddr, toAddr sdk.AccAddress, amt sdk.Coins) error {
    // 1. 验证地址
    if fromAddr.Empty() || toAddr.Empty() {
        return sdkerrors.Wrap(sdktypes.ErrInvalidAddress, "addr is empty")
    }

    // 2. 检查余额（检查完毕，但状态还未变更）
    balance := k.GetBalance(ctx, fromAddr, amt[0].Denom)
    if balance.LT(amt[0].Amount) {
        return sdkerrors.Wrapf(sdktypes.ErrInsufficientFunds, "insufficient balance")
    }

    // 3. 触发 BeforeSend Hook（危险点：状态还未更新！）
    if err := k.hooks.BeforeSend(ctx, fromAddr, toAddr, amt); err != nil {
        return err
    }

    // 4. 执行转账（减少发送方，增加接收方）
    k.SubBalance(ctx, fromAddr, amt)
    k.AddBalance(ctx, toAddr, amt)

    // 5. 触发 AfterSend Hook（危险点：此时钩子可能发起新的转账）
    if err := k.hooks.AfterSend(ctx, fromAddr, toAddr, amt); err != nil {
        // 注意：如果钩子失败，转账已经执行，状态不可回滚！
        return err
    }

    // 6. 发出事件
    ctx.EventManager().EmitEvent(...)

    return nil
}

// 风险的钩子实现（攻击者可控）
func (h MyHook) AfterSend(ctx sdk.Context, from, to sdk.AccAddress, amt sdk.Coins) error {
    // 在这里可以再次调用 SendCoins，形成重入！
    return k.SendCoins(ctx, to, attacker, amt)
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索 `SendCoins`, `BurnCoins`, `MintCoins` 等资产操作函数
- 追踪钩子调用点：`BeforeSend`, `AfterSend`, `BeforeBurn`, `AfterBurn` 等
- 识别钩子的实现方式（是否由外部模块注册）
- 检查状态变更的时机：是在钩子前还是钩子后
- 关注是否存在"检查后使用"（TOCTOU）的漏洞
- 追踪钩子链：是否可能通过钩子调用链导致深层重入

**快速定位保护机制技巧（L2-跳读 + L4-跨模块追踪）：**
- **L2** - 检查是否使用了 `SendEnabledCoin` 或其他保护机制
- **L2** - 查找钩子执行前是否已完成状态更新（**Checks → Effects → Hooks** 模式）
- **L2** - 验证钩子失败时是否能正确回滚状态
- **L4** - 追踪所有注册的钩子实现，检查是否可能发起新的 SendCoins 调用
- **L4** - 检查钩子中是否禁止了同一资产的重复转账
- **L2** - 识别是否存在递归调用的防护机制（如转账深度限制）

## Classify

**判定为漏洞：**
- Bank Keeper 的 SendCoins 在钩子执行前已完成状态更新，但钩子可能发起新的转账
- 钩子实现由外部不受信任的模块提供，可能包含恶意逻辑
- 状态更新与钩子调用之间无同步机制，导致钩子可见到中间状态
- 钩子失败时，已完成的转账无法回滚
- 存在钩子链式调用，允许无限深度的重入

**判定为误报：**
- Bank Keeper 使用了互斥锁或消息队列保护转账操作
- 钩子为只读操作或已被白名单限制
- 钩子失败时能正确使用 defer 或事务回滚机制恢复状态
- 钩子执行深度已被限制（如递归深度计数器）
- 所有外部钩子已被审计，确认无恶意逻辑

**判定为代码异味：**
- 钩子调用顺序不清晰，BeforeSend 和 AfterSend 的责任划分模糊
- 缺少文档说明 Bank Keeper 转账的原子性保证
- 钩子实现的安全性依赖于外部模块的自觉遵守

## Low risk

**以下场景可评为低风险：**
- 钩子为内置钩子，由官方审计过的模块实现（如治理、税收）
- 钩子已被限制为只读操作，无法发起新的转账
- Bank Keeper 使用了事务机制，钩子失败时能完全回滚
- 存在转账深度限制机制，防止无限递归
- 仅处理测试币种，未涉及真实价值资产
- 钩子注册机制已被限制，仅系统级模块可注册

## Audit Checklist

- [ ] 检查所有 Bank Keeper 的资产操作函数（SendCoins, BurnCoins, MintCoins）
- [ ] 识别钩子调用点，验证是否在状态更新前或之后
- [ ] 检查钩子失败时的处理机制，确认状态能正确回滚
- [ ] 审查所有注册的钩子实现，确认无恶意逻辑
- [ ] 验证是否存在转账深度限制机制
- [ ] 检查 BeforeSend 和 AfterSend 的语义是否正确分离
- [ ] 执行单元测试，模拟钩子中的重入场景
- [ ] 检查所有调用 SendCoins 的地方，是否可能受到钩子重入的影响

## References

- [Cosmos SDK Bank Module](https://docs.cosmos.network/main/modules/bank/)
- [Bank Module Keeper Implementation](https://github.com/cosmos/cosmos-sdk/blob/main/x/bank/keeper/send.go)
- [Hook Pattern in Cosmos SDK](https://docs.cosmos.network/main/building-modules/hook.html)
