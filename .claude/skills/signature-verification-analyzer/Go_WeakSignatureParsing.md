# Go_WeakSignatureParsing - 弱签名解析

**场景：** Go 链下服务、跨链中继器、预言机签名聚合、轻节点验证  
**成因：** 使用不安全的签名解析库或自实现，未严格校验签名格式/长度/边界，可被恶意构造的签名绕过验证

## Details

### 典型代码示例

```go
// 危险：直接解析未验证格式
func VerifySignature(pubkey, message, sig []byte) bool {
    r := new(big.Int).SetBytes(sig[:32])  // 未校验长度
    s := new(big.Int).SetBytes(sig[32:64])
    // 未检查 r,s 是否在有效范围 [1, n-1]
    // 未检查 s 值是否为低位（可延展性攻击）
    return ecdsa.Verify(pub, hash, r, s)
}

// 危险：使用非常量时间比较
func CompareSignature(sig1, sig2 []byte) bool {
    return bytes.Equal(sig1, sig2)  // 时序攻击风险
}

// 危险：ASN.1 DER 解析未校验
func ParseDERSignature(der []byte) (*big.Int, *big.Int) {
    // 直接解析，未验证：sequence 标记、长度字段、前导零、整数编码
    return asn1.Unmarshal(der, &ecdsaSignature{})
}
```

### 快速定位核心操作技巧（L3-逐行读）

**关键函数模式：**
- `ecdsa.Verify` / `ed25519.Verify` / `secp256k1.VerifySignature`
- `SetBytes()` 处理签名分量 r/s
- `asn1.Unmarshal` / `derSignature.Parse`
- 自定义 `ParseSignature` / `DecodeSignature`

**检查清单：**
1. 签名长度是否硬编码校验（如 ECDSA 65字节、Ed25519 64字节）
2. r/s 分量是否检查范围 `0 < r,s < curve.N`
3. 是否规范化 s 值防止延展性（`s > N/2` 需转换为 `N-s`）
4. ASN.1 DER 解析是否使用 `btcec.ParseDERSignature` 等安全库
5. 是否存在前导零截断或填充不一致问题

### 快速定位保护机制技巧（L2-跳读）

**寻找验证逻辑：**
- `if len(sig) != ExpectedLen` 长度检查
- `if r.Cmp(curve.Params().N) >= 0` 范围验证
- `if s.Cmp(halfOrder) > 0` 延展性保护
- `crypto.SignatureLength` 常量定义
- 使用成熟库：`github.com/btcsuite/btcd/btcec`, `go-ethereum/crypto`

**保护缺失风险：**
- 若无上述检查，标记 **HIGH**
- 若依赖外部输入确定长度，标记 **CRITICAL**
- 若时间敏感操作未用 `subtle.ConstantTimeCompare`，标记 **MEDIUM**

## Classify

### 漏洞（HIGH/CRITICAL）
- 签名长度/格式完全不校验，攻击者可构造任意长度数据触发越界/panic
- r/s 值未限制在曲线阶内，可构造无效签名绕过验证
- 未规范化 s 值，同一签名存在多种有效形式（交易重放风险）
- DER 解析接受非规范编码（过长整数、冗余零、错误 tag）

### 误报
- 使用 `go-ethereum/crypto.VerifySignature` 等已内置全部检查的成熟库
- 签名来自可信环节（如本地密钥签名后直接验证，无外部输入）
- 已在上层业务逻辑强制限制签名来源（如白名单公钥）

### 代码异味（建议重构）
- 自实现签名解析但逻辑分散在多个函数，可读性差
- 硬编码魔数（如 32/64）未用常量定义
- 错误处理不明确（返回 false 无日志，无法溯源失败原因）

## Low risk

- **仅内部调试环境使用**：未部署到生产，且输入受严格访问控制
- **已有上游强校验**：调用方已通过区块链节点 RPC 预验证签名，此处为二次检查
- **非关键路径**：签名验证失败仅影响日志记录或监控统计，不涉及资金/权限决策
- **降级场景**：仅在主验证方式不可用时作为 fallback，且有速率限制+人工审核
- **EIP-2/BIP-66 之前的历史兼容**：明确注释说明需兼容非规范签名的历史区块，且有版本隔离
