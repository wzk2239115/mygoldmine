---
name: gas-optimization-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和优化Gas消耗（Gas Optimization）问题；重点关注链上状态读写、冗余计算、循环优化、数据结构效率等；涵盖状态变量缓存、calldata使用、存储布局、批量操作等优化场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Gas Optimization**

**Attention**  
当项目中存在频繁的链上状态读写、冗余计算、未优化的循环或数据结构操作时，应仔细审计相关代码。这类问题通常出现在核心业务逻辑模块（如资产转账、收益分配、质押/解质押、治理投票等）中，尤其在涉及用户批量操作或高频调用路径时更易暴露 Gas 使用低效问题。

**Early exit**  
如果项目为纯链下逻辑实现（如仅依赖预言机回调中继、无用户直接调用的链上合约）或合约仅作为静态数据容器（无状态变更、无复杂计算），且不涉及任何用户交易触发的链上执行逻辑，则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在资产分发、费用收取、用户奖励计算、批量操作等功能/业务逻辑实现中，包括但不限于未缓存状态变量、冗余的 require 检查、低效的数组遍历、未使用 calldata、未合并存储写入等方式：  
- 不必要的存储读取：多次读取同一状态变量但未缓存到内存，导致重复的昂贵 SLOAD 操作，详见：[Solidity_UnnecessaryStorageRead.md](Solidity_UnnecessaryStorageRead.md)  
- 低效循环：循环中包含冗余操作或未优化的存储访问，导致 Gas 消耗线性或指数增长，详见：[Solidity_InefficientLoop.md](Solidity_InefficientLoop.md)  
- 缺失 calldata：函数参数使用 memory 而非 calldata，增加不必要的数据复制开销，详见：[Solidity_MissingCalldata.md](Solidity_MissingCalldata.md)  
- 冗余检查：重复的条件检查或 require 语句，浪费 Gas 且降低代码可读性，详见：[Solidity_RedundantChecks.md](Solidity_RedundantChecks.md)  

**Rust**（针对 Solana 程序）  
常出现在账户状态更新、代币铸造/销毁、权限验证等业务逻辑实现中，包括但不限于重复反序列化账户数据、未复用中间计算结果、过度使用动态分配等方式：  
- 冗余反序列化：多次反序列化同一账户数据但未缓存，浪费计算单元（CU），详见：[Rust_RedundantDeserialize.md](Rust_RedundantDeserialize.md)  
- 未优化计算：复杂计算未缓存中间结果，导致重复计算浪费 CU，详见：[Rust_UnoptimizedComputation.md](Rust_UnoptimizedComputation.md)  
- 过度堆分配：频繁使用动态内存分配而非栈分配，增加内存开销和 CU 消耗，详见：[Rust_ExcessiveHeapAllocation.md](Rust_ExcessiveHeapAllocation.md)  

**Move**  
常出现在资源转移、能力（capability）管理、模块初始化等业务逻辑实现中，包括但不限于重复借用全局存储、未内联简单函数、过度使用 vector 操作等方式：  
- 冗余 borrow_global：多次借用同一全局资源但未缓存引用，增加不必要的访问开销，详见：[Move_RedundantBorrowGlobal.md](Move_RedundantBorrowGlobal.md)  
- 不必要的 Vector 操作：使用低效的 vector 操作（如频繁 push/pop）而非更高效的数据结构，详见：[Move_UnnecessaryVectorOps.md](Move_UnnecessaryVectorOps.md)  
- 错失内联：简单函数未标记为 inline，增加函数调用开销，详见：[Move_MissedInlining.md](Move_MissedInlining.md)  

**Vyper**  
常出现在代币授权、治理提案执行、收益再投资等业务逻辑实现中，包括但不限于未利用内存变量缓存、低效的事件触发、未精简条件分支等方式：  
- 缺失内存缓存：未使用内存变量缓存存储值，导致重复的昂贵存储读取操作，详见：[Vyper_MissingMemoryCaching.md](Vyper_MissingMemoryCaching.md)  
- 过度事件触发：在循环或高频调用中触发不必要的事件，增加 Gas 消耗，详见：[Vyper_ExcessiveEventEmission.md](Vyper_ExcessiveEventEmission.md)  
- 未优化分支：条件分支未按概率优化顺序，常见路径执行更多检查，详见：[Vyper_UnoptimizedBranching.md](Vyper_UnoptimizedBranching.md)  

**Go**（针对 CosmWasm 合约）  
常出现在 querier 调用、状态迁移、跨合约通信等业务逻辑实现中，包括但不限于重复查询链上状态、未复用上下文对象、过度序列化中间结构等方式：  
- 冗余 Querier 调用：多次查询相同的链上数据但未缓存结果，增加查询开销，详见：[Go_RedundantQuerierCall.md](Go_RedundantQuerierCall.md)  
- 不必要的序列化：频繁序列化/反序列化中间数据结构，增加计算和内存开销，详见：[Go_UnnecessarySerialization.md](Go_UnnecessarySerialization.md)  
- Context 未复用：每次操作都创建新的 context 对象而非复用，增加分配开销，详见：[Go_ContextNotReused.md](Go_ContextNotReused.md)