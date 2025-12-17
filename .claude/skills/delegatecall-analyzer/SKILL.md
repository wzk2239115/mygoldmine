---
name: delegatecall-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 Delegatecall 漏洞；重点关注 delegatecall 调用目标地址的可控性、代理合约初始化安全、逻辑委托执行的权限校验等；涵盖代理模式（UUPS、Transparent Proxy）、模块化架构、插件系统、可升级逻辑合约等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---

**Delegatecall**

**Attention**  
当项目使用 delegatecall 指令调用外部或用户可控地址的合约时，需高度警惕。该机制会将目标合约代码在调用者上下文中执行，若目标地址或逻辑未被严格约束，可能导致执行恶意代码、状态变量被覆写或权限被劫持。此类漏洞常见于代理模式（如 UUPS、Transparent Proxy）、模块化合约架构、插件系统或可升级逻辑合约中。

**Early exit**  
若项目代码中完全未使用 delegatecall（或等效机制，如 Solidity 的 delegatecall、EVM 汇编中的 DELEGATECALL 操作码，或 Rust/Move/Go 中对应 EVM/WASM/MoveVM 的底层调用接口），且无代理、模块热插拔、逻辑委托加载等设计，则可快速退出对 Delegatecall 类漏洞的审计。

**Cases**

**Solidity**  
常出现在可升级合约、中心化逻辑路由器、插件化治理模块等业务逻辑实现中，包括但不限于 UUPS 代理升级、自定义 fallback 转发器、权限委托执行器等方式：  
- Delegatecall 调用用户可控地址：delegatecall 的目标地址由用户输入或未受限变量决定，允许执行任意恶意代码，详见：[Solidity_DelegatecallToUserControlledAddress.md](Solidity_DelegatecallToUserControlledAddress.md)  
- 代理初始化不当：代理合约初始化逻辑存在漏洞，允许攻击者劫持代理或逻辑合约的控制权，详见：[Solidity_ImproperProxyInitialization.md](Solidity_ImproperProxyInitialization.md)  
- 路由器中未检查 Delegatecall：逻辑路由器使用 delegatecall 转发调用但未验证目标合约合法性，导致恶意逻辑被执行，详见：[Solidity_UncheckedDelegatecallInRouter.md](Solidity_UncheckedDelegatecallInRouter.md)  

**Rust**（针对 EVM 或 WASM 智能合约运行环境，如 Solana/ArbOS/EVM 兼容链的 Rust 合约）
常出现在跨合约调用、模块化逻辑加载或链上代码动态分发功能中，包括但不限于通过 invoke_call 指定 callee 并复用调用者上下文的方式：
- WASM 中的 Delegate Call 等效操作：在 WASM 环境中使用类似 delegatecall 的机制但未验证目标，导致上下文被污染，详见：[Rust_DelegateCallEquivalentInWASM.md](Rust_DelegateCallEquivalentInWASM.md)
- 未验证的动态逻辑加载：动态加载并执行外部逻辑模块但未验证来源，允许恶意代码在调用者上下文中执行，详见：[Rust_DynamicLogicLoadingWithoutValidation.md](Rust_DynamicLogicLoadingWithoutValidation.md)
- Solana CPI 权限上下文混淆：在跨程序调用（CPI）中复用调用者的账户权限上下文但未隔离，允许被调用程序访问或修改原本不授权的账户状态，详见：[Rust_SolanaCPIContextConfusion.md](Rust_SolanaCPIContextConfusion.md)  

**Move**  
常出现在能力委托、模块组合复用或动态资源操作场景中，包括但不限于通过 call 或 dynamic_dispatch 调用未验证来源的模块函数，导致执行上下文混淆：  
- 不安全的动态模块调用：通过动态分发调用外部模块但未验证模块身份，导致恶意模块在调用者上下文中执行，详见：[Move_UnsafeDynamicModuleCall.md](Move_UnsafeDynamicModuleCall.md)  
- 无作用域检查的 Capability 委托：Capability 对象被委托给外部模块但未限制其使用范围，导致权限滥用，详见：[Move_CapabilityDelegationWithoutScopeCheck.md](Move_CapabilityDelegationWithoutScopeCheck.md)  

**Vyper**  
常出现在自定义代理或逻辑分发器实现中，包括但不限于使用 raw_delegatecall 调用外部地址，且未对目标地址做白名单或完整性校验：  
- Raw_delegatecall 调用不可信地址：使用 raw_delegatecall 调用未经验证的外部地址，允许恶意代码在当前合约上下文中执行，详见：[Vyper_RawDelegatecallToUntrustedAddress.md](Vyper_RawDelegatecallToUntrustedAddress.md)  

**Go**（特指基于 Cosmos SDK 或类似框架开发的 WASM 合约或链上模块）  
常出现在链上可配置逻辑执行器、跨合约消息传递（如 CosmWasm 的 reply/execute 回调）等场景，若未验证目标合约身份或未隔离执行环境，可能引发上下文污染：  
- 未验证的 WASM 回调委托：WASM 合约间回调未验证目标合约身份，允许恶意合约在发起方上下文中执行，详见：[Go_UnverifiedWASMCallbackDelegate.md](Go_UnverifiedWASMCallbackDelegate.md)