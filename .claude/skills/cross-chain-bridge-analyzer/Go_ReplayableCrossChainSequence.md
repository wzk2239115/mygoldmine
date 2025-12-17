# 可重放跨链序列号 (Replayable Cross-Chain Sequence)

**Go**  
常出现在链下中继服务、跨链监听器或桥接守护进程（bridge daemon）的实现中。跨链消息序列号未正确跟踪或校验，允许攻击者重放已处理的消息，导致资金重复提取或状态重复变更。

## Details

**代码示例特征：**
```go
// 典型漏洞模式：直接处理消息无nonce/sequence校验
func (r *Relayer) ProcessCrossChainMsg(msg CrossChainMessage) error {
    // 缺少已处理消息检查
    return r.ExecuteOnTarget(msg.Payload)
}

// 或仅检查签名不检查序列号
func (b *Bridge) RelayMessage(msg Message, sig []byte) error {
    if !VerifySignature(msg, sig) { return ErrInvalidSig }
    // 缺少 msg.Nonce/Sequence 的唯一性校验
    return b.mint(msg.Recipient, msg.Amount)
}
```

**快速定位核心操作技巧（L3: 逐行读）：**
- 搜索消息处理入口：`Process.*Message`、`Relay.*`、`Handle.*Event`、`ExecuteCrossChain`
- 追踪资金/状态变更操作：`mint`、`transfer`、`updateState`、`Execute`
- 检查是否存在状态写入但缺少序列号递增：看是否有 `nonce++`、`lastSequence = msg.Sequence`
- 观察存储层：map/数据库是否记录 `processedMessages[msgHash]`、`usedNonces[sender][nonce]`

**快速定位保护机制技巧（L2: 跳读）：**
- 扫描消息ID唯一性检查：`if processed[msgID]`、`if usedNonces[nonce]`、`if sequence <= lastSequence`
- 查找持久化存储：`db.Set("processed:"+hash)`、`processedMap[hash] = true`
- 确认序列号严格递增：`require(msg.Sequence == expected+1)`、`if sequence != last+1 { revert }`
- 检查消息哈希存储：`keccak256(abi.encode(...))`、`sha256(msg.Bytes())`
- 审计等级判定：若无任何上述检查机制 → 严重漏洞；若有检查但可绕过（如仅内存存储重启后清空）→ 中危

## Classify

**漏洞判定：**
- 消息可被重复执行且产生实际状态变更（资金转移/权限授予/数据篡改）
- 序列号检查缺失、不完整或可被绕过（如检查后存储前存在race condition）
- 已处理消息标记存储在非持久化介质（内存/临时缓存），重启后失效

**误报判定：**
- 消息幂等性设计：重复执行无副作用（如查询操作、只读调用）
- 上层智能合约已实现nonce机制，中继层无需重复校验
- 消息本身包含时间戳且有严格过期检查，过期消息无法执行

**代码异味：**
- 序列号检查存在但未持久化到磁盘/链上，存在数据丢失风险
- 仅依赖内存map而非数据库或链上状态存储
- 分布式中继节点间未同步已处理消息状态

## Low risk

**以下场景可评估为低风险：**
- 消息处理有金额上限/频率限制，单次重放损失可控且有监控告警
- 重放需要高额Gas费用或抵押品，经济上不可行
- 测试网或仅内部使用的桥接服务，无实际资产风险
- 中继服务采用多签或阈值签名方案，需要m/n个节点同时配合才能重放（但注意这不能完全消除风险）
- 跨链消息仅传递非关键数据（如链下索引、日志同步），不涉及资产或权限操作
- 已有外部监控系统可实时检测并自动阻断异常重放行为

## 审计专业技巧与经验

### 深度审计检查清单

**存储层持久化分析：**
- 追踪已处理消息的存储位置：是否持久化到 `RocksDB`/`BadgerDB`/数据库而非仅内存
- 检查存储的数据结构是否能在节点重启后恢复：查看初始化代码 `InitDB()`、`LoadCheckpoint()`
- 验证存储写入是否在消息执行前（预检）还是执行后（事后补救），前者更安全
- 追踪分布式中继场景中，多个节点间是否通过共享存储（Redis/Etcd）或链上状态同步

**消息去重的完整性检查：**
```go
// 正确模式：执行前检查，执行后立即标记
func (r *Relayer) Process(msg Message) error {
    hash := Hash(msg)
    if r.storage.Exists(fmt.Sprintf("processed:%s", hash)) {
        return ErrAlreadyProcessed
    }

    // 原子操作：先标记后执行
    if err := r.storage.Set(fmt.Sprintf("processed:%s", hash), true); err != nil {
        return err
    }
    return r.Execute(msg)
}

// 反面模式：执行后标记（存在时间窗口漏洞）
func (r *Relayer) ProcessUnsafe(msg Message) error {
    if err := r.Execute(msg); err != nil { return err }
    r.storage.Set(fmt.Sprintf("processed:%s", hash), true)  // 执行成功但崩溃会导致重放
}
```

**序列号严格递增验证：**
- 检查序列号是否允许并发跳过（gap）：若 `lastSeq=5, incoming=8`，是否接受？应当拒绝
- 确认序列号检查在链上逻辑层面是否有效：跨链桥接合约是否重复校验？（避免假安全感）
- 审查序列号的存储与更新是否为原子操作，防止竞态条件导致的乱序处理

### 真实漏洞案例与识别

**案例1：Poly Network 跨链漏洞（2021）**
- 问题：中继层未严格校验Ethereum/EOS上的合约调用序列号，攻击者可重放跨链转账
- 识别信号：搜索消息处理函数中缺少 `processedMessages[msgHash]` 的初始化或查询逻辑
- 修复验证：确认是否补加了 `require(!processed[msgHash]); processed[msgHash] = true;`

**案例2：Horizon Bridge 重放漏洞（2022）**
- 问题：多链中继在单个节点实现了去重，但多节点环境中未通过共享状态同步，导致不同节点重复处理同一消息
- 识别信号：在分布式中继环境中，去重状态仅存储在本地内存或单个节点数据库
- 修复验证：检查是否使用了 Consensus、Raft、中心化队列（Kafka）等机制确保全局状态一致性

**案例3：LayerZero omnichain 的假false positives**
- 问题：开发者误以为上层应用合约的nonce机制能覆盖中继层重放风险，未额外校验
- 识别信号：中继层完全缺少nonce/sequence检查，但代码注释说"依赖应用层nonce"
- 误报原因：若应用层合约确实对每笔交易进行了严格的nonce递增检查，中继层冗余校验不是必须但强烈推荐

### 误报与真漏洞的区分经验

**容易被误报为漏洞的模式：**

1. **内存消息缓存未持久化** → 需检查是否是临时缓存还是去重机制
   - 若仅用于同一轮处理中的去重，且处理完后持久化到链上，则非漏洞
   - 若用于跨节点去重且无其他持久化机制，则是真漏洞

2. **序列号检查在业务逻辑后** → 审查是否存在早期return导致部分状态修改
   - 若检查在所有修改前进行，只是代码位置不优美，非漏洞
   - 若检查后仍有状态修改且检查可被绕过（如条件逻辑错误），则是漏洞

3. **去重依赖签名校验** → 审查签名是否包含nonce字段
   - 若签名包含完整的nonce+payload，且签名验证通过，重放会失败（不是漏洞）
   - 若签名仅覆盖payload部分，nonce在签名外，则可能被重放（是漏洞）

**识别真漏洞的关键信号：**
- 状态变更函数（`mint`, `transfer`, `burn`）前无条件检查已处理消息ID或nonce
- 分布式场景中，去重状态仅存储在易丧失的介质（内存/本地文件），无中心化同步
- 序列号检查存在但可被条件逻辑绕过（如多条件判断中一条失效）
- 已处理消息记录存在时间有效期但未在链上永久记录（重启后可再次处理）

### 实践审计建议

**第一阶段：静态分析**
- Grep关键字：`ProcessCrossChain`, `Relay`, `ExecuteMsg`, `processedMessages`, `usedNonces`
- 绘制消息流向图：从网络接收 → 签名校验 → 去重检查 → 状态修改 → 持久化
- 识别所有状态修改点，确认每个点前都有去重机制

**第二阶段：存储分析**
- 确认去重数据的存储后端：数据库类型、持久化策略、备份机制
- 模拟节点重启，验证已处理消息记录是否可恢复
- 在多节点环境中检查状态同步机制

**第三阶段：并发场景模拟**
- 构造同时提交重复消息的测试用例
- 验证 race condition 下是否存在短暂的处理窗口
- 检查atomic操作或锁机制是否覆盖了检查+执行的整个过程

**第四阶段：链上确认**
- 若跨链涉及目标链智能合约，确认合约层是否有二次校验
- 审查目标合约中消息数据的使用方式，是否包含nonce或其他去重标识
- 确认链上状态最终一致性，防止底层重组导致的消息重复执行
