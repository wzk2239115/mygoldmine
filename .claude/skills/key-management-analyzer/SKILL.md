---
name: key-management-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证密钥管理（Key Management）漏洞；重点关注密钥材料的生成、存储、传输和使用安全，包括硬编码密钥、弱随机数生成、明文存储、链上暴露、内存泄露等；涵盖钱包集成、签名服务、多签管理、身份认证、预言机签名验证等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Key Management**

**Attention**  
当项目中涉及私钥、助记词、签名密钥或其他敏感密钥材料的生成、存储、传输或使用时，需仔细审计相关代码。此类漏洞通常源于将密钥硬编码、明文存储、在链上暴露、或依赖不安全的随机源生成密钥，常见于钱包集成、签名服务、多签管理、身份认证及预言机签名验证等模块。

**Early exit**  
如果项目完全不涉及任何密钥的生成、管理、存储或使用（例如纯逻辑合约、无签名验证机制、无外部账户交互、无加密操作），且所有身份或权限控制均通过地址或角色而非密钥材料实现，则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在钱包代理、多签控制器、链下签名验证、升级权限控制等业务逻辑实现中，包括但不限于将私钥或助记词硬编码在合约中、依赖 blockhash 或 block.timestamp 生成密钥、在事件或状态变量中记录密钥材料等方式：  
- 硬编码私钥：私钥或助记词直接写入合约代码，任何人可通过查看合约字节码获取，详见：[Solidity_HardcodedPrivateKey.md](Solidity_HardcodedPrivateKey.md)  
- 弱密钥生成：使用不安全的随机源（如 blockhash）生成密钥，可被预测或操纵，详见：[Solidity_WeakKeyGeneration.md](Solidity_WeakKeyGeneration.md)  
- 事件中暴露密钥：密钥材料或敏感信息在事件日志中记录，链上永久可见，详见：[Solidity_KeyExposureInEvent.md](Solidity_KeyExposureInEvent.md)  

**Rust**（适用于智能合约如 Solana 程序或 Off-chain 服务）  
常出现在密钥派生、签名服务、密钥轮换逻辑中，包括但不限于使用非加密安全的 RNG、将密钥写入日志或临时文件、未正确清理内存中的密钥缓冲区等方式：  
- 不安全的 RNG 用于密钥：使用 rand::thread_rng 等非加密安全的随机数生成器生成密钥，可被预测，详见：[Rust_InsecureRNGForKey.md](Rust_InsecureRNGForKey.md)  
- 日志中的密钥材料：密钥或种子在调试日志中输出，可能被日志系统持久化或泄露，详见：[Rust_KeyMaterialInLog.md](Rust_KeyMaterialInLog.md)  
- 未清理密钥内存：密钥使用后未从内存中安全清除，可能被其他进程读取或通过内存转储泄露，详见：[Rust_UnsanitizedKeyMemory.md](Rust_UnsanitizedKeyMemory.md)  

**Move**  
常出现在账户密钥管理、能力（capability）绑定、资源访问控制等逻辑中，包括但不限于通过公开函数暴露密钥句柄、在结构体中不加保护地存储密钥引用、错误地将密钥作为可复制资源处理等方式：  
- 不当密钥 Capability：密钥相关的 Capability 对象设计不当，可被复制或非授权获取，详见：[Move_ImproperKeyCapability.md](Move_ImproperKeyCapability.md)  
- 密钥资源误用：密钥作为资源存储但未正确限制访问或转移权限，详见：[Move_KeyResourceMisuse.md](Move_KeyResourceMisuse.md)  

**Vyper**  
常出现在签名验证、权限控制或预言机适配器等模块中，包括但不限于在状态变量中存储临时私钥、使用可预测变量初始化密钥、未限制密钥相关函数的调用权限等方式：  
- 可预测密钥初始化：使用 block.timestamp 等可预测值作为密钥种子或初始化参数，详见：[Vyper_PredictableKeyInit.md](Vyper_PredictableKeyInit.md)  
- 无限制密钥函数：密钥管理相关函数未设置访问限制，任意用户可调用修改密钥，详见：[Vyper_UnrestrictedKeyFunction.md](Vyper_UnrestrictedKeyFunction.md)  

**Go**（适用于链下组件如中继器、签名服务、CLI 工具）  
常出现在密钥加载、加密操作、配置文件解析等逻辑中，包括但不限于从明文配置文件读取私钥、使用 math/rand 而非 crypto/rand 生成密钥、密钥在错误处理路径中泄露至日志等方式：  
- 配置中的明文密钥：私钥以明文形式存储在配置文件中，任何可访问配置文件的人都能获取，详见：[Go_PlaintextKeyInConfig.md](Go_PlaintextKeyInConfig.md)  
- 非加密 Rand 用于密钥：使用 math/rand 而非 crypto/rand 生成密钥，随机性不足可被预测，详见：[Go_NonCryptoRandForKeys.md](Go_NonCryptoRandForKeys.md)  
- 错误日志泄露密钥：密钥在错误处理或调试日志中输出，可能被日志收集系统记录，详见：[Go_KeyLeakInErrorLog.md](Go_KeyLeakInErrorLog.md)