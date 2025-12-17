# Go_CrossChainLiquidityMisquote

**适用范围**：Cosmos SDK、IBC 中继器、链下流动性服务、跨链桥协调器

**核心风险**：跨链流动性桥报价与实际可用流动性不符，导致跨链交易失败、资金卡住或滑点异常

## Details

### 代码示例

```go
// 典型场景：链下服务查询目标链流动性并报价
type LiquidityBridge struct {
    cache map[string]*LiquidityQuote
    mu    sync.RWMutex
}

func (b *LiquidityBridge) GetQuote(destChain string, amount sdk.Coin) (*Quote, error) {
    b.mu.RLock()
    cached := b.cache[destChain]  // 🚨 使用缓存数据报价
    b.mu.RUnlock()
    
    if cached != nil && time.Since(cached.Timestamp) < 5*time.Minute {
        return &Quote{
            Available: cached.Available,  // 🚨 未验证链上实时状态
            Price: cached.Price,
        }, nil
    }
    
    // 🚨 查询时未检查池子健康度、未计算滑点
    balance := b.queryBalance(destChain)
    return &Quote{Available: balance}, nil
}

// IBC 中继场景
func (r *Relayer) EstimateLiquidity(packet ibctypes.Packet) error {
    // 🚨 直接使用本地状态估算，未同步目标链最新状态
    localState := r.stateCache[packet.DestChain]
    if localState.Balance.Amount.GT(packet.Amount) {
        return r.relay(packet)  // 🚨 实际中继时可能失败
    }
    return errors.New("insufficient liquidity")
}
```

### 快速定位核心操作技巧（L3 逐行读）

1. **流动性查询入口**：搜索 `GetQuote`、`EstimateLiquidity`、`CheckAvailability` 函数
2. **缓存使用点**：检查 `cache`、`stateCache`、`sync.RWMutex` 使用处，确认数据新鲜度
3. **跨链状态同步**：追踪 `query`、`Sync`、`Update` 调用，验证是否实时获取目标链状态
4. **余额计算逻辑**：逐行审查 `balance`、`available`、`reserves` 计算是否包含：
   - 锁定中的流动性扣除
   - 待处理交易的预留
   - 池子深度与滑点估算
5. **关键失败路径**：在 IBC 回调 `OnRecvPacket`、`OnAcknowledgement` 中验证实际流动性不足时的降级处理

### 快速定位保护机制技巧（L2 跳读 + L4 跨模块追踪）

1. **保护机制关键词**（L1）：搜索 `health check`、`staleness`、`max age`、`verify`、`sync interval`
2. **跳读验证点**（L2）：
   - 报价函数开头是否有 `if time.Since() > threshold` 强制刷新逻辑
   - 是否存在 `ctx.WithTimeout()` 限制跨链查询时间
   - 返回前是否调用 `Validate()` 或 `Sanitize()`
3. **跨模块追踪**（L4）：
   - 追踪 `LiquidityProvider` 接口实现，检查是否在 keeper 层二次验证
   - 检查 IBC module 的 `OnChanOpenTry` 是否设置流动性阈值
   - 追踪 Cosmos SDK 的 `EndBlocker` 是否定期同步状态
4. **缺失判定**：若上述机制缺失，且报价直接用于资金转移决策，则为高危

## Classify

**漏洞判定（Critical/High）**：
- 报价数据陈旧（超过 N 个区块未刷新）且直接用于执行跨链转账
- 未扣除锁定流动性，导致报价虚高，实际执行失败概率 >20%
- 多链并发场景下无乐观锁或版本控制，报价竞态导致超额分配

**误报判定**：
- 报价仅用于 UI 显示或预估，非交易执行依据
- 存在完善的链上二次验证机制（如目标链合约在执行前重新检查）
- 报价失败后有自动重试且上限合理（<3 次）

**代码异味（Medium）**：
- 有刷新机制但间隔过长（>30s）
- 使用缓存但缺少监控告警
- 错误处理不当但有降级到保守报价的逻辑

## Low risk

1. **只读场景**：报价仅用于链下数据分析、Dashboard 展示，不触发任何链上操作
2. **完善的补偿机制**：存在链上托管合约在流动性不足时自动退款，且用户资金无损失风险
3. **保守报价策略**：实际可用流动性打 50% 折扣报价，且有历史数据证明未出现失败案例
4. **测试网环境**：仅在测试链运行，主网代码已修复或使用不同实现
5. **小额交易限制**：单笔交易上限远低于池子深度（<5%），且有速率限制（如 10 笔/分钟）
