---
name: signature-verification-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证签名验证（Signature Verification）漏洞；重点关注链下签名验证机制的安全性，包括签名重放、未绑定业务上下文、签名验证逻辑绕过、签名结构解析错误等；涵盖授权模块、跨链桥、治理投票、访问控制等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Signature Verification**

**Attention**  
当项目涉及链下签名验证、授权委托、身份认证或跨链消息验证等业务逻辑时，需特别关注签名验证实现是否正确。此类漏洞通常源于签名重放、未绑定业务上下文（如缺少 nonce 或 chainId）、签名验证逻辑绕过或对签名结构解析错误，常见于授权模块、跨链桥、治理投票及访问控制组件中。

**Early exit**  
若项目代码中完全未使用任何链下签名机制（例如无 EIP-712、ECDSA、EdDSA 等签名验证逻辑，亦无涉及外部签名输入的身份验证或授权流程），则可快速退出对该漏洞类型的审计。

**Cases**  

**Solidity**  
常出现在授权委托、跨链消息验证、治理投票等业务逻辑实现中，包括但不限于未校验 chainId、缺少 nonce 防重放、签名可重用、未验证 signer 地址合法性等方式：  
- 签名重放攻击：签名消息未包含唯一标识（如 nonce），允许攻击者在不同上下文重复使用同一签名，详见：[Solidity_SignatureReplay.md](Solidity_SignatureReplay.md)  
- 缺失 ChainId 检查：签名未绑定链 ID，允许跨链重放攻击，详见：[Solidity_MissingChainIdCheck.md](Solidity_MissingChainIdCheck.md)  
- 签名者上下文未绑定：签名消息未包含完整业务上下文（如合约地址、操作类型），导致签名可被用于非预期场景，详见：[Solidity_UnboundSignerContext.md](Solidity_UnboundSignerContext.md)  

**Rust**  
常出现在基于 Substrate 或 Solana 的链下授权、账户代理、跨链通信等业务逻辑实现中，包括但不限于未验证签名者身份、签名上下文未绑定交易参数、签名可重放等方式：  
- 签名上下文绑定：签名消息未绑定具体交易参数或操作上下文，允许签名被用于其他操作，详见：Rust_SignatureContextBinding.md  
- 可重放签名：签名验证逻辑未防止重放，同一签名可被多次使用，详见：Rust_ReplayableSignature.md  
- 弱签名者验证：签名者身份验证逻辑不完整或可被绕过，允许未授权操作，详见：Rust_WeakSignerValidation.md  

**Move**  
常出现在 Aptos 或 Sui 链上的资源授权、跨账户操作、模块权限控制等业务逻辑实现中，包括但不限于直接信任外部签名而未校验 message digest、未使用 Move 提供的 auth 合约原语、签名与调用参数脱钩等方式：  
- 未验证外部签名：直接信任外部传入的签名但未验证其真实性和有效性，详见：Move_UnverifiedExternalSignature.md  
- 签名未绑定摘要：签名验证未正确绑定消息摘要，允许签名被用于不同消息内容，详见：Move_SignatureWithoutDigestBinding.md  

**Vyper**  
常出现在 DeFi 协议的链下授权、限价单签署、批量交易等业务逻辑实现中，包括但不限于未使用 ecrecover 安全封装、签名消息未哈希标准化、可重放签名构造等方式：  
- 不安全的 ecrecover 使用：直接使用 ecrecover 但未验证返回值或处理边界情况，可能接受无效签名，详见：Vyper_InsecureEcrecoverUsage.md  
- 非规范化签名：接受非规范化（malleable）签名，允许攻击者修改签名格式但保持有效性，详见：Vyper_NonCanonicalSignature.md  

**Go**（用于链下服务或轻节点验证）  
常出现在跨链中继器、预言机签名聚合、链下签名校验服务等业务逻辑实现中，包括但不限于使用非加密安全的签名解析库、未校验公钥与地址映射关系、签名消息结构未严格绑定业务语义等方式：  
- 弱签名解析：使用不安全的签名解析库或实现，容易受到格式攻击或恶意构造的签名影响，详见：Go_WeakSignatureParsing.md  
- 公钥与地址绑定缺失：未正确验证公钥与地址的映射关系，允许攻击者使用错误的公钥通过验证，详见：Go_MissingPubkeyToAddressBinding.md