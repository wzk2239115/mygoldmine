# Go_MissingPubkeyToAddressBinding

**漏洞类型**：公钥与地址绑定缺失  
**影响场景**：跨链中继器、预言机签名聚合、链下签名校验服务、轻节点验证

## Details

**代码示例特征**：
```go
// 典型漏洞模式：仅验证签名有效性，未绑定公钥与地址
func VerifySignature(message []byte, signature []byte, expectedAddr string) bool {
    pubkey, _ := crypto.Ecrecover(message, signature)  // 从签名恢复公钥
    return crypto.VerifySignature(pubkey, message, signature[:64])  // ❌ 仅验证签名数学正确性
}

// 攻击场景：攻击者用自己的私钥对消息签名，只要签名数学上有效即可通过
```

**快速定位核心操作**（审计等级：**L2-跳读**）：
- 关键函数：`crypto.Ecrecover()`、`secp256k1.RecoverPubkey()`、`VerifySignature()`
- 定位模式：搜索签名验证逻辑 → 检查是否存在 `Ecrecover/RecoverPubkey` → 确认恢复的公钥后续处理
- 核心判断：恢复公钥后是否调用 `PubkeyToAddress()` 或 `crypto.PubkeyToAddress()` 进行地址验证

**快速定位保护机制**（审计等级：**L3-逐行读**）：
- 检查项：`PubkeyToAddress(pubkey) == expectedAddr` 或 `bytes.Equal(addr[:], expectedAddr[:])`
- 保护缺失特征：
  - 恢复公钥后直接返回true/nil
  - 仅检查 `err == nil` 不比对地址
  - 公钥存储在链上但验证时未读取比对
  - 多签场景中仅统计有效签名数量，不验证签名者身份
- 跨模块追踪（**L4**）：验证函数被调用处是否在上层补充了地址校验

## Classify

**漏洞判定标准**：
- 恢复公钥后**无任何地址比对逻辑** → 确定漏洞
- 地址比对存在但使用**错误的公钥源**（如用户输入而非链上存储） → 确定漏洞
- 多签聚合中**未建立签名者白名单索引** → 确定漏洞

**误报场景**：
- 上层调用已完成地址验证，当前函数仅负责签名数学校验（需通过**L4级跨模块追踪**确认）
- 使用BLS或Schnorr聚合签名且已通过聚合公钥验证（需确认聚合密钥管理安全）

**代码异味**：
- 地址比对存在但依赖外部参数传入而非可信存储（降低可信根）
- 验证逻辑分散在多个函数间，职责不清晰

## Low risk

**低风险情况**：
- 验证失败后仅影响**只读查询**，不涉及状态变更或资金操作
- 签名消息本身已包含发送者地址且通过**独立可信渠道**（如链上事件）获取
- 验证用于**审计日志或统计**，业务逻辑另有权限控制
- **测试/模拟环境**代码且有明确注释说明
- 签名验证失败的容错代价低于实施攻击成本（如Faucet类服务且有速率限制）

**注意**：跨链桥、资产托管、权限控制类场景**不应降级**，即使存在额外防护层

## Audit Techniques & Differentiation

### 真实漏洞的审计特征

**1. 链上存储与链下验证不匹配（致命漏洞）**
```go
// ❌ 真实漏洞：未绑定链上存储的公钥
type Guardian struct {
    Address   string // 链上存储的权限地址
    PublicKey string // 链上存储的公钥（用于验证）
}

func ValidateGuardianAction(msg []byte, sig []byte, signer string) error {
    guardian := getGuardianFromChain(signer)

    // 错误实现：恢复公钥但直接信任，未与guardian.PublicKey比对
    recoveredPubkey, _ := crypto.Ecrecover(msg, sig)
    if recoveredPubkey == nil {
        return errors.New("invalid signature")
    }
    // ❌ 缺失关键步骤：应该验证 recoveredPubkey == guardian.PublicKey
    return nil
}
```
**审计标志**：`getGuardianFromChain()` 返回存储的公钥，但验证逻辑未读取该值进行比对

**2. 多签场景中的身份验证缺失（中等风险）**
```go
// ❌ 真实漏洞：统计签名数量但不验证签名者身份
func VerifyMultiSig(msg []byte, sigs [][]byte, requiredCount int) bool {
    validCount := 0
    for _, sig := range sigs {
        pubkey, err := crypto.Ecrecover(msg, sig)
        if err == nil && len(pubkey) > 0 {
            validCount++  // ❌ 仅计数，未检查pubkey是否在allowed list中
        }
    }
    return validCount >= requiredCount
}
```
**攻击链**：攻击者使用自己的私钥对消息签名，只要提交足够多的有效签名，即可伪造多签权限

**3. 跨链中继器中的公钥同步问题（高风险）**
```go
// ❌ 真实漏洞：验证器集合未与主链同步
func VerifyValidatorSignature(msg []byte, sig []byte) bool {
    pubkey, _ := crypto.Ecrecover(msg, sig)

    // ❌ 危险：使用本地缓存的验证器列表，可能与主链不同步
    return isInValidatorSet(pubkey)  // 缓存可能过期
}
```
**审计标志**：搜索验证器集合的更新时间 → 检查同步间隔 → 确认是否存在延迟利用风险

### 常见误报场景与区分方法

**误报1：分层验证设计（非漏洞）**
```go
// ✅ 正确设计：分离职责，上层完成地址绑定
func CryptoVerifySignature(msg []byte, sig []byte) ([]byte, error) {
    // L1：纯密码学验证，无地址绑定
    pubkey, err := crypto.Ecrecover(msg, sig)
    return pubkey, err
}

func VerifyTransactionSignature(tx *Transaction) error {
    // L2：业务层验证，绑定发送者地址
    pubkey, err := CryptoVerifySignature(tx.Data, tx.Signature)
    if err != nil {
        return err
    }

    addr := crypto.PubkeyToAddress(pubkey)
    if addr != tx.From {
        return errors.New("signature mismatch")
    }
    return nil
}
```
**区分方法**：
- 搜索低层函数的所有调用点（**L4级追踪**）
- 确认每个调用处上游是否都有地址比对逻辑
- 检查调用链是否存在"绕过"路径（如直接调用底层函数）

**误报2：BLS聚合签名的正确实现（非漏洞）**
```go
// ✅ 正确的BLS签名验证：聚合公钥处理本质不同
func VerifyBLSAggregate(msgs [][]byte, aggregatedPubkey *bls.PublicKey) bool {
    // BLS的设计特性：聚合后验证等价于逐个验证
    // 无需逐个恢复公钥，聚合密钥本身代表验证者集合
    return bls.VerifyAggregate(aggregatedPubkey, msgs)
}
```
**区分方法**：
- 确认使用的是否为BLS/Schnorr等支持聚合的签名方案（非ECDSA）
- 检查聚合公钥的来源：是否从可信预言机或链上合约获取
- 审计聚合密钥注册机制是否防止了假冒者注册

**误报3：只读操作中的宽松验证（低风险）**
```go
// ⚠️ 有风险但可接受：查询操作的可选签名验证
func QueryBalance(addr string, sig *OptionalSignature) uint64 {
    if sig != nil {
        pubkey, _ := crypto.Ecrecover(queryData, sig)
        // ⚠️ 仅用于审计日志，不影响余额返回
        logQuery(pubkey, addr)  // 记录查询来源
    }
    return getBalance(addr)  // 返回逻辑独立，不依赖签名验证
}
```
**区分方法**：
- 确认验证失败是否影响返回结果
- 检查操作是否涉及状态变更或资金转移
- 若仅用于日志/监控，可标记为低风险但需注明原因

### 现场审计的三阶段判定流程

**第一阶段（快速筛查，5分钟）**：
1. 搜索 `Ecrecover|RecoverPubkey` 的所有出现
2. 对每个出现检查后续5行代码
3. 若看到 `==|Equal|bytes.Compare` 与地址/公钥比对 → 继续深化
4. 否则 → 标记为潜在漏洞，进入第二阶段

**第二阶段（确认漏洞，15分钟）**：
1. 追踪恢复的公钥是否被传递到其他函数
2. 跨模块搜索该公钥的使用方式
3. 检查是否存在"代理验证"模式（A函数验证，B函数使用结果）
4. 验证所有调用路径是否都包含地址绑定

**第三阶段（评估风险，10分钟）**：
1. 分析操作场景（状态变更 vs 只读查询）
2. 检查是否存在其他防护层（速率限制、权限控制）
3. 评估攻击成本 vs 收益
4. 最终判定：确定漏洞 / 低风险 / 误报

### 实战案例对比

| 场景 | 代码特征 | 判定 | 关键证据 |
|------|--------|------|--------|
| 跨链桥接收器 | 恢复公钥 + 直接返回 | 确定漏洞 | 无地址比对，资金转移 |
| ERC-191签名验证 | 恢复公钥 + 上层比对 | 非漏洞 | L4追踪显示调用链完整 |
| 链下API服务 | 签名恢复用于日志 | 低风险 | 无状态变更，速率限制存在 |
| 多签投票 | 统计有效签名 | 确定漏洞 | 未检查签名者白名单 |
| BLS预言机 | 聚合公钥验证 | 非漏洞 | 聚合密钥注册安全 |
