---
name: economic-model-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证经济模型（Economic Model）漏洞；重点关注代币经济机制设计中的可操控性、套利机会和系统性失衡风险，包括经济参数边界缺失、反馈机制不足、激励错位等；涵盖代币分发、流动性管理、收益计算、治理权重分配等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Economic Model**  

**Attention**  
当项目中涉及代币经济机制设计（如激励分配、价格锚定、供需调节、质押收益、费用模型等）时，需重点审计其经济模型逻辑是否可被操控、套利或导致系统性失衡；此类漏洞通常源于经济参数未设合理边界、反馈机制缺失、或外部激励与协议目标不一致，常见于代币分发、流动性管理、收益计算、治理权重分配等模块。  

**Early exit**  
若项目代码中不包含任何经济激励机制、代币逻辑、费用结构或资源定价模型（例如仅为纯数据存储合约、无代币交互的工具库、或无经济行为的基础设施组件），则可快速退出对该漏洞类型的审计。  

**Cases**  

**Solidity**  
常出现在代币分发、流动性挖矿、质押收益、治理权重计算等业务逻辑实现中，包括但不限于固定/动态奖励分配、滑点敏感的价格函数、未限制的铸币/销毁权限、激励与行为脱钩等方式：  
- 无上限铸币奖励：代币铸造奖励未设上限，可能导致通货膨胀失控或经济模型崩溃，详见：[Solidity_UnboundedMintReward.md](Solidity_UnboundedMintReward.md)  
- 无上限固定 APY：固定年化收益率未设总量上限，长期运行导致协议资不抵债，详见：[Solidity_FixedAPYWithoutCap.md](Solidity_FixedAPYWithoutCap.md)  
- 治理权重操纵：治理投票权重计算存在漏洞，允许通过特定操作放大投票权，详见：[Solidity_GovernanceWeightManipulation.md](Solidity_GovernanceWeightManipulation.md)  

**Rust** (e.g., Solana programs)  
常出现在质押收益计算、代币通胀调控、费用再分配等业务逻辑实现中，包括但不限于未校验的通胀率更新、基于用户历史行为的奖励计算未防刷量、协议收入分配比例硬编码且不可治理等方式：  
- 未检查通胀率：通胀率参数可被随意修改且未验证合理性，导致代币供应失控，详见：[Rust_InflationRateUnchecked.md](Rust_InflationRateUnchecked.md)  
- 基于未验证历史的奖励：奖励基于用户历史数据计算但未防止数据伪造或刷量，详见：[Rust_RewardBasedOnUnverifiedHistory.md](Rust_RewardBasedOnUnverifiedHistory.md)  
- 硬编码费用分配：协议费用分配比例硬编码无法调整，无法适应市场变化，详见：[Rust_FeeSplitHardcoded.md](Rust_FeeSplitHardcoded.md)  

**Move** (e.g., Sui, Aptos)  
常出现在资源绑定型经济模型、动态费率调整、资产铸造配额等业务逻辑实现中，包括但不限于资源销毁与增发不对称、费率随外部预言机价格跳变无缓冲、权限控制缺失导致经济参数被任意修改等方式：  
- 资产铸造销毁不对称：代币铸造和销毁机制不平衡，导致供应量单向变化破坏经济模型，详见：[Move_AssetMintBurnAsymmetry.md](Move_AssetMintBurnAsymmetry.md)  
- 基于价格的费率跳变：费率直接跟随外部价格剧烈波动，无平滑机制导致用户体验差，详见：[Move_PriceBasedFeeJump.md](Move_PriceBasedFeeJump.md)  
- 经济参数无上限：关键经济参数（如通胀率、手续费）可被设置为任意值，缺乏合理边界，详见：[Move_EconomicParamNoCap.md](Move_EconomicParamNoCap.md)  

**Vyper**  
常出现在稳定币锚定机制、清算罚金设计、治理代币释放曲线等业务逻辑实现中，包括但不限于线性释放未考虑市场冲击、罚金比例不可调导致清算失效、锚定偏差反馈延迟等方式：  
- 线性释放无市场缓冲：代币线性释放未考虑市场承受能力，大量释放导致价格崩盘，详见：[Vyper_LinearVestingNoMarketCap.md](Vyper_LinearVestingNoMarketCap.md)  
- 不可调整清算罚金：清算罚金比例固定无法调整，市场变化时清算机制失效，详见：[Vyper_UnadjustableLiquidationPenalty.md](Vyper_UnadjustableLiquidationPenalty.md)  
- 稳定币锚定漂移无再平衡：稳定币脱锚后无自动再平衡机制，偏离持续扩大，详见：[Vyper_StablecoinPegDriftNoRebalance.md](Vyper_StablecoinPegDriftNoRebalance.md)  

**Go** (e.g., Cosmos SDK-based chains)  
常出现在链上通胀模型、区块奖励分配、手续费池分红等业务逻辑实现中，包括但不限于通胀率基于静态参数无法响应网络状态、奖励按地址而非质押量分配、手续费分红未考虑验证者在线率等方式：  
- 静态通胀无反馈：通胀率固定不变，无法根据网络状态（如质押率）动态调整，详见：[Go_StaticInflationNoFeedback.md](Go_StaticInflationNoFeedback.md)  
- 按地址而非质押量分配奖励：奖励分配未考虑质押量，导致激励机制失效，详见：[Go_RewardByAddressNotStake.md](Go_RewardByAddressNotStake.md)  
- 费用池分红忽略在线率：手续费分配未考虑验证者实际贡献和在线时间，详见：[Go_FeePoolDividendIgnoresUptime.md](Go_FeePoolDividendIgnoresUptime.md)