# Go_NonIsolatedVersionHandler - 非隔离的版本处理器

**适用场景**：Cosmos SDK 等链上模块升级场景  
**问题描述**：不同版本的消息处理器未进行隔离，导致升级后旧消息被新逻辑错误处理，或新旧版本逻辑混用造成状态不一致

---

## Details

### 代码示例

**漏洞场景 - 直接覆盖消息处理器**：
```go
// 升级前：v1 版本的消息处理器
func (k Keeper) HandleMsgStake(ctx sdk.Context, msg *MsgStake) error {
    // v1 逻辑：直接质押，不检查锁定期
    return k.bankKeeper.SendCoins(ctx, msg.Delegator, k.ModuleAddress, msg.Amount)
}

// 升级后：v2 直接覆盖，未版本隔离
func (k Keeper) HandleMsgStake(ctx sdk.Context, msg *MsgStake) error {
    // v2 逻辑：新增锁定期检查
    if msg.LockPeriod < MinLockPeriod {
        return ErrInvalidLockPeriod
    }
    // 问题：升级前提交的未执行消息（msg 中无 LockPeriod 字段）会失败
    return k.bankKeeper.SendCoins(ctx, msg.Delegator, k.ModuleAddress, msg.Amount)
}
```

**漏洞场景 - 消息路由未版本区分**：
```go
// 同一个 MsgType 被不同版本复用
func (k msgServer) processTransaction(ctx sdk.Context, msg sdk.Msg) error {
    switch msg.(type) {
    case *MsgTransfer:
        // 问题：未检查消息版本，v1 和 v2 的 MsgTransfer 结构不同
        return k.handleTransfer(ctx, msg.(*MsgTransfer))
    }
}

// v1: MsgTransfer 只有 Amount 字段
type MsgTransferV1 struct {
    Amount sdk.Coins
}

// v2: 新增 Memo 字段
type MsgTransferV2 struct {
    Amount sdk.Coins
    Memo   string // 新增字段，但旧消息解析会失败
}
```

**漏洞场景 - 状态机版本未同步**：
```go
func (k Keeper) EndBlock(ctx sdk.Context) {
    // 问题：升级后未检查链当前版本，直接使用新逻辑
    currentVersion := k.GetProtocolVersion(ctx)
    
    // 错误：未判断 currentVersion，直接执行 v2 逻辑
    for _, validator := range k.GetAllValidators(ctx) {
        // v2 新增的奖励分配算法，但可能在 v1 状态上执行
        k.DistributeRewardsV2(ctx, validator)
    }
}
```

### 快速定位核心操作技巧（L3:逐行读）

**关键代码路径**：
1. **消息处理器注册点**：`RegisterMsgServer()` 或 `Route().AddRoute()` - 检查是否按版本区分注册
2. **升级处理器**：`UpgradeHandler` 或 `SetUpgradeHandler()` - 确认是否处理旧消息兼容性
3. **消息类型定义**：proto 文件中的 `message Msg*` - 对比不同版本的字段变化
4. **状态机钩子**：`BeginBlocker`/`EndBlocker` - 检查是否有版本判断逻辑

**扫描关键字**：
- `func (k Keeper) Handle` - 消息处理入口
- `switch msg.(type)` - 消息路由逻辑
- `app.UpgradeKeeper.SetUpgradeHandler` - 升级触发点
- `ConsensusVersion()` - 模块共识版本号
- `GetProtocolVersion` / `ctx.BlockHeight()` - 版本/高度判断

**审计检查点**：
```go
// ✓ 正确：版本隔离的处理器
func (k msgServer) HandleMsg(ctx sdk.Context, msg sdk.Msg) error {
    moduleVersion := k.GetConsensusVersion(ctx)
    switch moduleVersion {
    case 1:
        return k.handleV1(ctx, msg)
    case 2:
        return k.handleV2(ctx, msg)
    }
}

// ✗ 错误：无版本判断直接处理
func (k msgServer) HandleMsg(ctx sdk.Context, msg sdk.Msg) error {
    return k.processMsg(ctx, msg) // 未区分版本
}
```

### 快速定位保护机制技巧（L2:跳读）

**保护机制检查列表**：

1. **版本号守卫**（L1:关键词扫描）：
   - 搜索 `ConsensusVersion` 返回值 - 模块是否声明版本
   - 搜索 `if version < X` 或 `switch version` - 是否有版本分支逻辑

2. **消息版本字段**（L2:跳读）：
   - 检查 proto 定义中是否有 `uint64 version` 字段
   - 检查 `ValidateBasic()` 是否校验消息版本号

3. **升级迁移函数**（L1:关键词扫描）：
   - 搜索 `Migrator` 或 `Migrate*` - 是否有数据迁移逻辑
   - 搜索 `CreateUpgradeHandler` - 升级时是否处理兼容性

4. **高度/时间门控**（L2:跳读）：
   - 搜索 `ctx.BlockHeight() >= upgradeHeight` - 是否按高度激活新逻辑
   - 搜索 `UpgradePlan.Height` - 是否有明确的升级高度

**典型保护模式**：
```go
// ✓ 保护：基于高度的逻辑切换
func (k Keeper) ProcessMsg(ctx sdk.Context, msg *Msg) error {
    if ctx.BlockHeight() < k.GetUpgradeHeight() {
        return k.handleLegacy(ctx, msg) // 旧逻辑
    }
    return k.handleNew(ctx, msg) // 新逻辑
}

// ✓ 保护：消息版本字段
type MsgStake struct {
    Version uint64 // 显式版本号
    Amount  sdk.Coins
}

func (m *MsgStake) ValidateBasic() error {
    if m.Version > MaxSupportedVersion {
        return ErrUnsupportedVersion
    }
}
```

**无保护特征**（高风险信号）：
- 升级 handler 为空或仅返回 nil
- 消息结构变更但未增加版本字段
- keeper 方法直接覆盖无版本分支
- EndBlocker/BeginBlocker 无版本判断就执行新逻辑

---

## Classify

### 漏洞（Critical/High）
- **直接状态污染**：旧消息在新逻辑下导致状态机分叉（如奖励计算错误、余额异常）
- **共识失败**：不同节点因升级时间差执行不同版本逻辑，导致区块验证失败
- **资金损失**：新旧逻辑不兼容导致质押/转账/奖励分配计算错误

**判定标准**：
1. 升级前后消息字段不兼容（新增必需字段、删除字段、改变语义）
2. 无任何高度/版本门控机制
3. 影响共识关键路径（BeginBlock/EndBlock/消息执行）

### 误报
- **仅内部重构**：keeper 内部方法调整，但对外接口未变且有兼容层
- **私有测试网**：明确标注为实验性模块，不涉及主网升级
- **向后兼容的字段新增**：新增可选字段（optional），旧消息仍可正常处理

**排除条件**：
- proto 字段标记为 `optional` 且处理逻辑有默认值兜底
- 仅升级测试模块（如 `x/testmodule`）且明确注释 non-production
- 已有完整的升级测试用例覆盖新旧消息混合场景

### 代码异味（Medium）
- **缺乏升级测试**：无升级路径测试但理论上兼容
- **版本号未递增**：proto 有变更但 `ConsensusVersion()` 未更新
- **文档缺失**：升级 handler 存在但无注释说明兼容性处理

**降级理由**：
- 有隐式版本控制（如通过治理参数间接控制）
- 变更仅影响非共识部分（如日志、事件）
- 已部署但无实际升级场景（单链无升级历史）

---

## Low Risk

### 低风险场景评级标准

1. **向后兼容的字段扩展**
   - 新增字段为 `optional` 且有默认值
   - 旧消息处理时自动填充默认值，行为不变
   - 示例：添加 `string memo = 3 [(gogoproto.nullable) = true];`

2. **独立的辅助功能升级**
   - 仅变更查询接口（gRPC Query Service），不涉及状态变更
   - 升级 CLI 命令或 REST API 端点，原有接口保留
   - 更新事件（Event）字段，不影响链上逻辑

3. **充分的兼容性保障**
   - 有完整的 `Migrator.Migrate()` 迁移旧数据
   - 升级 handler 中显式处理旧版本状态
   - 包含 `TestUpgradeCompat()` 测试新旧消息混合执行

4. **治理参数式升级**
   - 通过链上参数（params）控制功能开关，而非硬编码逻辑
   - 新逻辑默认关闭，需治理提案激活
   - 示例：`if k.GetParams(ctx).EnableNewFeature { ... }`

5. **非共识逻辑变更**
   - 仅修改 Keeper 查询方法（不变更状态）
   - 优化性能但输出结果一致
   - Gas 计算调整但有充分的测试覆盖

### 低风险标志
- 存在 `if fromVersion < toVersion` 的迁移逻辑
- 消息结构使用 `oneof` 支持多版本
- 文档明确说明兼容性策略（CHANGELOG/UPGRADING.md）
- CI 中有 `upgrade_test.go` 专门测试升级路径
