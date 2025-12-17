# Go_NonAtomicStateMigration

**漏洞类型**：非原子状态迁移  
**适用场景**：Cosmos SDK 等链上模块升级、治理驱动的状态迁移  
**风险等级**：Critical（可导致链状态不一致、共识失败）

## Details

### 代码示例

**漏洞代码**：
```go
// 模块升级处理器 - 未保证原子性
func (m Migrator) Migrate1to2(ctx sdk.Context) error {
    store := ctx.KVStore(m.keeper.storeKey)
    
    // 步骤1: 迁移账户余额格式
    balanceIterator := sdk.KVStorePrefixIterator(store, BalancePrefix)
    for ; balanceIterator.Valid(); balanceIterator.Next() {
        oldBalance := UnmarshalOldBalance(balanceIterator.Value())
        newBalance := ConvertBalance(oldBalance)
        store.Set(balanceIterator.Key(), Marshal(newBalance))
    }
    
    // 步骤2: 更新配置参数 - 此处若失败，步骤1已生效
    if err := m.updateParams(ctx); err != nil {
        return err // 已迁移的余额无法回滚
    }
    
    // 步骤3: 迁移质押数据 - panic会导致前面状态残留
    stakingData := store.Get(StakingKey)
    if len(stakingData) == 0 {
        panic("staking data not found") // 前序迁移已持久化
    }
    
    return nil
}
```

**关键风险点**：
- 多步骤状态修改缺乏事务边界
- 中途失败时无自动回滚机制
- panic 或 error 返回时已执行的 store.Set() 持久化
- 跨模块状态迁移缺少协调锁

### 快速定位核心操作（L3: 逐行读）

审计模块升级处理器时重点检查：
1. **迁移函数签名**：`Migrate*`, `RunMigrations`, `InitGenesis`, `ExportGenesis`
2. **状态写入序列**：连续多个 `store.Set()` / `store.Delete()` 调用
3. **错误处理**：`return err` 前已有状态修改操作
4. **panic 点**：状态写入后存在 `panic()` 或 `require.NoError()`
5. **跨 Keeper 调用**：一个迁移函数调用多个模块的 Keeper 方法
6. **迭代器操作**：`KVStorePrefixIterator` 遍历过程中修改状态

**扫描路径**：`x/*/migrations/*.go` → 定位迁移版本函数 → 追踪 Context 是否传递到所有子操作

### 快速定位保护机制（L2: 跳读）

检查是否存在原子性保证：
1. **CacheContext 包装**：
   ```go
   cacheCtx, writeFn := ctx.CacheContext()
   if err := migrate(cacheCtx); err != nil {
       return err // 未调用writeFn，状态未持久化
   }
   writeFn() // 统一提交
   ```
   - **关键词**：`CacheContext()`, `writeFn`, `commit`
   
2. **显式回滚逻辑**：
   ```go
   snapshot := captureState(ctx)
   if err := migrate(ctx); err != nil {
       restoreState(ctx, snapshot) // 手动回滚
       return err
   }
   ```
   - **关键词**：`snapshot`, `restore`, `rollback`

3. **迁移版本锁**：
   ```go
   if store.Has(MigrationLockKey) {
       return errors.New("migration in progress")
   }
   store.Set(MigrationLockKey, true)
   defer store.Delete(MigrationLockKey)
   ```

4. **预检查机制**：迁移前完整遍历验证，实际迁移时不再出错

**缺失保护信号**：
- 直接操作原始 Context 而非 CacheContext
- 无 defer 清理逻辑
- 缺少迁移状态标记位

## Classify

### 漏洞判定

满足以下条件确认为漏洞：
1. **状态修改可观测性**：迁移函数内存在 2+ 个状态写入操作（Set/Delete）
2. **非原子失败路径**：第一个状态修改后存在可能失败的分支（error/panic）
3. **无回滚能力**：未使用 CacheContext 或手动快照机制
4. **影响链级状态**：操作共识关键状态（质押、治理、账户余额、模块参数）

### 误报排除

以下情况不构成漏洞：
- 单一 Set 操作无后续逻辑（单步原子）
- 仅修改本地缓存/内存状态，未写入 KVStore
- 使用 CacheContext 包装且正确处理 writeFn
- 修改的是临时状态或调试日志（如事件 Emit）
- 多步骤间有显式校验保证幂等性（重入安全）

### 代码异味

需进一步研判的场景：
- 迁移函数调用外部模块 Keeper 但未确认其内部是否原子
- 使用 TransientStore（临时存储），需判断是否影响持久状态
- 迁移逻辑分散在多个文件/函数，需全局追踪执行顺序
- 复杂循环 + 条件分支，需人工验证所有失败路径

## Low risk

以下情况可评估为低风险：

1. **仅追加操作**：只新增键值对不修改/删除已有状态，失败仅导致部分数据缺失而非不一致
2. **幂等迁移**：可重复执行达到相同结果，链可通过重放区块自愈
3. **非共识状态**：操作的是客户端查询索引、统计数据等辅助状态
4. **测试网环境**：生产环境未部署的实验性功能
5. **已有外层保护**：框架层（如 `app.go` 的 `InitChainer`）统一使用 CacheContext
6. **迁移版本过低**：旧版本代码，实际升级已执行且链运行稳定超过一年
