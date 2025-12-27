---
name: design-pattern-recognizer
description: 识别协议设计模式，区分有意设计与安全漏洞，避免误报；重点关注治理模式(governance-minimized/timelocked/DAO)、安全模式(atomic protection/CEI/pull-over-push)、DeFi哲学(permissionless/composability)；在运行安全分析器前使用此技能评估项目设计理念，动态调整检测阈值；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
当审计智能合约项目时，必须首先识别项目的设计模式，以避免将有意设计误判为安全漏洞。此技能应在所有安全分析器执行前使用，为后续分析提供上下文。

**Early exit**
若项目不是智能合约项目（无 .sol/.rs/.move/.vy 文件），可快速退出。
若项目是标准 Web2 应用，跳过此技能。

**Cases**

**Solidity (EVM 智能合约)**
以下设计模式常被误判为漏洞，需特别识别：

- **治理最小化模式 (Governance Minimized)**: 合约不可升级、无管理员权限、参数固化
  - 详见: [Solidity_GovernanceMinimized.md](Solidity_GovernanceMinimized.md)
  - 影响: access-control-analyzer 检测阈值应降低 70%

- **原子性保护模式 (Atomic Protection)**: Solidity 0.8+ 依赖交易回滚而非显式锁
  - 详见: [Solidity_AtomicProtection.md](Solidity_AtomicProtection.md)
  - 影响: reentrancy-analyzer 严重性应降低 2 级

- **无许可设计模式 (Permissionless Design)**: 用户选择外部依赖（如预言机），协议不负责
  - 详见: [Solidity_PermissionlessDesign.md](Solidity_PermissionlessDesign.md)
  - 影响: oracle-manipulation-analyzer 应将用户可选场景标记为 Info

- **Checks-Effects-Interactions 模式**: 状态更新在外部调用前
  - 详见: [Solidity_ChecksEffectsInteractions.md](Solidity_ChecksEffectsInteractions.md)
  - 影响: 重入检测应验证是否完整遵循 CEI

- **Pull Over Push 模式**: 使用 claimable 而非主动推送
  - 详见: [Solidity_PullOverPush.md](Solidity_PullOverPush.md)
  - 影响: 重入风险已通过设计规避

**分析流程**

1. **扫描项目文档**
   - 阅读 README.md，查找关键词：governance-minimized, immutable, no admin, permissionless, oracle agnostic, free flash loans
   - 阅读合约注释，查找 @dev/@notice 中的设计说明

2. **检查代码结构**
   - Governance: 统计 onlyOwner 修饰符数量、检查 immutable 变量
   - Security: 检测 Solidity 版本、SafeMath 使用情况、CEI 模式遵循度
   - DeFi: 识别 permissionless 函数、oracle 参数化、免费闪电贷

3. **输出调整建议**
   创建分析笔记，记录：
   - 检测到的设计模式及证据
   - 建议调整的分析器及阈值
   - 应降级的漏洞类型及新严重性

**输出格式示例**

```
## 设计模式分析结果

### 检测到的模式
1. ✅ Governance Minimized (置信度: 95%)
   - 证据: README.md L8 提到 "governance-minimized base layer"
   - 证据: 代码中无 onlyOwner 修饰符
   - 证据: 合约使用 immutable 变量

2. ✅ Atomic Protection (置信度: 90%)
   - 证据: pragma solidity ^0.8.19
   - 证据: 无 SafeMath 导入
   - 证据: 外部调用后有代币转账（会回滚）

3. ✅ Permissionless Design (置信度: 98%)
   - 证据: README.md L42 "permissionless market creation"
   - 证据: 用户可选择 oracle 地址
   - 证据: flashLoan() 函数零费用

### 分析器调整建议
- access-control-analyzer: 降低检测阈值至 30%（原 100%）
- reentrancy-analyzer: 重入发现降级为 Info（原 Medium）
- oracle-manipulation-analyzer: 用户可选 oracle 标记为设计决策（原 High → Info）

### 严重性调整
- VULN-001 (Owner 权限): High → Low（governance-minimized 项目）
- VULN-003-006 (回调重入): Medium → Info（atomic protection）
- VULN-010-012 (单一预言机): High → Info（permissionless design）
```

**Quick Start**

在运行任何安全分析器前：
1. 运行 design-pattern-recognizer 识别设计模式
2. 根据输出调整后续分析器的严重性评级
3. 在最终报告中注明哪些发现是设计决策而非漏洞
