# 智能合约盲目信任中继负载

**语言**: Go  
**场景**: Cosmos SDK、自定义区块链链上验证、IBC 数据包中继、跨链预言机中继器  
**核心问题**: 链上合约直接使用中继器提供的数据但未二次验证

---

## Details

### 代码特征示例

```go
// 典型漏洞场景：Keeper 直接使用中继数据
func (k Keeper) HandleOracleData(ctx sdk.Context, relayMsg RelayMessage) error {
    // ❌ 直接使用 relayMsg.Price 未验证签名/时间戳/来源
    k.SetPrice(ctx, relayMsg.AssetID, relayMsg.Price)
    return nil
}

// IBC 中继场景
func (k Keeper) OnRecvPacket(ctx sdk.Context, packet channeltypes.Packet) error {
    var data OracleData
    types.ModuleCdc.UnmarshalJSON(packet.GetData(), &data)
    // ❌ 直接信任跨链数据包内容
    return k.ProcessOracleUpdate(ctx, data)
}
```

### 快速定位核心操作 **[审计等级: L3-逐行读]**

**关键模式**：
1. **Keeper 方法接收外部数据结构** - 搜索 `func (k Keeper) Handle*`、`OnRecv*`、`Process*`
2. **直接状态写入** - 检查 `k.Set*()` 调用是否紧随参数解包
3. **缺失验证链** - 在数据使用前查找：
   - `VerifySignature()` / `ValidateProof()`
   - `CheckTimestamp()` / `IsExpired()`
   - `ValidateSource()` / `IsAuthorizedRelayer()`

**定位技巧**：
- 追踪 IBC `OnRecvPacket` / `OnAcknowledgementPacket` 实现
- 检查 gRPC 端点中 `MsgServer` 的 handler 函数
- 搜索 `Unmarshal` 后立即调用业务逻辑的代码段

### 快速定位保护机制 **[审计等级: L4-跨模块追踪]**

**必查验证点**：
1. **签名验证层**：
   - `VerifyMultisig()` / `VerifySecp256k1Signature()`
   - Tendermint `crypto.PubKey.VerifySignature()`
   - 追踪到 `auth.Account` 或 validator 公钥集

2. **时间有效性**：
   ```go
   if msg.Timestamp < ctx.BlockTime().Add(-tolerance) { /* 过期检查 */ }
   ```

3. **白名单/权限校验**：
   - `k.IsAuthorized(ctx, msg.Relayer)`
   - 参数化配置 `Params().AllowedRelayers`

4. **数据合理性边界**：
   - 价格偏差检查：`abs(newPrice - oldPrice) / oldPrice < threshold`
   - 范围限制：`minValue < data < maxValue`

**跨模块追踪路径**：
- Keeper → Params 模块（验证配置）
- Keeper → Bank/Staking 模块（抵押品校验）
- BeginBlocker/EndBlocker 中的全局状态一致性检查

---

## Classify

### 确认为漏洞
1. **缺失签名验证** - 中继数据无密码学证明且可被任意伪造
2. **时间戳未校验** - 允许重放历史数据或使用过期数据
3. **无来源鉴权** - 任意地址可提交中继消息影响关键状态
4. **跨链数据盲信** - IBC 数据包内容未验证对端链状态证明

### 判定为误报
1. **前置验证存在** - 在 AnteHandler 或中间件层已完成签名/权限验证
2. **Tendermint 共识保证** - 数据由验证人多签提交（如 Oracle 模块投票机制）
3. **读写分离** - 仅读取中继数据用于查询，未写入状态或触发资金操作
4. **沙盒环境** - 测试链或隔离模块，影响范围受控

### 代码异味
1. **防护不充分** - 有签名验证但缺少时间窗口/重放保护
2. **单点信任** - 仅验证单个中继器而非多数共识
3. **弱边界检查** - 有范围验证但阈值设置不合理（如允许 100% 价格波动）
4. **日志缺失** - 关键数据接收点未记录审计日志

---

## Low Risk

### 可降级场景
1. **非关键业务** - 数据仅用于统计/展示，不影响共识或资产转移
2. **双重验证机制** - 中继数据需经链上二次投票或延迟生效
3. **金额限制** - 单次中继影响的资产价值受严格上限约束
4. **可逆操作** - 存在治理否决或紧急暂停机制
5. **冗余数据源** - 多个独立中继器聚合，异常值自动过滤
6. **短生命周期** - 中继数据仅在单个区块内有效，无持久化风险

### 降级评估要点
- **影响面**: 受损害的用户/资产范围
- **可利用性**: 攻击者需控制的前置条件（如控制中继器私钥）
- **检测能力**: 链上监控能否及时发现异常行为
- **恢复成本**: 是否可通过升级或状态迁移修复
