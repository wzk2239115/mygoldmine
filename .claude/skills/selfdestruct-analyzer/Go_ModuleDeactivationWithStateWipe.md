# Go 模块禁用后状态清除漏洞审计

## Details

**典型代码模式：**

```go
// 易受攻击的模块禁用逻辑
func (k Keeper) DeactivateModule(ctx sdk.Context, moduleID string) error {
    // 1. 禁用模块标志
    k.SetModuleStatus(ctx, moduleID, StatusInactive)
    
    // 2. 清除模块状态（危险点：跨状态操作）
    k.DeleteAllModuleData(ctx, moduleID)  // ⚠️ 未验证依赖关系
    
    // 3. 触发清理回调
    if err := k.notifyModuleShutdown(ctx, moduleID); err != nil {
        // 错误处理不当可能导致状态不一致
        return err
    }
    
    // 4. 清除权限映射
    k.RevokeAllPermissions(ctx, moduleID)  // 可能影响其他模块
    
    return nil
}
```

**快速定位核心操作技巧（L2：跳读）：**
- 搜索关键函数：`Delete*`、`Remove*`、`Clear*`、`Prune*`、`Wipe*`、`Deactivate*`
- 追踪 KVStore 批量删除：`Iterator` + `Delete` 组合、`DeletePrefix` 等批量清除操作
- 识别模块间状态引用：检查被清除的 key 是否被其他模块的 Keeper 方法引用
- 关注 Protobuf 状态字段：查找 `Status`、`IsActive`、`Deprecated` 等生命周期标志

**快速定位保护机制技巧（L3：逐行读 + L4：跨模块追踪）：**
- **L2（跳读）** 检查事务性保护：是否使用 `CacheContext` 或多阶段提交确保清除操作原子性
- **L3（逐行读）** 验证依赖检查逻辑：
  - 是否存在 `HasDependentModules`、`CheckReferences`、`ValidateSafeToDelete` 等前置校验
  - 清除操作前是否遍历检查跨模块引用（如 `k.bankKeeper.HasBalance()`）
  - 错误处理是否回滚已执行的部分清除（检查 `defer` 或显式回滚逻辑）
- **L3（逐行读）** 识别状态锁机制：`mutex`、`locked` 标志、`IsMigrating` 等并发保护
- **L4（跨模块追踪）** 追踪 Keeper 依赖链：
  - 检查其他模块的 `BeginBlocker`/`EndBlocker` 是否依赖被清除的状态
  - 验证 `Hooks` 机制中的监听器是否已正确注销（`RegisterHooks`/`UnregisterHooks`）
  - 追踪 IBC 通道状态、Staking 代理关系等全局依赖
- **L4（跨模块追踪）** 审查权限系统影响：清除操作是否遗漏 `authz` 授权记录、`feegrant` 津贴等衍生状态

## Audit Professional Techniques（审计专业技巧）

### 阶段一：快速判断真假漏洞的四个关键问题

**问题1：数据是否真的被删除了？**
```go
// ❌ 真实删除 - 高风险
k.stateStore.DeletePrefix(moduleKey)

// ✓ 软删除 - 需进一步审计
module.Status = INACTIVE
k.Set(ctx, key, module)

// ⚠️ 延迟删除 - 需检查清理器
k.AddToCleanupQueue(ctx, moduleKey, blockHeight+unbondingPeriod)
```
**审计要点**：若为硬删除，立即转入深度分析；若为软删除，检查依赖方是否都检查 `Status` 标志。

**问题2：清除前是否遍历检查了所有依赖？**
```go
// ✓ 安全做法：前置检查所有引用
for _, referrer := range k.GetAllModuleDependencies(ctx, moduleID) {
    if referrer.IsActive && referrer.RefersTo(moduleID) {
        return fmt.Errorf("cannot delete: module %s still referenced by %s", moduleID, referrer.ID)
    }
}

// ❌ 危险做法：盲目删除，异常时才发现
k.DeleteAllModuleData(ctx, moduleID)
```
**审计要点**：搜索删除前是否有 `Check*`、`Validate*`、`HasDependencies` 等前置校验函数调用。

**问题3：错误发生时能否回滚？**
```go
// ✓ 原子性保护
cacheCtx, commit := ctx.CacheContext()
if err := k.performDelete(cacheCtx, moduleID); err != nil {
    return err  // 自动回滚，不调用 commit
}
commit()

// ❌ 无法回滚的多步骤删除
k.DeleteModule(ctx, moduleID)      // 成功
k.RevokePermissions(ctx, moduleID) // 失败 - 模块已删除但权限未清
```
**审计要点**：多步骤删除必须包裹在 CacheContext 中，或有显式 defer 回滚机制。

**问题4：Hooks 和事件监听器是否安全注销？**
```go
// ✓ 完整的清理流程
k.UnsubscribeFromHooks(ctx, moduleID)
k.UnregisterFromEventBus(ctx, moduleID)
k.DeleteModule(ctx, moduleID)

// ❌ 危险：Hook 仍然活跃，访问已删除数据
k.DeleteModule(ctx, moduleID)
// Hook 回调仍可能在 EndBlocker 中触发，访问已删除的 k.GetModuleState()
```
**审计要点**：追踪 `RegisterHooks` 在何处，确保对应的 `UnregisterHooks` 在删除前被调用。

### 阶段二：真实漏洞 vs 误报的对比案例

| 特征 | 真实漏洞 | 误报 |
|-----|--------|------|
| **删除范围** | 硬删除关键状态，无软删除标志 | 软删除或延迟删除，保留核心数据 |
| **前置检查** | 无依赖校验或校验不完整（仅检查直接引用） | 有完整的前置检查，遍历所有依赖方 |
| **事务保护** | 多步骤删除无 CacheContext 保护 | 单一原子操作或被 CacheContext 包裹 |
| **Hook 注销** | 删除后 Hook 仍活跃，访问已删除数据 | Hook 在删除前已注销，或已检查 Status 标志 |
| **错误日志** | 异常消息笼统，难以追踪根因 | 明确的错误上下文，包含模块 ID 和步骤信息 |
| **跨模块引用** | 其他模块直接访问（无 nil 检查） | 其他模块通过接口或查询方法，有安全检查 |

### 阶段三：高效定位漏洞的检查清单

**第1轮（代码扫描，5分钟）：**
- [ ] 搜索 `Delete*`、`Wipe*`、`Deactivate*` 删除入口，标记所有删除操作
- [ ] 在删除操作前搜索 `Check*`、`Validate*` 前置校验，无校验 = 红旗
- [ ] 检查删除操作是否在 `CacheContext` 内或有显式回滚逻辑

**第2轮（依赖追踪，10分钟）：**
- [ ] 列举所有引用被删除数据的 Keeper 方法（通过搜索 key 前缀）
- [ ] 每个引用方检查是否有 `IsActive`、`IsDeleted` 状态检查或 nil 检查
- [ ] 追踪被删除的 key 是否在 `BeginBlocker`、`EndBlocker`、`Hooks` 中被访问

**第3轮（边界场景，5分钟）：**
- [ ] 是否存在并发删除场景（多个 tx 同时删除或访问）
- [ ] 升级或硬分叉时是否有恢复策略
- [ ] 删除失败时的恢复流程是否文档化

## Classify

**判定为漏洞：**
- 模块状态清除未验证依赖关系，导致其他模块访问已删除数据引发 panic 或状态不一致
- 清除操作非原子性，部分失败时已执行的删除无法回滚，造成孤儿状态或资金锁定
- 未同步注销跨模块引用（如 Hooks、权限映射、IBC 连接），导致回调触发空指针或逻辑错误
- 清除操作缺乏前置依赖检查，仅靠异常处理捕获问题（应该提前防止）

**判定为误报：**
- 模块采用软删除（标记 `IsDeleted` 但保留数据），其他模块通过检查标志位安全处理
- 清除操作前已通过治理提案强制迁移所有依赖状态，且有明确文档和链上证明
- 仅清除临时缓存或统计数据，不影响核心业务逻辑的正确性
- 删除操作被完整的 CacheContext 包裹，异常时自动回滚，无部分清除的风险

**判定为代码异味：**
- 清除逻辑分散在多个函数中，缺乏统一的 `CleanupManager` 或清理编排器
- 依赖关系校验不完整，仅检查直接引用而忽略间接依赖（如通过事件监听器的隐式耦合）
- 错误日志不明确，无法通过日志快速定位哪个步骤的清除失败

## Low risk

**以下场景可评为低风险：**
- 清除的模块为纯计算模块（如统计、聚合），无持久化状态或资金托管功能
- 模块已通过链上治理进入"废弃"状态超过解绑期（unbonding period），所有历史依赖已自然过期
- 清除操作包裹在 `CacheContext` 中并有完整的 `panic` 捕获和回滚机制
- 仅在测试网或沙箱环境执行清除操作，主网部署采用不可变模块设计
- 存在全局状态快照和回滚机制，清除操作可通过升级或硬分叉恢复
- 清除前已设置合理的宽限期（grace period），并通过链上事件通知所有依赖方完成迁移
