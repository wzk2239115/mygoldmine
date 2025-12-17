---
name: reentrancy-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证重入攻击（Reentrancy）漏洞；重点关注外部合约调用与状态更新的执行顺序，包括状态更新滞后、重入锁缺失、跨合约回调风险等；涵盖资金提取、代币转账、跨合约交互、回调处理等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
当项目涉及外部合约调用（如调用用户提供的地址或接口）并在调用后才更新内部状态（如余额、权限、计数等）时，需重点审计是否可能被恶意合约利用递归调用反复进入函数，从而绕过状态检查、重复提取资产或执行逻辑。此类漏洞常见于资金提取、授权转移、跨合约交互等业务模块。

**Early exit**
若项目代码中完全不包含对外部地址的调用（如 call、delegatecall、transfer 等低层或高层调用），且所有状态变更均在外部交互前完成，则可快速排除重入漏洞风险，结束对该类型漏洞的审计。

**Cases**  

**Solidity**  
常出现在资金提取、跨合约交互、回调处理等业务逻辑实现中，包括但不限于 withdraw、transfer、fallback/receive 函数、ERC777 回调、自定义钩子（hook）等实现方式：  
- 提取函数重入：资金提取函数在更新余额前进行外部调用，允许恶意合约递归调用重复提取资金，详见：[Solidity_WithdrawReentrancy.md](Solidity_WithdrawReentrancy.md)  
- 回调重入：使用回调机制（如 ERC777 hooks）时未防护重入，允许接收方在回调中再次调用合约函数，详见：[Solidity_CallbackReentrancy.md](Solidity_CallbackReentrancy.md)  
- 跨合约重入：多合约交互场景中，合约A调用合约B，B又回调A，导致状态检查被绕过，详见：[Solidity_CrossContractReentrancy.md](Solidity_CrossContractReentrancy.md)  

**Rust (with ink! or Solana programs)**  
常出现在涉及跨账户调用（invoke_signed、invoke、external call）或 CPI（Cross-Program Invocation）的业务逻辑中，包括但不限于代币提取、委托授权、多签操作等实现方式：  
- CPI 重入：跨程序调用时未遵循 Checks-Effects-Interactions 模式，被调用程序可再次调用发起方导致重入，详见：[Rust_CPIReentrancy.md](Rust_CPIReentrancy.md)  
- 外部调用重入：外部合约调用返回前状态未更新，允许被调用方在回调中利用旧状态重复操作，详见：[Rust_ExternalCallReentrancy.md](Rust_ExternalCallReentrancy.md)  

**Move**  
常出现在跨模块调用或资源转移逻辑中，尤其在涉及 capability 或 witness 模式下对外部脚本或模块的回调处理时，包括但不限于 withdraw、unstake、flash_loan 等场景：  
- 资源重入：资源转移过程中调用外部模块，外部模块可利用执行上下文中的未完成状态发起重入攻击，详见：[Move_ResourceReentrancy.md](Move_ResourceReentrancy.md)  

**Vyper**
常出现在使用 raw_call 或调用外部接口的 withdraw、swap、flash loan 等逻辑中，包括但不限于未使用重入锁或状态检查顺序不当的实现方式：
- Raw_call 重入：使用 raw_call 进行外部调用时未设置重入保护，允许被调用合约在返回前再次调用发起合约，详见：[Vyper_RawCallReentrancy.md](Vyper_RawCallReentrancy.md)

**Go**（适用于 Cosmos SDK、Substrate 和其他基于 Go 的链）
常出现在 Keeper 方法调用、IBC 消息处理、BeginBlocker/EndBlocker 回调、跨链转账等业务逻辑实现中，包括但不限于未保护的 Keeper 间调用、IBC 回调中的状态变更未原子性、临时账户状态污染等方式：
- Keeper 回调重入：Keeper 方法未防止重入，在执行过程中调用其他 Keeper 允许重入攻击，导致账户余额被多次扣减或权限被绕过，详见：[Go_KeeperCallbackReentrancy.md](Go_KeeperCallbackReentrancy.md)
- IBC 消息处理重入：IBC 模块处理跨链消息时在状态未确认前触发回调，攻击者可通过回调在状态不一致时发起重入，导致资产错误转移或协议状态破坏，详见：[Go_IBCMessageHandlerReentrancy.md](Go_IBCMessageHandlerReentrancy.md)
- 银行模块转账重入：bank Keeper 的 SendCoins/BurnCoins 调用在触发钩子时未防护重入，允许在转账过程中重新进入转账逻辑，详见：[Go_BankKeeperTransferReentrancy.md](Go_BankKeeperTransferReentrancy.md)  