# 案例研究贡献指南

欢迎为 blockchain_goldmine 案例研究数据库做出贡献！本指南将帮助您理解如何提交高质量的区块链安全事件案例。

## 目录

- [贡献类型](#贡献类型)
- [质量标准](#质量标准)
- [提交流程](#提交流程)
- [案例研究要求](#案例研究要求)
- [审查流程](#审查流程)
- [风格指南](#风格指南)
- [工具与资源](#工具与资源)

---

## 贡献类型

我们接受以下类型的贡献：

### 1. 新增案例研究

为尚未记录的区块链安全事件创建完整的案例研究文档。

**适合的案例**：
- ✅ 损失 ≥ $1M USD 的安全事件
- ✅ 具有技术新颖性的攻击（即使损失较小）
- ✅ 对行业有重大影响的事件（如导致监管变化、标准更新）

**不适合的案例**：
- ❌ 私钥泄露或社会工程攻击
- ❌ 中心化交易所的链下安全问题
- ❌ Rug pull（故意欺诈）
- ❌ 无法验证的事件或缺少链上数据

### 2. 更新现有案例

- 添加新发现的技术细节
- 更新资金追回状态
- 补充审计报告或事后分析
- 修正错误或不准确的信息

### 3. 改进文档质量

- 修复拼写/语法错误
- 优化代码示例
- 添加图表和可视化
- 改善链接和参考资料

---

## 质量标准

### 必需条件（所有案例必须满足）

#### 1. 可验证性
- ✅ 至少 **2个** 一级或二级来源（见下方来源分级）
- ✅ **链上交易数据**可验证（Etherscan/Solscan链接）
- ✅ 财务损失数据有可靠来源支持

#### 2. 技术准确性
- ✅ 代码示例准确（直接来自项目源码或审计报告）
- ✅ 攻击流程描述清晰且可重现
- ✅ 映射到至少 **1个** blockchain_goldmine 漏洞模式

#### 3. 完整性
- ✅ 包含所有必需章节（见模板）
- ✅ YAML frontmatter 字段完整填写
- ✅ 提供明确的参考资料链接

#### 4. 专业性
- ✅ 客观中立的语气（避免情绪化表述）
- ✅ 技术术语使用准确
- ✅ 包含对审计人员有实用价值的分析

### 来源分级

**一级来源**（最高权威性，必需）：
- 官方事后分析报告（项目方发布）
- 专业审计报告
- 链上交易数据和验证的合约代码
- GitHub 安全公告 (CVE)

**二级来源**（强烈推荐，至少1个）：
- 知名安全公司分析（PeckShield, SlowMist, CertiK等）
- Rekt News 深度报道
- 著名安全研究员分析（@samczsun, @Mudit__Gupta, @bertcmiller等）
- 学术论文

**三级来源**（补充材料）：
- 专业加密媒体（CoinDesk, TheBlock, Decrypt）
- 社区讨论（Reddit, Twitter, Discord）
- 技术博客文章

**最低要求**：至少 1 个一级来源 + 1 个二级来源

---

## 提交流程

### 步骤 1：准备工作

1. **选择案例**
   - 查看 [案例研究索引](README.md) 确保未被记录
   - 在 [GitHub Issues](https://github.com/user/blockchain_goldmine/issues) 中搜索是否有人已认领

2. **收集资料**
   - 至少2个权威来源的技术分析
   - 链上交易哈希和区块浏览器链接
   - 官方公告或事后分析报告
   - 审计报告（如有）
   - 漏洞代码片段

3. **创建Issue认领任务**（推荐）
   ```markdown
   标题: [Case Study] YYYY_project_name - $XXM 损失

   我计划为 [项目名] 的 [漏洞类型] 攻击事件创建案例研究。

   - 事件日期: YYYY-MM-DD
   - 损失金额: $XXM
   - 主要来源: [列出2-3个]
   - 预计完成时间: YYYY-MM-DD

   请问是否有人已经在处理此案例？
   ```

### 步骤 2：创建案例文档

1. **复制模板**
   ```bash
   cp case_studies/_templates/case_study_template.md \
      case_studies/[category]/YYYY_project_name.md
   ```

2. **填写内容**
   - 完整填写 YAML frontmatter
   - 按章节顺序完成所有必需内容
   - 使用规定的代码注释符号（✅ ❌ ⚠️ 💡）
   - 确保所有链接可访问

3. **自查清单**
   - [ ] YAML frontmatter 所有必填字段已完成
   - [ ] 至少2个权威来源已引用
   - [ ] 所有链上交易已验证
   - [ ] 代码示例已测试或来自官方源码
   - [ ] 已链接到相关漏洞模式文件
   - [ ] 审计检查清单已完成
   - [ ] 无拼写/语法错误
   - [ ] 所有外部链接可访问

### 步骤 3：本地验证

运行以下命令检查文档格式：

```bash
# 检查 Markdown 语法
markdownlint case_studies/[category]/YYYY_project_name.md

# 验证 YAML frontmatter（如有工具）
python scripts/validate_case_study.py case_studies/[category]/YYYY_project_name.md

# 检查链接有效性
markdown-link-check case_studies/[category]/YYYY_project_name.md
```

### 步骤 4：提交 Pull Request

1. **Fork 仓库**
   ```bash
   # 1. Fork github.com/user/blockchain_goldmine
   # 2. Clone 你的 fork
   git clone https://github.com/YOUR_USERNAME/blockchain_goldmine.git
   cd blockchain_goldmine
   ```

2. **创建分支**
   ```bash
   git checkout -b case-study/YYYY-project-name
   ```

3. **提交更改**
   ```bash
   git add case_studies/[category]/YYYY_project_name.md
   git commit -m "Add case study: Project Name Attack (Month YYYY) - $XXM"
   ```

4. **推送并创建PR**
   ```bash
   git push origin case-study/YYYY-project-name
   # 在 GitHub 上创建 Pull Request
   ```

5. **PR 描述模板**
   ```markdown
   ## 案例研究: [项目名称]攻击事件

   ### 基本信息
   - 事件日期: YYYY-MM-DD
   - 损失金额: $XXX million
   - 漏洞类型: [重入/闪电贷/桥接/等]
   - 区块链: Ethereum/Solana/etc.

   ### 来源
   - 官方事后分析: [链接]
   - 安全分析: [链接1], [链接2]
   - 链上交易: [Etherscan链接]

   ### 检查清单
   - [x] 复制并完整填写模板
   - [x] 至少2个权威来源
   - [x] 链上数据已验证
   - [x] 映射到漏洞模式: [链接]
   - [x] 本地通过格式验证
   - [x] 已自查所有章节

   ### 相关Issue
   Closes #XXX (如有)
   ```

### 步骤 5：响应审查

- 查看审查者的评论
- 及时进行修改
- 保持礼貌和专业的沟通
- 标记已解决的评论

---

## 案例研究要求

### YAML Frontmatter 必填字段

```yaml
---
incident_name: "..."        # 必需
date: "YYYY-MM-DD"          # 必需
category: ["..."]           # 必需，至少1个
blockchain: "..."           # 必需
amount_lost_usd: 123456     # 必需（数字）
severity: "..."             # 必需: Critical/High/Medium/Low
status: "..."               # 必需
vulnerability_root_cause: "..." # 必需
exploit_transactions: ["..."]   # 必需，至少1个
related_vulnerabilities:    # 必需，至少1个
  - path: "..."
    relevance: "Primary"
references:                 # 必需
  official_postmortem: "..." # 推荐
  security_analysis: ["..."] # 必需，至少1个
  blockchain_explorer: "..." # 必需
tags: ["..."]              # 必需，至少2个
contributors: ["..."]      # 必需
last_updated: "YYYY-MM-DD" # 必需
review_status: "Draft"     # 必需
---
```

### 必需章节

所有案例研究必须包含以下章节（详细结构见模板）：

1. ✅ **执行摘要** - 2-3段，包含快速导航
2. ✅ **背景** - 协议概览、攻击前状态、审计历史
3. ✅ **技术分析** - 攻击时间线、根因分析、代码剖析、漏洞模式链接
4. ✅ **影响分析** - 财务、技术、生态系统影响
5. ✅ **响应与恢复** - 即时/短期/长期响应
6. ✅ **审计人员经验总结** - 检测策略、检查清单、误报识别
7. ✅ **参考资源** - 完整的来源列表
8. ✅ **相关案例** - 至少链接到1个相关案例或模式

### 代码示例要求

- **漏洞代码**: 必须来自实际项目源码或审计报告
  - 标注文件名、行号、部署地址
  - 使用 ❌ 标记漏洞点
  - 添加详细注释解释为何有漏洞

- **修复代码**: 展示正确实现
  - 使用 ✅ 标记安全模式
  - 解释修复的原理
  - 可以是项目实际修复或推荐最佳实践

- **攻击代码**: 展示攻击合约（如适用）
  - 简化但保留核心逻辑
  - 添加执行流程注释
  - 可以是实际攻击代码或重构的PoC

**示例**：
```solidity
// ✅ 好的示例
// 文件: contracts/Vault.sol (Lines 145-165)
// 部署地址: 0xabc... (Ethereum Mainnet)
// 审计状态: 已审计（Company, 2023-01-15）- 此漏洞被遗漏

function withdraw(uint256 amount) external {
    require(balances[msg.sender] >= amount);

    // ❌ 漏洞: 外部调用在状态更新前（重入风险）
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success);

    balances[msg.sender] -= amount; // ❌ 状态更新太晚
}

// ❌ 不好的示例
function withdraw() external {
    // 这个函数有漏洞（没有上下文、注释、来源）
    msg.sender.call("");
}
```

---

## 审查流程

### 审查级别

所有提交的案例研究将经过三级审查：

#### Level 1: 自动化检查（立即）
- Markdown 语法验证
- YAML frontmatter 格式检查
- 链接有效性检查
- 字数统计（最少 3000 字）

#### Level 2: 社区审查（1-3天）
- 技术准确性验证
- 来源可信度评估
- 完整性检查

**审查者关注点**：
- 事实是否准确？
- 来源是否可靠？
- 技术分析是否合理？
- 是否有明显遗漏？

#### Level 3: 核心团队审查（3-7天）
- 深度技术验证
- 漏洞模式映射准确性
- 审计建议实用性
- 整体质量评估

**核心团队可能要求**：
- 补充来源
- 修正技术细节
- 改进代码示例
- 重新组织结构

### 审查标准

案例研究需满足以下标准才能被接受：

**基础标准**（必需）：
- [ ] 所有必填字段已完成
- [ ] 至少2个权威来源
- [ ] 链上数据可验证
- [ ] 映射到漏洞模式
- [ ] 无明显技术错误

**质量标准**（强烈推荐）：
- [ ] 代码示例详细且准确
- [ ] 攻击流程清晰可重现
- [ ] 审计建议具体可执行
- [ ] 语言专业且易懂
- [ ] 格式一致美观

**卓越标准**（可选加分）：
- [ ] 包含攻击PoC测试代码
- [ ] 原创的分析洞察
- [ ] 高质量图表和可视化
- [ ] 对比多个类似案例
- [ ] 提供形式化验证建议

### 常见拒绝原因

- ❌ **来源不足**: 只有1个来源或来源不可靠
- ❌ **无法验证**: 缺少链上交易或合约地址
- ❌ **技术错误**: 对攻击原理的描述错误
- ❌ **不完整**: 缺少必需章节或字段
- ❌ **重复**: 已有相同案例的高质量文档
- ❌ **不符合收录标准**: 案例类型不适合（如私钥泄露）

---

## 风格指南

### 语言与语气

**推荐**：
- ✅ 客观中立的描述
- ✅ 技术准确的术语
- ✅ 清晰简洁的表达
- ✅ 面向审计人员的专业语气

**避免**：
- ❌ 情绪化的评论（"愚蠢的错误"、"荒谬的设计"）
- ❌ 主观判断（"明显是..."、"毫无疑问..."）
- ❌ 过度简化（"仅仅因为..."）
- ❌ 营销语言（"革命性的"、"史诗级的"）

**示例对比**：

❌ 不好：
> 开发团队犯了一个极其愚蠢的错误，居然在外部调用后才更新余额，这简直是区块链开发的基础常识！任何有经验的开发者都不会犯这种低级错误。

✅ 好：
> `withdraw` 函数违反了 Checks-Effects-Interactions 模式，在外部调用后才更新用户余额。这种模式在审计报告中被遗漏，可能是因为代码复杂度较高且缺少重入测试覆盖。

### 格式规范

#### 标题层级
- H1 (`#`): 仅用于主标题（案例名称）
- H2 (`##`): 主要章节（执行摘要、技术分析等）
- H3 (`###`): 子章节
- H4 (`####`): 具体细分
- H5-H6: 避免使用（层级过深）

#### 代码块
```solidity
// 始终指定语言
// 添加注释说明上下文
// 使用标准注释符号（✅ ❌ ⚠️ 💡）
```

#### 表格
- 使用 Markdown 表格
- 第一行为表头
- 保持列对齐
- 不要嵌套复杂内容

#### 列表
- 无序列表：使用 `-`
- 有序列表：使用 `1.`, `2.` 等
- 任务列表：使用 `- [ ]` 和 `- [x]`
- 嵌套列表：缩进2个空格

#### 链接
- 行内链接：`[链接文本](URL)`
- 引用链接：避免使用（保持文档可读性）
- Etherscan/区块浏览器：始终提供完整URL
- GitHub：使用相对路径链接项目内文件

### 代码注释符号

统一使用以下符号标注代码：

| 符号 | 含义 | 使用场景 |
|-----|------|---------|
| ✅ | 正确/安全 | 安全的代码实现、推荐做法 |
| ❌ | 错误/危险 | 漏洞代码、危险模式 |
| ⚠️ | 警告 | 需要根据上下文判断的代码 |
| 💡 | 洞察 | 关键知识点、审计技巧 |
| 🔄 | 循环 | 递归或循环操作 |
| 💰 | 财务 | 涉及资金转移的操作 |

**示例**：
```solidity
function withdraw(uint256 amount) external {
    require(balances[msg.sender] >= amount); // ✅ 检查在前

    // ❌ 危险: 外部调用在状态更新前
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success);

    // 💡 关键点: 此时攻击者可以重入
    balances[msg.sender] -= amount; // ❌ 状态更新太晚

    // 💰 资金已转移但状态未更新
}
```

---

## 工具与资源

### 推荐工具

#### 1. 区块浏览器
- **Ethereum**: [Etherscan](https://etherscan.io)
- **Solana**: [Solscan](https://solscan.io), [Solana Explorer](https://explorer.solana.com)
- **BSC**: [BscScan](https://bscscan.com)
- **Polygon**: [PolygonScan](https://polygonscan.com)
- **Arbitrum**: [Arbiscan](https://arbiscan.io)

#### 2. 安全分析来源
- **Rekt News**: https://rekt.news (DeFi 安全事件深度报道)
- **PeckShield**: https://twitter.com/peckshield (实时告警)
- **SlowMist**: https://slowmist.io/hacked (被黑事件数据库)
- **CertiK**: https://certik.com/resources/blog

#### 3. 审计报告来源
- **Code4rena**: https://code4rena.com/reports
- **Sherlock**: https://audits.sherlock.xyz
- **OpenZeppelin**: https://blog.openzeppelin.com/security-audits
- **Trail of Bits**: https://github.com/trailofbits/publications

#### 4. 开发者工具
- **Foundry**: 测试和PoC开发
  ```bash
  forge test --match-contract VaultExploitTest -vvv
  ```
- **Hardhat**: 测试环境
- **Tenderly**: 交易模拟和调试
- **Etherscan Deth**: 反编译字节码

#### 5. 文档工具
- **Markdown编辑器**: VSCode + Markdown All in One
- **代码高亮**: 使用语言标识符（`solidity`, `rust`, `javascript`）
- **图表**: Excalidraw（ASCII图）, Mermaid（流程图）
- **截图**: 使用区块浏览器截图时标注关键信息

### 有用的资源

#### 学习资料
- [Solidity Security Considerations](https://docs.soliditylang.org/en/latest/security-considerations.html)
- [ConsenSys Smart Contract Best Practices](https://consensys.github.io/smart-contract-best-practices/)
- [SWC Registry](https://swcregistry.io/) - 智能合约弱点分类
- [DeFi Threat Matrix](https://github.com/manifoldfinance/defi-threat)

#### 社区
- **Discord**: [加入 blockchain_goldmine 服务器](链接)
- **Telegram**: [案例研究讨论组](链接)
- **GitHub Discussions**: [论坛](链接)

---

## 常见问题

### Q: 我可以为小额损失（<$1M）的事件创建案例研究吗？

A: 可以，如果该事件具有以下特点之一：
- 技术上有新颖性（全新的攻击向量）
- 对行业有重大影响（导致标准更新等）
- 是某类漏洞的经典案例
否则，建议优先记录高影响事件。

### Q: 案例研究可以用英文编写吗？

A: 当前项目主要使用简体中文。如果您更熟悉英文，可以先用英文编写，我们可以协助翻译。请在PR中注明。

### Q: 如果找不到官方事后分析报告怎么办？

A: 可以使用多个二级来源（安全公司分析、研究员分析等）替代。但必须确保：
1. 至少有2个独立的可靠来源
2. 链上数据可验证
3. 在文档中明确标注"无官方事后分析"

### Q: 案例研究需要包含攻击的PoC代码吗？

A: 不是必需的，但强烈推荐。PoC代码可以：
- 验证您对漏洞的理解
- 帮助审计人员学习检测方法
- 提高案例研究的实用价值

如果添加PoC，请使用 Foundry/Hardhat 测试格式。

### Q: 如何处理仍在调查中的事件？

A: 可以创建"草稿"状态的案例研究，但需要：
1. YAML 中设置 `review_status: "Draft - Under Investigation"`
2. 在执行摘要中明确标注"调查进行中"
3. 避免未经证实的推测
4. 随时更新已确认的信息

### Q: 我可以更新他人提交的案例研究吗？

A: 可以！欢迎任何改进，包括：
- 补充新发现的技术细节
- 更新资金追回状态
- 修正错误
- 添加新的参考资料

请创建PR并在描述中说明更新内容。

### Q: 审查通常需要多长时间？

A: 一般流程：
- 自动化检查：立即
- 社区审查：1-3天
- 核心团队审查：3-7天
- 总计：约1-2周

高质量的提交（完整、准确、有详细来源）会更快通过审查。

---

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系：

- **GitHub Issues**: [提交问题](https://github.com/user/blockchain_goldmine/issues)
- **Discord**: [加入讨论](链接)
- **Email**: maintainer@blockchain-goldmine.org

---

## 许可协议

所有贡献的内容将在 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 许可下发布。这意味着：

- ✅ 任何人可以自由使用、分享、修改
- ✅ 必须注明原作者
- ✅ 衍生作品必须使用相同许可

提交PR即表示您同意以此许可发布您的贡献。

---

**感谢您为区块链安全社区做出贡献！**

通过记录和分析历史安全事件，我们帮助整个行业学习、改进，最终减少未来的安全事故。每一个案例研究都是宝贵的集体知识资产。

---

**更新日期**: 2024-12-14
**版本**: 1.0
