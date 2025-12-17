---
name: dos-attacks-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证拒绝服务（DoS Attacks）漏洞；重点关注可能导致合约无法正常执行的机制，包括无界循环、外部调用依赖、资源耗尽、数组增长等风险；涵盖批量处理、治理投票、奖励分发、清算机制、回调处理等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**DoS Attacks**

**Attention**  
当项目中存在依赖外部调用、循环操作、资源消耗型逻辑或对用户输入/状态数量无限制的处理机制时，需警惕拒绝服务（DoS）风险。此类漏洞通常源于未对操作复杂度、Gas 消耗、迭代次数或外部调用失败情形进行合理约束，常见于批量处理、治理投票、奖励分发、清算机制、回调处理等模块。

**Early exit**  
若项目代码中完全不涉及循环结构、外部调用（如 call、delegatecall、transfer）、批量操作、状态依赖型条件判断，且所有函数均为常量时间复杂度（O(1)）且不依赖未受限制的用户输入数量，则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在批量转账、奖励分发、治理投票、清算回调等业务逻辑实现中，包括但不限于无上限循环、依赖外部调用结果推进状态、未限制数组长度等方式：  
- 无界循环：迭代用户可控数量的元素但未设上限，导致 Gas 消耗超限使交易失败，详见：[Solidity_UnboundedLoop.md](Solidity_UnboundedLoop.md)  
- 外部调用 DoS：依赖外部调用成功才能继续执行，恶意合约可通过 revert 阻止整个流程，详见：[Solidity_ExternalCallDoS.md](Solidity_ExternalCallDoS.md)  
- 数组增长 DoS：数组无限增长但遍历时未分页，导致 Gas 消耗超出区块上限，详见：[Solidity_ArrayGrowthDoS.md](Solidity_ArrayGrowthDoS.md)  

**Rust (针对 Solana/EVM-compatible chains)**  
常出现在账户状态批量更新、指令处理循环、PDA 操作等业务逻辑实现中，包括但不限于未限制账户数量、未对计算复杂度做上限约束等方式：  
- 无界迭代：指令处理中迭代账户或数据结构但未设上限，导致计算单元（CU）耗尽交易失败，详见：[Rust_UnboundedIteration.md](Rust_UnboundedIteration.md)  
- 账户枚举 DoS：需要遍历大量账户但未分批处理，攻击者可通过创建大量账户使操作无法完成，详见：[Rust_AccountEnumerationDoS.md](Rust_AccountEnumerationDoS.md)  

**Move**  
常出现在资源批量销毁、表（Table）遍历、事件触发等业务逻辑实现中，包括但不限于对全局状态无限制遍历、未校验输入规模等方式：  
- 表迭代 DoS：遍历 Table 或全局存储但未限制迭代次数，导致 Gas 超限交易失败，详见：[Move_TableIterationDoS.md](Move_TableIterationDoS.md)  
- 资源销毁 DoS：批量销毁资源但未分批处理，单次操作消耗过多 Gas 导致失败，详见：[Move_ResourceDestructionDoS.md](Move_ResourceDestructionDoS.md)  

**Vyper**  
常出现在类似 Solidity 的批量处理或回调场景中，包括但不限于 for 循环遍历用户列表、transfer 触发 revert 传播等方式：  
- 无界 for 循环：使用 for 循环处理用户列表但未限制长度，导致 Gas 消耗超限，详见：[Vyper_UnboundedForLoop.md](Vyper_UnboundedForLoop.md)  
- 转账 Revert DoS：批量转账时单个失败导致所有转账回滚，恶意用户可故意触发失败阻止分发，详见：[Vyper_TransferRevertDoS.md](Vyper_TransferRevertDoS.md)  

**Go (针对 Cosmos SDK 或其他 Go-based 链)**  
常出现在 BeginBlocker/EndBlocker 钩子、keeper 批量处理、IBC 回调等业务逻辑实现中，包括但不限于未分页处理状态迭代、未限制请求负载大小等方式：  
- 未分页迭代 DoS：遍历链上存储但未使用分页，数据量过大时导致区块处理超时或节点崩溃，详见：[Go_UnpagedIterationDoS.md](Go_UnpagedIterationDoS.md)  
- 重 BeginBlocker：BeginBlocker 中执行复杂计算或大量状态变更，导致区块生成延迟或失败，详见：[Go_HeavyBeginBlocker.md](Go_HeavyBeginBlocker.md)