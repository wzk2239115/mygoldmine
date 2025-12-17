---
name: flash-loan-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证闪电贷（Flash Loan）相关漏洞；重点关注闪电贷回调逻辑、价格预言机操纵、状态变更顺序及外部调用安全性；涵盖借贷协议、AMM DEX、收益聚合器、杠杆交易等业务场景；检测价格操纵、重入攻击、清算滥用等风险；利用按编程语言组织的参考资料目录中的参考指南。
---
**Flash Loan 漏洞研判笔记**

**Attention**  
当项目涉及无需抵押即可临时借出大额资产的机制（即闪电贷）时，需重点审计其回调逻辑、价格预言机使用、状态变更顺序及外部调用安全性。此类漏洞成因通常源于协议在未验证价格合理性或未限制状态变更顺序的情况下，允许攻击者通过闪电贷操纵资产价格、流动性或内部状态，从而在单个交易中完成“借出–操纵–偿还–获利”的闭环。常见于借贷协议、AMM DEX、收益聚合器、杠杆交易等模块。

**Early exit**  
若项目代码中完全未集成任何闪电贷接口（如未实现 FlashLoanReceiver 接口、未调用主流闪电贷协议如 Aave、dYdX、Balancer 等的借贷函数，且自身未提供闪电贷功能），则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在借贷协议、价格敏感型 DeFi 产品（如 Stablecoin 铸造、杠杆挖矿、自动做市商）的业务逻辑实现中，包括但不限于未验证价格预言机数据、未对资产余额变动做限制、未采用"Checks-Effects-Interactions"模式等方式：  
- 闪电贷价格操纵：协议使用可被闪电贷操纵的价格源（如单一 DEX 即时价格），攻击者通过闪电贷操纵价格并获利，详见：[Solidity_FlashLoan_PriceManipulation.md](Solidity_FlashLoan_PriceManipulation.md)  
- 闪电贷重入：闪电贷回调中触发重入攻击，在状态更新前重复借贷或提取资产，详见：[Solidity_FlashLoan_Reentrancy.md](Solidity_FlashLoan_Reentrancy.md)  
- 清算滥用：利用闪电贷瞬间改变抵押品或债务价值，触发不合理的清算并从中获利，详见：[Solidity_FlashLoan_LiquidationAbuse.md](Solidity_FlashLoan_LiquidationAbuse.md)  

**Rust**  
常出现在基于 Solana 或类似账户模型的 DeFi 应用中，包括但不限于未校验临时资产注入对状态计算的影响、在 CPI 调用前未冻结关键状态等方式：  
- Solana 预言机滥用：在 Solana 上利用闪电贷操纵 DEX 储备量，影响依赖该储备的预言机价格，详见：[Rust_FlashLoan_SolanaOracleAbuse.md](Rust_FlashLoan_SolanaOracleAbuse.md)  
- 状态污染：闪电贷执行期间账户状态被临时修改，后续逻辑基于被污染的状态做出错误决策，详见：[Rust_FlashLoan_StatePoisoning.md](Rust_FlashLoan_StatePoisoning.md)  

**Move**
常出现在 Aptos 或 Sui 生态中的 AMM、借贷池合约中，包括但不限于未对 coin 借入/归还操作实施原子性约束、依赖可被瞬时操纵的流动性比例作为业务决策依据等方式：
- 流动性预言机利用：利用闪电贷改变 AMM 池子的流动性比例，操纵基于该比例的预言机价格，详见：[Move_FlashLoan_LiquidityOracleExploit.md](Move_FlashLoan_LiquidityOracleExploit.md)
- 无抵押借贷：闪电贷机制实现不当，允许在无抵押情况下借出资产且未确保原子性归还，详见：[Move_FlashLoan_BorrowWithoutCollateral.md](Move_FlashLoan_BorrowWithoutCollateral.md)
- 资源销毁未确认：闪电贷偿还时销毁 coin 资源但未验证销毁量与借出量的一致性，允许通过 coin 拆分绕过偿还检查，详见：[Move_FlashLoan_UnverifiedResourceBurn.md](Move_FlashLoan_UnverifiedResourceBurn.md)  

**Vyper**  
常出现在采用 Vyper 编写的 DEX 或收益协议中，包括但不限于未在外部调用前固化关键变量、未限制回调深度或可重入上下文等方式：  
- 回调重入：闪电贷回调函数中存在重入漏洞，允许在回调中再次调用借贷函数，详见：[Vyper_FlashLoan_CallbackReentrancy.md](Vyper_FlashLoan_CallbackReentrancy.md)  
- 代币余额假设：协议假设代币余额在单笔交易中不会剧烈变化，闪电贷破坏此假设导致逻辑错误，详见：[Vyper_FlashLoan_TokenBalanceAssumption.md](Vyper_FlashLoan_TokenBalanceAssumption.md)  

**Go**  
（注：Go 本身不直接用于智能合约开发，但在 Cosmos SDK 或基于 Tendermint 的链中可能实现类似闪电贷的模块逻辑）  
常出现在 Cosmos 生态的借贷或跨链桥模块中，包括但不限于在 MsgServer 处理中未验证临时资产注入后的状态一致性、未校验跨链消息与本地资产状态的同步性等方式：  
- Cosmos 借贷模块：自定义借贷模块实现闪电贷功能但未确保操作原子性，允许部分执行成功导致资金损失，详见：[Go_FlashLoan_CosmosLendingModule.md](Go_FlashLoan_CosmosLendingModule.md)  
- IBC 套利利用：利用跨链闪电贷在不同链间套利，协议未对跨链资产流动设置合理限制，详见：[Go_FlashLoan_IBCArbitrageExploit.md](Go_FlashLoan_IBCArbitrageExploit.md)