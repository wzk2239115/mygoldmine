# Go Keeper Callback Reentrancy（Keeper 回调重入）

## Details

**典型代码模式（Cosmos SDK）：**

```go
// 易受攻击的代码模式：Keeper 方法中未防止重入
func (k Keeper) TransferCoins(ctx sdk.Context, fromAddr sdk.AccAddress, toAddr sdk.AccAddress, amt sdk.Coins) error {
    // 1. 检查余额
    fromBalance := k.GetBalance(ctx, fromAddr)
    if !fromBalance.IsGTE(amt) {
        return sdkerrors.Wrapf(sdktypes.ErrInsufficientFunds, "insufficient balance")
    }

    // 2. 执行状态变更前的检查
    module := k.GetModuleAccount(ctx, types.ModuleName)
    if module == nil {
        return sdkerrors.Wrap(sdktypes.ErrInvalidRequest, "module account not found")
    }

    // 3. 调用其他 Keeper（危险点：状态未更新，可能回调当前 Keeper）
    if err := k.bankKeeper.SendCoins(ctx, fromAddr, toAddr, amt); err != nil {
        return err
    }

    // 4. 执行钩子回调（危险点：此时状态仍未变更）
    if err := k.OnTransfer(ctx, fromAddr, toAddr, amt); err != nil {
        return err
    }

    // 5. 更新状态（太晚！在回调中已经可能被重入）
    k.SetBalance(ctx, fromAddr, fromBalance.Sub(amt...))
    k.SetBalance(ctx, toAddr, k.GetBalance(ctx, toAddr).Add(amt...))

    return nil
}

// 风险的回调函数
func (k Keeper) OnTransfer(ctx sdk.Context, from, to sdk.AccAddress, amt sdk.Coins) error {
    // 回调中可以再次调用 TransferCoins，形成重入
    return k.ExternalModuleKeeper.DoSomethingThatCallsBack(ctx, from, to, amt)
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索 `Keeper` 接收者的方法定义，重点关注涉及账户余额、权限变更的操作
- 追踪方法内部是否调用了其他 `Keeper`（如 `bankKeeper.SendCoins`, `stakingKeeper.Delegate` 等）
- 识别状态变更的顺序：**检查 → 调用其他 Keeper → 执行钩子 → 更新状态** 的模式
- 关注是否有 `AfterTransfer`、`OnStake`、`OnUnbond` 等钩子函数，这些可能导致重入
- 检查 `remaining_accounts` 或消息中的 delegator/validator 地址是否可控

**快速定位保护机制技巧（L2-跳读 + L4-跨模块追踪）：**
- **L2** - 检查是否使用互斥锁（`mutex.Lock()`）或原子操作保护 Keeper 方法
- **L2** - 查找重入防护标志：`is_locked`、`processing`、`in_progress` 等名称
- **L2** - 验证是否使用 `defer unlock` 模式进行解锁保护
- **L4** - 跨 Keeper 追踪：检查被调用的其他 Keeper 方法是否可能反向调用当前 Keeper
- **L4** - 跟踪消息路由：查看 MsgServer 中的消息处理顺序，确认不存在循环调用
- **L2** - 识别状态变更顺序是否遵循 **CEI 模式**（Checks-Effects-Interactions）

## Classify

**判定为漏洞：**
- Keeper 方法检查通过后，在调用其他 Keeper 或执行钩子前，状态尚未更新
- 被调用的其他 Keeper 可能直接或间接调用回当前 Keeper 的相同方法
- 回调函数中无互斥保护，允许重复进入同一 Keeper 方法
- `remaining_accounts` 或消息中的地址可被恶意构造，导致同一方法被多次调用

**判定为误报：**
- Keeper 方法已使用互斥锁或其他同步机制保护，防止并发调用
- 被调用的其他 Keeper 为只读操作，无法修改状态或触发反向调用
- 钩子函数已被明确禁止调用同一 Keeper 的状态修改方法
- 所有跨 Keeper 调用都经过白名单检查，确保调用链不存在循环

**判定为代码异味：**
- Keeper 方法内部存在多层 Keeper 调用，未清晰标注依赖关系
- 状态变更与 Keeper 交互逻辑混杂，可读性差
- 缺少文档说明 Keeper 方法的调用安全性和重入风险

## Low risk

**以下场景可评为低风险：**
- Keeper 方法使用了互斥锁或消息队列机制确保原子性
- 钩子函数已被明确限制，仅允许特定的只读操作
- 跨 Keeper 调用链已被完整审计，确认不存在重入路径
- 业务逻辑包含天然的防护机制（如 nonce 递增、账户状态标志等）
- 重入攻击的经济收益远小于 gas 消耗成本（Cosmos 链上交易费用）
- 仅在测试网或开发环境部署，未处理实际资产

## Audit Checklist

- [ ] 检查所有 Keeper 方法的状态变更顺序，确认遵循 **Checks-Effects-Interactions** 模式
- [ ] 识别所有跨 Keeper 调用点，验证是否可能触发回调重入
- [ ] 检查钩子函数注册机制，确认回调中无权限提升操作
- [ ] 验证 Keeper 方法是否使用互斥锁或消息队列机制保护
- [ ] 检查消息验证逻辑，确保地址参数不可被恶意构造
- [ ] 执行单元测试，模拟重入场景验证防护有效性
- [ ] 检查 BeginBlocker 和 EndBlocker 中是否存在状态依赖，可能导致块级重入

## References

- [Cosmos SDK Keeper Pattern](https://docs.cosmos.network/main/building-modules/keeper.html)
- [Cosmos SDK Message Handlers](https://docs.cosmos.network/main/building-modules/msg-server.html)
- [Bank Module Hook Implementation](https://github.com/cosmos/cosmos-sdk/blob/main/x/bank/keeper/send.go)
