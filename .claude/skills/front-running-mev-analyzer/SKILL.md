---
name: front-running-mev-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证前置交易抢跑（Front-running）和矿工可提取价值（MEV）漏洞；重点关注交易排序依赖、内存池可见性、价格发现机制等安全风险，包括 DEX 抢跑、竞拍抢跑、预言机 MEV、治理投票抢跑等；涵盖去中心化交易所、竞拍系统、预言机交互、随机数生成、治理投票等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Front-running / MEV (Miner/Maximal Extractable Value)**

**Attention**  
当项目涉及链上状态依赖用户提交的敏感交易（如价格、订单、竞拍、随机数等），且未对交易顺序或前置状态进行保护时，应重点审计交易逻辑是否暴露在可被外部观察并抢先执行的风险中。此类漏洞常见于去中心化交易所（DEX）、竞拍、预言机交互、随机数生成、治理投票及订单簿类业务模块。

**Early exit**  
若项目完全不涉及用户提交可被他人观察并利用的链上交易（例如仅实现静态存储、纯链下逻辑、或无状态读取功能），且无任何与交易排序、价格发现、订单撮合、时间窗口敏感逻辑相关的业务，则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在去中心化交易、流动性提供、竞拍及预言机回调等业务逻辑实现中，包括但不限于基于公开内存池的交易签名、未使用提交-揭示（commit-reveal）模式的竞拍、依赖链上时间戳或区块哈希生成随机性的机制：  
- DEX 抢跑：用户提交交易到公开内存池，MEV 机器人检测到后抢先提交高 Gas 交易在前面执行获利，详见：[Solidity_DexFrontRunning.md](Solidity_DexFrontRunning.md)  
- 竞拍抢跑：竞拍出价在内存池中可见，攻击者观察后提交更高出价抢先成交，详见：[Solidity_AuctionFrontRunning.md](Solidity_AuctionFrontRunning.md)  
- 预言机 MEV：预言机价格更新交易被 MEV 机器人检测，抢先在价格更新前后执行套利交易，详见：[Solidity_OracleMEV.md](Solidity_OracleMEV.md)  

**Rust (用于如Solana程序)**  
常出现在基于账户状态更新的金融协议、竞拍或随机选择机制中，包括但不限于未对交易执行顺序做抗抢跑设计、依赖当前slot或时钟信息进行关键决策、未引入交易混淆或延迟提交机制：  
- Solana 竞拍 MEV：竞拍程序中出价信息对验证者可见，验证者可调整交易顺序优先执行特定出价，详见：Rust_SolanaAuctionMEV.md  
- Solana 抽奖抢跑：抽奖结果依赖可预测的链上状态，攻击者通过抢跑优先提交有利交易，详见：Rust_SolanaLotteryFrontRunning.md  

**Move**  
常出现在涉及资源状态竞争的DeFi协议、治理提案投票或NFT铸造逻辑中，包括但不限于未隔离用户操作的原子性、允许公开读取待处理操作状态、或在模块中暴露可被抢先调用的公开入口函数：  
- DeFi MEV：DeFi 协议中交易意图对验证者可见，验证者可通过调整交易顺序提取 MEV，详见：Move_DefiMEV.md  
- NFT 铸造抢跑：NFT 铸造交易在内存池中可见，攻击者抢先提交交易优先铸造稀有 NFT，详见：Move_NFTMintFrontRunning.md  

**Vyper**  
常出现在AMM类交易对、治理快照或时间窗口敏感逻辑中，包括但不限于依赖block.timestamp作为唯一时间源、未使用加密承诺方案处理用户意图、或在swap或mint函数中暴露可预测状态：  
- AMM 抢跑：用户在 AMM 上提交交易，MEV 机器人检测到大额交易后抢先交易操纵价格获利，详见：Vyper_AMMFrontRunning.md  
- 治理 MEV：治理投票交易在内存池中可见，攻击者观察投票倾向后抢先投票影响结果，详见：Vyper_GovernanceMEV.md  

**Go (用于Cosmos SDK等链开发)**  
常出现在自定义交易处理逻辑、IBC跨链消息解析或链上治理模块中，包括但不限于在CheckTx/DeliverTx阶段暴露可被节点利用的排序信息、未对交易内容加密或混淆、或在状态机中引入可被外部节点预判的确定性逻辑：  
- Cosmos 交易 MEV：验证者可观察交易内容并调整交易顺序，在 CheckTx/DeliverTx 阶段提取 MEV，详见：Go_CosmosTxMEV.md  
- IBC 抢跑：跨链消息传递过程中交易意图可见，中继者或验证者可抢先执行相关操作获利，详见：Go_IBCFrontRunning.md