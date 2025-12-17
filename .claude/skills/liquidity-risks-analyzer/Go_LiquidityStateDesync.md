# Go_LiquidityStateDesync - 流动性状态失步

**适用场景**：Cosmos SDK、IBC 中继器、链下流动性服务、跨链流动性协调器、质押衍生品后台服务

**核心风险**：链下服务与链上流动性状态不同步，导致过度承诺流动性、提取失败、资金锁定或流动性池崩溃。

---

## Details

**典型代码模式**：

```go
// 链下流动性管理器缓存链上状态
type LiquidityManager struct {
    cachedBalance map[string]*big.Int  // 缓存的流动性余额
    lastSyncBlock uint64                // 最后同步的区块高度
    mu            sync.RWMutex
}

func (lm *LiquidityManager) GetAvailableLiquidity(token string) *big.Int {
    lm.mu.RLock()
    defer lm.mu.RUnlock()
    return lm.cachedBalance[token]  // ❌ 直接返回缓存值，未验证链上状态
}

func (lm *LiquidityManager) CommitWithdrawal(token string, amount *big.Int) error {
    available := lm.GetAvailableLiquidity(token)
    if amount.Cmp(available) > 0 {
        return errors.New("insufficient liquidity")
    }
    // ❌ 基于过期缓存做决策，链上实际可能已被提取
    return lm.executeWithdrawal(token, amount)
}
```

**快速定位核心操作技巧**（审计等级：**L3 - 逐行读**）：
- 搜索关键词：`cachedBalance`、`lastSync`、`UpdateLiquidity`、`GetBalance`、`AvailableLiquidity`
- 关注流动性查询函数是否直接读缓存而未调用链上查询（`QueryBalance`、`GetPoolReserves`）
- 检查状态更新时间戳/区块高度是否在每次操作前验证：`if time.Since(lastUpdate) > threshold`
- 追踪提取/承诺路径：`Withdraw`、`Commit`、`Reserve` 函数内是否先调用同步方法
- 定位并发场景：多协程同时操作缓存时是否存在 TOCTOU（Time-of-Check-Time-of-Use）窗口

**快速定位保护机制技巧**（审计等级：**L2 - 跳读**）：
- 查找同步机制：`SyncFromChain`、`RefreshState`、`PollChainState` 是否定期调用
- 检查版本控制：`stateVersion`、`nonce`、`blockHeight` 字段是否用于乐观锁
- 验证回退机制：失败时是否调用 `Rollback`、`RevertCache`
- 搜索健康检查：`HealthCheck`、`ValidateState`、`CompareWithChain` 是否在关键路径执行
- 确认过期策略：缓存是否设置 TTL（`expireAt`、`maxAge`），超时是否强制重新同步

---

## Classify

**归类为漏洞的条件**：
1. 缓存流动性状态后，在执行资金操作（提取/转移/承诺）前未重新查询链上状态
2. 缺乏区块高度或时间戳验证，导致跨多个区块的操作基于过期数据
3. 并发场景下无原子性保证，存在 Race Condition 导致重复承诺同一笔流动性
4. IBC 跨链场景中，Packet Timeout 后未回滚本地流动性锁定状态

**归类为误报的条件**：
1. 缓存仅用于只读查询（如仪表盘展示），不影响资金操作决策
2. 已实现乐观锁或 Compare-And-Swap（CAS），链上交易失败时自动重试并刷新状态
3. 操作前已显式调用 `mustSync()` 或 `refreshFromChain()`，且有事务性保证

**归类为代码异味的条件**：
1. 同步频率过低但设置了安全边界（如仅允许操作缓存额度的 80%）
2. 有健康检查但未集成到告警系统，仅记录日志
3. 状态不一致可通过链上交易的 Gas 估算失败自然拦截，但缺乏明确注释说明

---

## Low risk

**以下场景可评为低风险**：

1. **只读场景**：流动性状态仅用于 UI 展示或分析统计，不直接触发链上交易
2. **延迟容忍**：业务允许 1-2 个区块的延迟（如流动性挖矿收益计算），且最终结算以链上为准
3. **安全冗余**：缓存值保守估计（如乘以 0.9 安全系数），即使失步也不会超额承诺
4. **双重验证**：链下决策后，链上合约仍会执行充分性检查（如 `require(balance >= amount)`）
5. **小额测试环境**：仅用于测试网或沙盒环境，资金风险可控
6. **短生命周期**：缓存 TTL < 1 个区块时间，且高频自动刷新
7. **幂等操作**：操作可重复执行且结果一致（如仅查询不修改状态）
