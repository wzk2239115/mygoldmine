# Go_HeavyBeginBlocker - 重 BeginBlocker DoS

## Details

**典型代码模式：**
```go
func (k Keeper) BeginBlocker(ctx sdk.Context) {
    // 危险：无分页的全量状态迭代
    k.IterateAllProposals(ctx, func(proposal types.Proposal) bool {
        k.ProcessProposal(ctx, proposal)  // 复杂计算
        return false
    })
    
    // 危险：无上限的批量操作
    for _, validator := range k.GetAllValidators(ctx) {
        k.CalculateRewards(ctx, validator)  // Gas 密集
    }
}
```

**快速定位核心操作 (L2-L3)：**
- 搜索 `BeginBlocker` / `EndBlocker` 函数定义
- 关注迭代器使用：`IterateAll*` / `GetAll*` / `store.Iterator()`
- 检查循环内是否存在：状态写入、复杂计算、跨模块调用
- 重点审查：无 `break` 条件的迭代、嵌套循环、递归调用
- Gas 消耗估算：计算复杂度是否与链上状态数量线性/指数相关

**快速定位保护机制 (L2-L3)：**
- 检查分页参数：`limit` / `MaxIterations` / `PageRequest`
- 查找早期退出：`if count > MaxItems { break }`
- Gas 限制检查：`ctx.GasMeter().GasConsumed()` 对比 `BlockGasLimit`
- 时间限制：`ctx.BlockTime()` 比较或超时设置
- 延迟执行机制：任务队列、批处理分散到多个区块

## Classify

**确认为漏洞：**
- BeginBlocker 中存在无界迭代，且迭代次数随链上状态增长（如用户数、提案数）
- 单次迭代内存在 O(n) 以上复杂度操作，可导致区块生成超时
- 无任何 Gas 或数量限制，攻击者可通过低成本操作触发（如创建大量小额提案）

**判定为误报：**
- 迭代有明确上限且上限受共识参数硬性约束（如 `MaxValidators=100` 且不可治理修改）
- 迭代对象数量极小且不可人为增加（如系统内置的少数固定账户）
- 已存在 Gas 计量且确认会触发 `OutOfGas` 而非卡死节点

**归类为代码异味：**
- 存在理论风险但当前链上数据量距离阈值很远（需评估增长速度）
- 有分页但分页大小设置不合理（如默认 1000，建议调整为 100）
- 复杂度可优化但不会导致实际 DoS（如 O(n log n) 可优化为 O(n)）

## Low risk

**以下情况评为低风险：**
- 迭代对象受严格数量限制（< 100）且通过经济机制约束（如创建成本 > 1000 USD）
- 复杂操作已缓存或预计算，BeginBlocker 仅读取缓存结果
- 存在治理可调节的紧急熔断开关（如 `DisableFeature` 参数）
- 历史数据证明极端情况下仍在安全范围（如测试网压力测试）
- 影响范围局限于单一非关键模块（如统计模块），不影响共识或转账
- 需要攻击者持有大量代币或满足苛刻前置条件（成本 > 收益）

## 审计专业技巧与真实案例

### 1. 真实漏洞的明确特征

**特征一：无界迭代 + 人为可控的增长因子**
```go
// 真实漏洞案例：Cosmos Hub 提案模块早期版本
func (k Keeper) BeginBlocker(ctx sdk.Context) {
    // 任何人都可以创建提案（创建成本极低）
    proposals := k.GetAllProposals(ctx)  // 无上限
    for _, proposal := range proposals {
        k.TallyVotes(ctx, proposal)  // O(n) 操作，n=投票数
    }
}
```
审计要点：
- 追溯 `GetAllProposals()` 的数据来源：是否由用户输入直接驱动
- 检查创建提案的成本：如果 `1 提案 < 0.001 USD`，则可无成本膨胀
- 实际测试：本地启动测试网，创建 1000 个提案，测量区块生成时间增长曲线

**特征二：嵌套迭代导致的指数复杂度**
```go
// 真实漏洞：staking 模块
for _, validator := range k.GetAllValidators(ctx) {  // O(n)
    for _, delegation := range k.GetValidatorDelegations(ctx, validator.Address) {  // O(m)
        k.UpdateDelegationRewards(ctx, delegation)  // O(1) but called n*m times
    }
}
// 总复杂度 O(n*m)，当 n=500 validators, m=1000 delegations 时 = 500k 次操作
```

### 2. 误报的常见陷阱

**陷阱一：混淆"理论上限"和"实际达成"**
```go
// 常被误报为漏洞
MaxValidators := 300  // 参数看似很大
for i := 0; i < MaxValidators; i++ {
    k.ProcessValidator(ctx, i)
}
```
区分技巧：
- 查询链上现状：`cosmos query staking validators` 看实际验证人数
- Cosmos Hub 实际运行中通常只有 180-200 个验证人，远低于 300
- **误报判定**：如果历史 6 个月内最高值 < 250，即使代码允许 300 也是低风险
- **真实漏洞**：如果有治理提案可将 300 改为 10000，则风险真实存在

**陷阱二：遗漏缓存或批处理机制**
```go
// 审计员可能认为是漏洞
func (k Keeper) BeginBlocker(ctx sdk.Context) {
    for _, token := range k.GetAllTokens(ctx) {
        price := k.FetchPriceFromOracle(ctx, token)  // 看似是网络调用？
        k.UpdatePrice(ctx, token, price)
    }
}

// 但实际上在 app.go 中已缓存
func NewKeeper(...) {
    keeper.priceCache = NewLRUCache(10000)  // 已缓存
    keeper.lastUpdate = time.Now()
}
```
审计要点：
- 不仅查看 BeginBlocker，必须检查 NewKeeper 的初始化逻辑
- 搜索 `cache`, `precompute`, `memoize` 关键词
- 追溯函数调用栈：看价格是否从缓存读取还是重新计算

**陷阱三：误判动态参数为固定值**
```go
// 误报常见错误
MaxBatchSize := 100  // 审计员认为"最多 100 个，安全"

// 但实际上这是可治理的
var MaxBatchSize int64 = 100
func init() {
    // 在 genesis 中可配置，未来可通过治理改为 10000
}
```
正确审计步骤：
- 检查参数是否来自 `paramtypes.Subspace`（可治理）
- 搜索 `params.SetParamSet()`、`proposal type` 关键词
- 如果发现是可治理参数，需评估：当前值是否合理 + 社区治理历史

### 3. 深度审计检查清单

**步骤一：确定数据源的可控性（最关键）**
| 数据来源 | 风险等级 | 审计方法 |
|---------|--------|--------|
| 用户创建的对象（提案、委托）| 🔴 高 | 追溯创建成本；搜索 `create` 权限 |
| 固定系统账户（验证人初始集合）| 🟡 中 | 检查是否可动态新增；查历史数据 |
| 治理参数 | 🟡 中 | 评估社区治理制约；检查 vote weight |
| 外部预言机数据 | 🔴 高 | 检查是否有故障降级；看超时处理 |

**步骤二：Gas 消耗估算与实测**
```bash
# 实测 Gas 消耗的科学方法
# 1. 启动测试网（--verbose 打印 Gas 日志）
simd start --log_level debug

# 2. 创建测试数据
# 创建 N=100 个提案，观测：
# - BeginBlocker Gas 消耗的增长率
# - 区块生成时间是否线性增长

# 3. 关键指标
# 当 N=100 时，BeginBlocker Gas > BlockGasLimit * 50% 即为高风险
```

**步骤三：对比历史版本和竞品代码**
- 查 Cosmos SDK changelog：该模块在历史上是否被修复过相同问题
- 对标 Osmosis、Evmos 等成熟链：它们的 BeginBlocker 如何处理
- 这样能识别出"业界公知的陷阱"

### 4. 实战：区分真实漏洞 vs 误报的决策树

```
发现疑似漏洞 (BeginBlocker 中有迭代)
    │
    ├─ 迭代对象数量是否 > 1000?
    │  ├─ 否 → [检查 B]
    │  └─ 是 → 是否由用户可控操作生成?
    │     ├─ 是 → 🔴 真实漏洞，建议修复
    │     └─ 否 → [检查 B]
    │
    ├─ [检查 B] 每次迭代的操作复杂度
    │  ├─ O(1) 或 O(log n) → 风险大幅降低
    │  ├─ O(n) 或 O(n log n) → [检查 C]
    │  └─ O(n²) 或更高 → 即使小数据也有风险
    │
    └─ [检查 C] 是否存在分页或数量限制
       ├─ 有硬性代码限制 (< 100) → 🟡 低风险
       ├─ 有参数限制但可治理 → 检查社区治理历史和参数值趋势
       ├─ 有 Gas 计量且会触发 OOG → 🟡 低风险（会报错而非卡死）
       └─ 无任何限制 → 🔴 真实漏洞
```

### 5. 常见的真误报案例总结

| 案例 | 初步判定 | 最终判定 | 关键发现 |
|------|--------|--------|---------|
| Evmos staking BeginBlocker 循环所有验证人 | 🔴 高 | 🟡 低 | 验证人数 < 100，硬限制；历史 1 年无变化 |
| Cosmos authz 模块批量授权 | 🔴 高 | 🔴 真漏洞 | 创建成本 0，可创建百万级授权；已在 v0.46 修复 |
| Osmosis 周期性激励发放 | 🟡 中 | 🟢 安全 | 虽然迭代所有池子，但池子总数 < 5000 且增速可控；预计算缓存 |
| 某 testnet 提案清理逻辑 | 🔴 高 | 🟡 低 | 历史提案自动清理，非人为增长；清理成本已参数化 |

### 6. 审计报告模板

建议漏洞报告中包含以下信息以避免误报纠纷：
```
[链接到代码] Line XXX
当前行为: BeginBlocker 中无界迭代 GetAllXXX
数据来源: 由调用 CreateXXX() 生成，任何地址可调用
创建成本: 0 - N token （成本分析）
扩展潜力: 无硬限制，可线性膨胀至 N = 10^6
Gas 估算: 单次迭代 ~XXX gas，总计 10^6 * XXX = 超过 BlockGasLimit
实测结果: 创建 1000 个 XXX 后区块生成时间延长 3 倍
建议修复: 添加分页（limit=100）/ 添加早期退出条件
```
