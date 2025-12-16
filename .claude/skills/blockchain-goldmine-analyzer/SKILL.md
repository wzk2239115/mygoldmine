---
name: blockchain-goldmine-analyzer
description: 智能合约审计技能：识别合约编程语言，生成合约审计建议，推荐后续分析。
---

# 概述与边界

该技能用于分析智能合约项目，识别合约的编程语言和类型，并基于 Blockchain Security Goldmine 知识库为用户推荐相应的审计重点和检查清单。

**适用场景**：
- 项目被 `project-profiler` 识别为智能合约项目
- 需要快速了解合约项目的安全审计要点

**输出产物**：
- `.workspace/tasks/{TASK_ID}/blockchain-audit-profile.md` - 合约审计建议报告

# 分析方法

## 1. 识别合约编程语言

通过扫描源代码和配置文件，识别合约使用的编程语言：

**识别规则**：
- **Solidity**（EVM）：
  - 文件扩展名 `.sol`
  - 代码特征：`pragma solidity`、`contract {}`、`interface {}`、`library {}`
  - 常见框架：Hardhat、Truffle、Foundry
  - 主流平台：Ethereum、BSC、Polygon、Arbitrum

- **Rust（Solana/Substrate）**：
  - 文件扩展名 `.rs`
  - 代码特征：`#[program]`、`#[derive(Accounts)]`、Anchor 框架特征
  - 常见框架：Anchor、Solana SDK、Substrate

- **Move（Aptos/Sui）**：
  - 文件扩展名 `.move`
  - 代码特征：`module {}`、`public fun`、资源定义
  - 常见框架：Move language、Aptos SDK

- **Vyper（EVM 替代）**：
  - 文件扩展名 `.vy`
  - 代码特征：Vyper 特定的语法结构
  - 主流平台：Ethereum

- **Go（Cosmos/IBC）**：
  - 文件扩展名 `.go`
  - 代码特征：Cosmos SDK、Keeper 模式
  - 常见框架：Cosmos SDK、Tendermint

## 2. 识别合约类型和应用场景

根据代码内容推断合约应用场景：

| 应用类型 | 特征关键词 | 推荐审计重点 |
|---------|-----------|-----------|
| **DeFi 协议**（借贷、交换、流动性） | `swap`、`liquidity`、`borrow`、`lend`、`oracle` | Reentrancy、Flash Loan、Oracle Manipulation、Access Control |
| **NFT/代币标准** | `ERC721`、`ERC20`、`ERC1155`、`mint`、`burn` | Integer Overflow、Access Control、Upgrade Risks |
| **跨链桥接** | `bridge`、`relay`、`signature`、`multi-sig` | Cross-Chain Bridge、Signature Verification、Access Control |
| **治理合约** | `vote`、`proposal`、`timelock`、`governance` | Governance、Access Control、Business Logic |
| **稳定币** | `mint`、`collateral`、`peg`、`liquidation` | Oracle Manipulation、Business Logic、Integer Overflow |
| **衍生品** | `derivative`、`perpetual`、`leverage`、`liquidation` | Business Logic、Front-Running & MEV、Oracle Manipulation |

## 3. 基于 Blockchain Security Goldmine 推荐审计重点

根据识别的语言和应用类型，推荐用户关注的漏洞类别。

**Top 5 通用漏洞类别（所有合约都应检查）**：
1. ✅ **Access Control** - 权限验证缺失或不当
2. ✅ **Reentrancy** - 重入攻击（主要针对 EVM）
3. ✅ **Integer Overflow/Underflow** - 整数溢出
4. ✅ **Business Logic Flaws** - 业务逻辑漏洞
5. ✅ **Signature Verification** - 签名验证不当

**语言特定的漏洞类别**：

| 语言 | 特有风险 | 重点审计 |
|------|--------|--------|
| Solidity | EVM 特性、Gas 成本 | Reentrancy、Delegatecall、Selfdestruct、DoS Attacks |
| Rust | 所有权系统、CPI 调用 | CPI Reentrancy、Account Validation、Signer Verification |
| Move | 资源安全、能力系统 | Resource Safety、Capability Patterns、Module Visibility |
| Vyper | EVM 语法差异 | Reentrancy、Raw Call、Gas Optimization |
| Go | Keeper 模式、IBC | Keeper Vulnerabilities、IBC Security |

**应用场景特定的漏洞类别**：

| 场景 | 高危漏洞 | 中危漏洞 |
|------|---------|--------|
| DeFi 协议 | Flash Loan、Oracle Manipulation、Reentrancy | Front-Running & MEV、Business Logic |
| 跨链桥接 | Cross-Chain Bridge、Signature Verification | DoS Attacks、Integer Overflow |
| 治理合约 | Governance（Flash Loan Voting）、Access Control | Timestamp Dependence、Business Logic |
| NFT | Access Control、Business Logic | Insecure Randomness、Integer Overflow |

# 输出要求

## 1. 合约审计建议报告

**输出路径**：`.workspace/tasks/{TASK_ID}/blockchain-audit-profile.md`

**文件内容格式**：

```markdown
# 智能合约审计建议

## 基本信息
- **项目名称**：{project_name}
- **项目路径**：{project_root}
- **扫描时间**：{scan_time}
- **项目分类**：智能合约项目

## 合约编程语言
- **主要语言**：{language}
- **框架/工具链**：{framework}
- **检测依据**：{evidence}

## 应用场景推断
- **推断场景**：{inferred_application}
- **场景特征**：{characteristics}

## 审计建议

### 优先级 1 - 必须检查（关键）
- [ ] Access Control - 详见 Blockchain Security Goldmine: access_control/
  - 检查清单：权限验证、角色定义、修饰符使用
- [ ] Reentrancy（仅Solidity/EVM）- 详见 blockchain_goldmine: reentrancy/
  - 检查清单：external call 顺序、状态更新时序、防护机制
- [ ] Integer Overflow/Underflow - 详见 blockchain_goldmine: integer_overflow/
  - 检查清单：算术运算安全性、SafeMath 使用、Solidity 版本（^0.8.0 自动检查）

### 优先级 2 - 重点检查（高）
- [ ] Business Logic Flaws - 详见 blockchain_goldmine: business_logic/
  - 检查清单：状态转换逻辑、边界条件、异常情况处理
- [ ] Signature Verification - 详见 blockchain_goldmine: signature_verification/
  - 检查清单：签名有效性、重放攻击防护、签名恢复正确性

### 优先级 3 - 应用场景特定检查
{application_specific_checks}

### 优先级 4 - 高级检查
- [ ] Gas Optimization - 详见 blockchain_goldmine: gas_optimization/
- [ ] Upgrade Risks（如使用代理）- 详见 blockchain_goldmine: upgrade_risks/
- [ ] Economic Model（如代币经济学）- 详见 blockchain_goldmine: economic_model/

## 推荐资源
- 📚 Blockchain Security Goldmine: https://github.com/wangzekai/blockchain_goldmine
- 🛠️ 静态分析工具：
  - Solidity: Slither, Mythril, Semgrep
  - Rust: cargo-audit, Clippy
  - Move: Move Prover
- 📖 官方文档：
  - Solidity: https://docs.soliditylang.org/en/latest/security-considerations.html
  - Solana: https://docs.solana.com/developing/programming-model/security
  - Move: https://move-language.github.io/move/

## 后续步骤
1. ✅ 阅读本报告的审计建议
2. ⏳ 使用 Blockchain Security Goldmine 中的相关文档进行详细审计
3. ⏳ 根据应用场景，重点关注对应的漏洞类别
4. ⏳ 使用静态分析工具进行自动化扫描
5. ⏳ 进行代码审查和测试
```

## 2. 必需包含内容

| 字段 | 必需 | 说明 |
|------|------|------|
| 合约编程语言 | 是 | 识别的主要编程语言（Solidity/Rust/Move/Vyper/Go） |
| 框架/工具链 | 是 | 合约使用的开发框架（Hardhat/Truffle/Anchor 等） |
| 应用场景推断 | 是 | 推断的应用场景（DeFi/NFT/跨链/治理 等） |
| 优先级 1 审计清单 | 是 | 必须检查的基础漏洞类别 |
| 优先级 2 审计清单 | 是 | 重点检查的漏洞类别 |
| 应用场景特定检查 | 是 | 根据推断场景的特定检查项 |

## 3. 与 Blockchain Security Goldmine 的关联

该技能输出的报告应该能够无缝引导用户使用 Blockchain Security Goldmine：

- 每个推荐的漏洞类别都应提供指向 goldmine 相应目录的链接
- 例如：`Reentrancy - 详见 blockchain_goldmine: reentrancy/SKILL.md`
- 报告应列出每个类别在 goldmine 中的文档路径

# 执行规范

## 快速识别算法

**步骤 1**：检测编程语言
- 按优先级扫描：配置文件 → 源代码文件扩展名 → 代码关键词

**步骤 2**：推断应用场景
- 根据代码中出现的关键词（`swap`、`oracle`、`bridge`、`vote` 等）推断应用场景
- 如果无法确定，标记为"通用合约"

**步骤 3**：生成审计建议
- 基于语言和应用场景，组合推荐的漏洞类别
- 遵循优先级顺序，确保关键漏洞总是包含在内

## 不做的事

❌ 进行深度代码审计（这是后续任务）
❌ 扫描具体的漏洞代码（这是后续任务）
❌ 生成完整的审计报告（这是最后的 report-generator 任务）
✅ 生成审计建议和方向性指导

