# Go 未分页迭代 DoS (Unpaged Iteration DoS)

**适用范围**: Cosmos SDK 及其他 Go-based 区块链  
**常见位置**: BeginBlocker/EndBlocker、Keeper 迭代逻辑、IBC 回调、查询处理函数

---

## Details

### 典型代码特征

```go
// 漏洞示例：EndBlocker 中无限制迭代
func (k Keeper) ProcessExpiredOrders(ctx sdk.Context) {
    store := ctx.KVStore(k.storeKey)
    iterator := sdk.KVStorePrefixIterator(store, []byte("orders/"))
    defer iterator.Close()
    
    for ; iterator.Valid(); iterator.Next() {
        var order Order
        k.cdc.MustUnmarshal(iterator.Value(), &order)
        // 处理每个订单...
        k.processOrder(ctx, order)
    }
}

// 查询函数中未使用分页
func (k Keeper) AllValidators(ctx sdk.Context) []Validator {
    var vals []Validator
    k.IterateValidators(ctx, func(val Validator) bool {
        vals = append(vals, val)
        return false // 继续迭代全部
    })
    return vals
}
```

### 快速定位核心操作技巧 (审计等级: **L2-跳读**)

**关键模式识别**:
- `sdk.KVStorePrefixIterator` + `for iterator.Valid()` 循环体
- `Iterate*` 系列函数（如 `IterateValidators`, `IterateAccounts`）
- `BeginBlocker`/`EndBlocker` 中的批量处理逻辑
- 查询 RPC 方法中返回切片/数组的函数

**扫描要点**:
1. Ctrl+F 搜索: `Iterator(`, `Iterate`, `BeginBlocker`, `EndBlocker`
2. 检查是否存在 `limit`, `pagination`, `MaxIterations` 等控制变量
3. 计算迭代次数：固定上限 vs 链上状态决定

### 快速定位保护机制技巧 (审计等级: **L1-关键词扫描**)

**防护关键词**:
```go
// 正向保护指标
query.PageRequest       // gRPC 查询分页
ctx.GasMeter()         // Gas 消耗自然限制
MaxIterations          // 硬编码上限
break / return         // 提前退出条件
```

**验证清单**:
- [ ] 是否引用 `query.PageRequest` 或 `pagination.ParsePagination()`
- [ ] 迭代循环是否有计数器 + 上限检查 (`count >= MAX_LIMIT`)
- [ ] Gas 消耗是否足以在合理时间内耗尽 (检查 `GasConfig`)
- [ ] 是否仅在测试/genesis 等非生产场景使用全量迭代

---

## Classify

### 确认为真实漏洞的条件

1. **触发路径可达**: 攻击者可通过交易、提案或自然业务流程触发迭代逻辑
2. **无界状态增长**: 迭代数据集大小由外部可控因素决定（如用户注册数、订单数）
3. **Gas 失效**: 迭代在 BeginBlocker/EndBlocker/Deliver 等非查询上下文中，或单次迭代消耗极低无法有效限制
4. **实际危害**: 模拟测试中可导致区块时间超时（如 >5s）、内存溢出或节点崩溃

### 误报场景

- 迭代数据集有业务上限（如最多 100 个验证人、固定数量的权限列表）
- 仅在 genesis/upgrade 等一次性操作中使用
- 查询函数且外部已有分页中间件保护
- Gas 机制已足以限制（需实际计算验证）

### 代码异味

- 技术上有上限但未明确文档化，未来维护可能破坏假设
- 循环中包含复杂计算或嵌套迭代，虽有上限但性能较差
- 使用 `defer iterator.Close()` 但可能提前 panic 导致资源泄漏

---

## Low Risk

以下情况可降级为低风险:

1. **链治理可控**: 迭代集合大小由治理参数严格限制，且修改需提案周期（如验证人数量上限 200）
2. **经济成本保护**: 每次新增迭代项需消耗大量代币且无退款机制（如高昂注册费用），攻击成本显著高于 DoS 收益
3. **监控可预警**: 链上有监控指标在数据量达到阈值前告警，运营团队可提前介入
4. **影响范围局限**: 仅影响特定查询 API 性能，不影响共识层，且有服务端超时机制兜底
5. **历史实证**: 主网运行多年数据量未突破安全阈值，且业务模型决定增长缓慢（需评审业务逻辑合理性）

**注意**: 即使评为低风险，仍建议在审计报告中标注为"需长期监控"项，并要求项目方建立数据增长监控。
