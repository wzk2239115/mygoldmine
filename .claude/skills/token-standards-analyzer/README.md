# 代币标准审计指南库 - 使用指南

## 项目概览

这是一个专业的代币标准实现审计参考库，包含 22 个精心编写的审计小抄文件，覆盖 6 个编程语言（Solidity、Vyper、Rust、Move、Go）和多个代币标准（ERC-20、ERC-721、ERC-1155、SPL Token、CW20、CW721、Cosmos Token、IBC Token 等）。

## 文件组织结构

```
token_standards/
├── general.md                                    # 通用审计方法论
├── Solidity_ERC20_*.md                          # Solidity ERC-20 审计指南 (3个)
├── Solidity_ERC721_*.md                         # Solidity ERC-721 审计指南 (2个)
├── Solidity_ERC1155_*.md                        # Solidity ERC-1155 审计指南 (2个)
├── Vyper_ERC20_*.md                             # Vyper ERC-20 审计指南 (2个)
├── Vyper_ERC721_*.md                            # Vyper ERC-721 审计指南 (1个)
├── Rust_SPLToken_*.md                           # Rust SPL Token 审计指南 (2个)
├── Rust_CW20_*.md                               # Rust CW20 审计指南 (1个)
├── Rust_CW721_*.md                              # Rust CW721 审计指南 (1个)
├── Move_Coin_*.md                               # Move Coin 审计指南 (2个)
├── Move_NFT_*.md                                # Move NFT 审计指南 (1个)
├── Go_Token_*.md                                # Go Token 审计指南 (2个)
└── Go_IBCToken_*.md                             # Go IBC Token 审计指南 (1个)
```

## 快速开始

### 第一步：确认审计范围

根据项目使用的编程语言快速定位相关的审计指南：

| 编程语言 | 代币标准 | 文件前缀 |
|---------|---------|---------|
| Solidity | ERC-20 | Solidity_ERC20_ |
| Solidity | ERC-721 | Solidity_ERC721_ |
| Solidity | ERC-1155 | Solidity_ERC1155_ |
| Vyper | ERC-20 | Vyper_ERC20_ |
| Vyper | ERC-721 | Vyper_ERC721_ |
| Rust | SPL Token | Rust_SPLToken_ |
| Rust | CW20 | Rust_CW20_ |
| Rust | CW721 | Rust_CW721_ |
| Move | Coin | Move_Coin_ |
| Move | NFT | Move_NFT_ |
| Go | Token | Go_Token_ |
| Go | IBC Token | Go_IBCToken_ |

### 第二步：阅读通用指南

先阅读 `general.md`，了解：
- 5 个审计等级（L0-L4）和每个等级的耗时
- 标准的审计流程和方法论
- 漏洞/误报/代码异味的判断标准
- 常见陷阱检查表

### 第三步：按等级进行审计

针对具体的代币标准实现，按以下流程审计：

#### L0：快速资格确认（3分钟）
使用 `general.md` 中的关键词列表，快速确认项目是否涉及代币标准。

#### L1：关键词扫描（5-10分钟）
在相应的审计指南文件中查看"核心操作定位"部分，使用推荐的关键词搜索核心函数。

#### L2：跳读验证（10-20分钟）
在审计指南文件中查看"保护机制定位"部分，检查返回值、接口、事件定义的符合性。

#### L3：逐行验证（20-40分钟）
深入阅读代码，验证转账逻辑、授权机制、错误处理等细节。

#### L4：跨模块追踪（40+分钟）
追踪完整的业务流程，检查权限控制、重入防护、状态一致性等。

## 审计指南文件的标准结构

每个审计指南文件都包含三个主要部分：

### 1. Details 部分

**目的**：快速定位问题所在

**包含内容**：
- 问题的简要描述和影响范围
- 代码示例（展示常见的错误实现）
- 核心操作定位技巧（L1：关键词扫描等）
- 保护机制定位技巧（L2-L3：如何验证逻辑）

**使用方式**：
1. 快速阅读问题描述，理解这个漏洞是什么
2. 使用推荐的关键词快速在代码中搜索相关函数
3. 参考代码示例识别常见的错误模式

### 2. Classify 部分

**目的**：判断发现的问题是漏洞、误报还是代码异味

**包含内容**：
- 漏洞判定标准（Bug）- 什么情况下确认为漏洞
- 误报排除标准（False Positive）- 什么情况下应该排除
- 代码异味（Code Smell）- 可疑但非严格漏洞的迹象

**使用方式**：
1. 发现问题后，参考"漏洞判定"部分的标准评估
2. 检查是否符合"误报排除"中的任何条件
3. 如果符合某个条件就需要排除或降低等级

### 3. Low risk 部分

**目的**：识别应该评为低风险的合理情况

**包含内容**：
- 各种低风险评级的合理场景和背景说明

**使用方式**：
1. 对于发现的问题，查看是否属于"低风险"部分的某个场景
2. 如果项目有合理的背景（如明确的文档说明），则评为低风险
3. 避免误判为严重漏洞

## 审计工作流示例

### 示例：审计一个 Solidity ERC-20 合约

**第一步：定位相关文件**
```
因为是 Solidity ERC-20，所以查看：
- general.md （通用方法论）
- Solidity_ERC20_MissingRequiredFunctions.md
- Solidity_ERC20_InvalidReturnValue.md
- Solidity_ERC20_InvalidEventDefinition.md
```

**第二步：L0 快速确认**
在代码中搜索 `ERC-20`, `IERC20`, `transfer`, `approve` 等关键词，确认确实是代币合约。

**第三步：L1 关键词扫描（5-10分钟）**
使用每个文件中的关键词列表：
```
搜索: function totalSupply, function balanceOf, function transfer,
      function approve, function transferFrom, function allowance
```
确认所有 6 个核心函数都存在。

**第四步：L2 跳读验证（10-20分钟）**
逐一检查：
- 返回值是否正确（bool 而不是 void）
- Transfer 和 Approval 事件是否正确定义
- 是否实现了 IERC20 接口

**第五步：L3 逐行验证（20-40分钟）**
深入检查：
- transfer 是否正确扣减发送者余额、增加接收者余额
- approve 是否更新 allowance 映射
- transferFrom 是否检查授权额度并扣减
- 所有转账都是否发出 Transfer 事件

**第六步：分类和报告**
参考 Classify 部分，判断是否为漏洞、误报或代码异味，据此撰写审计报告。

## 关键特点

### 1. 语言简洁精炼
- 所有文件都采用精炼的表述
- 无冗长的背景说明或不必要的解释
- 可直接用作审计工作中的参考小抄

### 2. 代码示例准确
- 所有代码示例都是真实的代码，而不是伪代码
- 清晰标注问题所在（使用 ❌ 标记）
- 给出实际的错误表现

### 3. 关键词扫描高效
- 推荐的关键词都经过验证，确实能快速定位问题
- 避免过多的噪音结果
- 支持 IDE 内的快速搜索

### 4. 审计等级清晰
- 从 L0（3分钟）到 L4（40+分钟）清晰划分
- 不同审计深度的要求明确
- 可根据时间和风险等级灵活调整

### 5. 误报排除完整
- 每个文件都包含常见的误报场景
- 帮助审计员避免误判
- 节省重复确认的时间

### 6. 考虑实际场景
- 低风险评定考虑多种合理的实现场景
- 不过度判断代理模式、继承链等复杂情况
- 提供背景因素说明

## 常用查询

### 问题：项目使用 Solidity，需要审计 ERC-20，应该看什么文件？

答：按以下顺序：
1. general.md - 了解通用审计方法
2. Solidity_ERC20_MissingRequiredFunctions.md - 核心函数检查
3. Solidity_ERC20_InvalidReturnValue.md - 返回值检查
4. Solidity_ERC20_InvalidEventDefinition.md - 事件定义检查

### 问题：发现代币合约缺少 transfer 函数，应该评为什么等级？

答：参考相应文件的 Classify 部分：
1. 确认合约是否声称实现 ERC-20 标准
2. 检查 Classify 中的"漏洞判定"标准
3. 查看"误报排除"是否适用
4. 最后判断是 High/Medium/Low 还是误报

### 问题：代币合约的某个细节不符合标准，但项目文档中有说明，怎么办？

答：参考"Low risk"部分：
1. 查看是否属于"合约明确文档声明"的场景
2. 如果有充分的文档支持，可以评为 Info/Low
3. 确保文档清晰明确地说明了这个偏离

## 审计清单使用

对于每个发现的问题，可以用以下清单进行检查：

- [ ] 问题明确性：问题描述是否清晰具体？
- [ ] 标准符合性：是否确实违反了声称的标准？
- [ ] 影响范围：这个问题会影响什么功能？
- [ ] 误报排除：是否属于"误报排除"中的任何情况？
- [ ] 低风险场景：是否属于"低风险"中的任何场景？
- [ ] 证据充分性：是否有充分的代码证据支持这个发现？
- [ ] 等级评定：是否正确评定了问题的严重程度？

## 补充资源

### 参考标准规范
- ERC-20: https://eips.ethereum.org/EIPS/eip-20
- ERC-721: https://eips.ethereum.org/EIPS/eip-721
- ERC-1155: https://eips.ethereum.org/EIPS/eip-1155
- Cosmos SDK Token: https://docs.cosmos.network/v0.45/modules/bank/
- Move Documentation: https://move-language.github.io/

### 推荐工具
- Solidity: Slither, Hardhat
- Vyper: Vyper Compiler
- Rust: Cargo, Clippy
- Go: go vet, go staticcheck

## 反馈和改进

如果在使用过程中发现：
- 某个审计指南不够准确或清晰
- 遗漏了某个常见的漏洞模式
- 有建议改进的地方

欢迎提交反馈。这个库会根据实际审计工作的经验不断优化。

---

**最后更新**：2024 年
**涵盖的漏洞类型**：22 种
**总代码行数**：1936 行
**审计覆盖范围**：6 种编程语言，10 个代币标准
