# Go_StaticInflationNoFeedback - 静态通胀无反馈

**影响范围**: Cosmos SDK-based chains 通胀模块  
**问题核心**: 通胀率固定不变，无法根据网络状态（如质押率、流通量）动态调整，导致经济模型失衡

## Details

**代码示例场景**: 
- `x/mint/keeper/keeper.go` 中 `Minter` 结构直接使用固定 `Inflation` 参数
- `BeginBlocker` 每个区块铸造代币时使用静态 `params.InflationRate`
- 缺失基于 `StakingKeeper.BondedRatio()` 的动态调整逻辑

**快速定位核心操作技巧**（L2: 跳读）:
- 搜索关键函数: `MintCoins()`, `BeginBlocker()`, `NextInflationRate()`, `NextAnnualProvisions()`
- 定位 mint 模块的 `keeper` 包，检查通胀计算函数是否包含参数化输入
- 检查 `Minter` 结构体字段，若 `Inflation` 为常量或仅从 params 静态读取则可疑
- 追踪 `BlockProvision` 计算是否引用 `totalSupply`, `bondedRatio` 等动态变量

**快速定位保护机制技巧**（L3: 逐行读）:
- 查找 `CalculateInflation()` 或类似函数，确认是否有 `if bonded < targetBonded` 分支逻辑
- 检查 params 定义（`x/mint/types/params.go`），是否存在 `InflationRateChange`, `InflationMax/Min` 等弹性参数
- 验证是否调用 `stakingKeeper.TotalBondedTokens()` 获取实时质押状态
- 确认 `Params.Validate()` 中是否限制通胀率范围且允许动态更新机制

## Classify

**漏洞判定**:  
若通胀率硬编码或仅从治理参数单次加载，且无任何基于链上状态（质押率、通胀周期、供应量变化）的动态调整，则为**经济模型缺陷**

**误报场景**:  
- 代码中存在 `GetInflationAdjustment()` 等调整函数，但审计时未完整追踪调用链
- 通过治理提案可实时调整参数，且有自动化脚本监控并触发提案（需确认链外机制是否可靠）
- 设计文档明确说明该链处于测试网或初期阶段，刻意使用固定通胀以简化模型

**代码异味**:  
即使存在动态调整逻辑，但调整粒度过粗（如年度一次）、阈值设置不合理（min=max）、或依赖链外预言机输入但无超时/异常兜底，均属设计不足

## Low risk

**符合以下任一条件可评为低风险**:
1. **透明治理**: 链上治理可快速（<7天）通过提案调整通胀参数，且历史记录显示社区响应积极
2. **影响有限**: 固定通胀率处于合理区间（如 2%-8%），且链供应量已达稳态阶段，短期内静态模型不会导致恶性通胀或通缩
3. **补偿机制**: 虽无动态通胀，但存在其他经济平衡手段（如燃烧机制、弹性质押奖励加成）部分抵消固定通胀的负面影响
4. **已计划修复**: 项目路线图明确下一版本将引入动态通胀（需确认已有 PR 或 ADR 文档），且当前版本仅作过渡使用
5. **小规模测试**: 链尚未主网启动或 TVL < $1M，经济模型缺陷风险敞口小

## 审计专业技巧

### 真实漏洞的特征标记

**漏洞确认清单**（需要全部满足才能定性为真实漏洞）:
1. **不可逆的固定通胀**: 通胀率在代码中硬编码（无法通过治理修改），且无任何中断/暂停机制
   - 真实漏洞: `const FIXED_INFLATION = 0.07`（常量值）
   - 误报: `params.InflationRate` 且 params 可通过 governance 更新
2. **链上环境验证失败**: 在测试网已上线但官方文档未明确说明是否为刻意的简化设计
3. **经济学合理性缺失**: 通胀率固定但没有考虑 network growth、validator 增长、或 capital 的实际需求
   - 示例：固定 5% 通胀，但 bonded ratio 从 30% 下降至 10% 时仍不调整，导致年度新增代币相对质押规模 5x 增长

**误报常见陷阱**:
- 看到 `inflation` 变量名就认为是漏洞，未检查是否可被治理参数覆盖
- 未完整追踪函数链：A 函数调用 B，B 调用了动态逻辑，但审计只读了 A
- 混淆"设计缺陷"与"紧急风险"：固定通胀本身可能是设计选择，只有在经济危害时才升级为漏洞

### 审计现场区分技巧

**第一层过滤（5分钟快速判断）**:
```go
// 快速grep：搜索关键词，评估是否有动态调整
grep -r "InflationRate\|Inflation" x/mint/ --include="*.go" | grep -v "test\|comment"

// 如果只出现 params 读取，无条件逻辑 → 继续深入
// 如果出现 if bonded, switch epoch, case network_state → 标记为需要二阶段审计
```

**第二层验证（10-15分钟详细分析）**:
1. **追踪完整调用链**（不能中断）:
   - BeginBlocker() → MintCoins() → BlockProvisions()
   - 确认 BlockProvisions 计算中是否引用任何动态变量（bondedRatio, totalSupply, blockHeight % period）
2. **检查 Minter 结构的演变**:
   ```go
   type Minter struct {
       Inflation         sdk.Dec // 如果这里固定或只读 params，风险较高
       AnnualProvisions  sdk.Dec // 如果每 epoch 重算，可能有调整机制
   }
   ```
3. **验证参数治理路径**:
   - 查找 `UpdateParams()` 或 governance proposal handler
   - 确认 InflationRate 是否在 ParamChanges 白名单中
   - 检查历史区块链数据：过去6个月是否有过参数调整提案（通过 MsgGovSubmitProposal 搜索）

**第三层确认（现场决策）**:

| 信号 | 判定 | 处理方式 |
|------|------|--------|
| 固定 inflation，无治理路径，且已运行 >3 月未更新 | 真实漏洞 | 评为 Medium，建议治理提案流程 |
| 固定 inflation，但可通过治理修改，且社区知情 | 设计选择 | 评为 Low，记录在案 |
| inflation 动态调整但逻辑有 bug（如 min=max） | 真实漏洞 | 评为 High（若影响严重）或 Medium |
| 看似固定但藏在 hook 或 module extension 中的动态调整 | 误报 | 需要补充文档澄清，或代码重构提高可读性 |

### 常见误报案例与纠正方法

**案例1: 误读 params 赋值为固定**
```go
// 审计时看到这行代码认为是漏洞：
inflation := params.InflationRate

// 实际需要追踪：
// Step 1: InflationRate 是否在创世时硬编码还是可修改？
// Step 2: 在 x/mint/types/params.go 中查找 ParamSetPairs()
// Step 3: 如果 InflationRate 在 ParamSetPairs 中，则可治理修改 → 误报

// 纠正方法：
// 不仅读当前赋值，还要回溯 InflationRate 的定义和更新路径
```

**案例2: 漏读补偿机制导致的误报**
```go
// BeginBlocker 中仅见固定通胀，误认为无其他平衡机制
// 但实际在 EndBlocker 或 hook 中存在：
- 燃烧机制（gas fee burn）
- 质押奖励衰减（staking rewards rate curve）
- 交易税（dev tax, treasury fund）

// 纠正方法：
// 必须审计整个模块生命周期（BeginBlocker → ProcessTxs → EndBlocker）
// 不能仅看 mint 模块，需要审计 bank, staking, distribution 模块的配合
```

**案例3: 测试网 vs 主网代码路径混淆**
```go
// 常见误报：在 testnet 代码中看到固定参数
// 但主网已有不同配置（通过环保护网链参数文件）

// 纠正方法：
// 查询实际运行链的链参数（query gov params 或 genesis file）
// 不依赖代码中的默认值，优先使用链上现状数据
```

### 现场审计检查清单

- [ ] 通过 `chain-id` 和 `genesis.json` 确认目标链身份（避免审计错链）
- [ ] 下载链的实时 params：`gaiad query mint params --node <rpc>`
- [ ] 检查过去 6-12 个月的治理提案日志，统计参数变更频率
- [ ] 对比代码版本和链实际运行版本（有时链运行的是旧版本）
- [ ] 确认经济白皮书或文档中对通胀策略的陈述，与代码是否一致
- [ ] 与项目方沟通设计意图：是否刻意选择固定通胀作为初期设计
- [ ] 评估链龄和 TVL：初期链的固定通胀可接受度更高
