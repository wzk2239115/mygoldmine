# Solidity 闪电贷清算滥用 (FlashLoan Liquidation Abuse)

**漏洞概述**  
攻击者利用闪电贷瞬间操纵抵押品价格或债务价值，触发协议清算逻辑，以低于正常市场价获取资产或窃取清算奖励。常见于借贷协议的清算模块、价格预言机集成点、健康因子计算逻辑中。

---

## Details

**代码示例（典型清算函数）**
```solidity
function liquidate(address borrower, address collateral, address debt) external {
    uint256 collateralPrice = oracle.getPrice(collateral);  // 价格查询点
    uint256 debtPrice = oracle.getPrice(debt);
    uint256 healthFactor = calculateHealth(borrower, collateralPrice, debtPrice);  // 健康因子计算
    
    require(healthFactor < 1e18, "Position healthy");  // 清算条件判断
    
    uint256 liquidationBonus = debtAmount * 108 / 100;  // 清算激励
    collateralToken.transfer(msg.sender, liquidationBonus);  // 资产转移
}
```

**定位核心操作（L3-逐行读）**  
- 清算触发条件：`require(healthFactor < threshold)` 或 `if(collateralValue < debtValue * ratio)`
- 价格获取调用：`oracle.getPrice()`, `getLatestPrice()`, `consult()`, `peek()`
- 健康因子计算：`calculateHealth()`, `getUserAccountData()`, `getBorrowLimit()`
- 资产转移逻辑：清算者获得抵押品的 `transfer()` 或 `safeTransfer()` 调用
- 关注点：价格取值时点是否在同一交易内、是否可被 DEX 流动性操纵

**定位保护机制（L2-跳读 + L4-跨模块追踪）**  
- 价格源防御：
  - L2：查找 `twap`, `timeWeightedAverage`, `chainlinkAggregator` 等时间加权/预言机聚合关键词
  - L4：追踪 `oracle` 变量定义，确认是否使用 Chainlink/Pyth 等链下预言机或多 DEX TWAP
- 清算延迟机制：
  - L2：扫描 `liquidationDelay`, `cooldownPeriod`, `lastUpdate + minInterval`
  - L1：全局搜索 `block.timestamp` 或 `block.number` 作为时间锁
- 清算阈值保护：
  - L3：逐行检查清算比率计算逻辑，确认是否留有安全缓冲（如 150% 抵押率）
  - L2：跳读查找 `minCollateralRatio`, `liquidationThreshold`, `safetyMargin` 常量定义
- 单次清算限额：
  - L1：关键词扫描 `maxLiquidationAmount`, `partialLiquidation`, `closeFactor`
  - L3：确认是否限制单次清算比例（如最多清算 50% 债务）

---

## Classify

**漏洞判定（满足以下任一条件）**
1. 价格源可在单笔交易内操纵：仅依赖单一 DEX 的 `reserves` 或 `getAmountsOut` 实时价格，无 TWAP/延迟机制
2. 健康因子计算缺陷：清算阈值过高（如抵押率 100%）或计算逻辑存在精度损失/溢出风险
3. 清算激励设计不当：清算奖励比例过高（>10%）且无单次限额，可通过闪电贷放大收益
4. 时间窗口漏洞：价格更新与清算判断分离在不同交易/区块，可被抢跑（frontrun）
5. 跨资产价格不一致：多抵押品协议中，不同资产价格更新频率不同，可利用时间差

**误报排除（满足以下全部条件）**
- 使用去中心化预言机（Chainlink）或 30 分钟以上 TWAP 且流动性深度充足（>1000 ETH）
- 清算需经过延迟期（>1 区块）或采用拍卖机制
- 存在多重价格源校验（如预言机偏差 >5% 时拒绝交易）

**代码异味（需降级关注度）**
- 预言机采用 TWAP 但周期较短（<10 分钟）且流动性一般（100-1000 ETH）
- 清算奖励在合理范围（3-8%）但未设置单次清算上限
- 存在手动调整清算参数的 `onlyOwner` 函数（中心化风险但非直接漏洞）

---

## Low Risk

**以下场景可评为低风险（需明确标注前提条件）**
1. **小额资金池**：协议 TVL < 50 ETH，即使存在价格操纵路径，闪电贷成本 >潜在收益
2. **高抵押率要求**：清算阈值 ≥ 200% 且使用 Chainlink 预言机，操纵成本远超清算利润
3. **部分清算机制**：单次仅可清算 20% 债务 + 24 小时冷却期，无法通过单次闪电贷完成攻击
4. **白名单资产**：仅支持 WETH/USDC 等深度流动性资产（>10 亿美元），DEX 价格操纵不可行
5. **清算惩罚转移**：清算罚金部分流入保险基金而非清算人，降低攻击动机
6. **测试网部署**：非主网环境且未处理真实资金

**注意**：以上低风险判定需在审计报告中附上具体数值依据（如当前 TVL、Uniswap V3 流动性深度截图、预言机更新频率测试数据），避免主观臆断。

---

## 审计专业技巧

### 1. 价格源真伪辨别

**真实漏洞案例**
- **Beanstalk 闪电贷攻击**：协议仅依赖自身 Uniswap V2 池子计算豆币价格，攻击者通过闪电贷向池子大量注入 USDC，操纵 `reserve` 比例，瞬间抬高豆币价格至 $1.1+，触发清算逻辑，最终获利 8000 万美元
- **dYdX Flash Loan 滥用**：清算者通过闪电贷获取资金，同交易内操纵 Uniswap 池子流动性，强行降低抵押品价格至清算阈值，完成套利

**审计检查清单**
1. **价格查询代码跟踪**：从 `liquidate()` 函数倒推，找出所有 `oracle.getPrice()` 调用
   - 记录调用链：`liquidate()` → `getPrice()` → 实现逻辑在哪个文件
   - 检查是否通过 `address(oracle)` 初始化时指向了自定义合约而非官方 Chainlink/Pyth
2. **单一预言机依赖判定**：
   - 搜索代码中出现 `getPriceFrom()` 调用的次数，若仅有 1 个来源 → **高风险**
   - 若有 3+ 个来源且取中位数 → **低风险**
3. **实时价格 vs 时间加权价格**：
   - 实时价格特征：`getReserves()`, `balanceOf()`, `getAmountsOut()`，可在同交易内操纵
   - TWAP 特征：`twap`, `cumulativePrice`, `blockTimestampLast` 存在，需多区块参与，单交易难以操纵

**常见误报**
- 代码使用 `chainlinkAggregator.latestRoundData()` 但实际为已废弃接口 → 需检查 Chainlink 合约实际返回值
- 预言机地址在 `initialize()` 后被 `setOracle()` 修改为假地址 → 追踪历史交易验证当前地址真伪

### 2. 清算触发条件的逻辑缺陷

**真实漏洞案例**
- **Venus 清算漏洞**：清算条件判断缺少对 `borrower` 健康因子的实时重算，攻击者可在单笔交易内多次调用 `liquidate()` 清算同一用户，绕过"每用户单笔清算限制"
- **Cream Finance 回溯性攻击**：价格更新与清算判断在不同时间段，攻击者通过闪电贷操纵前一区块价格，在当前交易中触发基于旧价格的清算判断

**精准区分技巧**
1. **状态一致性检验**：
   ```solidity
   // 危险模式 - 无状态恢复
   uint256 health1 = calculateHealth(borrower);
   liquidateAssets(borrower);  // 修改状态
   // 后续逻辑还在用 health1 的值

   // 安全模式 - 先修改后验证
   liquidateAssets(borrower);
   uint256 health2 = calculateHealth(borrower);
   require(health2 >= threshold, "Still unhealthy");
   ```
   审计时需逐行跟踪：清算逻辑修改用户账户状态后，是否重新验证了清算条件

2. **健康因子计算的时间一致性**：
   - 在抵押品 + 债务价格都取完 **后** 才执行清算 → 时间窗口小 → 低风险
   - 先取抵押品价格，后续操作中债务价格改变 → 存在竞态条件 → 高风险

### 3. 清算奖励的合理性边界

**数据驱动的风险量化**
| 清算奖励比例 | 最小可盈利规模 | 风险等级 |
|:--|:--|:--|
| < 3% | 需要 DEX 深度 > 100M | 低风险 |
| 3-8% | DEX 深度 > 10M 可盈利 | 中风险（需多重防护） |
| 8-15% | DEX 深度 > 1M 可盈利 | **高风险** |
| > 15% | 任何流动性都可盈利 | **严重风险** |

**真实对比**
- Aave：清算奖励 5%（业界标准），但有单次清算 50% 债务上限 + 健康因子重算
- Compound：清算奖励 8%，但需清算后 `isClosed() == true` 才能完成 → 状态强制同步

### 4. 时间维度的攻击面分析

**时间漏洞的三种形态**
1. **区块级竞态**：闪电贷在区块内执行，价格可在同区块被操纵
   - 检查：预言机价格更新是否需要跨越 2+ 个区块

2. **交易级竞态**：闪电贷借用、操纵价格、触发清算在单笔交易内完成
   - 检查：清算逻辑中是否存在 `require(block.number > lastPriceUpdateBlock + 1)` 这样的延迟机制

3. **预言机更新滞后**：Chainlink 最多 1 小时更新一次低活跃资产价格
   - 检查：`oracle.getPrice()` 返回的时间戳是否被验证 `require(block.timestamp - priceTime < 1 hour)`

**实战案例**：PancakeBunny 破坏 $45M
- 攻击者借闪电贷操纵 Pancakeswap 价格 → 协议依赖该价格计算清算
- 防御失效原因：缺少 `block.timestamp` 校验，接受任意时间的价格更新

### 5. 审计报告的误报避坑指南

**常被误判为高危的低风险场景**
1. **"存在 DEX 价格调用" ≠ 可以被闪电贷操纵**
   - 需验证：是否使用 TWAP（需多区块）而非实时价格
   - 需验证：清算前是否有 `require(block.number > refBlock)` 延迟

2. **"使用 `safeTransfer` 就是安全的"** ← 仅涉及重入保护，与价格操纵无关

3. **"清算奖励只有 3%"** ← 需配合流动性深度评估，3% 奖励在 1B+ TVL 协议可接受，在 100M TVL 协议仍高风险

4. **"合约已审计过"** ← 需检查上次审计的作用域，可能未覆盖新增的清算逻辑版本

**避免误报的逻辑检验表**
```
[检查项目] | [低风险表现] | [高风险表现]
价格延迟 | block.number check + 2+ TWAP | 无延迟 + 单一实时价格
流动性深度 | >1B USDC 等值 | <100M
预言机多源 | 3+ 来源取中位数 | 单一来源
清算上限 | 单次 <50% 债务额 | 无上限

