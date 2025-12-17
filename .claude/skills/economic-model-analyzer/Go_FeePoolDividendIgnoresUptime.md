# 费用池分红忽略在线率 (Go_FeePoolDividendIgnoresUptime)

**适用链：** Cosmos SDK-based chains  
**漏洞类型：** 经济模型缺陷

## Details

### 代码示例特征
典型出现在 `x/distribution` 模块的费用分配逻辑中，关键代码模式：

```go
// 问题代码：按质押权重直接分配，未考虑在线率
func (k Keeper) AllocateFees(ctx sdk.Context, feePool sdk.Coins) {
    validators := k.stakingKeeper.GetAllValidators(ctx)
    for _, val := range validators {
        power := val.GetBondedTokens()  // 仅基于质押量
        share := feePool.MulInt(power).QuoInt(totalPower)
        k.AllocateTokensToValidator(ctx, val, share)  // 直接分配
    }
}
```

关注 `AllocateTokens`、`DistributeFees`、`WithdrawDelegationRewards` 等方法。

### 快速定位核心操作 **(L3: 逐行读)**
**审计路径：**
1. **模块入口** - 搜索 `x/distribution/keeper` 或 `EndBlocker` 中的费用分配调用
2. **分配逻辑** - 定位 `AllocateFees`/`AllocateTokens` 函数体
3. **权重计算** - 检查分配公式是否仅依赖 `BondedTokens`/`VotingPower`
4. **关键缺陷** - 验证是否缺少 `SignedBlocksWindow`、`MissedBlocksCounter`、`Uptime` 等在线率指标

**快速判断：** 若分配公式中无 `MissedBlocks`、`SigningInfo`、`UptimeRatio` 相关调用，即存在风险。

### 快速定位保护机制 **(L4: 跨模块追踪)**
**防御检查项：**
1. **Slashing 集成** - 追踪是否调用 `x/slashing` 模块的 `GetValidatorSigningInfo`
   ```go
   // 正确实现应包含
   signingInfo := k.slashingKeeper.GetValidatorSigningInfo(ctx, valAddr)
   uptimeRatio := CalculateUptime(signingInfo.MissedBlocksCounter)
   ```
2. **权重调整** - 检查 `power` 或 `share` 是否乘以在线时间系数
3. **条件过滤** - 验证是否排除已被 Jailed 或长期离线的验证者：
   ```go
   if val.IsJailed() || signingInfo.JailedUntil.After(ctx.BlockTime()) {
       continue  // 应跳过
   }
   ```
4. **跨模块依赖** - 确认 `stakingKeeper` 和 `slashingKeeper` 的数据同步性

**缺失判定：** 若分配逻辑未调用 `slashing` 模块接口，或仅在 Slash 时惩罚但分红时不考虑历史表现，即为缺陷。

## Classify

### 漏洞
- 分配完全忽略在线率，离线验证者仍获得完整分红
- 仅在极端情况（如被 Slash）才扣除，但日常分红未按实际贡献分配
- 链上存在费用池且未实施任何在线时间权重调整

### 误报
- 链已通过其他机制实现惩罚（如强制 Unbond 离线验证者）
- 测试网或实验性链，尚未启用经济激励
- 业务设计明确要求平均分配（需配合白皮书验证）

### 代码异味
- 在线率数据已记录但未应用到分配公式
- 存在 `UptimeWeight` 配置项但硬编码为 1.0
- 注释中提及"TODO: 考虑在线率"但未实现

## Low Risk

以下场景可降为低风险：

1. **次要费用池** - 仅影响小额交易手续费分配，主要奖励来自区块通胀且已考虑在线率
2. **短期偏差** - 在线率统计存在滞后（如按 Epoch 更新），但偏差窗口 < 100 区块
3. **冗余惩罚** - Slashing 模块已实施严格的离线惩罚（如 5% 质押削减），经济损失远超分红差额
4. **委托人保护** - 分红分配至委托人时按委托时长加权，间接弱化验证者在线率影响
5. **临时状态** - 代码处于迁移期，计划在下一版本引入 `SigningInfo` 集成
6. **治理豁免** - 通过链上治理投票明确允许该设计，作为特殊激励策略

**评估原则：** 若离线验证者获利空间 < 2% 年化收益差异，且存在其他制衡机制，可视为低风险。
