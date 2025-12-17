# Go_IgnoredIBCResponse - 忽略 IBC 响应检查

**漏洞类型**：未检查调用返回值（Unchecked Calls）  
**适用范围**：Cosmos SDK、IBC 协议、跨链模块  
**风险等级**：High/Critical

## Details

### 代码示例

```go
// 漏洞代码：未检查 IBC 响应状态
func (k Keeper) OnRecvPacket(ctx sdk.Context, packet channeltypes.Packet, ack exported.Acknowledgement) error {
    var data types.IBCTransferData
    types.ModuleCdc.MustUnmarshalJSON(packet.GetData(), &data)
    
    // 危险：直接使用 IBC 数据，未验证响应状态
    k.bankKeeper.MintCoins(ctx, types.ModuleName, sdk.NewCoins(data.Amount))
    k.bankKeeper.SendCoinsFromModuleToAccount(ctx, types.ModuleName, data.Receiver, sdk.NewCoins(data.Amount))
    
    return nil
}

// 漏洞代码：忽略 OnAcknowledgementPacket 错误
func (k Keeper) OnAcknowledgementPacket(ctx sdk.Context, packet channeltypes.Packet, ack channeltypes.Acknowledgement) error {
    var ackResp types.AckResponse
    types.ModuleCdc.MustUnmarshalJSON(ack.GetResult(), &ackResp)
    
    // 危险：未检查 ackResp.Success 状态，直接返回
    // 即使对端失败，也不回滚本地状态
    return nil
}

// 漏洞代码：忽略 TimeoutPacket 处理
func (k Keeper) OnTimeoutPacket(ctx sdk.Context, packet channeltypes.Packet) error {
    // 危险：空实现，超时时未回滚锁定资产
    return nil
}
```

### 快速定位核心操作（审计等级：L3-逐行读）

**关键搜索模式**：
- `OnRecvPacket`、`OnAcknowledgementPacket`、`OnTimeoutPacket` 回调函数
- `channeltypes.Packet`、`exported.Acknowledgement` 参数处理
- `SendPacket`、`WriteAcknowledgement` 调用点
- `MintCoins`、`BurnCoins`、`SendCoins` 在 IBC 回调中的使用
- `ctx.EventManager().EmitEvent` 后的状态变更

**审计检查点**：
1. 检查 `OnAcknowledgementPacket` 是否解析并验证 `ack.Success` 或 `ack.Error`
2. 检查 `OnTimeoutPacket` 是否回滚资产锁定/铸造操作
3. 检查 `OnRecvPacket` 返回的 `Acknowledgement` 是否包含执行结果
4. 检查多步骤操作（如先铸币后转账）的中间状态是否可被中断
5. 跟踪 `escrow` 账户余额变化与 IBC 回调的对应关系

### 快速定位保护机制（审计等级：L2-跳读）

**正向特征（存在保护）**：
- 明确检查 `ack.Success` 或解析自定义 `error` 字段
- `OnTimeoutPacket` 中调用补偿逻辑（如 `RefundTokens`）
- 使用 `Escrow` 模式先锁定资产，仅在确认成功后释放
- 在 `OnRecvPacket` 返回前构造包含执行状态的 `Acknowledgement`
- 使用 `keeper` 方法返回的 `error`，并在 IBC 回调中传播

**反向特征（缺失保护）**：
- `OnAcknowledgementPacket` / `OnTimeoutPacket` 为空实现或仅记录日志
- 直接操作资产而不检查 IBC 协议层状态
- 未区分 `SEND`/`RECV` 链的不同职责（如双向都铸币）
- 将 IBC 回调标记为 `_ = ...` 或注释 `// TODO: handle error`

## Classify

### 漏洞研判标准

**确认为漏洞**：
1. 资产操作可被单方面触发且无法回滚（如仅检查 `OnRecvPacket` 成功就铸币，但忽略对端的 `OnAcknowledgement` 失败）
2. 超时场景下锁定资产未释放，导致永久锁仓
3. 恶意中继器可通过伪造响应状态触发不一致状态（若未使用 IBC 协议保证）
4. 跨链铸币/销毁总量不守恒（发送链未销毁 + 接收链已铸造）

**归类为误报**：
1. 明确文档说明采用"乐观执行"模式，且有链下仲裁机制
2. 仅处理通知类消息（如同步价格预言机），失败不影响核心资产安全
3. IBC 回调中的非关键元数据更新（如更新统计计数器）

**代码异味（需进一步确认）**：
1. 有错误检查但仅记录日志，未阻断后续操作
2. 补偿逻辑存在但与正向操作不对称（如铸币 1000，回滚仅销毁 900）
3. 依赖事件监听而非直接返回值进行状态同步

## Low Risk

### 低风险场景

1. **无资产变更的纯查询操作**  
   如 IBC Query 请求、跨链元数据同步，失败仅影响数据时效性

2. **幂等性操作且有外部兜底**  
   操作可重入且最终由链下定时任务或治理提案修复不一致状态

3. **测试网或已废弃代码路径**  
   标记为 `Deprecated` 的 IBC 端口或仅在测试环境启用的模块

4. **失败概率极低的白名单机制**  
   仅与官方认证的中继器交互，且对端链已通过安全审计

5. **明确的降级策略**  
   失败时自动切换为安全模式（如禁用跨链功能直到人工介入）

**注意**：即使评为低风险，也需在审计报告中标注潜在的业务逻辑风险和建议添加监控告警。
