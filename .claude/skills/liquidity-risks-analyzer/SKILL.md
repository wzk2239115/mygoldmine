---
name: liquidity-risks-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证流动性风险（Liquidity Risks）漏洞；重点关注流动性池、AMM、质押、借贷等金融原语的流动性管理机制，包括流动性不足、单边流动性注入/撤出、流动性比例计算错误、滑点控制缺失等；涵盖流动性提供与移除、兑换池、质押收益池等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Liquidity Risks – 研判笔记**

---

**Attention**  
当项目涉及流动性池（Liquidity Pool）、自动做市商（AMM）、质押（Staking）、借贷（Lending/Borrowing）或代币兑换（Swap）等金融原语时，需重点审计其流动性管理机制。此类漏洞通常源于流动性不足、单边流动性注入/撤出、价格预言机失真、滑点控制缺失或流动性锁定机制薄弱，导致用户无法正常兑付、价格剧烈波动或协议资不抵债。

**Early exit**  
若项目代码不包含任何流动性提供、兑换、质押、借贷或资金池相关逻辑（例如仅为治理合约、纯 NFT 铸造或静态数据记录合约），则可快速退出对该漏洞类型的审计。

---

**Cases**

**Solidity**  
常出现在 AMM 兑换、流动性提供与移除、单边质押收益池等业务逻辑实现中，包括但不限于流动性比例计算错误、未限制最小流动性阈值、移除流动性时未校验池状态等方式：  
- 流动性耗尽：流动性池设计缺陷允许流动性被单方面大量提取，导致池子枯竭无法正常运作，详见：[Solidity_LiquidityDrain.md](Solidity_LiquidityDrain.md)  
- 无常损失利用：AMM 机制设计不当，攻击者通过特定操作放大流动性提供者的无常损失，详见：[Solidity_ImpermanentLossExploit.md](Solidity_ImpermanentLossExploit.md)  
- 不平衡流动性提取：允许不按比例提取流动性，破坏池子平衡导致价格扭曲，详见：[Solidity_UnbalancedLiquidityWithdrawal.md](Solidity_UnbalancedLiquidityWithdrawal.md)  

**Rust**（适用于 Solana、Sealevel 环境）  
常出现在基于账户模型的流动性池、质押池或跨链桥资金池实现中，包括但不限于未校验池余额变动、未限制单次流动性提取上限、未强制同步价格状态等方式：  
- 流动性池下溢：流动性提取计算错误或未校验，导致账户余额下溢，详见：[Rust_LiquidityPoolUnderflow.md](Rust_LiquidityPoolUnderflow.md)  
- 未检查流动性销毁：LP 代币销毁时未验证对应的流动性是否充足，允许过度提取，详见：[Rust_UncheckedLiquidityBurn.md](Rust_UncheckedLiquidityBurn.md)  

**Move**（适用于 Aptos、Sui）
常出现在资源型流动性池（如 coin swap pool）或共享资金库实现中，包括但不限于未正确管理 pooled_coin 资源、未在 withdraw 时验证 reserve ratio、允许零流动性状态持续运行等方式：
- 流动性储备耗尽：流动性池储备可被完全提取，导致池子无法继续提供服务，详见：[Move_LiquidityReserveDrain.md](Move_LiquidityReserveDrain.md)
- 池资源不一致：流动性池中的资源状态与实际储备不匹配，导致提取或兑换失败，详见：[Move_PoolResourceInconsistency.md](Move_PoolResourceInconsistency.md)
- LP代币精度漏洞：流动性凭证（LP代币）的小数精度设置不当，大额流动性操作时产生舍入误差，允许攻击者通过复数次操作积累误差盗取流动性，详见：[Move_LPTokenPrecisionExploit.md](Move_LPTokenPrecisionExploit.md)  

**Vyper**  
常出现在去中心化交易所（DEX）或收益聚合器的流动性管理模块中，包括但不限于未使用 safe math 处理池余额、未校验 slippage tolerance、允许在极端价格下执行 swap 等方式：  
- 滑点绕过流动性：未设置合理滑点保护，极端价格波动时流动性被快速消耗，详见：[Vyper_SlippageBypassLiquidity.md](Vyper_SlippageBypassLiquidity.md)  
- 零流动性重入：流动性为零时未暂停操作，允许重入攻击在空池状态下执行，详见：[Vyper_ZeroLiquidityReentrancy.md](Vyper_ZeroLiquidityReentrancy.md)  

**Go**（适用于 Cosmos SDK、IBC 中继器或链下流动性服务）  
常出现在链下流动性协调器、跨链流动性提供模块或质押衍生品后台服务中，包括但不限于未同步链上流动性状态、未设置流动性健康检查、错误估算可提取额度等方式：  
- 流动性状态失步：链下服务与链上流动性状态不同步，导致过度承诺或提取失败，详见：[Go_LiquidityStateDesync.md](Go_LiquidityStateDesync.md)  
- 跨链流动性错误报价：跨链流动性桥报价与实际可用流动性不符，导致跨链交易失败或卡住，详见：[Go_CrossChainLiquidityMisquote.md](Go_CrossChainLiquidityMisquote.md)