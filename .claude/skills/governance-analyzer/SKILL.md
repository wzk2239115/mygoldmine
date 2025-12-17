---
name: governance-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证治理攻击（Governance Attacks）漏洞；重点关注投票权操纵、提案执行缺陷、时间锁绕过、多签安全等；涵盖DAO治理、协议升级投票、参数调整提案、资金分配决策等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---

**Governance Attacks**

**Attention**
当项目实现去中心化治理机制（如DAO投票、提案系统、多签钱包、时间锁控制器等）时，需重点审计治理流程的安全性。此类漏洞通常源于投票权计算错误、提案验证不足、执行权限缺陷或经济激励设计不当，可导致协议参数被恶意修改、资金被非法提取或治理权被永久劫持。常见于DAO治理、协议升级投票、参数调整提案、资金分配决策、多签管理等模块。

**Early exit**
若项目代码中完全不涉及链上治理机制（无投票、提案、多签等功能）、所有关键参数由单一不可变地址控制且无升级机制、或采用完全中心化管理模式（明确声明且用户知晓），则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**
常出现在 DAO 治理合约、Governor 合约、Timelock 控制器、多签钱包、代币投票系统等业务逻辑实现中，包括但不限于投票权计算错误、提案执行权限不足、闪电贷投票攻击、委托投票缺陷等方式：
- 闪电贷投票攻击：攻击者通过闪电贷临时获取大量治理代币，操纵投票结果后归还代币，详见：[Solidity_FlashLoanGovernanceAttack.md](Solidity_FlashLoanGovernanceAttack.md)
- 提案执行权限绕过：提案执行函数缺少足够的权限检查或时间锁保护，允许未经投票通过的提案被执行，详见：[Solidity_ProposalExecutionBypass.md](Solidity_ProposalExecutionBypass.md)
- 投票权重计算错误：投票权重计算使用当前余额而非快照，允许代币在投票期间转移以重复投票，详见：[Solidity_VoteWeightManipulation.md](Solidity_VoteWeightManipulation.md)
- 时间锁绕过：时间锁实现存在漏洞，允许绕过延迟直接执行提案或取消已批准的提案，详见：[Solidity_TimelockBypass.md](Solidity_TimelockBypass.md)
- 委托投票劫持：委托投票机制存在缺陷，允许攻击者控制他人的投票权或委托关系被恶意修改，详见：[Solidity_DelegateVoteHijack.md](Solidity_DelegateVoteHijack.md)
- 多签阈值操纵：多签钱包的签名者管理或阈值修改存在漏洞，允许少数签名者控制整个钱包，详见：[Solidity_MultisigThresholdManipulation.md](Solidity_MultisigThresholdManipulation.md)

**Rust** (适用于 Solana、Substrate 等基于 Rust 的链)
常出现在链上治理模块、提案系统、验证者投票、参数治理等业务逻辑实现中，包括但不限于未验证提案者权限、投票计数溢出、治理代币快照缺失等方式：
- Solana 治理程序投票操纵：治理程序中投票账户验证不足，允许伪造投票或重复计票，详见：[Rust_SolanaGovernanceVoteManipulation.md](Rust_SolanaGovernanceVoteManipulation.md)
- 提案者权限缺失：任何人可创建提案但缺少质押或持币门槛，导致垃圾提案泛滥或恶意提案攻击，详见：[Rust_MissingProposerRequirement.md](Rust_MissingProposerRequirement.md)
- 投票计数整数溢出：投票计数时未使用 checked arithmetic，大量投票导致计数溢出使提案状态错误，详见：[Rust_VoteCountOverflow.md](Rust_VoteCountOverflow.md)
- 治理账户权限混淆：治理相关账户的 authority 验证不正确，允许未授权账户修改治理状态，详见：[Rust_GovernanceAccountAuthorityConfusion.md](Rust_GovernanceAccountAuthorityConfusion.md)

**Move**
常出现在 DAO 模块、治理提案系统、多签资源管理、能力委托投票等业务逻辑实现中，包括但不限于缺少投票快照机制、提案执行能力泄露、投票资源未锁定等方式：
- 缺少投票快照：投票权基于实时余额而非快照，允许代币在投票期间转移以获得多次投票机会，详见：[Move_MissingVoteSnapshot.md](Move_MissingVoteSnapshot.md)
- 提案执行能力泄露：提案执行所需的 Capability 对象管理不当，可被未授权模块获取并执行恶意提案，详见：[Move_ProposalExecutionCapabilityLeak.md](Move_ProposalExecutionCapabilityLeak.md)
- 投票代币未锁定：投票期间治理代币未被锁定，允许投票后立即出售代币逃避决策后果，详见：[Move_VoteTokenNotLocked.md](Move_VoteTokenNotLocked.md)
- 治理参数修改无延迟：关键治理参数修改立即生效而无时间锁保护，无法给用户退出时间，详见：[Move_GovernanceParamNoDelay.md](Move_GovernanceParamNoDelay.md)

**Vyper**
常出现在类似 Solidity 的 DAO 治理、投票合约、时间锁控制等业务逻辑实现中，包括但不限于投票状态管理错误、提案 ID 冲突、委托关系未验证等方式：
- 投票状态竞争条件：投票状态更新存在竞争条件，允许在同一区块内多次投票或改变投票，详见：[Vyper_VoteStateRaceCondition.md](Vyper_VoteStateRaceCondition.md)
- 提案 ID 碰撞：提案 ID 生成算法可预测或存在碰撞风险，允许覆盖已存在的提案，详见：[Vyper_ProposalIDCollision.md](Vyper_ProposalIDCollision.md)
- 投票权委托未验证：委托投票时未验证被委托人地址有效性，允许将投票权委托给合约或零地址导致投票权丢失，详见：[Vyper_UnverifiedVoteDelegation.md](Vyper_UnverifiedVoteDelegation.md)

**Go** (适用于 Cosmos SDK 等基于 Go 的链)
常出现在 gov 模块、参数变更提案、软件升级提案、验证者集变更等业务逻辑实现中，包括但不限于提案验证不足、投票权计算错误、紧急提案滥用等方式：
- Cosmos 治理提案验证缺失：治理提案内容验证不足，允许提交格式错误或恶意的提案导致链停止或状态损坏，详见：[Go_CosmosGovProposalValidationMissing.md](Go_CosmosGovProposalValidationMissing.md)
- 投票权计算基于未质押代币：投票权计算错误包含未质押或已解绑的代币，允许攻击者通过操纵质押状态获得额外投票权，详见：[Go_VotingPowerIncludesUnstaked.md](Go_VotingPowerIncludesUnstaked.md)
- 紧急提案无额外验证：紧急提案或快速通道提案缺少额外的安全检查，可被滥用快速通过恶意变更，详见：[Go_EmergencyProposalNoExtraValidation.md](Go_EmergencyProposalNoExtraValidation.md)
- 参数变更无范围限制：治理参数变更提案对新参数值无合理性检查，可设置极端值导致协议不可用，详见：[Go_ParamChangeNoRangeCheck.md](Go_ParamChangeNoRangeCheck.md)
