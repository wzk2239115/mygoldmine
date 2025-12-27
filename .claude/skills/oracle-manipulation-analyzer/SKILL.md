---
name: oracle-manipulation-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证预言机操纵（Oracle Manipulation）漏洞；重点关注外部数据源的可信性、更新机制和抗操纵性，包括不可信TWAP、单一数据源、未验证链下签名、价格偏差无熔断等；涵盖DeFi协议、借贷清算、稳定币定价、跨链桥等业务场景；利用按编程语言组织的参考资料目录中的参考指南。
---
**Oracle Manipulation**

**Attention**
当项目依赖外部或链下数据源（如价格、汇率、事件结果等）作为链上决策依据，且未对数据来源的可信性、更新机制或抗操纵性进行充分验证时，应重点审计 Oracle 相关模块。此类漏洞通常出现在 DeFi 协议（如借贷、衍生品、稳定币）、预言机集成、自动化清算、跨链桥等业务逻辑中，尤其集中在数据获取、验证、更新和使用环节。

**设计模式上下文**
在检测预言机操纵漏洞前，先运行 [design-pattern-recognizer](../design-pattern-recognizer/SKILL.md) 和 [protocol-doc-analyzer](../protocol-doc-analyzer/SKILL.md) 识别项目的设计理念和职责边界，以避免误报：

- **Permissionless Design 模式**（无许可设计）：
  - 特征: 用户可自由创建市场并选择 oracle，协议仅验证参数有效性而非质量
  - 证据:
    - createMarket() 函数接受 oracle 地址参数（用户提供）
    - 无 oracle 白名单验证
    - README 明确说明 "permissionless market creation" 或 "oracle agnostic"
    - README 有风险披露: "Users must evaluate oracle reliability"
  - 职责边界:
    - 协议职责: 验证 oracle 接口兼容性、参数范围有效性
    - 用户责任: 评估 oracle 可靠性、价格准确性
    - 安全边界: 协议不对用户选择的 oracle 质量负责
  - 影响: 用户可选 oracle 场景 → Info（用户责任），而非 High（协议漏洞）
  - 详见: [design-pattern-recognizer/Solidity_PermissionlessDesign.md](../design-pattern-recognizer/Solidity_PermissionlessDesign.md)

**调整建议（Permissionless 场景）**:
| 发现类型 | 原严重性 | 新严重性 | 条件 |
|---------|---------|---------|------|
| 单一预言机风险 | High | Info | 用户可选 + 有文档披露 |
| 未验证 oracle 可靠性 | High | Info | Permissionless 设计 |
| 缺少 oracle 白名单 | Medium | Info | Permissionless 理念 |

**仍需报告为高危的情况**（即使是 Permissionless）：
- 协议自身依赖用户选择的 oracle（职责混乱）
  - 示例: 用户创建市场时选择 oracle，但协议在全局清算逻辑中使用该 oracle
- 声称 permissionless 但有隐藏白名单或黑名单
- 用户可选 oracle 但无风险披露文档（用户不知情）
- Oracle 接口验证缺失（协议职责范围内）

**Early exit**  
若项目完全不依赖任何外部数据源（即所有状态变量均为链上原生生成、无任何价格或事件输入依赖），且未集成任何预言机服务（包括自建或第三方如 Chainlink、Pyth、Witnet 等），则可快速退出对该漏洞类型的审计。

**Cases**

**Solidity**  
常出现在价格预言机、借贷利率计算、清算阈值判定、跨链消息验证等业务逻辑实现中，包括但不限于直接使用 Uniswap/TWAP 价格、未验证签名的链下喂价、单一数据源无聚合机制等方式：  
- 不可信 TWAP 预言机：直接使用单个 DEX 的 TWAP 价格，易被闪电贷操纵，详见：[Solidity_UntrustedTWAPOracle.md](Solidity_UntrustedTWAPOracle.md)  
- 单一来源价格喂送：仅依赖单一预言机数据源，无冗余验证机制，数据源故障或作恶导致系统失效，详见：[Solidity_SingleSourcePriceFeed.md](Solidity_SingleSourcePriceFeed.md)  
- 未验证的链下签名数据：接受链下签名的价格数据但未验证签名者身份或数据时效性，详见：[Solidity_SignedOffchainDataWithoutValidation.md](Solidity_SignedOffchainDataWithoutValidation.md)  

**Rust**  
常出现在基于 Solana 或 Substrate 的 DeFi 项目中，涉及链下签名喂价、账户状态依赖外部聚合器、时序敏感的价格更新逻辑等，包括但不限于未校验喂价者权限、未设置价格偏差熔断、依赖单一客户端数据源等方式：  
- 未验证的预言机签名者：接受预言机数据但未验证提供者的签名或权限，允许恶意数据注入，详见：[Rust_UnverifiedOracleSigner.md](Rust_UnverifiedOracleSigner.md)  
- 价格偏差无熔断机制：价格更新未设置异常偏差检测，大幅波动时未触发保护机制，详见：[Rust_PriceDeviationWithoutCircuitBreaker.md](Rust_PriceDeviationWithoutCircuitBreaker.md)  
- 中心化聚合器依赖：完全依赖单一中心化聚合器服务，服务下线或作恶导致协议瘫痪，详见：[Rust_CentralizedAggregatorDependency.md](Rust_CentralizedAggregatorDependency.md)  

**Move**  
常出现在 Aptos 或 Sui 生态中的资产定价、流动性挖矿奖励计算、杠杆交易保证金评估等场景，包括但不限于直接读取未经验证的资源字段、未对预言机更新者实施访问控制、缺乏价格滑点检查等方式：  
- 未检查的预言机资源读取：直接读取预言机资源字段但未验证数据有效性或更新时间，详见：[Move_UncheckedOracleResourceRead.md](Move_UncheckedOracleResourceRead.md)  
- 缺失预言机更新者访问控制：预言机数据更新函数未限制调用者身份，任意用户可注入虚假数据，详见：[Move_MissingOracleUpdaterACL.md](Move_MissingOracleUpdaterACL.md)  
- 预言机使用无滑点控制：使用预言机价格进行交易或清算但未设置滑点保护，价格剧烈波动时损失扩大，详见：[Move_NoSlippageControlInOracleUsage.md](Move_NoSlippageControlInOracleUsage.md)  

**Vyper**  
常出现在基于 Vyper 编写的借贷协议、稳定币或期权合约中，涉及 TWAP 读取、链下签名价格注入、多源加权均价计算等，包括但不限于未校验时间窗口有效性、未对签名进行重放保护、未实现价格异常回退机制等方式：  
- TWAP 无时间戳验证：使用 TWAP 计算平均价格但未验证时间窗口的有效性，允许使用过期或未来数据，详见：[Vyper_TwapWithoutTimestampValidation.md](Vyper_TwapWithoutTimestampValidation.md)  
- 签名价格无 Nonce 检查：接受链下签名的价格数据但未验证 nonce，允许重放攻击，详见：[Vyper_SignedPriceWithoutNonceCheck.md](Vyper_SignedPriceWithoutNonceCheck.md)  
- 预言机回退机制缺失：主预言机失败时无备用机制，导致协议无法获取价格数据而瘫痪，详见：[Vyper_OracleFallbackMechanismMissing.md](Vyper_OracleFallbackMechanismMissing.md)  

**Go**  
常出现在 Cosmos SDK 或自定义区块链的链上验证逻辑、IBC 数据包中继、跨链预言机中继器等组件中，包括但不限于未验证外部数据签名、中继器未实施数据过滤、链上合约盲目信任中继消息等方式：  
- IBC 中未签名的外部数据：通过 IBC 接收外部数据但未验证数据签名或来源，允许恶意节点注入虚假信息，详见：[Go_UnsignedExternalDataInIBC.md](Go_UnsignedExternalDataInIBC.md)  
- 预言机中继器无数据清洗：中继器转发链下数据到链上但未进行数据格式验证或异常值过滤，详见：[Go_OracleRelayerWithoutDataSanitization.md](Go_OracleRelayerWithoutDataSanitization.md)  
- 智能合约盲目信任中继负载：链上合约直接使用中继器提供的数据但未二次验证，详见：[Go_SmartContractTrustsRelayPayloadBlindly.md](Go_SmartContractTrustsRelayPayloadBlindly.md)