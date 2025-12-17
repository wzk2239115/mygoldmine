# IBC 抢跑漏洞 (IBC Front-Running)

**Go (Cosmos SDK 生态)**

跨链消息传递过程中，交易意图在中继阶段暴露，使验证者、中继者或其他观察者能够提前获知即将发生的跨链操作，从而抢先执行相关交易获取套利机会。

## Details

**代码示例场景：**

```go
// IBC RelayPacket 处理流程
func (k Keeper) OnRecvPacket(ctx sdk.Context, packet channeltypes.Packet, relayer sdk.AccAddress) {
    var data types.FungibleTokenPacketData
    types.ModuleCdc.MustUnmarshalJSON(packet.GetData(), &data)
    
    // 跨链转账金额和接收者在此时可见
    amount := data.Amount  // 可被中继者观察
    receiver := data.Receiver  // 目标地址暴露
    
    // 执行实际转账前存在时间窗口
    k.bankKeeper.MintCoins(ctx, types.ModuleName, sdk.NewCoins(amount))
    k.bankKeeper.SendCoinsFromModuleToAccount(ctx, types.ModuleName, receiver, sdk.NewCoins(amount))
}
```

**快速定位核心操作技巧 (L3: 逐行读)：**
- 查找 `OnRecvPacket`、`OnAcknowledgementPacket`、`OnTimeoutPacket` 回调函数
- 定位 Packet 数据解析后到状态变更前的处理逻辑
- 检查 `BeginBlocker`/`EndBlocker` 中批量处理 IBC 消息的顺序
- 关注 `AnteHandler` 中对 IBC 交易的特殊处理路径
- 搜索 `RelayPacket`、`UpdateClient` 等中继操作的时序依赖

**快速定位保护机制技巧 (L2: 跳读)：**
- 检查是否存在 commit-reveal 模式（`keccak256(secret)` 提交后再揭示）
- 查找交易批处理或排序随机化机制（`shuffle`、`random`）
- 确认是否有时间锁或延迟执行逻辑（`timelock`、`delay`）
- 验证中继者权限控制（`authorized relayer list`）
- 检查滑点保护或价格预言机校验（`minAmountOut`、`oraclePrice`）

## Classify

**判定为漏洞的情形：**
- IBC 数据包在中继阶段暴露高价值操作意图（如大额跨链套利、DEX 交易参数）
- 验证者或中继者能在 `OnRecvPacket` 前插入自有交易改变链上状态
- 跨链消息顺序可被中继者操纵，且影响经济结果
- 缺少交易隐私保护，目标链 mempool 可见待处理的 IBC 数据包

**判定为误报的情形：**
- IBC 消息本身不涉及价格敏感操作（如简单跨链转账固定金额代币）
- 已实施批量原子执行，外部无法插入交易干扰
- 存在滑点保护或预言机校验，抢跑无利可图
- 链采用私有 mempool 或加密交易方案

**代码异味（需进一步验证）：**
- IBC 回调函数逻辑复杂但无明确的执行顺序保障
- 依赖外部价格源但未锁定查询时刻
- 中继者激励设计可能导致选择性中继或延迟攻击

## Low risk

**以下情况可评为低风险：**
- 跨链操作金额受严格上限限制（如单笔 < $1000）
- IBC 消息仅用于非金融场景（如跨链身份验证、治理投票通知）
- 目标链交易吞吐量极低，抢跑成本高于收益
- 已部署 MEV 拍卖机制（如 Skip Protocol），利润回流用户
- 存在多签或 DAO 延迟执行，抢跑者无法即时获利
- 采用阈值加密或时间锁加密（Timelock Encryption）保护交易内容

## 审计专业技巧

### 真实漏洞与误报的区分经验

**关键区分指标 1: 经济激励分析**

真实漏洞特征：
- 攻击者收益 >> 攻击成本（Gas费、交易费、中继费等）
- 存在明确的套利机制：例如在 `OnRecvPacket` 中解析出的汇率参数允许在目标链先行操纵价格，随后执行跨链转账
- 可重复性强：同一类型的 IBC 消息存在系统性的可利用性
- 验证者参与度高：通过 Proposer-Builder Separation（PBS）或直接验证者行为可持续获利

常见误报：
- 单次套利空间 < 中继成本 0.5% 以上被筛除
- 攻击需要控制多个链的验证者或中继者，成本过高
- IBC 消息虽然可见，但目标链已有充分流动性平衡，难以形成显著价格差异

**关键区分指标 2: 消息依赖链分析**

真实漏洞特征：
```go
// 易受攻击模式：外部价格影响状态转换
func (k Keeper) OnRecvPacket(ctx sdk.Context, packet channeltypes.Packet, relayer sdk.AccAddress) {
    var data types.SwapPacketData
    types.ModuleCdc.MustUnmarshalJSON(packet.GetData(), &data)

    // 在接收确认前查询链上价格 - 可被抢跑
    poolPrice := k.dexKeeper.GetPoolPrice(ctx, data.TokenIn, data.TokenOut)

    // 按当前价格执行，但中继者已知这个价格会变化
    if data.MinAmountOut > poolPrice.MulInt(data.AmountIn) {
        // 执行交换 - 中继者可在此前抢跑改变 poolPrice
        k.ExecuteSwap(ctx, data)
    }
}
```

此处的误报情形：
- 如果 `MinAmountOut` 是由源链预言机给出的固定值，且已包含滑点保护（如 3% 以上），不构成实际风险

真实漏洞情形：
- `MinAmountOut` 是根据消息接收时的 DEX 价格动态计算的，或未实施滑点保护

**关键区分指标 3: 中继者权限模型**

审计核心问题：谁可以成为中继者？

真实漏洞场景：
- 任何人都可调用 `RelayPacket` 提交跨链消息
- 中继者激励机制（如交易费回扣）明确且不受限制
- 验证者可在区块提议权内自由排序 IBC 消息

误报场景：
- 中继者白名单制度（`authorized_relayer` 配置）且维护受限
- IBC 消息由特定的官方桥接服务独家中继，竞争受限
- 消息执行在专门的隔离交易（Bundle）中，外部无法插入

**关键区分指标 4: 状态快照与重入性**

```go
// 易受攻击的重入模式
func (k Keeper) OnRecvPacket(ctx sdk.Context, packet channeltypes.Packet) {
    var data types.PacketData
    types.ModuleCdc.MustUnmarshalJSON(packet.GetData(), &data)

    // 第一步：读取当前状态
    balance := k.GetBalance(ctx, data.Account)

    // ⚠️ 中间逻辑可能触发回调，改变上下文
    k.ProcessCallback(ctx, data.Callback)  // 可能嵌套调用 OnRecvPacket

    // 第二步：基于旧的状态快照执行
    k.UpdateBalance(ctx, data.Account, balance.Add(data.Amount))
}
```

真实风险：
- 在第一步和第二步间存在异步调用或跨块确认，使 `balance` 过期
- 接收链有多个 IBC 端口，回调可能在其他端口上重新进入本逻辑

误报风险：
- 现代 Cosmos SDK 的 `OnRecvPacket` 在原子交易上下文中执行，单块内无重入风险
- IBC 1.0+ 规范要求的 ack 机制确保顺序性

**关键区分指标 5: 时间戳与延迟利用**

```go
// 检查 IBC 超时参数
func (k Keeper) ValidatePacket(ctx sdk.Context, packet channeltypes.Packet) error {
    blockTime := ctx.BlockTime()
    timeout := packet.GetTimeoutTimestamp()

    // 如果超时时间过大，中继者可选择延迟执行
    if timeout.Sub(blockTime) > 1*time.Hour {
        // ⚠️ 审计点：一小时内，中继者掌握中继的时序选择权
        return nil
    }
    return ErrTimeoutTooLarge
}
```

真实漏洞：
- 超时窗口 > 10 分钟，中继者可等待链上状态变化后再中继，获取 MEV
- 无最小超时限制，恶意用户可设置极大超时值阻塞中继

误报漏洞：
- 业务逻辑本身要求大超时窗口（如跨多条链的异步合约调用），不能作为漏洞判定

### 审计步骤清单

1. **功能映射阶段**
   - 列举所有 IBC 回调函数及其触发的业务逻辑
   - 标注出涉及价格、金额、权限变化的操作
   - 跟踪状态变化前的外部数据依赖

2. **敏感数据曝光分析**
   - 检查 Packet 数据是否包含：金额、价格、账户、密钥相关信息
   - 跟踪数据从中继阶段到执行的流转路径
   - 验证是否存在加密或隐私保护措施

3. **经济价值计算**
   - 评估单次抢跑收益：`(操纵后价格 - 原价格) * 交易量`
   - 关联中继成本：`gas费 + IBC手续费 + 滑点损失`
   - 判定可重复性：同类型 IBC 消息出现频率

4. **防御机制完整性检查**
   - 逐行审读所有保护逻辑（滑点、预言机、权限检查）
   - 尝试逻辑绕过：能否改变参数使防御失效
   - 时序分析：防御与攻击的执行顺序能否被颠覆

5. **实际链上数据验证**
   - 查询历史 IBC 消息，统计相邻消息间的价格波动
   - 分析中继者行为模式（是否存在特定延迟模式）
   - 检查验证者提议的区块中 IBC 消息排序的规律性
