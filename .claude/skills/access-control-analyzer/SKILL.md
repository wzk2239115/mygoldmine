---
name: access-control-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证访问控制（Access Control）漏洞；重点关注权限敏感操作的访问控制机制，包括权限检查缺失、校验逻辑绕过、权限模型设计缺陷等；涵盖治理模块、管理员功能、升级逻辑、金库操作等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
当项目中存在权限敏感操作（如资金提取、参数修改、关键状态变更等）但未通过严格的角色或所有权校验机制进行保护时，需重点审计访问控制逻辑。此类漏洞通常源于权限检查缺失、校验逻辑绕过或权限模型设计缺陷，常见于治理模块、管理员功能、升级逻辑、金库操作等业务场景。

**设计模式上下文**
在检测访问控制漏洞前，先运行 [design-pattern-recognizer](../design-pattern-recognizer/SKILL.md) 识别项目的治理模式，以避免误报：

- **Governance Minimized 模式**（治理最小化）：
  - 特征: 合约不可升级、无管理员权限、参数在构造函数中固化（immutable）
  - 证据: 无 `onlyOwner` 修饰符、无 upgradeable 代理、README 明确说明 "governance-minimized"
  - 影响: 将检测阈值降低至 30%（原 100%）
  - 调整: "Owner 权限过大" 发现 → Low 或 Info（无 Owner）
  - 调整: "缺少紧急暂停" 发现 → Info（有意设计）
  - 详见: [design-pattern-recognizer/Solidity_GovernanceMinimized.md](../design-pattern-recognizer/Solidity_GovernanceMinimized.md)

- **Timelocked Governance 模式**（时间锁治理）：
  - 特征: 管理员操作需延迟执行、有 Timelock 合约
  - 影响: 将检测阈值降低至 50%
  - 调整: Owner 权限风险降级为 Medium（有延迟保护）

- **DAO Governed 模式**（DAO 治理）：
  - 特征: 治理由代币持有者投票决定、有 Governor 合约
  - 影响: 区分治理权限与管理员后门
  - 调整: 合法治理权限 → Low，隐藏后门 → High

**仍需报告为高危的情况**（即使是 Governance Minimized）：
- 声称 governance-minimized 但保留隐藏后门（如 `_secretAdmin`）
- 使用 immutable 但初始值可被构造函数恶意设置且无验证
- 通过 delegatecall 绕过 immutable 限制
- 文档声称 "no admin" 但代码有 onlyOwner 函数（误导）

**Early exit**  
如果项目代码中完全不存在特权操作（例如所有函数均为公开且无状态修改权限差异）、未定义任何角色或权限标识（如 owner、admin、governor 等），且业务逻辑不涉及任何条件性访问限制（如仅读取、无状态变更），则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在治理控制、协议升级、资金管理等业务逻辑实现中，包括但不限于 owner 权限滥用、modifier 缺失或误用、角色权限未隔离等方式：  
- Owner 特权滥用：合约所有者权限过大或未设限制，可随意更改关键参数、提取资金或绕过业务逻辑，导致中心化风险与资产安全隐患，详见：[Solidity_OwnerPrivilegeAbuse.md](Solidity_OwnerPrivilegeAbuse.md)  
- 访问修饰符缺失：关键函数未添加 onlyOwner/onlyRole 等访问控制修饰符，导致任意用户可调用敏感操作，详见：[Solidity_MissingAccessModifier.md](Solidity_MissingAccessModifier.md)  
- 基于角色的访问控制绕过：角色权限设计存在逻辑漏洞，允许低权限角色通过特定操作序列获得高权限或绕过角色检查，详见：[Solidity_RoleBasedControlBypass.md](Solidity_RoleBasedControlBypass.md)  

**Rust**（适用于 Solana、Sui 等基于 Rust 的链）  
常出现在账户权限校验、指令分发、状态初始化等业务逻辑实现中，包括但不限于未验证 signer、未检查账户所有权、权限上下文缺失等方式：  
- 缺失签名者检查：关键指令未验证交易签名者身份，导致任意用户可冒充授权账户执行敏感操作，详见：[Rust_MissingSignerCheck.md](Rust_MissingSignerCheck.md)  
- 未验证账户权限：操作账户数据前未检查账户的 owner 或 authority 字段，允许未授权账户被恶意修改，详见：[Rust_UnverifiedAccountAuthority.md](Rust_UnverifiedAccountAuthority.md)  
- 上下文权限错误：访问控制逻辑未正确使用或验证 Context 结构中的约束条件，导致权限检查可被绕过，详见：[Rust_ContextualAccessControlError.md](Rust_ContextualAccessControlError.md)  

**Move**  
常出现在资源操作、能力（Capability）管理、模块初始化等业务逻辑实现中，包括但不限于未使用 Capability 模式、直接暴露敏感函数、权限对象可伪造等方式：  
- 缺失 Capability 守卫：敏感资源操作未通过 Capability 对象进行权限控制，导致任意调用者可直接修改或转移资源，详见：[Move_MissingCapabilityGuard.md](Move_MissingCapabilityGuard.md)  
- 不当资源访问：资源读写逻辑未正确限制访问范围，允许未授权模块或账户访问私有资源状态，详见：[Move_ImproperResourceAccess.md](Move_ImproperResourceAccess.md)  
- 可伪造的访问令牌：权限凭证对象（如 AdminCap）设计不当，可被复制或伪造，导致权限控制机制失效，详见：[Move_ForgeableAccessToken.md](Move_ForgeableAccessToken.md)  

**Vyper**  
常出现在金库操作、参数配置、紧急暂停等业务逻辑实现中，包括但不限于未使用 @internal/@external 严格划分、缺少 if msg.sender == owner 校验、事件驱动权限绕过等方式：  
- 缺失 Owner 检查：关键状态变更函数未验证调用者是否为合约所有者，导致任意用户可执行特权操作，详见：[Vyper_MissingOwnerCheck.md](Vyper_MissingOwnerCheck.md)  
- 函数可见性设置不当：敏感内部函数未标记为 @internal，导致外部可直接调用，绕过访问控制逻辑，详见：[Vyper_ImproperFunctionVisibility.md](Vyper_ImproperFunctionVisibility.md)  
- 紧急功能暴露：紧急暂停、资金提取等高风险函数未设权限限制，可被恶意调用导致协议瘫痪或资产损失，详见：[Vyper_EmergencyFunctionExposed.md](Vyper_EmergencyFunctionExposed.md)  

**Go**（适用于 Cosmos SDK 等基于 Go 的链）  
常出现在 Keeper 方法、消息处理、参数治理等业务逻辑实现中，包括但不限于未校验 Msg.Signer、未限制 Keeper 方法调用上下文、治理提案权限扩散等方式：  
- 未验证消息签名者：消息处理函数未检查 Msg.Signer 是否具有执行权限，导致任意用户可提交特权操作消息，详见：[Go_UnverifiedMsgSigner.md](Go_UnverifiedMsgSigner.md)  
- Keeper 方法暴露：Keeper 方法未限制调用上下文，可在不应调用的场景被调用，绕过业务层访问控制，详见：[Go_KeeperMethodExposed.md](Go_KeeperMethodExposed.md)  
- 治理参数覆盖无鉴权：治理模块允许通过提案修改关键参数但未验证提案者权限或投票阈值，导致权限扩散，详见：[Go_GovParamOverrideWithoutAuth.md](Go_GovParamOverrideWithoutAuth.md)