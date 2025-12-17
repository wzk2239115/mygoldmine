# Go Unchecked Keeper Call

**漏洞类型**：未检查 Keeper 调用返回错误  
**适用范围**：Cosmos SDK、IBC 模块、自定义 Keeper 方法  
**常见场景**：`SendCoins`、`BurnCoins`、`MintCoins`、`TransferFrom`、`CallContract`、`ExecuteMsg`、IBC Packet 处理

## Details

### 典型代码模式

```go
// 漏洞示例：直接调用 Keeper 方法未检查 error
func (k Keeper) ProcessWithdrawal(ctx sdk.Context, addr sdk.AccAddress, amount sdk.Coins) error {
    // 直接调用 SendCoins，未检查返回值
    k.bankKeeper.SendCoins(ctx, k.GetModuleAddress(), addr, amount)
    
    // 继续后续逻辑，认为转账已成功
    k.SetWithdrawalStatus(ctx, addr, "completed")
    return nil
}

// 漏洞示例：IBC 回调中忽略错误
func (k Keeper) OnAcknowledgementPacket(ctx sdk.Context, packet channeltypes.Packet, ack []byte) error {
    k.bankKeeper.MintCoins(ctx, types.ModuleName, coins) // 未检查 error
    k.bankKeeper.SendCoinsFromModuleToAccount(ctx, types.ModuleName, recipient, coins) // 未检查 error
    return nil
}

// 漏洞示例：批量操作中部分失败
func (k Keeper) BatchReward(ctx sdk.Context, recipients []sdk.AccAddress, amount sdk.Coins) {
    for _, addr := range recipients {
        k.bankKeeper.SendCoins(ctx, k.GetModuleAddress(), addr, amount) // 部分失败被忽略
    }
}
```

### 快速定位核心操作（L2-L3）

**审计等级**：L2（跳读） → L3（逐行读）

**关键模式识别**：
- **Keeper 方法调用链**：搜索 `.bankKeeper.`、`.stakingKeeper.`、`.ibcKeeper.`、`.wasmKeeper.` 等调用
- **资产转移操作**：`SendCoins`、`SendCoinsFromModuleToAccount`、`SendCoinsFromAccountToModule`、`MintCoins`、`BurnCoins`
- **跨链操作**：`SendPacket`、`WriteAcknowledgement`、`OnRecvPacket`、`OnAcknowledgementPacket`
- **合约调用**：`Execute`、`Instantiate`、`Migrate`、`Sudo`
- **特征标记**：函数调用后直接换行，无 `if err != nil` 或 `_ = ` 或变量接收

**快速扫描技巧**：
```bash
# 搜索可能未检查的 Keeper 调用
grep -E "\.Send(Coins|CoinsFrom)" *.go | grep -v "err"
grep -E "\.(Mint|Burn)Coins" *.go | grep -v "err"
grep -E "\.Execute\(" *.go | grep -v "err"
```

### 快速定位保护机制（L1-L4）

**审计等级**：L1（关键词扫描） → L4（跨模块追踪）

**L1 - 关键词扫描**：
- 搜索 `if err != nil`、`errors.Wrap`、`return err` 判断是否有错误处理
- 检查 `defer` 中是否有 panic recovery 或回滚机制
- 查找 `sdk.Context` 的 `CacheContext()` 配合 `Write()` 的事务性操作

**L2 - 保护模式识别**：
```go
// 安全模式 1：显式错误检查
err := k.bankKeeper.SendCoins(ctx, from, to, amount)
if err != nil {
    return err
}

// 安全模式 2：使用 CacheContext 进行事务性操作
cacheCtx, write := ctx.CacheContext()
if err := k.ProcessOperation(cacheCtx, params); err != nil {
    return err // 不调用 write()，操作回滚
}
write() // 提交更改

// 安全模式 3：显式忽略（明确意图）
_ = k.bankKeeper.SendCoins(ctx, from, to, amount) // 开发者明确忽略
```

**L3 - 逐行追踪**：
- 检查函数返回值是否被正确传播到上层调用
- 确认错误处理逻辑是否会导致状态不一致
- 验证 `ctx` 是否为 CacheContext，失败时能否回滚

**L4 - 跨模块追踪**：
- 追踪 Keeper 方法的具体实现，确认内部是否有额外的安全检查
- 检查 AnteHandler 或 PostHandler 是否有全局性的保护机制
- 确认模块的 Invariants 检查是否能捕获状态不一致

## Classify

### 确定为漏洞的条件：
1. **关键路径未检查**：资产转移、权限变更、状态更新等关键操作的 error 未处理
2. **状态不一致风险**：Keeper 调用失败但后续逻辑继续执行，导致状态与实际不符
3. **无补偿机制**：没有 CacheContext、没有事务回滚、没有 Invariants 检查
4. **用户资产损失**：可能导致代币被锁定、转账失败但记录已更新、奖励发放失败等

### 判定为误报的条件：
1. **显式忽略**：使用 `_ = ` 明确表示开发者有意忽略（需进一步确认合理性）
2. **上层有检查**：当前函数未检查，但调用方有统一的错误处理
3. **Keeper 内部保证**：Keeper 方法内部已处理所有错误情况并保证操作原子性
4. **只读操作**：纯查询类 Keeper 调用，不涉及状态修改

### 代码异味的情况：
1. **非关键路径**：辅助性操作（如日志、事件）的 Keeper 调用未检查
2. **幂等操作**：重复执行不会造成额外影响的操作
3. **最佳实践违背**：虽不会立即造成损失，但违反编码规范，增加维护难度

## Low risk

### 低风险评级的适用场景：

1. **已有兜底机制**：
   - 模块实现了 Invariants 检查，能在 EndBlock 中捕获不一致
   - 存在定期的状态同步或对账机制
   - 上层有全局的错误处理或回滚逻辑

2. **影响范围受限**：
   - 仅影响单个用户的非关键数据（如元数据、备注）
   - 失败操作可通过重试恢复
   - 有独立的补偿或退款机制

3. **业务容错设计**：
   - 系统设计为最终一致性，可容忍短期不一致
   - 有链下监控和人工介入机制
   - 失败操作不会造成永久性资产损失

4. **环境限制**：
   - 操作仅在受信任的模块间调用
   - Keeper 方法由治理提案触发，有足够的审查时间
   - 测试网或开发环境部署

**注意**：即使评为低风险，也应要求开发团队添加错误检查，遵循最佳实践原则。
