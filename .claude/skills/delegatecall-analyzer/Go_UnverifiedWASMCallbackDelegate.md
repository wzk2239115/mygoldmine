# 未验证的 WASM 回调委托 (Unverified WASM Callback Delegate)

**漏洞类型**: 上下文污染 / 权限绕过  
**适用范围**: Cosmos SDK、CosmWasm、Polkadot 等支持 WASM 智能合约的区块链平台

## Details

**典型代码模式**：

```go
// 危险：直接接受外部指定的合约地址进行回调
func (k Keeper) ExecuteCallback(ctx sdk.Context, callbackAddr string, msg []byte) error {
    // 未验证 callbackAddr 的身份和权限
    result, err := k.wasmKeeper.Execute(ctx, callbackAddr, msg)
    return err
}

// CosmWasm Reply 场景
func (c *Contract) Reply(ctx sdk.Context, msg wasmvmtypes.Reply) (*Response, error) {
    // 未验证 msg.ID 对应的子消息来源
    SubMsgResponse := msg.Result.Unwrap()
    // 直接处理返回数据，可能被恶意合约污染
    return handleResponse(SubMsgResponse.Data)
}
```

**快速定位核心操作** (审计等级: **L3 逐行读**)  
- 搜索关键函数：`Execute`、`Reply`、`Callback`、`SubMsg`、`WasmMsg::Execute`
- 追踪跨合约调用链路：查找 `ExecuteMsg`、`WasmMsg`、`SubMsg` 的构造点
- 关注执行上下文：检查 `ctx` (Context) 是否被传递到不可信合约

**快速定位保护机制** (审计等级: **L2 跳读**)  
- 白名单验证：查找 `IsAllowedContract`、`VerifyContractAddr`、权限映射表
- 代码哈希校验：`k.wasmKeeper.GetContractInfo`、`CodeHash` 比对逻辑
- 调用者限制：`info.Sender` 验证、`require_auth` 检查
- 隔离标志：`SubMsg.ReplyOnSuccess` 配置、`isolate_context` 参数

## Classify

**判定为漏洞的条件**：
1. 接受任意外部地址作为回调目标，且该目标在调用方上下文中执行
2. Reply/Callback 处理器信任未验证的子消息返回数据，用于状态更新或权限决策
3. 跨合约调用可修改调用方存储，且无代码哈希或签名验证

**判定为误报的场景**：
1. 回调地址来自预部署的系统合约列表（硬编码或治理设置）
2. 子消息执行在独立上下文中，返回数据仅用于只读查询
3. 执行前已通过代码哈希验证目标合约版本

**判定为代码异味**：
1. 回调地址虽经过白名单验证，但白名单更新机制无多签/时间锁
2. 依赖 `info.Sender` 校验但存在可伪造的 IBC 消息场景
3. 存在验证逻辑但注释标注为"临时绕过"或"TODO"

## Low risk

**以下情况可降级为低风险**：
1. **受限上下文**：回调合约仅能访问只读接口（如查询类消息），无状态写入权限
2. **数据隔离**：子消息结果仅影响发起者自身账户余额/状态，不涉及全局权限
3. **经济成本**：执行回调需消耗高额 Gas，且单笔调用损失上限可控（如 < $1000）
4. **紧急开关**：存在可由治理快速冻结回调功能的开关，且历史响应时间 < 1小时
5. **监控告警**：回调异常（如 Gas 耗尽、返回值异常）有实时链上事件监控及自动暂停机制

**特殊豁免场景**：
- 仅在测试网启用的实验性功能
- 回调目标限定为同一开发团队部署的配套合约且定期审计

## 审计专业技巧

### 1. 代码静态分析清单

| 检查项目 | 审计问题 | 判定依据 |
|---------|---------|---------|
| **调用链追踪** | 回调地址是否经过 N 层函数封装？ | 追踪来源：是否最终指向用户输入或 msg 结构体字段 |
| **存储密钥分离** | 白名单是否与执行参数存储分离？ | 查看 `storeKey` 是否相同；白名单应在独立 Module 中 |
| **上下文传递** | `ctx` 中是否存在权限标记污染？ | 检查 `ctx.WithValue()` 链；警惕 `PermissionedContext` 的重用 |
| **返回值校验** | Reply 中是否直接解构返回数据？ | 反模式：`json.Unmarshal(msg.Result.Ok)` → 应先验证来源 |
| **Gas 限制** | SubMsg 是否设置 `gas_limit`？ | 缺失 = 恶意合约可造成 ReDoS；应 < 父消息 Gas 的 30% |

### 2. 常见误报案例与识别方法

**误报案例 A**：看起来接受任意地址，实际是白名单验证
```go
// 乍看高危：callbackAddr 参数可控
func (k Keeper) ProcessCallback(ctx sdk.Context, callbackAddr string, msg []byte) error {
    // 【误报陷阱】初审会认为直接执行
    return k.Execute(ctx, callbackAddr, msg)
}

// 【真相】在上一层已验证
func (k Keeper) PublicAPI(ctx sdk.Context, callbackAddr string, msg []byte) error {
    // 【关键】白名单检查发生在这里！
    if !k.isContractWhitelisted(callbackAddr) {
        return errors.New("not in whitelist")
    }
    return k.ProcessCallback(ctx, callbackAddr, msg)
}
```
**识别方法**：在调用函数处搜索上层入口；使用 IDE 的"调用者"功能反向追踪

**误报案例 B**：数据流是只读查询，不涉及状态修改
```go
func (c *Contract) Reply(ctx sdk.Context, msg wasmvmtypes.Reply) (*Response, error) {
    data := msg.Result.Ok
    // 【关键】仅用于构建只读查询响应
    price := parsePrice(data)  // 解析来自 Oracle 合约的价格

    // 【安全】价格仅用于计算返回值，不修改存储
    return &Response{
        Attributes: []Attribute{{Key: "price", Value: price}},
    }, nil
}
```
**识别方法**：追踪解析后的数据流；检查是否经过 `k.Set()`、`k.AddAmount()` 等修改操作；仅读取 = 风险等级 ↓

**误报案例 C**：SubMsg 在隔离上下文执行，不污染原上下文
```go
func (c *Contract) Execute(ctx sdk.Context, msg ExecuteMsg) (*Response, error) {
    // 【关键】gas_limit 限制了恶意合约的破坏范围
    subMsg := SubMsg{
        ID:                                1,
        Msg:                               WasmMsg{Execute: ...},
        GasLimit:                          Uint64(50000),  // 明确限制！
        ReplyOnSuccess:                    true,
    }
    return k.DispatchSubmessage(ctx, subMsg)
}

func (c *Contract) Reply(ctx sdk.Context, reply Reply) (*Response, error) {
    // 【事实】50k gas 无法造成全局损害
    return handleReply(reply)
}
```
**识别方法**：检查 SubMsg 配置，gas_limit 是否设置且 < 父消息 50%；是否使用隔离快照上下文

### 3. 真实漏洞的红旗信号

| 红旗信号 | 出现频率 | 利用难度 | 风险等级 |
|--------|--------|--------|--------|
| 回调地址来自用户输入 + 无白名单检查 | 高 | 低 | **P0** |
| 白名单存在但可被任意写入者修改 | 中 | 低 | **P0** |
| Reply 直接修改合约状态（如权限）| 中 | 中 | **P1** |
| SubMsg 无 gas_limit 或限制 > 50% | 高 | 高 | **P1** |
| 存在"绕过"注释 + 白名单验证不完整 | 低 | 中 | **P1** |
| IBC 消息可伪造调用方身份 + 依赖 Sender 验证 | 低 | 高 | **P2** |

### 4. 验证清单（Verification Checklist）

**确认为漏洞前必问 6 问**：

1. **数据源追踪**：回调地址的第一出现点是否在函数入参、消息字段或存储读取？
   - 入参 → 高风险；存储读取 → 检查写入点是否受保护

2. **执行上下文**：执行回调时是否传入原始 ctx？
   - 传入原始 ctx → 高风险；独立快照 ctx → 风险 ↓

3. **返回数据使用**：Reply/Callback 返回的数据是否用于权限决策或状态修改？
   - 用于权限/状态 → 必须验证来源；仅用于日志 → 风险 ↓

4. **白名单覆盖面**：是否所有回调入口都经过白名单检查？
   - 仅部分入口检查 → 存在绕过 → 漏洞

5. **历史变更**：白名单近 6 个月是否被恶意修改过？
   - 检查 git 历史；对比部署时的代码哈希

6. **Sender 校验的可信性**：在 IBC/跨链场景下，Sender 是否可被伪造？
   - 跨链场景仅依赖 Sender → 需要代码哈希额外验证

### 5. 审计报告模板（Audit Report Pattern）

```markdown
## 发现编号：[ID]
**标题**：Unverified WASM Callback Delegate
**严重级别**：[P0/P1/P2/Low]

### 证据链
1. 代码位置：file:line
2. 调用栈：FunctionA → FunctionB → vulnerable_Execute()
3. 数据流：user_input → callbackAddr → k.Execute(ctx, callbackAddr)

### 漏洞成立的前置条件
- [ ] 回调地址来自不可信源
- [ ] 白名单检查缺失或绕过路径存在
- [ ] 返回数据用于权限/状态决策

### 可能的误报原因
- [ ] 存在上层白名单检查（需验证所有入口）
- [ ] 数据流实际为只读查询
- [ ] 存在 Gas 限制 < 50% 的 SubMsg 隔离

### 最终判定
**结论**：[确认漏洞 / 条件漏洞 / 低风险 / 误报]
**建议**：[具体修复建议]
```
