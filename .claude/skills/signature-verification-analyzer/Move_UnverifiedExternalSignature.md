# Move 未验证外部签名漏洞审计指南

**漏洞类型：** 签名验证缺陷  
**适用链：** Aptos、Sui 等 Move 系公链  
**常见场景：** 资源授权、跨账户操作、模块权限控制、委托调用

## Details

**典型代码模式：**
```move
public entry fun transfer_with_signature(
    from: address,
    to: address,
    amount: u64,
    signature: vector<u8>  // 直接接收签名参数但未验证
) {
    // 缺少签名验证逻辑
    coin::transfer<AptosCoin>(from, to, amount);
}
```

**快速定位核心操作技巧（L2-L3）：**
- 扫描所有 `public entry` 或 `public` 函数签名，识别包含 `vector<u8>` 类型的签名参数
- 定位涉及权限操作的关键函数：`transfer`、`mint`、`burn`、`update_config`、`delegate`
- 追踪 `signer` 参数来源，判断是否通过参数传入而非交易验证获得
- 检查函数体内是否存在 `assert!` 或签名校验逻辑

**快速定位保护机制技巧（L3-L4）：**
- 查找 `ed25519::verify` 或 `secp256k1_ecdsa::verify` 等签名验证原语调用
- 检查是否使用 `account::create_signer_with_capability` 等官方认证机制
- 确认 message digest 构造：是否包含 `bcs::to_bytes`、`hash::sha3_256` 等哈希计算
- 验证签名内容绑定性：message 是否包含 `amount`、`to`、`nonce`、`deadline` 等关键参数
- 跨模块追踪：检查是否调用外部模块的签名验证服务但未验证返回值

## Classify

**漏洞判定条件：**
- 函数接受外部签名参数但完全未验证 → **高危漏洞**
- 验证签名但未绑定关键业务参数（如金额、接收方）→ **中危漏洞**
- 签名验证逻辑存在但可被绕过（如条件判断错误）→ **高危漏洞**

**误报识别：**
- 签名参数仅用于链下日志记录或事件触发，不影响状态变更
- 函数已通过 `&signer` 参数获得交易发起者的隐式授权，签名参数为冗余字段
- 私有函数（非 `public`）仅在内部模块调用，外部无法触发

**代码异味（需进一步确认）：**
- 签名验证存在但错误处理不当（仅 warning 不 abort）
- message digest 构造不完整，缺少 nonce 或时间戳导致重放风险
- 使用自定义签名验证算法而非标准库

## 审计专业技巧

### 真实漏洞识别经验

**真实漏洞的四大特征：**

1. **完整的"起点-路径-终点"利用链**
   - 起点：攻击者可控输入（public 函数参数）
   - 路径：输入直接或间接导致权限操作
   - 终点：可修改关键资源或转移资金
   - 反例（误报）：参数虽然不验证，但后续流程中被其他机制（如事件订阅方）拒绝使用

2. **调用链深度分析**
   - 追踪 `public entry` 函数的所有直接/间接被调函数
   - 检查中间层是否有隐式的权限检查（如通过 caller 账户地址推导）
   - 真实漏洞：函数无条件执行敏感操作（burn/mint/transfer）
   - 误报：虽无签名验证，但实际控制权由下层函数通过 Capability 系统强制

3. **状态变更影响范围**
   - 分析被修改的状态是否为全局资源或用户关键资源
   - 全局资源（如代币总供应量）的任意修改 = 高危漏洞
   - 用户个人资源的修改需权限检查 = 漏洞
   - 仅影响日志/临时数据 = 低风险

4. **多角色场景下的权限混淆**
   - 检查函数是否混淆了"数据所有者"和"操作发起者"的身份
   - 真实漏洞：`from` 账户的资金被 `tx.sender` 转走（没有 `from` 的同意）
   - 误报：`from` 和 `tx.sender` 必须相同（存在隐式检查）

### 常见误报案例分析

**案例1：外观检查不当导致的误报**
```move
// 看起来：签名参数未验证
public entry fun execute_action(
    action_data: vector<u8>,
    proof: vector<u8>  // 此时看起来没用
) {
    // 真相：proof 被传给权限检查模块
    assert!(verify_from_trusted_oracle(proof), ERR_INVALID);
    // 实际执行
}
```
- **误报指标**：搜索代码时漏看了 proof 的使用点，以为完全未验证
- **教训**：必须用 cross-reference 工具追踪所有参数使用，不能凭眼睛扫描

**案例2：隐式 signer 检查导致的误报**
```move
public entry fun admin_transfer(
    from: address,
    to: address,
    signer_proof: vector<u8>  // 看起来不验证
) acquires AdminConfig {
    let admin_config = borrow_global<AdminConfig>(from);
    // 真相：from 必须是 AdminConfig 的所有者，下一步验证会失败
    assert!(signer_exists_at(from), ERR_NOT_SIGNER);
}
```
- **误报指标**：`from` 参数必须拥有 AdminConfig 资源，自动限制了可操作范围
- **教训**：即使签名参数未验证，也要检查操作对象上是否有隐式权限约束

**案例3：时间锁导致的低风险分类**
```move
public entry fun delayed_mint(amount: u64, signature: vector<u8>) {
    // 签名不验证，但 mint 被延迟
    assert!(now() >= next_mint_time(), ERR_TOO_EARLY);
    assert!(amount <= DAILY_LIMIT, ERR_EXCEED_LIMIT);
}
```
- **误报指标**：虽然签名验证缺失，但实际风险被时间锁 + 金额限制大幅降低
- **教训**：综合考虑所有防护机制，不能单看签名验证

### 高级审计检查清单

**Step 1: 入口点确认**
- [ ] 是否确实是 `public` 或 `public entry`？（私有函数不是漏洞）
- [ ] 是否通过链上交易能直接调用？（某些 entry 有内部权限检查）
- [ ] 该函数是否在任何合约的升级黑名单中？

**Step 2: 参数关联性分析**
- [ ] 签名参数是否与其他参数（amount、to、deadline）有绑定关系？
- [ ] message digest 是否包含所有影响最终状态的参数？
- [ ] 是否存在参数重组可能（同一签名用于不同操作）？

**Step 3: 权限验证链追踪**
- [ ] 直接调用了 `ed25519::verify` / `secp256k1_ecdsa::verify`？
- [ ] 调用了权限中介函数（如 `assert_signer_cap`）？
- [ ] 权限验证是否可被 abort 异常绕过？
- [ ] 验证失败是直接 `abort` 还是仅记录日志？

**Step 4: 操作权限来源**
- [ ] 被操作资源的所有权是否与调用者匹配？
- [ ] 是否需要 Capability 才能访问（自动权限检查）？
- [ ] 是否在 genesis 初始化时被标记为不可修改？

**Step 5: 风险上下文评估**
- [ ] 函数涉及的资源总价值？（测试币 vs 主网资产）
- [ ] 是否有多重防线（及时发现+冻结机制）？
- [ ] 历史是否有类似函数被安全审计团队认证过？

## Low risk

**满足以下条件可降级为低风险：**
- 受影响资源价值有限：如测试代币、无经济价值的 NFT
- 存在外部约束条件：需配合其他高门槛操作（如多签、时间锁）才能利用
- 已有业务层防护：如交易金额上限、白名单限制、rate limiting
- 历史审计确认：该模式在同项目其他经审计模块中被认定为安全设计
- 临时测试代码：标注为 `#[test_only]` 或位于 `tests/` 目录
- 隐式权限检查：通过 Resource 所有权或 Capability 系统自动限制访问范围
