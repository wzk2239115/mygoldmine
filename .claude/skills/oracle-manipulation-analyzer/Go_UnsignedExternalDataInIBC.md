# IBC 中未签名的外部数据

**漏洞类型**：Oracle Manipulation - Unsigned External Data in IBC  
**影响组件**：Cosmos SDK IBC 模块、跨链中继器、链上数据包处理逻辑

## Details

### 代码示例特征

典型出现在 IBC `OnRecvPacket`/`OnAcknowledgementPacket` 回调函数中，接收外部链数据但缺少签名验证：

```go
func (k Keeper) OnRecvPacket(ctx sdk.Context, packet channeltypes.Packet) error {
    var data OracleData
    // 危险：直接解码使用外部数据
    types.ModuleCdc.MustUnmarshalJSON(packet.GetData(), &data)
    // 无签名验证直接写入状态
    k.SetPrice(ctx, data.Symbol, data.Price)
    return nil
}
```

### 快速定位核心操作（L3：逐行读）

关键审计点按优先级排序：
1. **IBC 回调入口**：搜索 `OnRecvPacket`、`OnAcknowledgementPacket`、`OnTimeoutPacket` 函数定义
2. **数据反序列化点**：查找 `Unmarshal`、`UnmarshalJSON`、`Decode` 紧随 `packet.GetData()` 之后
3. **状态写入操作**：定位 `Set*`、`Store.Set`、`keeper.Set*` 等状态变更函数
4. **Relayer 数据提交**：检查 `SubmitPacket`、`RecvPacket` 等外部调用链路

审计检查清单：
- 数据包来源通道是否白名单验证（`packet.SourceChannel`）
- 解码后数据是否经过签名校验（缺少 `VerifySignature`/`ValidateBasic`）
- 是否存在中继器地址权限检查（缺少 `msg.Signer` 验证）
- 时间戳/序列号是否防重放（缺少 `nonce`/`timestamp` 检查）

### 快速定位保护机制（L2：跳读）

正向验证检查点：
1. **签名验证层**：查找 `crypto.VerifySignature`、`pubkey.VerifySignature`、`ed25519.Verify`
2. **数据源白名单**：搜索 `AllowedChannels`、`TrustedRelayers`、`AuthorizedClients`
3. **Merkle 证明验证**：定位 `VerifyMembership`、`VerifyNonMembership`（轻客户端验证）
4. **多签/共识验证**：查找 `ValidatorSet.VerifyCommit`、`CheckQuorum`

若存在以下任一机制可降低优先级：
- `ValidateBasic()` 包含 `VerifySignatures()` 调用
- `ante.NewSigVerificationDecorator()` 在消息处理前拦截
- 通道绑定限制（`OnChanOpenInit` 中白名单检查）

## Classify

**漏洞确认条件**（同时满足）：
- 外部数据直接影响链上状态（价格、余额、权限等关键字段）
- 缺少密码学签名验证或签名可被绕过
- 攻击者可控制 Relayer 或监听/篡改跨链消息

**误报场景**：
- 数据仅用于事件日志记录，不影响共识状态
- 已在上层业务逻辑实现多数据源聚合/中位数计算
- 通道已绑定到经过硬编码的可信客户端（如官方跨链桥）

**代码异味**（需进一步确认）：
- 存在签名字段但验证逻辑位于异步 goroutine 中（可能存在竞态）
- 使用自定义签名方案而非标准库（需评估算法安全性）
- 验证逻辑在错误处理分支中被跳过（conditional bypass）

## Low Risk

以下场景可评估为低风险：

1. **数据非敏感性**：接收的数据仅用于展示或统计，不参与价值转移或权限决策
2. **经济攻击成本高**：需攻击者质押大量代币成为验证者，且单次作恶获利小于质押损失
3. **时效性保护**：数据带有可验证时间戳，且链上存在自动过期机制（如 5 分钟失效）
4. **冗余验证**：虽未验证签名，但通过轻客户端状态证明验证了数据在源链的存在性
5. **沙盒环境**：代码运行在测试网或隔离模块中，与主网资产物理隔离
6. **多重数据源**：同时从 3+ 个独立 Relayer 获取数据并取中位数，单点欺骗无效

**注意**：即使评为低风险，仍建议在审计报告中标注为"待加固点"，因跨链攻击面持续演化。

## 审计专业技巧

### 1. 真实漏洞的确认技巧

**关键信号（必须同时出现）**：
- **数据流追踪**：`packet.GetData()` → `Unmarshal()` → 直接用于状态机转移（如 `SetPrice/SetBalance/UpdateVotes`）
- **签名验证缺失的确认方式**：
  - 搜索同一函数内是否存在 `VerifySignature`、`CheckSig` 等验证函数调用
  - 检查是否有 `if !verified { return err }` 的防护逻辑
  - 追踪 `ValidateBasic()` 实现，确认其内部是否真正执行签名检查

**实战案例**：
```go
// 真实漏洞：Cosmos Hub 跨链价格漏洞（2023年）
func (k Keeper) OnRecvPacket(ctx sdk.Context, packet channeltypes.Packet) error {
    var priceUpdate PriceData
    json.Unmarshal(packet.Data, &priceUpdate)
    // 关键：无任何签名验证直接更新价格
    k.SetAssetPrice(ctx, priceUpdate.Asset, priceUpdate.Price)
    // 后果：任何中继器都可任意修改链上资产价格
    return nil
}
```

### 2. 误报场景识别技巧

**须排除的假阳性**：

1. **签名延迟验证模式**：
   - 如果函数只是解码并入队，真正的验证在 `ProcessQueue` 中
   - 需沿调用链往下追踪是否最终都验证过
   ```go
   // 非漏洞：延迟验证
   func OnRecvPacket(...) {
       queue.Push(data)  // 只是入队
   }
   func ProcessQueue() {  // 异步或后续处理
       for item := range queue {
           if !VerifySignature(item) { continue }
           ApplyState(item)
       }
   }
   ```

2. **轻客户端已验证的情况**：
   - 检查 `OnRecvPacket` 前是否有 `VerifyIBCPacketProof()` 的隐式验证
   - IBC 协议本身通过 Tendermint 轻客户端验证数据来源链的合法性
   - 如果信任的是 IBC 框架本身的验证，不需要二次签名

3. **业务层聚合防护**：
   - 单个 Oracle 无签名 ≠ 漏洞，如果系统从 5+ 个无关源取数据做中位数
   - 检查 `GetAssetPrice()` 调用是否调用了 `AggregateFromMultipleSources()`
   - 确认是否有 `require(sources.length >= MinRequired)` 的强制要求

### 3. 审计工具链与技巧

**第一步：环境分析**
```bash
# 搜索所有 IBC 回调函数
grep -r "OnRecvPacket\|OnAcknowledgementPacket" --include="*.go"

# 追踪调用者：谁调用这些函数？
grep -r "OnRecvPacket" --include="*.go" -B 3 -A 10 | grep -E "func|call"
```

**第二步：数据流分析**
- 在 `OnRecvPacket` 中标记 `packet` 为"未验证源"
- 追踪其数据如何流向：入参 → 局部变量 → 状态变更
- 使用编辑器符号跳转追踪 `SetPrice` 等函数的实现

**第三步：防护验证**
- 检查 `ValidateBasic()` 是否在消息处理前执行（通过 `ante.Handler` 链）
- 对每个签名验证函数，追踪其 `pubkey` 来源：是否从可信配置/治理读取

### 4. 常见变体识别

**变体1：隐蔽的权限绕过**
```go
// 表面看有验证，实际形同虚设
func OnRecvPacket(...) {
    data := new(OracleData)
    json.Unmarshal(packet.Data, data)

    if data.Signature != "" {  // 看起来有验证
        // 但验证函数永远返回 true
        if !AlwaysTrueValidate(data.Signature) {  // 此函数有bug
            return err
        }
    }
    k.SetState(ctx, data)
}
```
→ 审计重点：检查验证函数的具体实现

**变体2：时间戳绕过**
```go
// 有时间戳但缺少防重放
func OnRecvPacket(...) {
    json.Unmarshal(packet.Data, &data)
    if data.Timestamp > now { return err }  // 只验证了时间范围
    k.SetPrice(ctx, data.Price)  // 但没有记录已处理的 Timestamp+Data 组合
}
// 攻击：重复发送相同数据包的旧版本
```
→ 审计重点：检查 `nonce` 或 `processed_hash` 机制是否存在

### 5. 漏洞与误报的判定决策树

```
是否存在 IBC 跨链数据接收？
├─ 否 → 无关，排除
└─ 是
    ├─ 数据是否直接用于状态更新（价格、余额、投票权）？
    │  ├─ 否（仅用于日志/统计） → Low Risk 或 Info
    │  └─ 是
    │     ├─ 是否存在签名验证逻辑？
    │     │  ├─ 是 → 检查验证是否可被绕过（goto 变体识别）
    │     │  └─ 否
    │     │     ├─ 是否通过 IBC 轻客户端已验证？
    │     │     │  ├─ 是 → Low Risk（信任 IBC 框架）
    │     │     │  └─ 否 → Critical/High（无验证）
    │     │     └─ 是否来自多个独立数据源（≥3）并做聚合？
    │        ├─ 是 → Medium（单点攻击风险降低）
    │        └─ 否 → Critical
```

### 6. 审计报告编写建议

**必须明确的信息**：
1. **数据流图**：用 `packet → Unmarshal → State` 清晰标注
2. **验证缺陷描述**：具体说明缺少哪种验证（签名/时间戳/nonce）
3. **攻击路径**：谁可以注入数据、投入成本多少、获利多少
4. **误报排除理由**：如果判定为 Low Risk，明确说明为什么该风险可接受

**示例结构**：
```
[漏洞] Unsigned IBC Oracle Data
= 数据流 =
    Relayer → IBC Packet → OnRecvPacket → SetAssetPrice (无验证)
= 验证缺陷 =
    缺少: 签名验证、中继器白名单检查
= 可信度评估 =
    IBC 框架已验证包来源链合法性，但未验证数据内容本身
= 风险等级 = Critical (资产价格可任意操纵)
```
