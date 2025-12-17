# Cosmos 交易 MEV 漏洞审计

## Details

**代码示例场景：**
验证者在 `CheckTx`/`DeliverTx`/`AnteHandler` 阶段可观察并重排 mempool 交易，典型出现在 DEX swap、跨链桥消息处理、链上拍卖、清算触发等场景。

```go
// 典型漏洞代码模式
func (k Keeper) Swap(ctx sdk.Context, msg *MsgSwap) error {
    // 直接使用链上价格执行交易，无滑点保护
    price := k.GetCurrentPrice(ctx, msg.TokenIn, msg.TokenOut)
    amountOut := msg.AmountIn.Mul(price)
    
    // 验证者可在此交易前插入自己的交易
    k.Transfer(ctx, msg.Sender, msg.Receiver, amountOut)
    return nil
}
```

**快速定位核心操作技巧（L3-L4 审计等级）：**
- 关注 `AnteHandler`、`CheckTx`、`DeliverTx` 中的状态读取与修改顺序
- 搜索涉及价格敏感操作：`GetPrice`、`Swap`、`ExecuteTrade`、`Liquidate`、`Auction`
- 检查交易执行前的状态依赖：池子余额、Oracle 价格、待执行订单队列
- 追踪 mempool 策略配置：`PrepareProposal`、`ProcessProposal` 的自定义逻辑
- 跨模块追踪：`BeginBlock`/`EndBlock` 中批量处理逻辑是否可被单笔交易利用

**快速定位保护机制技巧（L2-L3 审计等级）：**
- 检查是否存在 `MinAmountOut`、`MaxSlippage`、`Deadline` 参数约束
- 验证是否使用 TWAP、延迟 Oracle、commit-reveal 模式
- 查找交易加密/混淆机制：`threshold encryption`、`tx privacy` 相关模块
- 检查 MEV 拍卖/分配机制：`x/builder`、`x/pob` (Skip Protocol) 等模块集成
- 验证交易排序是否完全由共识层控制（非应用层可干预）

## Classify

**归类为漏洞：**
- 验证者可通过重排交易直接获利，且用户交易会因此遭受可量化损失（如三明治攻击）
- 应用层逻辑主动暴露交易内容且无保护措施（如明文广播高价值操作意图）
- 自定义 `PrepareProposal` 允许验证者插入特权交易而无需参与 mempool 竞价

**归类为误报：**
- 已实现有效的滑点保护，用户可接受的 MEV 范围内
- 使用加密 mempool 或公平排序协议（如 Threshold Encryption、Fairblock）
- MEV 收益已通过机制设计回馈给用户或质押者（如 MEV-Boost 类方案）

**归类为代码异味：**
- 存在理论 MEV 可能但实际利用成本高于收益（如低流动性市场）
- 缺少保护机制但依赖外部约束（如链下协调、声誉系统）
- 时序依赖但无明确利益冲突（如治理投票排序）

## Low risk

**以下情况评为低风险：**
- MEV 金额小于单笔交易 gas 成本的 10 倍
- 操作涉及长时间锁定期或高额保证金，验证者作恶成本显著高于收益
- 存在后置惩罚机制（如 slashing）且检测概率高
- 受影响交易频率极低（如罕见的链上治理紧急提案）
- 用户已通过 UI 层充分告知风险并主动设置严格滑点保护

## 审计专业技巧

### 动态追踪与模拟执行技巧

**技巧1：状态快照对比法**
- 在 `BeginBlock` 处设置基准状态快照（包括账户余额、池子储备、Oracle 价格）
- 逐个 mempool 交易进行模拟执行，记录每步的状态变化
- 对比不同交易顺序下的最终状态差异，识别顺序依赖性
- 实际案例：Osmosis DEX 的流动性池滑点计算，验证者可通过抢跑 DEX 交易池化前的价格变动

**技巧2：价格偏离度量化分析**
- 建立参考价格基线（TWAP、Pyth Oracle、Chainlink）与链上执行价格的偏离度
- 计算单笔交易造成的滑点百分比，若滑点 >5% 需深入审查流动性池设计
- 实际案例：Anchor Protocol 清算时未设 `MaxSlippage`，导致验证者抢跑清算交易获利 2-3%

**技巧3：内存池持久化审查**
- 检查节点是否配置了内存池 `max_txs`、`max_txs_bytes` 参数
- 分析 `CheckTx` 中是否存在成本函数（gas 费用、优先级竞价）
- 跟踪自定义 `PrepareProposal` 中的交易排序逻辑：是否存在"保留位置"给验证者自己的交易

### 误报与真漏洞的区分标准

**常见误报场景及判断依据**

| 场景 | 误报信号 | 确认真漏洞的信号 |
|------|---------|-----------------|
| DEX Swap 的价格依赖 | 已设 `MinAmountOut >= 95% * expected_price` | `MinAmountOut` 为 0 或仅在链上查询价格无参考值 |
| Oracle 价格更新延迟 | 使用 TWAP（如 Uniswap v3 TWAP） | 直接使用 `block.timestamp` 的即时价格无任何历史参考 |
| 清算机制的激励 | 清算奖励固定比例 ≤ 5%，受保险基金覆盖 | 清算奖励 > 20%，或可通过 flash loan 无成本触发清算 |
| 跨链消息排序 | 使用 IBC 标准的 FIFO 或共识排序 | 自定义 `ProcessProposal` 允许重排跨链消息 |

**真实漏洞识别的三层递进法**

1. **第一层：交易执行路径分析**
   - 追踪用户交易从 `CheckTx` → `AnteHandler` → `DeliverTx` 的完整路径
   - 标记所有的状态读取操作（`Get*`）及其时序点
   - 识别"先读后写"的原子性缺陷，验证是否需要互斥保护

2. **第二层：验证者权限边界检查**
   - 确认 `PrepareProposal` 与 `ProcessProposal` 的输入验证是否严格
   - 检查验证者是否可通过 `FinalizeBlock` 执行特权操作
   - 验证交易签名是否完整保护了交易体，包括 `TimeoutHeight` 等参数

3. **第三层：经济模型与激励分析**
   - 计算单次 MEV 提取的预期收益（基于最近 100 个区块统计）
   - 对比验证者的惩罚成本（slashing fraction）与收益的比率
   - 若 `利益 / 惩罚成本 > 10`，则存在有吸引力的攻击激励

### 常见审计陷阱与规避方法

**陷阱1：忽视 `AnteHandler` 中的状态修改**
- 许多 MEV 漏洞隐藏在 Gas 消耗计算或 nonce 验证中
- 规避方法：为每个 `AnteDecorator` 生成执行跟踪，检查是否存在"提前消费"或"重放"风险

**陷阱2：低估自定义 mempool 策略的影响**
- Skip Protocol 等 MEV 交易包协议可能绕过标准的 mempool 排序
- 规避方法：检查链上是否集成了 `x/builder`、`x/mev`、`x/feemarket` 等模块的自定义逻辑

**陷阋3：误将链下协调视为完整防护**
- "我们通过声誉系统防止验证者作恶"通常不足以作为安全依赖
- 规避方法：要求链上强制执行（如加密 mempool、隐私交易池）或明确风险告知

### 审计报告的表述建议

**充分性证明的四要素模板**
```
1. 漏洞存在的必要条件（如"验证者观察到高价值交易"）
2. 验证者可执行的具体操作（如"通过 PrepareProposal 重排交易"）
3. 用户遭受的可量化损失（如"滑点损失 200 USDC"）
4. 防护措施的缺失（如"无 MaxSlippage 参数、无加密"）
```

实际案例：Cosmos DEX 的漏洞描述应从"存在价格依赖"升级为"验证者可在 1 秒内通过前置交易抬高价格 8%，导致用户滑点损失最高 10,000 USDC，目前仅依赖前端 UI 告知，链上无强制保护"
