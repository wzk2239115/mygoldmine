**Go**（适用于 Cosmos SDK 等链上模块升级场景）  
常出现在链上治理驱动的模块升级、共识参数热更新等逻辑中，包括但不限于 upgrade plan 未校验模块兼容性、handler 未版本隔离、状态迁移未原子化等方式：  
- 未验证的升级计划：治理提案触发的升级计划未验证新模块与现有状态的兼容性，导致升级后链功能异常，详见：Go_UnverifiedUpgradePlan.md
## Details

**代码示例：**

```go
// 风险示例：治理提案处理器未验证升级计划兼容性
func (k Keeper) ApplyUpgradePlan(ctx sdk.Context, plan types.Plan) error {
    // 直接应用升级计划，未验证
    k.ScheduleUpgrade(ctx, plan)
    return nil
}

// 风险示例：版本切换未校验状态schema
func (m *ModuleManager) RunMigrations(ctx sdk.Context, fromVersion uint64) error {
    for _, moduleName := range m.OrderMigrations {
        // 未检查目标版本与当前状态的兼容性
        m.Modules[moduleName].Migrate(ctx, fromVersion)
    }
}

// 风险示例：参数变更未验证范围
func (k Keeper) HandleParamChangeProposal(ctx sdk.Context, p ParamChange) {
    subspace := k.GetSubspace(p.Subspace)
    // 直接设置新参数值，未验证类型、范围、依赖
    subspace.Set(ctx, []byte(p.Key), p.Value)
}
```

**快速定位核心操作（L2-L3）：**  
- **L2 跳读**：扫描 `x/upgrade`, `x/gov` 模块的 `ApplyUpgrade`, `ScheduleUpgrade`, `RunMigrations` 函数，关注治理提案执行路径
- **L3 逐行读**：重点审查 `UpgradeHandler` 注册逻辑、`BeginBlocker` 中的版本切换分支、参数变更提案的 `ValidateBasic` 实现

**快速定位保护机制（L3-L4）：**  
- **L3 逐行读**：检查 `Plan.Info` 字段是否包含版本校验哈希、`ValidateBasic()` 是否验证 `Height` 合理性、迁移函数是否有 `ConsensusVersion()` 比对
- **L4 跨模块追踪**：追踪 `app.SetUpgradeHandler()` 注册的版本映射表、`module.Manager.RunMigrations()` 的版本依赖图、Store key 变更是否有兼容性矩阵

## Classify

**判定为漏洞：**
- 治理提案可设置任意升级高度但未验证二进制文件就绪状态
- 模块迁移函数缺失版本号检查，允许跨多版本降级
- 参数变更未校验新值对共识的影响（如 MaxValidators 降至当前活跃数以下）
- `BeginBlocker` 中执行升级时，未通过 `panic()` 中断链，导致异常状态被持久化到下个块
- 升级 handler 中新增的 Store key 与旧 Store 键值冲突，导致数据覆盖

**判定为误报：**
- 升级计划已在链外通过社会共识验证（需确认文档流程）
- 测试网环境明确允许激进升级策略
- 存在独立的 CI/CD 流程在提案前预执行兼容性测试
- 版本校验由外部编排系统（如 Cosmovisor）在执行前完成，链码无需重复验证
- 参数变更通过治理投票门槛和冷却期已充分审查，无额外链上检查必要

**判定为代码异味：**
- 版本校验逻辑存在但写在注释或文档中，未强制执行
- 依赖治理参数（如最小投票期）间接降低风险但无技术硬约束

## Audit Techniques & Real-World Patterns

### 审计关键信号与实战技巧

**信号1：版本映射表的可信度评估**
- **高风险特征**：`app.SetUpgradeHandler()` 中使用硬编码版本号，无版本枚举定义；Store 迁移跳过中间版本（如直接从 v1→v5）
- **实战技巧**：交叉对比 `module.Manager.GetVersionMap()` 与 `x/upgrade` 模块的升级历史；检查是否存在版本黑名单（如 v1.0.0-beta 被禁止升级）
- **真实案例**：某链升级时模块A升至v3但未执行v2的数据修复，导致某些字段为空。审计时发现 v2 handler 被注释而非删除，表明版本管理混乱
- **区分技巧**：若注释带有 TODO 和时间戳，且距今超过6个月，可判定为技术债风险而非临时跳过

**信号2：参数变更的约束边界**
- **高风险特征**：`ParamSetPairs` 缺少 `ValidatorFn`；参数变更提案无 `ValidateBasic()` 调用；参数新值允许范围无上下界定义
- **实战技巧**：追踪参数被读取的所有位置（grep `k.GetParam`），验证新值是否会破坏业务逻辑（如 gas 参数小于交易最小大小）
- **真实案例**：Cosmos Hub 曾提案降低 `MaxValidators`，但未检查当前活跃验证者数。若通过会导致某些验证者被强制移除，违反权益证明原则
- **区分技巧**：检查治理提案的提议者是否为技术委员会账户，或是否附带链下审计报告签名；若参数变更历史已存档在 GitHub 上，说明社会共识程度高

**信号3：迁移函数的原子性与可回滚性**
- **高风险特征**：`RunMigrations()` 中存在 `continue` 或错误处理不当；状态修改先执行后校验；缺少 checkpoint 机制
- **实战技巧**：检查迁移函数是否使用 `cache.MultiStore` 进行沙箱测试；通过代码覆盖率工具验证所有分支是否有测试用例
- **真实案例**：某链升级时，中途 Store key 迁移失败但之前的数据已修改。重启链时因为 height 已推进无法回滚，导致链停止
- **区分技巧**：若迁移逻辑中存在条件分支（如 `if from_version < 3`），必须逐个验证每个分支；检查测试用例是否覆盖降级路径（虽然不建议降级）

**信号4：跨模块依赖的版本一致性**
- **高风险特征**：`RunMigrations()` 的模块执行顺序不固定；新模块版本依赖旧模块状态但版本号倒序执行
- **实战技巧**：绘制模块依赖图，确保模块迁移按拓扑排序执行；检查 `app.mm.SetOrderMigrations()` 是否与 `SetOrderBeginBlockers()` 一致
- **真实案例**：某链中 bank 模块迁移在 auth 模块之后执行，但 bank 迁移中需要读取 auth 的账户信息，导致迁移失败
- **区分技巧**：若依赖关系写在 `x/upgrade` 的 README 中而非代码注释中，说明维护意识不足，风险等级上升

### 真实漏洞 vs 误报的区分经验表

| 特征 | 真实漏洞 | 误报 | 区分方法 |
|------|--------|------|--------|
| **版本跳跃** | 无版本号列表，可跨任意版本升级 | 版本白名单已在 SDK/模块中定义 | grep `version.*in\|switch.*version` 确认约束存在 |
| **参数验证** | ValidatorFn 缺失且无链外审查流程 | ValidatorFn 存在但代码中未调用 | 追踪参数从 GetParam 到使用的全路径 |
| **错误恢复** | 迁移失败后状态半持久化 | 迁移全程使用缓存，异常自动回滚 | 检查是否有 `defer Unlock()` 或显式事务边界 |
| **社会共识** | 升级提案无链外评论或投票记录 | 升级已在治理论坛讨论3个月以上 | 查看 `gov.Proposal.Metadata` 或治理论坛归档链接 |
| **二进制就绪** | 升级高度可由单个账户随意修改 | 升级高度由链上共识参数定义 | 检查 `plan.Height` 是否来自 `ParamSpace` 或硬编码常量 |

## Low risk

**以下场景可评为低风险：**  
- 升级计划仅修改非共识参数（如日志级别、RPC 限流）且有自动回滚机制
- 模块版本跳跃受白名单限制（如仅允许 v1→v2，不允许 v1→v3）
- 存在金丝雀验证：升级计划先在验证节点子集执行，通过健康检查后再全网推送
- 参数变更范围已在 `ParamSetPairs` 中定义 `ValidatorFn`，且关键参数需多轮提案
