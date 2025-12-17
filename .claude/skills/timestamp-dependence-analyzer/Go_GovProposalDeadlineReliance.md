# Go_GovProposalDeadlineReliance

**漏洞描述**  
治理提案截止时间直接依赖 `ctx.BlockTime()`，验证者可通过操纵区块时间戳（BFT 共识允许的时间漂移范围内）影响提案投票截止判断，导致投票窗口被人为延长或缩短。

---

## Details

### 典型代码示例（Cosmos SDK 治理模块）

```go
// 提案截止判断
func (k Keeper) CheckProposalDeadline(ctx sdk.Context, proposalID uint64) error {
    proposal, found := k.GetProposal(ctx, proposalID)
    if !found {
        return ErrProposalNotFound
    }
    
    // 直接使用区块时间判断截止
    if ctx.BlockTime().After(proposal.VotingEndTime) {
        return ErrVotingPeriodEnded
    }
    return nil
}

// 提案创建时设定截止时间
func (k Keeper) SubmitProposal(ctx sdk.Context, content Content, votingPeriod time.Duration) {
    proposal := NewProposal(content)
    proposal.VotingEndTime = ctx.BlockTime().Add(votingPeriod) // 直接依赖区块时间
    k.SetProposal(ctx, proposal)
}
```

### 快速定位核心操作技巧 **（L1-L2）**

- **关键字扫描（L1）**：搜索 `ctx.BlockTime()` + `After/Before/Compare` + 治理相关函数名（`Proposal`, `Vote`, `Deadline`, `EndTime`, `VotingPeriod`）
- **跳读确认（L2）**：检查时间比较语句周围是否存在：
  - `proposal.VotingEndTime` / `proposal.SubmitTime` 等时间字段
  - `DepositPeriod` / `VotingPeriod` 配置参数
  - 状态转换逻辑（`DepositPeriod → VotingPeriod → Passed/Rejected`）

### 快速定位保护机制技巧 **（L2-L3）**

- **跳读验证（L2）**：检查是否存在缓解措施：
  - 时间窗口最小延迟限制（如 `MinVotingPeriod`）
  - 区块高度混合判断（`ctx.BlockHeight()` 配合使用）
  - 外部时间源验证（如 Oracle 时间戳对比）
  
- **逐行审查（L3）**：确认关键路径：
  - `EndBlocker` 中提案状态自动转换逻辑
  - `ActiveProposalQueue` 的时间索引实现
  - 参数变更提案对 `VotingPeriod` 的修改权限

---

## Classify

### 确认为漏洞的条件
1. **时间依赖无保护**：`ctx.BlockTime()` 直接作为唯一判断依据，无区块高度或外部时间源交叉验证
2. **可操纵窗口显著**：BFT 共识允许的时间漂移（通常 ±3-10 秒）足以影响关键决策（如提案即将到期时的临门一脚投票）
3. **存在经济激励**：操纵时间可直接导致提案通过/失败，影响资金分配、参数变更等高价值决策

### 误报情况
1. **混合判断机制**：同时使用区块高度和时间戳，时间仅作辅助参考
2. **Grace Period 设计**：投票期远大于可操纵时间窗口（如 7 天投票期 vs 10 秒漂移）
3. **离线签名场景**：时间戳仅用于记录而非执行判断

### 代码异味（需标注但非必然漏洞）
- 时间比较与状态转换逻辑分离在不同模块
- `VotingPeriod` 参数可通过治理提案动态修改（存在博弈空间）
- 未记录 `ctx.BlockTime()` 与实际 UTC 时间的偏差历史

---

## Low risk

以下情况可降级为低风险：

1. **时间窗口显著富余**：投票期为 14 天及以上，验证者操纵 ±10 秒对结果影响可忽略
2. **紧急停止机制存在**：链上存在 `EmergencyPause` 或多签可中止异常提案
3. **后续人工审查流程**：提案执行前需链下治理论坛公示期（如 Snapshot 投票确认）
4. **低价值提案范围**：仅影响文本提案、参数微调等无直接经济价值决策
5. **验证者集合高度去中心化**：共谋成本极高（需 >1/3 验证者配合操纵时间）

**审计建议**：即使评为低风险，仍应在报告中标注该时间依赖模式，建议添加区块高度作为二级判断条件。
