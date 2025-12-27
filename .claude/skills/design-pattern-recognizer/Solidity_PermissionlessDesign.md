# Solidity - Permissionless Design Pattern

## Details

**定义**: Permissionless Design（无许可设计）是指 DeFi 协议允许用户自由创建市场、选择外部依赖（如预言机、抵押品）而无需协议方审核或白名单，协议仅验证参数有效性而非最优性，用户自行承担选择风险。

**设计哲学**: "Don't be evil, be neutral" - 协议保持中立，不对外部依赖质量做判断，最大化去中心化和创新自由度，将选择权和责任交给用户。

**核心特征**:
1. 用户可自由创建市场/池子，无需许可
2. 用户可选择外部依赖（oracle, collateral, parameters）
3. 协议仅验证参数范围，不验证参数质量
4. 无 oracle/collateral 白名单机制
5. README 明确说明用户责任边界

**应用场景**:
- **Lending 协议**: 用户创建借贷市场并选择 oracle
- **AMM DEX**: 用户创建任意代币对的流动性池
- **Options 协议**: 用户创建任意标的的期权合约
- **Prediction Markets**: 用户创建任意事件的预测市场

**为何被误判为漏洞**:

传统审计工具会将"用户可选 oracle"误认为预言机操纵漏洞:
- ❌ "单一预言机风险" → 实际: 用户选择，协议不负责
- ❌ "未验证 oracle 可靠性" → 实际: 有意设计，permissionless
- ❌ "可使用恶意 oracle" → 实际: 用户责任，协议保持中立
- ❌ "缺少 oracle 白名单" → 实际: 白名单违背 permissionless 理念

但这是有意设计，目的是:
- ✅ 最大化创新自由（任意资产可创建市场）
- ✅ 去中心化（协议不做中心化决策）
- ✅ 可组合性（支持任意 oracle 接口）
- ✅ 抗审查性（无单点控制）

**代码示例**:

```solidity
// ✅ Permissionless Design - 用户自由创建市场 (Morpho Blue 真实案例)
contract MorphoBlue {
    /// @notice Create a market with user-selected parameters
    /// @dev Anyone can create a market - no whitelist, no governance approval
    /// @param oracle User-selected oracle address
    /// @param lltv User-selected liquidation LTV
    function createMarket(
        address collateralToken,
        address loanToken,
        address oracle,  // ← 用户选择 oracle
        uint256 lltv
    ) external returns (bytes32 marketId) {
        // ✅ 仅验证参数范围（有效性），不验证质量
        require(lltv <= MAX_LLTV, "LLTV too high");
        require(lltv > 0, "LLTV cannot be 0");

        // ✅ 不验证 oracle 是否可靠（用户责任）
        // ✅ 不验证 collateral 是否安全（用户责任）

        marketId = keccak256(abi.encode(collateralToken, loanToken, oracle, lltv));
        markets[marketId] = Market({...});

        emit CreateMarket(marketId, msg.sender);
    }

    /// @notice Get oracle price - no validation
    /// @dev Price quality is user's responsibility
    function getOraclePrice(bytes32 marketId) public view returns (uint256) {
        Market memory market = markets[marketId];
        // ✅ 直接调用用户选择的 oracle，不验证可靠性
        return IOracle(market.oracle).latestAnswer();
    }
}
```

```solidity
// ❌ 非 Permissionless - 中心化控制
contract CentralizedProtocol is Ownable {
    mapping(address => bool) public approvedOracles;
    mapping(address => bool) public approvedCollaterals;

    // ❌ 仅协议方可添加 oracle
    function addOracle(address oracle) external onlyOwner {
        approvedOracles[oracle] = true;
    }

    // ❌ 创建市场需要使用白名单
    function createMarket(
        address collateral,
        address oracle
    ) external {
        require(approvedCollaterals[collateral], "Collateral not approved");
        require(approvedOracles[oracle], "Oracle not approved");
        // ...
    }
}
```

**Quick Locating (L2-L3 审计级别)**:

**L2 跳读**:
1. 搜索 `createMarket`/`createPool` 函数 → 检查是否有白名单验证
2. 搜索 `approvedOracles`/`whitelistedTokens` → 若无则可能是 permissionless
3. 搜索 `onlyOwner`/`onlyGovernance` 限制 → 若创建函数无限制则是 permissionless
4. 查看 README 是否提到 "permissionless", "oracle agnostic", "user responsibility"

**L3 逐行**:
1. 分析 createMarket() 的参数验证逻辑:
   - ✅ 仅验证范围: `require(lltv <= MAX_LLTV)`
   - ❌ 验证质量: `require(isOracleReliable(oracle))`
2. 检查是否有 oracle 白名单: `mapping(address => bool) approvedOracles`
3. 查看 oracle 调用是否有可靠性检查
4. 阅读 README 的风险披露部分

**快速检测脚本**:
```bash
# 检测 Permissionless Design 特征
echo "=== Permissionless Design 检测 ==="
echo "1. createMarket 函数权限:"
grep -A 10 "function createMarket" src/**/*.sol | grep -E "onlyOwner|onlyGovernance|require.*approved"
echo "2. Oracle 白名单:"
grep -r "approvedOracles\|whitelistedOracles\|oracleWhitelist" src/ | wc -l
echo "3. Collateral 白名单:"
grep -r "approvedCollaterals\|whitelistedTokens" src/ | wc -l
echo "4. README 中的用户责任声明:"
grep -i "user.*responsib\|oracle.*agnostic\|permissionless" README.md
```

## Classify

**真实漏洞 vs 设计决策判定**:

### ✅ 这是 Permissionless Design（非漏洞）的条件:

**必须同时满足以下条件**:

1. **代码证据** (必须满足所有 3 项):
   - createMarket() 函数无需许可（无 onlyOwner, 无白名单检查）
   - oracle 参数由用户提供，协议不验证质量
   - 仅验证参数有效性（范围），不验证最优性

2. **文档证据** (至少满足 1 项):
   - README 明确说明 "permissionless market creation"
   - README 明确说明 "oracle agnostic" 或 "user-selected oracle"
   - README 有风险披露: "Users should evaluate oracle reliability"

3. **职责边界** (必须明确):
   - 协议职责: 验证参数范围 (e.g., LTV < 100%)
   - 用户职责: 评估 oracle 质量、collateral 风险
   - 安全边界: 协议不对外部依赖质量负责

**示例判定 - Morpho Blue**:

✅ **代码证据**:
   - createMarket() 无需许可，任何人可调用
   - oracle 参数由用户提供
   - 仅验证 `lltv <= MAX_LLTV`，不验证 oracle 可靠性

✅ **文档证据**:
   - README.md L42: "permissionless market creation"
   - README.md L89: "Users should evaluate oracle reliability when creating markets"

✅ **职责边界**:
   - 协议: 验证 LTV 范围有效
   - 用户: 选择可靠 oracle
   - 边界: 协议不对 oracle 质量负责

**结论**: Morpho Blue 的 "单一预言机" 发现应标记为 **Info（用户责任）**，而非漏洞

### ❌ 这是真实漏洞的情况:

**任何以下情况表明不是 Permissionless Design，仍需报告**:

1. **声称 permissionless 但实际有白名单**:
   ```solidity
   // ❌ 声称 permissionless，但有隐藏白名单
   function createMarket(address oracle) external {
       // 隐藏的白名单检查
       require(_isApprovedOracle(oracle), "Oracle not approved");
   }
   ```

2. **协议依赖 oracle 但不允许用户选择**:
   ```solidity
   // ❌ 协议依赖 oracle，但用户无法选择
   address public immutable ORACLE;  // 协议方固定

   function liquidate(address user) external {
       uint256 price = IOracle(ORACLE).latestAnswer();
       // 协议依赖固定 oracle = 协议责任，需验证可靠性
   }
   ```

3. **文档与代码不一致**:
   - README 声称 "permissionless"
   - 但代码中 createMarket() 有 onlyOwner 限制 → 这是漏洞（误导）

4. **无风险披露的 permissionless**:
   ```solidity
   // ⚠️ 代码是 permissionless，但 README 无风险披露
   // 用户可能不知道需要自己评估 oracle
   // 需要添加文档说明用户责任
   ```

### 边界情况处理

| 情况 | 判定 | 严重性 | 说明 |
|-----|------|-------|------|
| 部分参数可选，部分固定 | 混合设计 | Medium | 需区分协议责任和用户责任 |
| 有推荐 oracle，但用户可选其他 | Permissionless | Info | 推荐不等于白名单 |
| DAO 投票决定白名单 | 非 Permissionless | Low-Medium | 去中心化但仍有限制 |
| 协议验证 oracle 接口但不验证质量 | Permissionless | Info | 接口验证是技术要求 |
| 用户可选 oracle 但协议自己也用它 | 混合责任 | Medium | 需明确职责边界 |

## Low Risk

**何时降低风险等级**:

### 降级规则表

| 原始发现 | 降级条件 | 新等级 | 原因 |
|---------|---------|-------|------|
| 单一预言机风险 | 用户可选，有文档披露 | **Info** | 用户责任，已披露 |
| 未验证 oracle 可靠性 | Permissionless 设计 | **Info** | 有意设计，协议中立 |
| 可使用恶意 oracle | 用户选择，风险自担 | **Info** | 用户责任边界 |
| 缺少 oracle 白名单 | Permissionless 理念 | **Info** | 白名单违背设计哲学 |
| 缺少 collateral 白名单 | Permissionless 理念 | **Info** | 用户评估抵押品风险 |

### 具体调整建议

**1. 针对 oracle-manipulation-analyzer**:

```markdown
## 调整建议

检测到项目采用 Permissionless Design（oracle agnostic）：
- "单一预言机" 发现: High → Info（用户责任）
- "未验证 oracle" 发现: High → Info（有意设计）
- 添加注释: "用户选择 oracle 并自行承担风险，协议保持中立"

**需验证的 Permissionless 特征**:
1. createMarket() 无需许可（无 onlyOwner）
2. oracle 参数由用户提供
3. README 有用户责任披露

**仍需报告高危的情况**:
- 协议自身依赖用户选择的 oracle（职责混乱）
- 声称 permissionless 但有隐藏白名单
- 无风险披露文档（用户不知情）
```

**2. 针对 access-control-analyzer**:

```markdown
## 调整建议

检测到 Permissionless 市场创建:
- "任何人可创建市场" 发现: Medium → Info（有意设计）
- 标记为 permissionless 特性而非访问控制缺失
```

### 报告中的正确表述

**❌ 错误报告**:
```
严重性: High
漏洞: 单一预言机风险
描述: 协议使用单一 oracle 提供价格，存在预言机操纵风险
建议: 使用多个 oracle 并取中位数，或采用时间加权平均价格
```

**✅ 正确报告 (Permissionless Design 识别后)**:
```
严重性: Info（用户责任）
发现: Permissionless Oracle Selection
描述: 此项目采用 permissionless 设计，用户在创建市场时自由选择 oracle。
      协议仅验证参数范围有效性（LTV < MAX_LTV），不验证 oracle 可靠性。
      这是有意的设计决策，目的是最大化去中心化和创新自由度。
证据:
  - README.md L42: "permissionless market creation"
  - README.md L89: "Users should evaluate oracle reliability when creating markets"
  - createMarket() 函数无需许可，oracle 参数由用户提供
  - 代码仅验证参数范围，不验证 oracle 质量
职责边界:
  - 协议职责: 验证 LTV <= MAX_LLTV（参数有效性）
  - 用户职责: 评估 oracle 可靠性、选择安全的抵押品
  - 安全边界: 协议不对用户选择的 oracle 质量负责
影响: 用户需自行承担 oracle 操纵风险，这是 permissionless 设计的权衡
建议:
  - 用户: 选择使用可靠 oracle 的市场（如 Chainlink, Uniswap TWAP）
  - 协议: 在前端 UI 显示 oracle 来源，帮助用户评估风险
```

**⚠️ 需要保留的中危报告 (混合职责场景)**:
```
严重性: Medium
漏洞: 协议依赖用户选择的 oracle
描述: 协议在全局清算逻辑中使用用户选择的 oracle，职责边界混乱
代码位置: Liquidator.sol:89
证据:
  - createMarket() 允许用户选择 oracle
  - 但 globalLiquidate() 使用该 oracle 进行协议层清算
  - 职责混乱: 用户选择 (用户责任) vs 协议使用 (协议责任)
建议:
  - 方案 A: 协议层清算使用独立的可信 oracle
  - 方案 B: 明确文档说明协议不做全局清算，仅支持市场内清算
```

## 实际案例分析

### 案例 1: Morpho Blue Permissionless Markets

**代码**:
```solidity
function createMarket(
    address collateralToken,
    address loanToken,
    address oracle,  // 用户选择
    uint256 lltv
) external returns (bytes32 marketId) {
    require(lltv <= MAX_LLTV, "LLTV too high");  // 仅验证范围
    // 不验证 oracle 可靠性
    // 不验证 collateral 安全性

    marketId = keccak256(abi.encode(collateralToken, loanToken, oracle, lltv));
    markets[marketId] = Market({...});
}
```

**传统审计工具报告**:
- ❌ High: 单一预言机风险
- ❌ High: 未验证 oracle 可靠性
- ❌ Medium: 缺少 oracle 白名单

**正确分析 (Permissionless Design)**:
```markdown
严重性: Info（用户责任）
发现: Permissionless Design - Oracle Agnostic
证据:
  - README: "permissionless market creation"
  - README: "Users should evaluate oracle reliability"
  - 代码: 用户选择 oracle，协议不验证
职责边界:
  - 协议: 验证 LTV 范围
  - 用户: 选择可靠 oracle
结论: 安全，用户自担风险
```

### 案例 2: Uniswap V2 任意代币对

**设计**:
- 任何人可创建任意代币对的流动性池
- 无代币白名单
- 用户自行评估代币风险

**判定**: Permissionless Design，"缺少代币白名单" 为设计决策而非漏洞

### 案例 3: Compound V2 (对比案例 - 非 Permissionless)

**设计**:
```solidity
// 仅治理可添加市场
function _supportMarket(CToken cToken) external {
    require(msg.sender == admin, "Only admin");
    markets[address(cToken)] = Market({...});
}
```

**判定**: 非 Permissionless，协议对市场质量负责，需验证 oracle 可靠性

### 案例 4: 伪 Permissionless (反面案例)

```solidity
// ❌ 声称 permissionless 但有隐藏限制
function createMarket(address oracle) external {
    require(!blacklistedOracles[oracle], "Oracle blacklisted");
    // 有黑名单 = 协议在做判断 = 非真正 permissionless
}
```

**判定**: 非真实 Permissionless，oracle 风险仍需报告为 Medium

## 用户责任 vs 协议责任

### 清晰的职责边界

#### ✅ 用户责任（Permissionless 场景）

| 用户选择 | 用户责任 | 协议职责 |
|---------|---------|---------|
| Oracle 地址 | 评估 oracle 可靠性、操纵风险 | 验证 oracle 接口兼容性 |
| Collateral 代币 | 评估代币流动性、合约风险 | 验证 ERC20 接口 |
| LTV 参数 | 选择合理的 LTV 值 | 验证 LTV <= MAX_LLTV |
| Interest Rate 模型 | 评估利率合理性 | 验证模型接口兼容性 |

#### ❌ 协议责任（中心化场景）

| 协议选择 | 协议责任 | 审计要求 |
|---------|---------|---------|
| 固定 Oracle | 确保 oracle 可靠性 | 必须验证多签、延迟、去中心化 |
| 白名单 Collateral | 确保代币安全性 | 必须审查代币合约代码 |
| 固定 LTV | 确保 LTV 合理性 | 必须进行压力测试 |
| 协议 Interest Rate | 确保利率模型安全 | 必须审查模型逻辑 |

### 混合责任场景（需特别注意）

**场景 1: 用户选择，协议也使用**
```solidity
// ⚠️ 职责混乱
mapping(bytes32 => Market) public markets;  // 用户创建

function globalLiquidate() external {
    for (bytes32 marketId in allMarkets) {
        uint256 price = markets[marketId].oracle.latestAnswer();
        // 协议在全局逻辑中使用用户选择的 oracle
    }
}
```

**判定**: Medium 风险（职责边界不清）

**场景 2: 推荐但不强制**
```solidity
// ✅ 清晰边界
address public recommendedOracle;  // 推荐

function createMarket(address oracle) external {
    // 用户可选其他 oracle，协议不强制
}
```

**判定**: Info（Permissionless）

## DeFi 生态中的 Permissionless 理念

### 核心原则

1. **协议中立性**: 协议不做主观判断
2. **创新自由度**: 支持任意资产/参数组合
3. **去中心化**: 无单点控制或审批流程
4. **可组合性**: 兼容任意符合接口的外部依赖
5. **抗审查性**: 协议无法阻止用户创建市场

### 权衡取舍

| 优点 | 代价 |
|-----|------|
| ✅ 最大化创新（支持任意资产） | ⚠️ 用户可能选择不良 oracle |
| ✅ 去中心化（无需许可） | ⚠️ 无法阻止恶意市场 |
| ✅ 可组合性（任意 oracle 接口） | ⚠️ oracle 质量参差不齐 |
| ✅ 抗审查（协议无法关停市场） | ⚠️ 监管风险 |

### 在审计中的处理

- **识别 Permissionless 设计**
- **区分协议责任和用户责任**
- **验证文档是否充分披露风险**
- **调整严重性**: 用户责任 → Info
- **报告中引用职责边界说明**

## 检查清单

使用此清单验证 Permissionless Design 模式:

- [ ] createMarket/createPool 函数无需许可（无 onlyOwner）
- [ ] oracle/collateral 参数由用户提供
- [ ] 协议仅验证参数有效性，不验证质量
- [ ] 无 oracle 白名单: `approvedOracles` mapping 不存在
- [ ] 无 collateral 白名单: `whitelistedTokens` mapping 不存在
- [ ] README 明确说明 "permissionless" 或 "oracle agnostic"
- [ ] README 有风险披露: "Users should evaluate..."
- [ ] 职责边界清晰: 协议验证范围，用户验证质量
- [ ] 协议自身不依赖用户选择的 oracle（无混合职责）
- [ ] 代码与文档一致（无隐藏白名单）

全部 ✅ → 确认 Permissionless Design，调整 oracle 相关发现

## 总结

**核心原则**: Permissionless Design 将选择权交给用户，协议保持中立

**识别要点**:
1. 用户可自由创建市场，选择 oracle/collateral
2. 协议仅验证有效性（范围），不验证质量
3. README 明确披露用户责任边界

**影响**:
- oracle-manipulation-analyzer: High → Info（用户责任）
- "单一预言机" 发现: 标记为用户选择，已披露
- "缺少白名单" 发现: 标记为 permissionless 特性

**在报告中**:
- 明确区分协议责任和用户责任
- 引用 README 的职责边界说明
- 标记为 "用户责任" 而非 "协议漏洞"
- 验证文档是否充分披露风险
