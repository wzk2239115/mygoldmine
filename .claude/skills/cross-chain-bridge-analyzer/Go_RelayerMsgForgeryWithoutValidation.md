# Go - 中继器消息伪造无验证

**漏洞类型**：跨链桥接安全  
**影响范围**：链下中继服务、跨链监听器、桥接守护进程（bridge daemon）  
**核心风险**：中继器转发跨链消息前未验证其真实性，允许注入虚假消息，导致资产损失或状态篡改

## Details

**代码示例特征**：
```go
// 危险模式：直接转发无验证
func (r *Relayer) ProcessMessage(msg *BridgeMessage) {
    // 缺少签名验证
    // 缺少源链事件验证
    // 缺少序列号防重放
    r.TargetChain.SubmitMessage(msg)
}
```

**快速定位核心操作**（L3-逐行读）：
- 关注函数名：`Process*`, `Relay*`, `Forward*`, `Submit*`, `Bridge*`
- 定位消息接收点：监听源链事件的`EventHandler`, `OnMessage`, `HandleEvent`
- 追踪消息流转：从接收 → 处理 → 转发的完整链路
- 检查序列号管理：`nonce`, `sequence`, `messageId`的获取与使用

**快速定位保护机制**（L4-跨模块追踪）：
- 签名验证：搜索`VerifySignature`, `ecrecover`, `crypto.Verify`, `ValidateProof`
- 源链验证：查找`VerifyReceipt`, `GetTransactionReceipt`, `ConfirmBlock`
- 防重放机制：检查`processedNonces`, `executedMessages`, `messageStatus`映射表
- 多签机制：定位`threshold`, `quorum`, `requiredSigners`, `MultiSigValidate`
- 超时机制：寻找`expiry`, `deadline`, `timeout`字段及其校验逻辑

## Classify

**漏洞判定**：
- 消息签名完全缺失或仅验证格式不验证签名者身份
- 源链事件未通过RPC确认真实性，仅依赖监听的事件日志
- 序列号/nonce可被攻击者控制或未与已处理列表比对
- 多签阈值可被绕过或签名者集合未与白名单校验
- 时间戳/过期时间字段存在但未实际校验

**误报识别**：
- 该中继器仅用于测试环境且有明确注释说明
- 消息验证逻辑在调用链的上游已完成（需跨模块确认）
- 使用成熟的跨链协议SDK且版本无已知漏洞（如IBC、LayerZero）

**代码异味**：
- 验证逻辑存在但可通过特殊路径绕过
- 使用自定义密码学实现而非标准库
- 错误处理仅记录日志但仍继续执行
- 验证失败后有重试逻辑且无次数限制

## Audit Techniques（审计专业技巧）

**第一步：追踪消息完整生命周期**
```go
// 检查点清单：
// 1. 消息入口点 - 谁可以调用 ProcessMessage()?
// 2. 签名数据来源 - signature 字段如何填充？自生成还是外部提供？
// 3. 验证主体 - VerifySignature() 是否真的校验了 msg 内容的哈希？
// 4. 验证结果处理 - 验证失败是否真的阻止了后续操作？
// 5. 链下存储状态 - processedMessages 在哪里更新？可否被篡改？
```

**第二步：区分真实漏洞 vs 误报**

| 特征 | 真实漏洞 | 常见误报 |
|-----|--------|--------|
| **签名验证缺失** | VerifySignature() 根本不存在或被注释掉；参数传入错误导致校验失效 | 验证逻辑在父类/接口中实现；通过依赖注入的中间件处理 |
| **源链确认** | 仅监听事件日志，未通过 RPC GetTransactionReceipt() 二次确认 | 使用成熟SDK（IBC、LayerZero）的内置确认机制 |
| **重放保护** | nonce/sequence 字段存在但未与 processedMessages 比对；只验证格式不验证值 | nonce 通过智能合约锁定递增；使用不可重放的消息哈希 |
| **多签绕过** | threshold = 1 或签名集合可为空；{}/nil 判断缺失 | 签名者通过多链治理合约动态管理；有可信的更新机制 |

**第三步：钓鱼式代码审计**

```go
// 反面教材 1：看似有验证但实际无效
func (r *Relayer) ProcessMessage(msg *BridgeMessage) error {
    // 陷阱：只验证签名格式，不验证签名值
    if msg.Signature == "" {
        return errors.New("missing signature")
    }
    // ❌ 危险：没有调用 VerifySignature()！
    r.TargetChain.SubmitMessage(msg)
    return nil
}

// 反面教材 2：验证逻辑存在但可被绕过
func (r *Relayer) ProcessMessage(msg *BridgeMessage) error {
    // 陷阱：验证结果被忽略
    _ = r.VerifySignature(msg)
    // ❌ 继续执行，验证形同虚设
    r.TargetChain.SubmitMessage(msg)
    return nil
}

// 反面教材 3：重放防护失效
func (r *Relayer) ProcessMessage(msg *BridgeMessage) error {
    // 陷阱：nonce 检查有漏洞
    if r.processedNonces[msg.Nonce] {
        return errors.New("already processed")
    }
    // ❌ 问题：processedNonces 是本地内存，重启后清空
    // ❌ 问题：没有持久化到数据库或链上
    r.processedNonces[msg.Nonce] = true
    r.TargetChain.SubmitMessage(msg)
    return nil
}
```

**第四步：区分真假的关键问题**

| 问题 | 如何验证 | 陷阱 |
|-----|---------|------|
| 验证失败是否阻止提交？ | 搜索 if !verify { return } 的模式；检查 error 处理 | error 被记录但执行继续；或只在特定路径检查 |
| nonce/sequence 来自哪里？ | 跟踪值的来源：消息本身 vs 链下状态 vs 链上合约 | 如果来自消息本身且无防重放，可伪造 |
| 签名者身份如何确认？ | 找 ecrecover/SignerAddress 的调用；比对 signers 映射表 | 只验证签名格式；signers 列表未与主链同步 |
| 何时更新已处理列表？ | 应在验证成功+提交前更新 | 在提交后异步更新；或未更新 |

**第五步：常见的隐蔽漏洞模式**

1. **签名回源攻击**：验证代码存在但签名使用 msg.Sender 而非调用者身份
2. **并发竞态**：验证与状态更新间的 TOCTOU 漏洞（检查后使用）
3. **版本混淆**：新旧消息格式并存，验证逻辑仅作用于新格式
4. **超时失效**：expiry 字段存在但未实际校验；或校验逻辑在 msg.Timestamp（攻击者控制）而非 block.timestamp
5. **回退路径**：主验证路径严格，但存在 AdminProcessMessage() 等管理员路径绕过

**第六步：实战经验——5个真实漏洞案例识别**

1. **Poly Network（2021）**：源链验证缺失，攻击者直接调用 putCurEpochConsPubKeyBytes() 修改验证者集合
   - 识别特征：跨链消息处理函数无权限检查且直接修改核心参数

2. **Ronin（2022）**：5/9 多签中有 4 个签名者私钥泄露，但代码本身支持多签
   - 识别特征：多签逻辑正确，但签名者管理/更新流程未审计

3. **Nomad（2022）**：xDomainMessageSender 未真正与跨链消息绑定
   - 识别特征：状态变量用于验证但在消息处理前被攻击者修改（TOCTOU）

4. **Wormhole（2022）**：序列号校验缺失，VAA 可被重放
   - 识别特征：哈希值验证存在，但 VAA 本身无序列号且无 nonce 映射表

5. **Bridge Exploit at Binance（2021）**：中继器假设源链事件必然真实，未通过 RPC 确认
   - 识别特征：仅依赖事件监听，未调用 eth_getTransactionByHash() 二次确认

## Low risk

**降级为低风险的场景**：
- 中继器仅转发公开数据且不涉及资产操作或状态变更
- 目标链合约侧已实现完整的二次验证（需审计目标合约确认）
- 消息仅用于触发链下索引或通知，不影响链上状态
- 系统架构中该中继器仅作为备份节点，主验证由其他模块完成
- 验证逻辑缺失但消息来源受可信执行环境（TEE）保护
- 跨链消息价值上限受严格限制且有熔断机制
