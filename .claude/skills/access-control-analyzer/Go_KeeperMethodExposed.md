# Keeper 方法暴露（Go - Cosmos SDK）

**漏洞描述：** Keeper 方法未限制调用上下文，可在不应调用的场景被调用，绕过业务层访问控制

## Details

**对应代码示例：**
```go
// keeper.go - 风险示例
func (k Keeper) ForceTransfer(ctx sdk.Context, from, to sdk.AccAddress, amount sdk.Coins) error {
    // 直接执行转账，无权限检查
    return k.bankKeeper.SendCoins(ctx, from, to, amount)
}

// msg_server.go - 可能被滥用
func (ms msgServer) AdminAction(goCtx context.Context, msg *types.MsgAdminAction) (*types.MsgAdminActionResponse, error) {
    // 仅检查 msg.Sender 是否为管理员
    if !ms.Keeper.IsAdmin(ctx, msg.Sender) {
        return nil, sdkerrors.Wrap(sdkerrors.ErrUnauthorized, "not admin")
    }
    // 但其他模块可能直接调用 Keeper.ForceTransfer，绕过此检查
    return ms.Keeper.ForceTransfer(ctx, msg.From, msg.To, msg.Amount)
}
```

**快速定位核心操作的技巧（L2:跳读）：**  
- 扫描 `keeper/*.go` 文件中的导出方法（大写开头）
- 重点关注涉及资产操作、状态修改、权限变更的方法：`Transfer`、`Mint`、`Burn`、`SetAdmin`、`UpdateParams`
- 检查方法签名是否包含 `sdk.Context` 但缺少权限参数（如 `caller sdk.AccAddress`）
- 追踪方法被调用位置：仅在 `msg_server.go` 中调用为预期，在 `hooks.go`、`abci.go`、其他模块中调用需警惕

**快速定位保护机制的技巧（L3:逐行读）：**  
- 在 Keeper 方法内部查找权限校验逻辑：`require.Equal`、`if !k.IsAuthorized`、`k.authKeeper.HasPermission`
- 检查是否使用 `ctx` 提取调用者身份：`sdk.UnwrapSDKContext(goCtx)` + 上下文元数据验证
- 确认 `msg_server.go` 中的校验是否与 Keeper 方法解耦：若仅在 msg_server 中校验，其他路径可能绕过
- 搜索 `internal` 或 `private` 关键字：Go 中使用小写方法名限制跨包调用，但模块内仍可访问

## Classify

**漏洞判定：**  
- Keeper 方法涉及特权操作（转账、铸币、参数修改）且无内置权限校验，同时存在多个调用路径（消息处理、钩子、EndBlocker、其他模块依赖）
- 调用上下文无法被 Keeper 方法感知（如 `ctx` 中未包含 `Msg.Signer` 或无法追溯调用来源）

**误报判定：**  
- Keeper 方法仅执行只读查询操作（`GetBalance`、`QueryParams`），无状态修改
- 所有调用方均已在上层正确校验权限，且调用路径被限制在单一入口（如仅通过 msg_server 调用）
- 方法使用 `unexported` 命名（小写开头），且仅在 keeper 内部被私有方法调用

**代码异味判定：**  
- Keeper 方法包含部分校验（如金额范围检查），但缺少调用者身份校验
- 特权操作被拆分为多个 Keeper 方法，单个方法看似安全，但组合调用可绕过限制

## Low risk

- **有限作用域暴露：** Keeper 方法仅在受信任的模块间调用（如 staking 模块调用 bank 模块），且调用链路已审计确认安全
- **降级操作权限：** 暴露的方法仅执行低敏感度操作（如记录日志、更新非关键状态），即使被滥用影响有限
- **全局治理保护：** 所有特权操作强制要求通过治理提案触发，且提案流程已包含多签/时间锁验证
- **显式设计意图：** 文档明确说明某 Keeper 方法设计为跨模块调用接口，且调用方权限已在架构层统一管理（如通过 Capability Keys 机制）

## 审计专业技巧：真实漏洞 vs 误报区分

### 技巧1：权限校验的"深度追踪"
**真实漏洞特征：**
- Keeper 方法不进行任何权限校验，在 msg_server 中的权限检查被设计为**可选的**（如通过配置开关或特殊条件跳过）
- 权限校验存在于 msg_server，但 Keeper 方法可被其他模块的 hooks 直接调用，形成**多入口绕过**
- 使用 `goCtx` 从 context 中反解权限信息，但该信息**不可信**（可被其他模块修改）

**区分要点：** 检查权限信息来源的可信度。如果权限来自 `msg.Signer`（消息体），需确认是否有签名验证；如果来自 `ctx` 元数据，需确认是否被中间件/模块间调用篡改过。

**示例对比：**
```go
// 真实漏洞：权限仅在 msg_server 检查
func (k Keeper) MintTokens(ctx sdk.Context, to sdk.AccAddress, amount sdk.Coins) error {
    // 无权限检查！
    return k.bankKeeper.MintCoins(ctx, types.ModuleName, amount)
}

// 误报：Keeper 有内置权限检查机制
func (k Keeper) MintTokens(ctx sdk.Context, to sdk.AccAddress, amount sdk.Coins) error {
    if !k.hasRole(ctx, to, "minter") {  // ✓ 内置权限校验
        return sdkerrors.Wrap(sdkerrors.ErrUnauthorized, "no minter role")
    }
    return k.bankKeeper.MintCoins(ctx, types.ModuleName, amount)
}
```

### 技巧2：调用路径的"完整链路追踪"
**关键问题：** Keeper 方法是否**必然**通过安全的调用路径被调用？

**真实漏洞指标：**
- Keeper 方法可被外部消息（如 `MsgCustom`）直接或间接触发，消息本身无法控制调用参数
- 被 `module.BeginBlocker()` 或 `module.EndBlocker()` 无条件调用，且这些方法参数不受治理控制
- 暴露在 gRPC 查询接口中（如 `func (ks queryServer) GetKeeper()` 返回 Keeper 对象），允许客户端直接调用
- 被导出给其他模块作为接口（`NewKeeper` 返回的结构体暴露了敏感方法）

**区分要点：** 追踪**入站流量**。画出调用关系图，从消息 → msg_server → Keeper → 后端操作，标记每个环节的权限检查位置。

**实战经验：**
```
// 不安全链路（真实漏洞）：
用户发送 Msg → msg_server 有权限检查 →
  但同时 Keeper.AdminFunc 被 module.BeginBlocker 调用（无签名验证）→
  结果：定时器可触发特权操作

// 安全链路（误报）：
用户发送 Msg → msg_server 权限检查 →
  Keeper.AdminFunc（内无权限检查，但仅在 msg_server 被调用）→
  后端操作
  // 这里需要确认：是否有其他代码路径也调用 AdminFunc？grep 全仓库。
```

### 技巧3：Cosmos SDK 特定的"上下文持菌检查"
**常见误报陷阱：**
- Keeper 方法参数中有 `caller sdk.AccAddress`，但这个参数来自消息体且**未被签名验证**
- 权限校验使用 `ctx.From()` 或 `ctx.GetSigners()`，但调用者传入的 `ctx` 被篡改过（如在 AnteHandler 中）

**真实漏洞指标：**
```go
// 漏洞：调用者身份无法验证
func (k Keeper) TransferAdmin(ctx sdk.Context, newAdmin string) error {
    // caller 来自不可信源
    k.SetAdmin(ctx, newAdmin)
    return nil
}

// vs 正确做法
func (k Keeper) TransferAdmin(ctx sdk.Context, newAdmin string) error {
    caller := sdk.UnwrapSDKContext(ctx)  // 这里 caller 是从哪提取的？
    if !k.IsAdmin(ctx, caller) {  // 需要确认 caller 是否可信
        return sdkerrors.Wrap(sdkerrors.ErrUnauthorized, "not admin")
    }
    k.SetAdmin(ctx, newAdmin)
    return nil
}
```

**关键审计点：** 使用 `sdk.UnwrapSDKContext()` 时，需确认 `ctx` 来自 `BaseApp` 的 `DeliverTx` 流程（可信）还是其他模块传入（不可信）。

### 技巧4：误报的五个常见原因

1. **混淆"导出"与"可调用"**
   Keeper 方法大写开头确实可被其他包导入，但如果仅在 msg_server 中调用，且调用链路被完整审计，则不构成漏洞。需确认是否真的存在未授权的调用路径。

2. **忽视治理层面的保护**
   如果特权操作强制要求通过治理提案触发，且提案本身有多签验证，则 Keeper 方法无权限校验是设计决策，非漏洞。但需确认提案流程确实被执行。

3. **过度信任 capability key 机制**
   Cosmos SDK 中，如果操作被 Capability Key 保护（仅持有 key 的模块可调用），审计时容易将其视为不需要额外权限校验。但需确认 key 的生成、存储、传递过程本身无漏洞。

4. **误解 internal/private 的作用范围**
   Go 的小写方法名仅限制**包外调用**，模块内的其他方法仍可访问。如果只看到方法是小写就判为安全，可能遗漏**包内的非预期调用路径**。

5. **忽视模块初始化阶段**
   某些 Keeper 方法在 `InitGenesis()` 中被调用，此时链处于初始化状态。如果在这个阶段存在权限验证的跳过逻辑（如 `if !k.Initialized { return nil }`），可能成为真实漏洞。

### 技巧5：实战检查清单
1. ✓ 在仓库根目录执行 `grep -r "\.ForceTransfer\|\.MintTokens\|\.SetAdmin"` 找出所有调用点
2. ✓ 对每个调用点追踪权限来源：是 msg.Signer（通过签名验证）还是 ctx 元数据（可能被篡改）
3. ✓ 检查 EndBlocker/BeginBlocker 是否调用了特权操作，若有，检查触发参数是否可控
4. ✓ 查看 Keeper 的导出签名，识别是否接受 `caller sdk.AccAddress` 参数，若无，则所有权限校验必须在外层
5. ✓ 对标准库对比：staking/bank 等官方模块如何处理类似情景，学习最佳实践
6. ✓ 若判定为误报，生成测试证明：写单元测试模拟未授权调用，应该失败
