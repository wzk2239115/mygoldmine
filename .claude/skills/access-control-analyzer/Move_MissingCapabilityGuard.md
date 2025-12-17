**Move**  
常出现在资源操作、能力（Capability）管理、模块初始化等业务逻辑实现中，包括但不限于未使用 Capability 模式、直接暴露敏感函数、权限对象可伪造等方式：  
- 缺失 Capability 守卫：敏感资源操作未通过 Capability 对象进行权限控制，导致任意调用者可直接修改或转移资源，详见：Move_MissingCapabilityGuard.md

## Details

**对应代码示例：** 资源的 `move_to`/`move_from`/`borrow_global_mut` 操作函数、管理员权限函数（mint/burn/freeze）、配置修改函数、资源所有权转移函数、模块初始化后的特权操作。

**快速定位到核心操作的技巧（L2:跳读）：**
- 搜索 `public fun` 中包含 `borrow_global_mut`、`move_from`、`move_to` 的函数
- 定位资源修改操作（mint、burn、freeze、update_config、transfer_ownership）
- 检查带 `acquires` 关键字的公开函数，确认其是否修改全局资源
- 关注模块初始化后仍可调用的特权函数（非 `init` 函数但操作敏感状态）

**快速定位到保护机制的技巧（L3:逐行读）：**
- 检查敏感函数参数中是否包含 Capability 类型（如 `&MintCapability`、`&AdminCap`）
- 确认 Capability 结构体定义是否带 `store` 能力（有 `store` 则可转移，需二次校验使用场景）
- 验证 Capability 的分发逻辑：仅在 `init` 函数中创建并 `move_to` 给特定地址（`@admin`、`@deployer`）
- 检查是否使用 `assert!(signer::address_of(&caller) == @admin, ENOT_AUTHORIZED)` 替代 Capability 模式（直接地址校验属于弱保护）

## Classify

**漏洞研判标准：**
- 敏感资源操作函数为 `public` 且参数不包含 Capability 对象，仅通过地址比较或无校验即可执行
- Capability 对象具备 `store` 能力且无使用限制，可被转移给任意账户后滥用
- 初始化函数未将 Capability 限制分发给特定账户，或通过 `public fun` 暴露 Capability 获取接口

**误报识别：**
- 函数虽为 `public` 但仅修改调用者自己地址下的资源（`move_to<T>(&signer, ...)`），无跨账户权限提升风险
- 敏感操作已通过 `friend` 声明限制调用模块范围，且 friend 列表均为受信任模块
- Capability 不可转移（无 `store` 能力）且仅在 `init` 中分发给部署者账户，后续无泄露路径

**代码异味：**
- 使用地址硬编码校验（`assert!(addr == @0x123, ...)`）替代 Capability 模式，降低权限管理灵活性
- Capability 对象虽存在但未在所有敏感操作中强制要求，部分函数绕过 Capability 直接执行
- Capability 分发后无撤销机制，无法应对密钥泄露或权限误发场景

## Low risk

**低风险评级场景：**
- 敏感操作已通过不可转移 Capability（无 `store` 能力）保护，且 Capability 仅在 `init` 中发给唯一管理员账户并严格持有
- 资源操作虽公开但影响范围受限于调用者自身资源，不存在跨账户攻击面（如用户自己的 NFT 转移函数）
- 存在多层防护：Capability + 时间锁 + 多重签名，关键操作需多个 Capability 持有者联合授权
- 模块已冻结发布（`--no-republish`）且 Capability 分发给去中心化治理合约，单一实体无法滥用权限

## 审计专业技巧

### 真实漏洞的典型特征

**1. 权限转移/重定向漏洞**
- Capability 具有 `store` 能力，允许被 `move_to` 到任意账户或存储在全局资源中，攻击者可通过交易交互获取 Capability 副本
- 检查方法：搜索 `move_to<Cap>(&signer, cap)` 且 signer 非硬编码地址，或在 public 函数中允许动态指定 Capability 存储位置
- 真实案例：Aptos 某 DeFi 协议 MintCapability 可通过 `public fun grant_mint_right(receiver: address, cap: MintCapability)` 转移到攻击者地址

**2. 初始化逻辑漏洞**
- `init` 函数使用 `signer::address_of(&creator) == tx::sender()` 进行权限判断，但允许任意账户重复调用初始化函数
- 多个账户可各自创建并持有 Capability 副本，导致权限分散且无法有效撤销
- 检查方法：确认 `init` 函数是否被一次性初始化机制保护（如通过共享 object 或 object state），而非仅依赖 `#[init]` 属性

**3. Capability 不完整覆盖**
- 核心敏感函数使用了 Capability 保护，但部分辅助/更新函数绕过了 Capability 检查
- 例如：`mint` 函数需要 MintCapability，但 `mint_and_transfer` 函数遗漏了 Capability 参数要求
- 检查方法：列出所有修改关键全局状态的函数，逐一验证 Capability 要求的一致性

**4. Signer 类型滥用**
- 通过 `signer::address_of(&signer)` 校验而非使用强类型 Capability，权限检查效果弱化
- 攻击者若获得部署者的私钥或伪造 tx sender，则权限校验失效
- 真实案例：某协议使用 `assert!(signer::address_of(&caller) == @admin)` 而非 Capability，导致部署者私钥泄露时全盘沦陷

**5. 友元模块漏洞**
- `friend module_a, module_b` 声明模块 A/B 可调用内部函数，但模块 B 本身存在权限漏洞，导致权限提升链路被打开
- 需要递归检查所有 friend 模块的权限管理
- 检查方法：追踪 friend 声明的模块，确认其内部也拥有完善的权限控制机制

### 常见误报场景

**1. 自操作资源不违反权限**
- 函数签名 `public fun transfer_nft(owner: &signer, nft_id: u64, to: address)`，通过 signer 验证所有权
- 这是正常的资源管理模式，非权限漏洞（用户转移自己的资源）
- 区分方法：检查 move_to/move_from 操作的资源地址是否与 signer 地址一致

**2. 有条件的 Capability 分发**
- `public fun request_mint_capability(requester: &signer, approval: &ApprovalToken) -> MintCapability`
- 虽然函数公开，但通过强制要求 ApprovalToken 进行了二次授权检查
- 区分方法：检查所有必需参数是否都具有权限语义（来自受信任的初始化或白名单）

**3. 受限的 Friend 模块生态**
- 使用 `friend` 声明限制调用者为特定模块，且这些模块经过审计且权限管理完善
- 虽然内部实现可能复杂，但权限入口点已被限制
- 区分方法：确认 friend 模块列表中所有模块都在审计范围内，且无外部 public 接口泄露权限

**4. Object 模式的灵活权限**
- Aptos Object 模式中，Capability 以 Object 形式存储，允许更灵活的所有权转移
- 只要 Object ownership 链路清晰且受控（如 SignerOwned、Owned to SingleOwner），权限仍在掌控中
- 区分方法：追踪 Object 的创建、转移、销毁全生命周期

### 审计检查清单

**第一轮扫描（快速定位风险）**
- [ ] 搜索所有 public 函数中包含 `move_from`/`borrow_global_mut` 的操作
- [ ] 列出所有定义的 Capability 类型及其能力集（是否含 `store`）
- [ ] 确认 `init` 函数是否被一次性初始化保护（非幂等性设计）
- [ ] 检查 friend 声明的模块是否超过 5 个（过多 friend 增加权限泄露风险）

**第二轮深入分析（确认漏洞真实性）**
- [ ] 针对每个敏感函数，追踪其调用链路：谁可以调用 -> 调用者权限如何验证
- [ ] 验证 Capability 分发的完整性：所有地方的 Capability 创建是否都通过 init 函数，无泄露路径
- [ ] 检查 Capability 使用的强制性：核心敏感操作是否在所有代码路径中都要求 Capability
- [ ] 测试 init 函数的一次性：尝试重复调用 init，观察是否被保护

**第三轮确认（评估实际风险）**
- [ ] 权限提升路径：攻击者从哪一步开始可以获得权限，所需条件是否现实可达
- [ ] 影响范围：一旦权限被滥用，可控制的资源规模（全局状态、用户资产等）
- [ ] 撤销能力：发现权限泄露后，是否存在撤销/冻结机制
