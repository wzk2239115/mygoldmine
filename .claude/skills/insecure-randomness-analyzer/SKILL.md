---
name: insecure-randomness-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证不安全随机数（Insecure Randomness）漏洞；重点关注依赖可预测或可操纵链上数据（如block.timestamp、blockhash、区块高度等）作为随机源的业务逻辑，涵盖链上游戏、NFT铸造、抽奖、随机奖励分配等依赖随机性的业务场景；利用按编程语言组织的参考资料目录中的参考指南。
vulnerability_type: 密码学安全漏洞
---
**Insecure Randomness 研判笔记**

**Attention**  
当项目中涉及依赖链上生成的“随机数”来决定关键业务结果（如抽奖、NFT mint 顺序、游戏胜负、质押奖励分配等）时，需警惕 Insecure Randomness 漏洞。该漏洞的根本成因在于区块链环境的确定性与公开性，使得任何仅依赖可预测或可被矿工/验证者操控的链上数据（如 block.timestamp、block.difficulty、blockhash 等）生成的“随机性”均不具备密码学安全性，易被攻击者提前计算或操纵。

**Early exit**  
若项目代码中完全不涉及依赖任何形式的链上随机数决定业务逻辑结果（例如：无抽奖、无随机分配、无基于随机性的游戏机制、无依赖随机种子的 NFT 属性生成等），则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在链上游戏、NFT 铸造、抽奖合约、随机奖励分配等业务逻辑实现中，包括但不限于直接使用 block.timestamp、block.difficulty、blockhash(number)、address.balance 等作为随机源的方式：  
- 区块时间戳作为随机数：使用 block.timestamp 作为随机种子，矿工可在小范围内操纵时间戳影响随机结果，详见：[Solidity_BlockTimestampAsRandom.md](Solidity_BlockTimestampAsRandom.md)  
- Blockhash 操纵：使用 blockhash 作为随机源，矿工可通过丢弃不利区块操纵结果，详见：[Solidity_BlockhashManipulation.md](Solidity_BlockhashManipulation.md)  
- Commit-Reveal 绕过：实现 commit-reveal 模式但存在漏洞，允许攻击者预测或操纵最终随机值，详见：[Solidity_CommitRevealBypass.md](Solidity_CommitRevealBypass.md)  

**Rust (e.g., Solana programs)**  
常出现在基于 Solana 的链上游戏或随机分配逻辑中，包括但不限于依赖 Clock::get().unix_timestamp、recent_blockhashes 或交易签名作为伪随机源的方式：  
- 时钟时间戳作为随机数：使用 Clock 的 unix_timestamp 作为随机种子，验证者可操纵出块时间影响随机性，详见：[Rust_ClockTimestampAsRandom.md](Rust_ClockTimestampAsRandom.md)  
- Blockhash 可预测性：使用 recent_blockhashes 作为随机源，但这些值对验证者可见且可预测，详见：[Rust_BlockhashPredictability.md](Rust_BlockhashPredictability.md)  

**Move (e.g., Sui/Aptos)**  
常出现在 NFT 属性随机生成、链上抽奖等场景中，包括但不限于依赖时间戳、交易哈希或对象 ID 作为随机种子的方式：  
- 基于时间戳的随机性：使用链上时间戳生成随机数，验证者可通过调整时间影响结果，详见：[Move_TimestampBasedRandomness.md](Move_TimestampBasedRandomness.md)  
- 交易哈希误用：使用交易哈希作为随机源，但交易哈希对提交者可见且可预测，详见：[Move_TransactionHashMisuse.md](Move_TransactionHashMisuse.md)  

**Vyper**  
常出现在 DeFi 奖励随机发放、游戏类合约中，包括但不限于使用 block.timestamp 或 block.prevrandao（原 difficulty）直接参与随机逻辑的方式：  
- 时间戳随机性：使用 block.timestamp 生成随机数，矿工可在容差范围内操纵，详见：[Vyper_TimestampRandomness.md](Vyper_TimestampRandomness.md)  
- Prevrandao 假设：依赖 prevrandao 作为随机源但未充分理解其可预测性和可操纵性，详见：[Vyper_PrevrandaoAssumption.md](Vyper_PrevrandaoAssumption.md)  

**Go (e.g., Cosmos SDK-based chains)**  
常出现在基于 Cosmos SDK 构建的链上应用中，若其 keeper 或 handler 逻辑依赖区块头字段（如 time、height）或未经验证的外部输入生成"随机性"，可能导致 Insecure Randomness：  
- 区块时间随机性：使用 BlockTime 或 BlockHeight 作为随机源，验证者可通过调整出块影响随机结果，详见：[Go_BlockTimeRandomness.md](Go_BlockTimeRandomness.md)  
- 未验证的熵源：使用外部输入或消息内容作为随机源但未验证其不可预测性，详见：[Go_UnverifiedEntropySource.md](Go_UnverifiedEntropySource.md)