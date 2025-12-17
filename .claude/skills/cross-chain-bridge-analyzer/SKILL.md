---
name: cross-chain-bridge-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证跨链桥接（Cross-Chain Bridge）漏洞；重点关注跨链消息验证、签名校验、资产映射及中继机制的实现，包括跨链消息来源验证不足、伪造中继请求、重放攻击、状态映射逻辑缺陷等；涵盖桥接合约、中继器逻辑、预言机接口、资产锁定/铸造模块等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Cross-Chain Bridge 漏洞研判笔记**

---

**Attention**  
当项目涉及跨链资产转移、消息传递或状态同步功能时，需重点审计桥接协议中对源链与目标链间数据验证、签名校验、资产映射及中继机制的实现。此类漏洞通常源于对跨链消息来源的验证不足、伪造中继请求、重放攻击或状态映射逻辑缺陷，常见于桥接合约、中继器逻辑、预言机接口及资产锁定/铸造模块。

**Early exit**  
若项目代码库中完全不包含跨链通信逻辑（如无桥接合约、无第三方桥集成、无跨链消息处理函数、无与 Chainlink CCIP/LayerZero/IBC/Hyperlane 等跨链框架的交互），且业务范围严格限定于单一链内操作，则可快速退出对该漏洞类型的审计。

---

**Cases**

**Solidity**  
常出现在跨链资产桥接、通用消息传递或 NFT 跨链迁移功能中，包括但不限于轻客户端验证缺失、中继签名未绑定 nonce、源链事件解析逻辑可绕过等方式：  
- 跨链签名绕过：跨链消息签名验证逻辑存在漏洞，允许伪造签名通过验证，详见：[Solidity_CrossChainSignatureBypass.md](Solidity_CrossChainSignatureBypass.md)  
- 中继器重放攻击：中继消息未包含唯一标识，允许同一消息被重复提交执行，详见：[Solidity_RelayerReplayAttack.md](Solidity_RelayerReplayAttack.md)  
- 资产映射逻辑缺陷：源链和目标链资产映射关系错误，导致资产铸造或锁定异常，详见：[Solidity_AssetMappingLogicFlaw.md](Solidity_AssetMappingLogicFlaw.md)  

**Rust**  
常出现在基于 Substrate 或 Solana 的跨链中继器、状态验证器或桥接 pallet 实现中，包括但不限于未校验跨链消息来源链的共识状态、跨链调用上下文未隔离、外部账户伪造等方式：  
- 不安全的轻客户端验证：轻客户端验证逻辑不完整，允许伪造的区块头或状态证明通过，详见：[Rust_InsecureLightClientVerification.md](Rust_InsecureLightClientVerification.md)  
- 跨链调用上下文泄露：跨链调用时执行上下文未正确隔离，导致权限泄露或状态污染，详见：[Rust_CrossChainCallContextLeak.md](Rust_CrossChainCallContextLeak.md)  
- 伪造来源账户：跨链消息的来源账户未正确验证，允许攻击者伪造身份，详见：[Rust_ForgedOriginAccount.md](Rust_ForgedOriginAccount.md)  

**Move**  
常出现在基于 Aptos 或 Sui 的跨链资产托管与铸造逻辑中，包括但不限于未验证远程链的事件证明、资源状态映射未原子化、跨链操作权限未限制等方式：  
- 未验证远程事件证明：接受跨链事件但未验证其在源链上的有效性证明，允许伪造事件，详见：[Move_UnverifiedRemoteEventProof.md](Move_UnverifiedRemoteEventProof.md)  
- 非原子桥接状态更新：跨链桥状态更新操作非原子性，部分失败导致资产卡在中间状态，详见：[Move_NonAtomicBridgeStateUpdate.md](Move_NonAtomicBridgeStateUpdate.md)  
- 无限制跨链铸造：跨链资产铸造未限制权限或额度，允许无限制铸币，详见：[Move_UnrestrictedCrossChainMint.md](Move_UnrestrictedCrossChainMint.md)  

**Vyper**  
常出现在简化版跨链锁定/释放合约或预言机驱动的桥接逻辑中，包括但不限于事件日志解析可被操控、目标链未验证源链区块头、跨链操作无速率限制等方式：  
- 桥接中的事件日志欺骗：解析跨链事件日志时未充分验证，允许伪造日志触发错误铸造，详见：Vyper_EvLogSpoofingInBridge.md  
- 缺失源区块头检查：目标链未验证源链区块头有效性，接受未确认或伪造的跨链消息，详见：Vyper_MissingSourceBlockHeaderCheck.md  
- 无限制跨链提取：跨链资产提取未设置速率限制或单笔上限，可能被快速耗尽，详见：Vyper_UnthrottledCrossChainWithdraw.md  

**Go**  
常出现在链下中继服务、跨链监听器或桥接守护进程（bridge daemon）的实现中，包括但不限于未校验交易真实性即转发消息、跨链请求序列号可重放、签名验证逻辑存在旁路等方式：  
- 中继器消息伪造无验证：中继器转发跨链消息前未验证其真实性，允许注入虚假消息，详见：Go_RelayerMsgForgeryWithoutValidation.md  
- 可重放跨链序列号：跨链消息序列号未正确跟踪，允许重放已处理的消息，详见：Go_ReplayableCrossChainSequence.md  
- 守护服务签名绕过：桥接守护进程的签名验证逻辑存在绕过路径，允许未授权操作，详见：Go_SignatureBypassInGuardianService.md