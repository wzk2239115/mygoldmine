---
name: unchecked-calls-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证未检查外部调用（Unchecked Calls）漏洞；重点关注外部合约调用、低层级调用（如call、delegatecall）、跨程序调用（CPI）等场景中未验证返回值或执行状态的问题，包括代币转账、预言机回调、桥接交互等业务场景；涵盖状态不一致、资金丢失、逻辑绕过等风险；利用按编程语言组织的参考资料目录中的参考指南。
---
**Unchecked Calls**

**Attention**  
当项目中存在对外部合约或低层级调用（如 Solidity 的 `call`、Rust 的 `external_call`、Move 的 `native` 调用等）且未对返回值或执行状态进行验证时，需重点审计。此类漏洞通常出现在与跨合约交互、代币转账、预言机回调、桥接交互等涉及外部调用的业务模块中，若调用失败未被检测，可能导致状态不一致、资金丢失或逻辑绕过。

**Early exit**  
若项目代码完全不涉及任何外部合约调用、低层级调用或跨模块/跨链交互（例如纯内部状态机、无外部依赖的静态计算逻辑），则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在代币转账、跨合约委托调用、预言机响应处理等功能中，包括但不限于使用 `.call()`, `.send()`, `.transfer()` 或 `delegatecall` 时忽略返回值：  
- 未检查低层级调用：使用 call/staticcall/delegatecall 进行外部调用但未检查返回的布尔值，导致调用失败被忽略，详见：[Solidity_UncheckedLowLevelCall.md](Solidity_UncheckedLowLevelCall.md)  
- 忽略转账结果：使用 send 或 call 进行以太币转账但未验证返回值，导致转账失败时状态未回滚，详见：[Solidity_IgnoredTransferResult.md](Solidity_IgnoredTransferResult.md)  
- 预言机回调失败：调用预言机合约或处理回调时未检查执行结果，导致数据获取失败但业务逻辑继续执行，详见：[Solidity_FailedOracleCallback.md](Solidity_FailedOracleCallback.md)

**Rust**（适用于 Solana 或 Substrate 框架）  
常出现在跨程序调用（CPI）或账户交互逻辑中，包括但不限于使用 `invoke`, `invoke_signed` 时未检查 `Result`：  
- 未检查 CPI 结果：跨程序调用（invoke/invoke_signed）后未检查返回的 Result，导致调用失败被静默忽略，详见：[Rust_UncheckedCPI.md](Rust_UncheckedCPI.md)  
- 忽略指令执行结果：处理指令或账户操作时未验证执行状态，导致部分失败时整体逻辑仍继续，详见：[Rust_IgnoredInstructionResult.md](Rust_IgnoredInstructionResult.md)

**Move**  
常出现在与外部模块交互或使用 `native` 函数调用系统资源时，包括但不限于调用 `coin::transfer`、`aptos_framework` 中的跨账户操作未验证执行结果：  
- 未检查外部转账：调用外部模块的转账函数但未检查返回值或异常，导致转账失败时状态不一致，详见：[Move_UncheckedExternalTransfer.md](Move_UncheckedExternalTransfer.md)  
- 忽略 Native 调用结果：使用 native 函数与底层系统交互时未处理可能的错误返回，导致系统调用失败被忽略，详见：[Move_IgnoredNativeCallResult.md](Move_IgnoredNativeCallResult.md)

**Vyper**  
常出现在使用 `raw_call` 或调用外部合约接口时未验证返回布尔值或状态码，包括但不限于桥接逻辑或动态调用场景：  
- 未检查 raw_call：使用 raw_call 进行动态调用但未检查返回的成功标志，导致调用失败被忽略，详见：[Vyper_UncheckedRawCall.md](Vyper_UncheckedRawCall.md)

**Go**（适用于 Cosmos SDK 或其他区块链中间件）  
常出现在 ABCI 调用、跨模块消息传递（如 IBC）或调用外部 keeper 方法时忽略错误返回，包括但不限于 `SendCoins`, `CallContract`, `ExecuteMsg` 等操作未处理 error：  
- 未检查 Keeper 调用：调用 Keeper 方法执行链上操作但未检查返回的 error，导致操作失败被静默忽略，详见：[Go_UncheckedKeeperCall.md](Go_UncheckedKeeperCall.md)  
- 忽略 IBC 响应：处理跨链 IBC 消息时未验证响应状态或错误码，导致跨链操作失败时状态不同步，详见：[Go_IgnoredIBCResponse.md](Go_IgnoredIBCResponse.md)