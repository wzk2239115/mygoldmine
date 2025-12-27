---
name: protocol-doc-analyzer
description: 分析 README、白皮书、审计报告，提取设计意图和风险披露；重点关注有意设计决策、用户责任声明、已知权衡；避免将文档明确说明的功能误判为漏洞；解析 README 中的设计哲学、白皮书中的威胁模型、审计报告中的已知问题；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**
当审计项目时，必须先分析项目文档以理解设计意图，避免将有意设计误判为安全漏洞。此技能应在运行安全分析器前使用。

**Early exit**
若项目根目录无 README.md 且无 docs/ 目录，可快速退出。
若项目文档不完整（< 100 行），降低此技能权重，但仍应尝试从代码注释中提取信息。

**Cases**

**Solidity (智能合约项目)**
需分析的文档类型：

- **README.md 分析**: 提取设计哲学、安全假设、已知权衡
  - 详见: [Solidity_ReadmeAnalysis.md](Solidity_ReadmeAnalysis.md)

- **白皮书分析**: 解析威胁模型、信任假设、安全边界
  - 详见: [Solidity_WhitepaperAnalysis.md](Solidity_WhitepaperAnalysis.md)

- **审计报告分析**: 识别已知设计决策、已修复漏洞、审计方认可的权衡
  - 详见: [Solidity_AuditReportAnalysis.md](Solidity_AuditReportAnalysis.md)

**分析流程**

### 第一步: 扫描 README.md

**查找设计哲学关键词**:
- Governance: governance-minimized, immutable, no admin, timelock, DAO
- Security: atomic protection, CEI, pull over push, reentrancy guard
- DeFi: permissionless, oracle agnostic, free flash loans, composability, trustless
- Risk: user responsibility, known tradeoffs, security assumptions

**提取风险披露**:
- "Users should evaluate..."
- "User responsibility..."
- "Known tradeoffs..."
- "Does not validate..."
- "No guarantee of..."

**识别已知限制**:
- "Does not validate oracle quality"
- "No parameter optimality checks"
- "Cannot be paused"
- "Immutable after deployment"

### 第二步: 解析白皮书（如果存在）

**定位威胁模型章节**:
- "Threat Model"
- "Security Assumptions"
- "Trust Model"
- "Attack Vectors"
- "Security Considerations"

**提取信任假设**:
- 用户需评估什么？
  - Oracle reliability
  - Collateral risk
  - Parameter optimality
- 协议保证什么？
  - Parameter validity (范围检查)
  - Interface compatibility
  - Transaction atomicity

**识别安全边界**:
- 协议职责: 验证参数有效性、执行业务逻辑、防护已知攻击向量
- 用户职责: 评估外部依赖质量、选择合理参数、承担市场风险
- 不负责: Oracle 质量、代币流动性、外部合约安全性

### 第三步: 分析审计报告（如果存在）

**查找 "Acknowledged"/"Informational" 标记**:
这些是设计决策，非漏洞:
```
Issue #12: User-selected oracles (Acknowledged)
→ 这不是漏洞，是 permissionless 设计

Issue #7: No emergency pause (Acknowledged as design decision)
→ 这不是漏洞，是 governance-minimized 设计

Issue #15: Free flash loans (Informational)
→ 这不是漏洞，是可组合性特性
```

**识别 "Won't Fix" 项**:
有意权衡，非漏洞:
```
Issue #9: Cannot upgrade to fix bugs (Won't Fix)
→ 设计权衡: 信任代码而非治理
```

**检查已修复漏洞**:
避免重复报告:
```
Issue #3: Reentrancy in withdraw() (Fixed in commit abc123)
→ 如果当前代码已修复，不应再报告
```

### 第四步: 输出抑制/降级建议

**记录哪些发现应被抑制或降级**:

| 发现类型 | 抑制/降级条件 | 新严重性 | 证据来源 |
|---------|-------------|---------|---------|
| 免费闪电贷 | README 明确为特性 | Info | README.md:L56 |
| 用户选择 oracle | 文档说明用户责任 | Info | README.md:L89 |
| 无紧急暂停 | 审计报告 Acknowledged | Info | Audit Report:Issue #7 |
| Owner 权限 | Governance-minimized | Low | README.md:L8 |
| 单一预言机 | Permissionless + 风险披露 | Info | README.md:L42,L89 |

**输出格式示例**

```
## 文档分析结果

### 项目信息
- 项目名称: Morpho Blue
- 文档路径: README.md, docs/, audits/
- 主要文档: README.md (完整), Spearbit Audit (2023-08)

### README.md 提取的设计意图

#### 1. Free Flash Loans
- **有意设计**: ✅ 是
- **原因**: "Enhance DeFi composability - free flash loans allow other protocols to integrate without fee overhead"
- **引用**:
  - README.md:L56 - "Free flash loans to enhance composability"
  - Whitepaper Section 4.2 - "Composability Design Philosophy"
- **建议**: 将 "免费闪电贷漏洞" 标记为 Info（设计特性）

#### 2. Oracle Selection
- **有意设计**: ✅ 是
- **原因**: "Permissionless market creation - users choose oracles and bear the risk"
- **引用**:
  - README.md:L42 - "Anyone can create a market with their chosen oracle"
  - README.md:L89 - "Users must evaluate oracle reliability when creating markets"
- **建议**: oracle-manipulation-analyzer 应标记用户可选场景为 Info

#### 3. Governance Minimized
- **有意设计**: ✅ 是
- **原因**: "Maximize decentralization and immutability - no admin privileges"
- **引用**:
  - README.md:L8 - "governance-minimized base layer"
  - README.md:L15 - "Immutable contracts, no upgradability"
- **建议**: access-control-analyzer 应降低阈值至 30%

### 风险披露

#### 1. Oracle Reliability
- **用户责任**: ✅ 是
- **文档说明**: "Users must evaluate oracle reliability when creating markets. The protocol only validates that the oracle implements the required interface, not that it provides accurate prices."
- **引用**: README.md:L89-L92 (Risk Disclosure section)
- **建议**: 单一预言机发现应注明 "用户自选，协议不负责"

#### 2. Collateral Risk
- **用户责任**: ✅ 是
- **文档说明**: "The protocol does not whitelist collateral tokens. Users must assess collateral liquidity and smart contract risk."
- **引用**: README.md:L95-L97
- **建议**: 抵押品风险发现标记为用户责任

### 审计报告分析

**审计报告路径**: audits/spearbit_2023_08.pdf

#### 1. Acknowledged Issues (设计决策，非漏洞)

**Issue #12: User-Selected Oracles**
- **类型**: Acknowledged as design decision
- **审计方评论**: "The permissionless design allows users to choose their own oracles. This is a conscious design choice to maximize decentralization."
- **建议**: 抑制相关 oracle 操纵发现，标记为 Info

**Issue #7: No Emergency Pause**
- **类型**: Acknowledged
- **审计方评论**: "The protocol is designed to be governance-minimized. Lack of pause functionality is intentional."
- **建议**: 将 "缺少紧急暂停" 标记为设计权衡，Info 级别

**Issue #15: Free Flash Loans**
- **类型**: Informational
- **审计方评论**: "Free flash loans are a feature to enhance DeFi composability, not a vulnerability."
- **建议**: 标记为设计特性

#### 2. Won't Fix Issues (有意权衡)

**Issue #9: Cannot Upgrade to Fix Bugs**
- **类型**: Won't Fix
- **项目方回复**: "Immutability is core to our design philosophy. We prefer thorough audits and testing over upgradability."
- **建议**: 将 "无法升级" 标记为设计哲学

#### 3. Fixed Issues (避免重复报告)

**Issue #3: Reentrancy in withdraw()**
- **状态**: Fixed in commit `abc123def`
- **修复验证**: 已验证修复
- **建议**: 如当前代码已修复，不应重复报告

### 威胁模型

**从白皮书提取的威胁模型**:

**协议假设**:
- 用户足够成熟，能评估市场风险
- 用户会选择可靠的 oracle 和安全的抵押品
- 智能合约代码经过充分审计和测试

**协议职责**:
- 验证参数范围（如 LTV < 100%）
- 执行借贷和清算逻辑
- 防护已知的智能合约攻击向量（重入、整数溢出等）

**用户职责**:
- 评估 oracle 质量和可靠性
- 评估抵押品流动性和智能合约风险
- 选择合理的市场参数（LTV, Interest Rate Model）
- 监控市场健康度，及时清算

**安全边界**:
- 协议 **验证**: 参数有效性（范围内）
- 协议 **不验证**: 参数最优性（oracle 可靠性、LTV 合理性）
- 原因: Permissionless 设计，保持协议中立

### 抑制/降级建议汇总

| 漏洞类型 | 原因 | 建议操作 | 证据引用 |
|---------|------|---------|---------|
| 免费闪电贷 | README 明确为特性 | 标记为 Info（设计特性） | README.md:L56 |
| 用户可选 oracle | 文档说明用户责任 | 降级为 Info（用户责任） | README.md:L89, Audit:Issue #12 |
| 无紧急暂停 | 审计报告 Acknowledged | 标记为设计权衡 | Audit:Issue #7 |
| Owner 权限过大 | Governance-minimized | High → Low | README.md:L8 |
| 无法升级 | 设计哲学 (Won't Fix) | 标记为设计权衡 | Audit:Issue #9 |
| 单一预言机 | Permissionless + 披露 | High → Info | README.md:L42,L89 |

### 需保留的真实漏洞

以下发现在文档中 **未提及** 或 **未被审计方认可**，应保留为真实漏洞:

1. **跨函数重入** (未在审计报告中提及)
2. **整数溢出** (在 unchecked 块内，未经审计)
3. **权限控制绕过** (与文档声称的 governance-minimized 矛盾)

这些发现应保持原严重性或根据技术分析调整。
```

**Quick Start**

在运行安全分析器前：
1. 运行 protocol-doc-analyzer 解析文档
2. 记录所有有意设计决策和用户责任声明
3. 在分析时抑制/降级相关发现
4. 在最终报告中引用文档说明，增强可信度
