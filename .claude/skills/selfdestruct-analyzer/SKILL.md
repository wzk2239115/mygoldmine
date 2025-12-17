---
name: selfdestruct-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证合约自毁（Selfdestruct）漏洞；重点关注合约销毁机制的调用条件、权限控制及其对依赖组件的影响，包括权限检查缺失、资金转移不当、状态依赖破坏等；涵盖代理模式、金库管理、临时合约、紧急熔断等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Selfdestruct**

**Attention**  
当智能合约中包含主动销毁自身（即调用类似 `selfdestruct` 的指令）的逻辑时，需仔细审计其调用条件、权限控制以及对依赖该合约的其他组件的影响。此类漏洞通常出现在支持合约升级、紧急熔断、资金回收或临时部署逻辑的业务模块中，尤其在代理模式、金库（Vault）、清算器（Liquidator）或一次性任务合约中较为常见。

**Early exit**  
若项目代码中完全未使用任何合约自毁机制（如 Solidity 中的 `selfdestruct`、Rust/Move 中无等效逻辑、Vyper 中未调用 `destroy`、Go 合约中无销毁行为等），且业务逻辑不涉及临时性或可销毁合约设计，则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在紧急停止（Emergency Stop）、代理逻辑清理、临时任务合约回收等业务逻辑实现中，包括但不限于通过 `selfdestruct` 主动销毁合约、在升级流程中废弃旧逻辑合约、或在金库清空后移除自身等方式：  
- 紧急关停中的自毁：紧急情况下调用 selfdestruct 销毁合约，但未考虑依赖方影响或资金转移目标可控性，详见：[Solidity_SelfDestructInEmergencyShutdown.md](Solidity_SelfDestructInEmergencyShutdown.md)  
- 可升级代理销毁：代理合约或逻辑合约在升级过程中被 selfdestruct，导致系统崩溃或资金锁定，详见：[Solidity_UpgradeableProxyDestruction.md](Solidity_UpgradeableProxyDestruction.md)  
- 临时任务合约清理：一次性任务合约完成后自毁，但未妥善处理剩余状态或资金，详见：[Solidity_TemporaryTaskContractCleanup.md](Solidity_TemporaryTaskContractCleanup.md)

**Rust (e.g., Solana programs)**  
Rust 编写的区块链程序（如 Solana）本身不提供 `selfdestruct` 语义，但若通过关闭账户（close account）并转移剩余 lamports 实现类似效果，则可能引入等效风险。常出现在可关闭状态账户、一次性指令处理器等业务逻辑中，包括但不限于关闭用户状态账户、任务完成后的资源回收等方式：  
- 账户关闭作为自毁：程序通过关闭账户（将 lamports 转移并清零数据）模拟 selfdestruct，但未验证关闭条件或目标地址，详见：[Rust_AccountCloseAsDestruct.md](Rust_AccountCloseAsDestruct.md)  
- 一次性指令清理：指令执行后关闭相关账户回收租金，但未妥善处理账户间依赖关系，详见：[Rust_OneTimeInstructionCleanup.md](Rust_OneTimeInstructionCleanup.md)

**Move**  
Move 语言中虽无直接 `selfdestruct`，但可通过 `move_to`/`move_from` 或资源销毁（如 `burn`）间接实现合约逻辑"失效"。常出现在权限回收、临时策略模块、用户退出机制等业务中，包括但不限于销毁策略资源、移除用户凭证等方式：  
- 策略资源销毁：策略或权限资源被 burn 销毁，但未验证销毁条件或影响范围，导致系统功能失效，详见：[Move_PolicyResourceBurn.md](Move_PolicyResourceBurn.md)  
- 临时模块失效：临时模块通过移除关键资源实现"自毁"，但未处理对其他模块的影响，详见：[Move_TemporaryModuleDeactivation.md](Move_TemporaryModuleDeactivation.md)

**Vyper**  
常出现在资金回收、合约退役或治理触发的销毁场景中，包括但不限于使用 `selfdestruct` 指令在满足特定条件（如治理投票通过）后移除合约，或在多签金库清空后自毁等方式：  
- 治理触发的销毁：通过治理提案触发 selfdestruct 销毁合约，但未验证投票合法性或资金转移安全性，详见：[Vyper_GovernanceTriggeredDestruction.md](Vyper_GovernanceTriggeredDestruction.md)  
- 多签金库自毁：多签金库在资金清空后自毁，但未确保所有资金已正确转移或依赖方已更新，详见：[Vyper_MultiSigVaultSelfDestruct.md](Vyper_MultiSigVaultSelfDestruct.md)

**Go (e.g., Cosmos SDK-based chains)**  
在基于 Go 的区块链（如 Cosmos SDK）中，智能合约或模块通常不支持运行时自毁，但若通过模块禁用、状态清除或账户注销模拟销毁行为，则需评估其安全性。常出现在模块生命周期管理、账户注销、策略废弃等逻辑中，包括但不限于禁用模块后清除状态、逻辑账户注销等方式：  
- 模块禁用后状态清除：模块被禁用后清除所有状态数据，但未验证清除操作的原子性或对其他模块的影响，详见：[Go_ModuleDeactivationWithStateWipe.md](Go_ModuleDeactivationWithStateWipe.md)  
- 逻辑账户删除：通过删除账户数据模拟"自毁"，但未妥善处理账户间依赖或资金转移，详见：[Go_LogicalAccountDeletion.md](Go_LogicalAccountDeletion.md)