# Solidity_MissingChainIdCheck

**漏洞类型**：签名验证 - 缺失 ChainId 检查  
**风险等级**：High / Critical  
**影响范围**：授权委托、跨链消息验证、治理投票、许可转账、元交易

## Details

**代码示例**：
```solidity
// 漏洞场景：签名验证未绑定 chainId
function executeWithSignature(address user, uint256 amount, bytes memory signature) external {
    bytes32 hash = keccak256(abi.encodePacked(user, amount)); // ❌ 缺少 chainId
    address signer = recoverSigner(hash, signature);
    require(signer == authorizedSigner, "Invalid signer");
    _transfer(user, amount);
}

// 正常场景：包含 chainId 绑定
bytes32 hash = keccak256(abi.encodePacked(user, amount, block.chainid, nonce));
```

**快速定位核心操作**（审计等级：L2 跳读）：
- 定位所有 `ecrecover` / `ECDSA.recover` / `recoverSigner` 调用点
- 追溯其 hash 参数的构造源头（通常是 `keccak256` / `_hashTypedDataV4`）
- 检查 hash 输入是否包含链相关标识（`block.chainid` / `chainId` / domain separator）

**快速定位保护机制**（审计等级：L3 逐行读）：
- 确认 hash 构造中是否显式包含 `block.chainid`
- 若使用 EIP-712，检查 `DOMAIN_SEPARATOR` 是否正确绑定 chainId 且不可被覆盖
- 若使用自定义结构，验证 chainId 是硬编码还是动态获取（`constructor` 中缓存 chainId 存在分叉风险）
- 排查 `block.chainid` 是否被管理员可修改变量替代

## Classify

**漏洞**：
- 签名 hash 未绑定任何链标识，可直接跨链重放
- EIP-712 的 `DOMAIN_SEPARATOR` 未包含 chainId 或构造错误
- chainId 为可修改的状态变量而非 `block.chainid`

**误报**：
- 合约仅部署于单链且明确注释不考虑多链场景（需评估业务合理性）
- 签名内容包含合约地址，且该地址在目标链上不存在或由不同实体控制（需验证确定性部署风险）
- 签名已通过其他链上下文绑定（如区块哈希、交易哈希），但需极度谨慎评估

**代码异味**：
- 使用 `constructor` 中缓存的 chainId 而非 `block.chainid`（硬分叉后失效）
- EIP-712 实现正确但缺少 chainId 校验的注释说明

## Audit Professional Skills

**真实漏洞识别指标**：
1. **跨链重放可行性评估**（Critical 判定必需）
   - 合约代码中明确检查 `msg.sender` 或 `tx.origin` 是否匹配授权方
   - 如果缺失，攻击者可在 Polygon 签名后直接在 Arbitrum 上重放（需验证签名者权限一致）
   - 实战经验：检查调用链 `executeWithSignature → _transfer → balanceOf`，如果 `_transfer` 内部未做身份再验证，风险升级为 Critical

2. **EIP-712 陷阱识别**
   ```solidity
   // 真实案例 1：DOMAIN_SEPARATOR 在 constructor 中缓存
   bytes32 immutable DOMAIN_SEPARATOR;
   constructor() {
       DOMAIN_SEPARATOR = keccak256(abi.encode(
           keccak256("EIP712Domain(...)"),
           block.chainid,  // ❌ 若链发生硬分叉重组，该值失效
           address(this)
       ));
   }

   // 审计建议：动态计算或在 L2 升级事件中重新验证
   ```

3. **权限边界穿越检查**
   - 审计点：签名验证 → 权限执行的中间过程是否存在 `delegatecall` 或 `call.value`
   - 实例：Approve 操作通过签名授权，但涉及第三方合约调用，可能被重定向
   - 防御验证：确认签名的 `to` 字段或目标合约地址是否在签名内容中

4. **单链特例的业务确认**（误报防线）
   - 代码审计：搜索所有 chain 相关配置（如 `require(block.chainid == 1)`）
   - 文档验证：确认白皮书、部署文档中是否明确声明"单链部署"
   - 风险：仅从代码无法确定，需与 PM / 安全负责人确认，不可仅凭推测标记为 Green

## Distinguish: Real Vulnerability vs. False Positive

**误报常见陷阱**：

| 场景 | 初期判定 | 审计深入 | 最终判定 |
|------|---------|---------|---------|
| 签名缺 chainId，但合约部署地址通过 CREATE2 确定性生成 | 🔴 HIGH | 检查该地址在 L2 / 侧链是否可被重现；若不同实体控制则存在真实风险 | 🟡 MEDIUM（依赖部署策略） |
| EIP-712 未检查 chainId，但使用了 Permit2 / Router 统一管理 | 🔴 HIGH | Permit2 内部是否包含 chainId 校验；若有则为误报 | 🟢 LOW（若下游正确） |
| 签名内含合约地址 + nonce，缺 chainId | 🔴 HIGH | 验证该合约是否可在多链部署；若确定单链则误报 | 🟢 LOW（确认单链）→ 🔴 HIGH（确认多链） |
| 使用 OpenZeppelin ERC712 但未覆盖 domainSeparatorV4 | ⚠️ 需逐行读 | 检查 OZ 版本与 chainId 处理方式；新版已修复 | 🟢 LOW（新版）→ 🔴 HIGH（旧版） |

**实战案例分析**：
- **真实漏洞案例**（2023 年审计）：某跨链桥接合约的 `validateSignature` 未绑定 chainId，攻击者从 Optimism 网络窃取签名后在 Arbitrum 重放，成功冻结用户资产。根本原因：签名内容只包含 `(amount, recipient, nonce)`，无链标识。

- **误报案例**：DAO 治理合约的投票权签名缺少 chainId。深入审查发现：(1) 合约明确部署于 Ethereum 主网；(2) 签名仅用于链下 IPFS 投票计数；(3) 执行时由合约内的管理员多签重新验证。结论：误报，但建议添加注释防止未来维护风险。

## Low risk

- 签名仅用于链下验证或事件日志，不触发状态变更或资产操作
- 签名消息已通过 nonce + 短时效时间戳组合，且目标链上该签名者不具备相同权限
- 合约明确设计为多链共享签名池（如跨链桥接收签名），且下游有独立的链标识校验
- 测试合约或示例代码，非生产环境部署
- 使用经审计的第三方库（如 OpenZeppelin 5.0+）且其 DOMAIN_SEPARATOR 实现已验证正确

## Auditor's Practical Checklist

**快速评估清单**（5分钟预检）：
```
□ 搜索 ecrecover / ECDSA.recover 调用 → 追溯 hash 来源
□ 检查 keccak256 输入参数：是否包含 block.chainid / domainSeparator
□ 若使用 EIP-712：验证 DOMAIN_SEPARATOR 动态性与 chainId 绑定
□ 确认部署链数量（单链 vs 多链）→ 查看部署脚本 / 部署地址记录
□ 检查签名权限作用域：是否限于特定合约地址 + 具体操作
```

**深度审计关键点**（审计等级 L1）：
1. **跨域签名滥用风险**
   - 关键词搜索：`bytes32 hash = keccak256` 或 `_hashTypedDataV4`
   - 验证 hash 输入不仅包含 chainId，还需包含 `address(this)` 防止合约地址冲突
   - 案例：Uniswap Permit 若缺少地址校验，可能在 Wrapped Token 合约间造成重放

2. **时间戳漏洞**（常被忽视的深层问题）
   - 若签名包含时间戳但未校验 `block.timestamp > deadline`，攻击者可长期囤积签名
   - 实例：Balancer 元交易曾存在此漏洞，允许交易在数月后执行

3. **Nonce 机制失效**
   - 检查 nonce 是否递增：`require(nonce == expectedNonce); expectedNonce++;`
   - 若 nonce 是映射而非递增，可能导致重复消费（如 `mapping(address => bool) used[nonce]`）

**常见误报的破除方法**：
- **"单链合约不需要 chainId"**：虽然逻辑上成立，但规范要求仍应包含链标识，防止未来升级为多链时遗漏
- **"签名内容包含合约地址就足够"**：不足。攻击者可部署完全相同的合约副本在其他链，除非地址通过 CREATE2 确定性生成且跨链不可重现
- **"大规模项目的库实现必然正确"**：OpenZeppelin 早期版本的 DOMAIN_SEPARATOR 在 fork 后失效；Curve 的签名验证曾缺少边界检查

**防御模式验证**：
```solidity
// ✅ 防御模式 1：完整的 EIP-712 实现
function permit(address owner, address spender, uint256 value, uint256 deadline,
                uint8 v, bytes32 r, bytes32 s) external {
    require(block.timestamp <= deadline, "Expired");
    bytes32 hash = _hashTypedDataV4(keccak256(abi.encode(..., owner, spender, value)));
    // domainSeparator 内部已包含 block.chainid（动态计算）
    address signer = ecrecover(hash, v, r, s);
    require(signer == owner, "Invalid signature");
    // ...
}

// ✅ 防御模式 2：显式绑定所有关键参数
bytes32 hash = keccak256(abi.encode(
    PERMIT_TYPEHASH,
    owner,
    spender,
    value,
    nonces[owner]++,  // 防止重放
    deadline,
    block.chainid,    // 链绑定
    address(this)     // 合约绑定
));
```

## Summary for Auditors

审计该漏洞时的核心判断树：
1. 是否存在签名验证逻辑？否 → 无此漏洞
2. 签名 hash 是否包含 block.chainid 或 DOMAIN_SEPARATOR？包含 → 检查动态性；不包含 → 继续
3. 合约是否设计为多链部署？是 → Critical 确认；否 → 检查业务文档
4. 是否使用第三方库（OZ/Permit2）？是 → 验证库版本与实现；否 → 继续
5. 除链标识外，是否包含合约地址 + 用户地址 + nonce？全包含 → 风险降级到 Medium；缺失任一 → 升级到 Critical

