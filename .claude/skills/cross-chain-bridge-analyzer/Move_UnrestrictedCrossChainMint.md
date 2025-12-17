# Move_UnrestrictedCrossChainMint

**Move 语言 - 无限制跨链铸造漏洞**

常见于 Aptos/Sui 跨链桥中，铸造函数缺乏权限验证、铸造上限校验或跨链消息验证，导致攻击者可无限铸造跨链资产。

## Details

**典型代码模式：**

```move
public entry fun mint_bridged_token(
    account: &signer,
    amount: u64,
    chain_id: u64
) acquires BridgeState {
    let token = coin::mint<BridgedUSDC>(amount); // 无权限检查
    coin::deposit(signer::address_of(account), token);
}
```

**核心操作定位技巧（L2-跳读）：**
- 搜索 `mint`、`create`、`issue` 等铸造关键字
- 重点关注 `public entry` 或 `public` 函数的铸造逻辑
- 检查函数参数中是否存在 `amount`、`to` 等可控变量
- 追踪 `Coin::mint`、`Token::mint_token` 等原生铸造调用
- 查看是否存在 `acquires` 全局资源但未校验状态

**保护机制定位技巧（L3-逐行读）：**
- 权限验证：`assert!(signer::address_of(account) == @bridge_admin, ERR_UNAUTHORIZED)`
- Cap 机制：`assert!(bridge_state.minted + amount <= bridge_state.cap, ERR_EXCEED_CAP)`
- 跨链证明验证：`verify_cross_chain_message(proof, validators)`
- Nonce/序列号：`assert!(!bridge_state.processed_nonces.contains(&nonce), ERR_REPLAY)`
- MintCapability 持有检查：`borrow_global<MintCap<T>>(@bridge_module)`
- 多签门槛：`assert!(approvals.length() >= THRESHOLD, ERR_INSUFFICIENT_APPROVALS)`

## Classify

**真实漏洞标准：**
- 铸造函数为 `public entry` 且无 `Capability` 参数约束
- 缺失 `assert!` 验证调用者身份或权限
- 铸造量完全由外部参数决定，无上限或余额映射校验
- 跨链消息未验证签名、Merkle 证明或 VAA（Wormhole）
- 全局 `MintCap` 资源可被任意模块借用

**误报情况：**
- 铸造函数接受 `&MintCapability<T>` 且 Cap 仅由管理员持有
- 存在 `friend` 模块限制，仅可信模块调用
- 铸造前已通过 `event::emit` 或 Oracle 验证跨链锁定
- 测试/演示代码（需确认部署环境）

**代码异味：**
- 铸造有权限检查但使用硬编码地址而非动态角色系统
- Cap 存在但阈值设置过高（如 u64::MAX）
- 跨链验证存在但签名者集合可被单点控制

## Low risk

**降级为低风险的场景：**
- 铸造的是非价值代币（如测试币、积分）且明确标注用途
- 存在时间锁或延迟执行机制，可在攻击窗口内响应
- 铸造受外部 Oracle 喂价控制，且 Oracle 有多节点共识
- 合约处于沙盒环境或隔离链，不与主网资产互通
- 铸造总量即使无限制，但销毁机制确保供给平衡且经济模型可承受短期波动
- 跨链桥 TVL 极小（如 <$10k）且已明确风险提示

## 审计专业技巧

**漏洞确认的实战检查清单：**

1. **权限验证深度审查**
   - 逐行检查 `assert!` 中的条件是否可被绕过（如使用 OR 逻辑时的短路问题）
   - 验证调用者检查是否使用 `signer::address_of()` 而非 `tx_context::sender()`（某些链版本差异）
   - 检查是否存在特殊账户（如零地址、系统地址）被硬编码为管理员
   - 确认权限检查代码是否在铸造操作**之前**执行（避免乱序执行）

2. **跨链消息验证的陷阱**
   - 验证签名验证使用的是 ECDSA、EdDSA 还是自定义算法（自定义算法高风险）
   - 检查签名者集合是否可动态更新，以及更新是否需要多签门槛
   - 查看 Merkle 证明验证是否存在遗漏分支的情况（仅验证根但未验证完整路径）
   - 追踪 Oracle 数据来源：是否来自链外且缺乏冗余验证

3. **Capability 机制的正确用法判断**
   - 区分 `MintCapability<T>` 的所有权位置：是否在合约部署时生成后立即销毁（销毁 = 无法铸造，非漏洞）
   - 验证 Cap 在存储时是否使用 `move_to(&signer, cap)` 而非全局存储，避免任意账户借用
   - 检查 Cap 的借用是否通过 `borrow_global_mut` 且目标地址为常量管理员地址
   - 查看是否存在"包装 Cap"的中间层（如 BridgeCap 结构体包含实际 MintCap），这可能隐藏权限问题

## 真实漏洞与误报的区分经验

**常见误报场景分析：**

**Case 1: 硬编码管理员地址的假象**
```
真实情况：address 为 0x1（系统地址）或合约发布者，无法更改 → 低风险或无风险
虚假判断：认为硬编码就是漏洞 → 错误
检查方法：查看 address 是否通过 `@bridge_module` 等符号化常量（需回溯定义），而非魔法数字
```

**Case 2: `friend` 模块的权限隐蔽性**
```
真实情况：Bridge Module 声明 friend ModuleX，ModuleX 的 mint_bridged 函数仅供 Bridge 调用
虚假判断：看到 public entry mint_bridged 就认为直接可调 → 错误
检查方法：必须完整扫描模块声明的 friend 列表，追踪所有调用方是否被限制
```

**Case 3: 测试网 vs 主网代码的混淆**
```
真实情况：GitHub repo 中存在调试注释如 `// TESTNET ONLY` 或特殊 flag 控制
虚假判断：直接复制测试网代码逻辑为主网漏洞 → 误判
检查方法：查看部署环境配置、环境变量、构建脚本中是否有条件编译
```

**Case 4: 双重验证的隐藏**
```
真实情况：前端 UI 做了第一层检查，链上只做补充校验（需要威胁模型评估）
虚假判断：只看链上代码，认为检查不足 → 部分误导
检查方法：审查是否存在事件日志记录证明链下验证，但理想情况仍应链上完整验证
```

**真实漏洞的识别要点：**

1. **权限+金额的完全可控组合**：同时满足 (1) 任意账户可调用 AND (2) amount 参数完全不受限
2. **回放攻击防护缺失**：跨链消息无 nonce、timestamp 等唯一标识符
3. **多链状态不一致**：某条链上的铸造无法被其他链感知，可利用同一消息在多链重放
4. **Oracle 单点依赖**：价格喂价仅来自一个节点且无应急降级机制
5. **时间窗口利用**：从锁定事件到铸造确认间存在可利用的时间差，且无冻结保护

**专业判断的关键问卷：**

- [ ] 是否追踪了所有可能调用铸造函数的路径（包括通过 delegation、router 合约）
- [ ] 跨链验证中的验证者集合是否真的来自信任的预言机网络（vs 自定义黑名单）
- [ ] 铸造的 Token 类型定义中是否包含 `copyable` 属性，可被复制则高风险
- [ ] 是否存在"测试"或"演示"的标记，但实际已部署到主网
- [ ] 铸造速率是否有隐性限制（如 per-block rate limit 在虚拟机层面实现）
- [ ] 管理员变更是否需要社区投票或多签，避免单点风险升级
