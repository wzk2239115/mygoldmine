---
name: timestamp-dependence-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证时间戳依赖（Timestamp Dependence）漏洞；重点关注依赖区块时间戳（block.timestamp 或等效字段）作为关键决策依据的业务逻辑，包括时间戳作为熵源、状态切换触发器、权限控制依据等；涵盖随机数生成、限时活动、时间锁、利率计算、状态机驱动等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Timestamp Dependence**

**Attention**  
当项目逻辑依赖区块链区块时间戳（block.timestamp 或等效字段）作为关键决策依据（如随机数生成、状态切换、权限控制或奖励发放）时，需仔细审计相关代码。此类漏洞源于矿工/验证者对时间戳具有一定操控能力（通常在一定容差范围内），导致协议行为可被操纵。该问题常见于抽奖、限时活动、时间锁、利率计算或状态机驱动的业务模块中。

**Early exit**  
若项目代码中完全未使用区块时间戳（如 block.timestamp、env::block_timestamp()、@timestamp 等语言内置时间源）作为任何逻辑判断或状态变更的输入条件，且所有时间敏感操作均依赖链下可信预言机或用户自定义时间戳（并有相应验证机制），则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在随机数生成、限时竞拍、质押奖励计算、状态机超时判断等业务逻辑实现中，包括但不限于直接使用 block.timestamp 作为熵源、截止条件或状态切换触发器：  
- 时间戳作为熵源：使用 block.timestamp 作为随机数种子，可被矿工在一定范围内操纵，详见：[Solidity_TimestampAsEntropy.md](Solidity_TimestampAsEntropy.md)  
- 竞拍截止时间操纵：竞拍或限时活动依赖 block.timestamp 判定截止，矿工可通过调整时间戳影响竞拍结果，详见：[Solidity_AuctionDeadlineManipulation.md](Solidity_AuctionDeadlineManipulation.md)  
- 质押奖励时间依赖：质押奖励计算直接基于 block.timestamp 差值，可被操纵导致奖励分配不公，详见：[Solidity_StakingRewardTimeDependency.md](Solidity_StakingRewardTimeDependency.md)  

**Rust (e.g., Solana/Anchor)**  
常出现在基于 slot 或 block timestamp 的状态检查、任务过期机制、或时间加权奖励分配功能中，包括但不限于使用 Clock::get().unix_timestamp 作为关键条件而未设容差边界：  
- 基于时间戳的状态转换：状态机依赖链上时间戳进行转换，验证者可通过调整时间影响状态切换时机，详见：[Rust_TimestampBasedStateTransition.md](Rust_TimestampBasedStateTransition.md)  
- 过期任务绕过：任务或锁定期检查依赖时间戳，可通过时间漂移提前或延迟触发，详见：[Rust_ExpiredTaskBypass.md](Rust_ExpiredTaskBypass.md)  

**Move**
常出现在 Aptos 或 Sui 链上合约中依赖 @timestamp 或 chain_time 作为解锁条件、投票截止或费率调整依据的逻辑中，包括但不限于直接比较当前链时间与预设阈值而无延迟缓冲：
- 时间锁金库操纵：资金解锁依赖链上时间戳，验证者可通过时间调整影响解锁时机，详见：[Move_TimeLockedVaultManipulation.md](Move_TimeLockedVaultManipulation.md)
- 投票截止时间依赖：治理投票截止时间直接依赖区块时间戳，验证者可通过调整出块时间影响投票窗口，详见：[Move_VotingDeadlineTimestampDependency.md](Move_VotingDeadlineTimestampDependency.md)
- 收费率动态调整漂移：收费率、奖励倍数等参数根据时间戳动态调整但未设延迟缓冲，导致同一区块内不同交易的费率不一致，详见：[Move_FeeRateTimestampDrift.md](Move_FeeRateTimestampDrift.md)  

**Vyper**  
常出现在 DeFi 协议的利率模型、治理提案截止、或 NFT 铸造窗口控制中，包括但不限于使用 block.timestamp 判断窗口开启/关闭而未考虑时间漂移：  
- 铸造窗口利用：NFT 或代币铸造窗口依赖 block.timestamp，矿工可调整时间戳抢先或延后铸造，详见：Vyper_MintWindowExploit.md  
- 治理截止绕过：治理提案截止判断依赖时间戳，可被操纵影响投票窗口和结果，详见：Vyper_GovernanceDeadlineBypass.md  

**Go (e.g., Cosmos SDK modules)**  
常出现在基于 ctx.BlockTime() 的治理投票截止、质押解绑期判断或奖励分发逻辑中，包括但不限于未对时间窗口设置最小延迟或未引入外部时间验证：  
- 质押解绑时间检查：质押解绑期依赖区块时间判断，验证者可通过时间调整影响解绑时机，详见：Go_StakingUnbondingTimeCheck.md  
- 治理提案截止依赖：治理提案截止时间直接依赖区块时间，可被验证者操纵影响投票结果，详见：Go_GovProposalDeadlineReliance.md