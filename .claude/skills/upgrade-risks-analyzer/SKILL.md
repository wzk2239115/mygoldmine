---
name: upgrade-risks-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证升级风险（Upgrade Risks）漏洞；重点关注可升级架构中的安全隐患，包括未保护的初始化器、存储布局冲突、升级权限滥用、状态迁移不兼容等；涵盖代理模式、模块化协议、治理驱动升级、程序热更新等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Upgrade Risks**

**Attention**  
当项目采用可升级架构（如代理模式、模块热替换等）时，若升级机制缺乏权限控制、状态一致性校验或初始化逻辑保护，可能导致逻辑覆盖、存储冲突或权限劫持等风险。此类漏洞通常出现在治理模块、代理合约、初始化器或模块化协议的核心升级逻辑中。

**Early exit**  
若项目明确采用不可升级架构（如无代理合约、无动态模块加载机制、无版本切换逻辑），且所有合约/模块均以 immutable 方式部署，则可快速退出对 Upgrade Risks 的审计。

**Cases**

**Solidity**  
常出现在代理模式（如 UUPS、Transparent Proxy）、模块化协议升级、治理驱动的合约替换等业务逻辑实现中，包括但不限于未校验 initializer 调用次数、逻辑合约覆盖存储布局不兼容、升级权限未最小化等方式：  
- 未保护的初始化器：初始化函数未防止重复调用，允许攻击者重新初始化合约覆盖关键状态，详见：[Solidity_UnprotectedInitializer.md](Solidity_UnprotectedInitializer.md)  
- 升级时存储冲突：逻辑合约升级时存储变量布局变更，导致新旧版本数据映射错误或状态损坏，详见：[Solidity_StorageCollisionInUpgrade.md](Solidity_StorageCollisionInUpgrade.md)  
- 过度升级权限：升级权限未限制或集中在单一地址，存在中心化风险和治理风险，详见：[Solidity_ExcessiveUpgradePrivilege.md](Solidity_ExcessiveUpgradePrivilege.md)

**Rust**（适用于 Solana、CosmWasm 等）  
常出现在可升级程序（Program）或模块热加载机制中，包括但不限于 upgrade_authority 未冻结、状态迁移未验证、新旧版本 ABI 不兼容等方式：  
- 未冻结的升级权限：程序升级权限（upgrade_authority）未冻结或转移到治理合约，存在单点升级风险，详见：[Rust_UnfrozenUpgradeAuthority.md](Rust_UnfrozenUpgradeAuthority.md)  
- 不兼容的状态迁移：程序升级时账户数据结构变更但未提供迁移逻辑，导致旧数据无法被新版本正确解析，详见：[Rust_IncompatibleStateMigration.md](Rust_IncompatibleStateMigration.md)  
- 缺失版本验证：升级过程未验证新版本与旧版本的兼容性，可能导致关键逻辑被破坏，详见：[Rust_MissingVersionValidation.md](Rust_MissingVersionValidation.md)

**Move**  
常出现在模块更新（module update）或脚本热部署机制中，包括但不限于未限制更新者权限、资源类型定义变更导致状态不一致、未启用模块冻结策略等方式：  
- 无限制的模块更新：模块更新权限未受限制，允许任意地址发布新版本覆盖现有模块，详见：[Move_UnrestrictedModuleUpdate.md](Move_UnrestrictedModuleUpdate.md)  
- 资源布局不兼容：模块升级时资源结构定义变更，导致已存在的资源实例无法被正确访问，详见：[Move_ResourceLayoutIncompatibility.md](Move_ResourceLayoutIncompatibility.md)  
- 缺失模块冻结：模块未设置冻结机制，允许在生产环境持续修改核心逻辑，详见：[Move_MissingModuleFreeze.md](Move_MissingModuleFreeze.md)

**Vyper**  
常出现在基于代理的可升级合约架构中，包括但不限于初始化函数未防重入、升级函数未限制调用者、逻辑合约未声明 nonreentrant 等方式：  
- 可重入的初始化器：初始化函数未设置重入保护，可在初始化过程中被恶意合约重入调用，详见：[Vyper_ReentrantInitializer.md](Vyper_ReentrantInitializer.md)  
- 无限制的代理升级：代理合约升级函数未限制调用者身份，任意用户可替换逻辑合约地址，详见：[Vyper_UnrestrictedProxyUpgrade.md](Vyper_UnrestrictedProxyUpgrade.md)

**Go**（适用于 Cosmos SDK 等链上模块升级场景）  
常出现在链上治理驱动的模块升级、共识参数热更新等逻辑中，包括但不限于 upgrade plan 未校验模块兼容性、handler 未版本隔离、状态迁移未原子化等方式：  
- 未验证的升级计划：治理提案触发的升级计划未验证新模块与现有状态的兼容性，导致升级后链功能异常，详见：[Go_UnverifiedUpgradePlan.md](Go_UnverifiedUpgradePlan.md)  
- 非隔离的版本处理器：不同版本的消息处理器未进行隔离，导致升级后旧消息被新逻辑错误处理，详见：[Go_NonIsolatedVersionHandler.md](Go_NonIsolatedVersionHandler.md)  
- 非原子状态迁移：模块升级时状态迁移逻辑未保证原子性，部分迁移失败导致链状态不一致，详见：[Go_NonAtomicStateMigration.md](Go_NonAtomicStateMigration.md)