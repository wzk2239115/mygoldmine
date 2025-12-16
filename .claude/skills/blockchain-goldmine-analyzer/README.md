# blockchain-goldmine-analyzer

智能合约安全审计技能，识别合约编程语言和应用场景，生成基于 Blockchain Security Goldmine 的审计建议。

## 功能

- 🔍 **自动识别合约编程语言**：Solidity、Rust、Move、Vyper、Go
- 📊 **推断应用场景**：DeFi、NFT、跨链桥接、治理、稳定币等
- ✅ **生成审计建议**：基于语言和应用场景的分层审计清单
- 🔗 **集成 Blockchain Security Goldmine**：无缝链接到详细的审计文档

## 使用方法

### 作为 Vul-AI 技能

当项目被 `project-profiler` 识别为智能合约项目时，自动触发本技能：

```bash
python3 quick-scan.py /path/to/smart-contract-project
```

### 独立使用

```bash
python3 quick-scan.py /path/to/contract --output report.md
```

### 输出示例

生成的报告包含：

1. **基本信息** - 项目名称、路径、扫描时间
2. **合约编程语言** - 识别的主要编程语言和框架
3. **应用场景推断** - 推断的应用类型（DeFi/NFT/etc）
4. **审计建议** - 分层的检查清单
   - 优先级 1：所有合约都需要检查的通���漏洞
   - 优先级 2：语言特定的风险
   - 优先级 3：应用场景特定的风险
5. **推荐资源** - 静态分析工具和文档链接

## 审计清单示例

```markdown
### 优先级 1 - 必须检查（关键）
- [ ] **Access Control** - 详见 Blockchain Security Goldmine
- [ ] **Integer Overflow/Underflow**
- [ ] **Reentrancy**（Solidity/EVM）
- [ ] **Business Logic Flaws**

### 优先级 2 - 重点检查（高）
- [ ] **Delegatecall**（Solidity）
- [ ] **CPI Reentrancy**（Rust）
- [ ] **Resource Safety**（Move）

### 优先级 3 - 应用场景特定检查（DeFi）
- [ ] **Flash Loan** - DeFi 特有风险
- [ ] **Oracle Manipulation**
- [ ] **Front-Running & MEV**
```

## 与 Blockchain Security Goldmine 的关联

本技能生成的报告会引导用户查看 Blockchain Security Goldmine 中的详细文档：

```
.claude/skills/blockchain_goldmine/
├── access_control/
├── reentrancy/
├── integer_overflow/
├── flash_loan/
├── oracle_manipulation/
├── cross_chain_bridge/
├── governance/
├── business_logic/
└── ... (22+ 个漏洞类别)
```

每个推荐的审计项都可以直接映射到 goldmine 中的相应目录。

## 支持的编程语言

| 语言 | 文件后缀 | 框架 | 平台 |
|------|--------|------|------|
| Solidity | `.sol` | Hardhat, Truffle, Foundry | Ethereum, BSC, Polygon, Arbitrum |
| Rust | `.rs` | Anchor, Solana SDK | Solana, Substrate |
| Move | `.move` | Move Language | Aptos, Sui |
| Vyper | `.vy` | Vyper Framework | Ethereum |
| Go | `.go` | Cosmos SDK | Cosmos, IBC |

## 支持的应用场景

- 🏦 **DeFi**：借贷、交换、流动性挖矿
- 🎨 **NFT**：代币、收藏品、市场
- 🌉 **跨链桥接**：资产跨链转移
- 🗳️ **治理**：DAO、投票、提案
- 💰 **稳定币**：抵押稳定币、算法稳定币
- 📈 **衍生品**：永续合约、杠杆、期货

## 文件结构

```
blockchain-goldmine-analyzer/
├── SKILL.md           # 技能定义和规范
├── quick-scan.py      # 快速扫描脚本
└── README.md          # 本文件
```

## 配置参数

在 `.claude/settings.json` 中配置（如需）：

```json
{
  "skills": {
    "blockchain-goldmine-analyzer": {
      "enabled": true,
      "auto_trigger": true
    }
  }
}
```

## 许可证

本技能遵循与主项目相同的许可证。

## 相关资源

- 📚 [Blockchain Security Goldmine](../)
- 🔗 [Solidity 安全考虑](https://docs.soliditylang.org/en/latest/security-considerations.html)
- 🔗 [Solana 安全最佳实践](https://docs.solana.com/developing/programming-model/security)
- 🔗 [Move 语言文档](https://move-language.github.io/move/)
