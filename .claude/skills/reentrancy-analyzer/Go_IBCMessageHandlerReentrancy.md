# Go IBC Message Handler Reentrancy（IBC 消息处理重入）

## Details

**典型代码模式（Cosmos IBC）：**

```go
// 易受攻击的代码模式：IBC 回调中状态未锁定
func (k Keeper) OnRecvPacket(ctx sdk.Context, packet channeltypes.Packet, relayer sdk.AccAddress) ibcexported.Acknowledgement {
    // 1. 解析 IBC 包数据
    var data types.TransferPacketData
    if err := types.ModuleCdc.UnmarshalJSON(packet.GetData(), &data); err != nil {
        return channeltypes.NewErrorAcknowledgement(err)
    }

    // 2. 执行业务逻辑（危险点：状态还未更新）
    receiver, err := sdk.AccAddressFromBech32(data.Receiver)
    if err != nil {
        return channeltypes.NewErrorAcknowledgement(err)
    }

    // 3. 造币新资产到接收端（此时跨链转账状态未在本地记录）
    amount, ok := sdk.NewIntFromString(data.Amount)
    if !ok {
        return channeltypes.NewErrorAcknowledgement(sdkerrors.Wrap(sdktypes.ErrInvalidCoins, "amount is not a valid uint"))
    }

    // 4. 触发钩子（危险点：在状态未确认的情况下回调）
    if err := k.OnIBCTransfer(ctx, data); err != nil {
        // 注意：如果回调失败，但硬币已经被造出来了！
        return channeltypes.NewErrorAcknowledgement(err)
    }

    // 5. 才真正更新本地状态
    k.RecordIBCTransfer(ctx, data)

    return channeltypes.NewResultAcknowledgement(data)
}

// 风险的 IBC 回调
func (k Keeper) OnIBCTransfer(ctx sdk.Context, data types.TransferPacketData) error {
    // 在此回调中，接收端合约可能发起新的跨链转账，导致嵌套 IBC 调用
    return k.externalKeeper.ProcessIBCCallback(ctx, data)
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索 `OnRecvPacket`, `OnAcknowledgement`, `OnTimeoutPacket` 等 IBC 回调处理函数
- 追踪包数据验证与造币/销毁操作的顺序
- 识别是否存在钩子调用（Hook）或向其他模块转发消息的逻辑
- 检查 IBC 包序列号（sequence）是否被正确验证，防止重放
- 关注跨链消息的原子性：检查是否存在部分执行成功、部分失败的场景

**快速定位保护机制技巧（L2-跳读 + L4-跨模块追踪）：**
- **L2** - 检查 `OnRecvPacket` 前是否锁定相关状态（如转账通道、账户）
- **L2** - 查找状态变更顺序：**验证包合法性 → 更新本地状态 → 造币/销毁 → 回调**
- **L2** - 验证包序列号递增机制是否被正确实现，防止重放
- **L4** - 追踪回调链路：检查钩子函数是否可能发起新的 IBC 包
- **L4** - 跨模块验证：确认 IBC 包处理与其他模块（如 DeFi）的交互不存在循环调用
- **L2** - 检查超时处理：`OnTimeoutPacket` 是否正确回滚状态

## Classify

**判定为漏洞：**
- IBC 包处理时，在回调执行前状态尚未记录（如造币/销毁已完成，但转账记录未保存）
- 回调函数允许发起新的 IBC 消息或跨链操作，导致嵌套调用
- 包序列号验证缺失或不完整，允许重放攻击
- 超时处理与常规处理的状态更新不一致，导致资产重复计数

**判定为误报：**
- IBC 包处理已使用通道级互斥锁保护，防止并发处理同一通道的包
- 回调函数为只读操作，无法修改状态或发起新的 IBC 操作
- 包序列号机制已被正确实现，通道中的每个包都有唯一的序列号
- 超时处理与常规处理的逻辑完全对称，确保状态一致性

**判定为代码异味：**
- IBC 包处理中存在多个回调点，调用链复杂，难以追踪
- 造币与销毁逻辑分散在不同位置，缺少集中的资产管理
- 缺少清晰的文档说明 IBC 消息处理的原子性保证

## Low risk

**以下场景可评为低风险：**
- IBC 包处理使用了通道级锁或消息队列机制，确保原子性
- 回调函数已被明确限制为只读操作，无状态修改权限
- 包序列号机制已被正确实现，并被完整审计
- 跨链消息的发送端已被审计，确认不存在循环调用路径
- 业务逻辑包含天然的防护机制（如时间锁、签名验证等）
- 仅处理测试资产或虚拟资产，未涉及真实价值转移

## Audit Checklist

- [ ] 检查所有 IBC 回调函数（OnRecvPacket, OnAcknowledgement, OnTimeoutPacket）
- [ ] 验证包序列号机制是否正确实现，确保不可重放
- [ ] 确认状态更新顺序遵循 **Verify → Update State → Mint/Burn → Callback** 模式
- [ ] 检查回调函数是否可能发起新的 IBC 操作，追踪调用链
- [ ] 验证超时处理是否与正常处理的状态更新一致
- [ ] 检查通道级别的并发控制机制
- [ ] 执行压力测试，模拟高频 IBC 消息转发场景
- [ ] 审查所有与 IBC 交互的外部模块，确认不存在循环依赖

## References

- [Cosmos IBC Specification](https://github.com/cosmos/ibc)
- [IBC Go Module Implementation](https://github.com/cosmos/ibc-go/tree/main/modules/core)
- [IBC Hooks Middleware](https://github.com/cosmos/ibc-apps/tree/main/middleware/packet-forward-middleware)
