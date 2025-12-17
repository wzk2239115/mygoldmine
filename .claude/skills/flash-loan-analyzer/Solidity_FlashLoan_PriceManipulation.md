# Solidity 闪电贷价格操纵漏洞审计指南

**漏洞描述**  
协议使用可被闪电贷操纵的价格源（如单一 DEX 即时价格、池内余额比例），攻击者通过闪电贷在单笔交易内操纵价格并从依赖该价格的业务逻辑中获利。常见于借贷协议、Stablecoin 铸造、清算机制、自动做市商等价格敏感型 DeFi 产品。

---

## Details

### 代码示例

```solidity
// 易受攻击的价格获取方式
function getPrice() public view returns (uint256) {
    uint256 reserve0 = token0.balanceOf(address(pair));
    uint256 reserve1 = token1.balanceOf(address(pair));
    return reserve1 * 1e18 / reserve0;  // 直接使用即时储备量计算价格
}

function borrow(uint256 amount) external {
    uint256 collateralValue = getPrice() * userCollateral[msg.sender];  // 使用可操纵价格
    require(collateralValue >= amount * collateralRatio, "Insufficient");
    // ... 借贷逻辑
}
```

### 快速定位核心操作技巧 **(L3-L4: 逐行读→跨模块追踪)**

1. **价格读取调用链追溯**：从价值计算函数（`borrow`、`mint`、`liquidate`、`swap`）反向追踪价格获取函数
2. **关键模式识别**：
   - `balanceOf(pair/pool)` + 除法运算 → 即时储备量价格
   - `getReserves()` 无时间加权 → 单点价格
   - `slot0()` (Uniswap V3) 直接使用 → 可操纵价格
3. **交易原子性检查**：价格读取与状态变更是否在同一交易内完成（无延迟/多区块保护）

### 快速定位保护机制技巧 **(L2-L3: 跳读→逐行读)**

1. **TWAP 验证** (L2)：
   - 搜索 `observe()`、`consult()`、`累积价格变量`
   - 检查是否使用时间窗口 ≥ 15 分钟
   
2. **Chainlink 预言机** (L1-L2)：
   - 关键词：`AggregatorV3Interface`、`latestRoundData()`
   - 检查是否验证 `updatedAt`、`answeredInRound`、价格偏差阈值
   
3. **价格偏差限制** (L2)：
   - 搜索 `priceDeviation`、`maxPriceChange`、百分比阈值检查
   
4. **双预言机验证** (L3)：
   - 是否对比多个价格源并设置容差范围
   
5. **重入保护** (L1)：
   - `ReentrancyGuard`、`nonReentrant` 修饰符（必要但不充分）

---

## Classify

### 确认为漏洞的判定标准

1. **直接漏洞**：
   - 价格源为单一 AMM 的即时储备量/`slot0()`且无二次验证
   - 价格直接影响资产铸造/借贷/清算且单笔交易可完成攻击闭环
   - 无滑点限制、无价格变动阈值、无冷却期
   
2. **条件漏洞**：
   - TWAP 时间窗口 < 3 分钟（可通过多区块操纵）
   - 预言机存在但未正确校验时效性/偏差
   - 价格聚合逻辑存在中值计算错误或权重失衡

### 归类为误报的情况

1. 价格仅用于展示/日志，不影响资金流或铸造逻辑
2. 协议本身为 AMM，使用自身储备量计价属于业务逻辑（需确认无跨池套利漏洞）
3. 已采用 Chainlink + TWAP 双预言机且正确实现容差检查
4. 价格变动受硬编码上限约束且上限值合理（需计算攻击成本）

### 代码异味标记

1. 使用预言机但无降级/暂停机制（价格异常时无应对措施）
2. TWAP 实现正确但时间窗口可由治理动态调整为极短值
3. 价格偏差检查存在但阈值过于宽松（如 50% 偏差）

---

## Low Risk

### 低风险评级适用场景

1. **攻击成本高于收益**：
   - 协议流动性极小，操纵价格所需资金 > 可获利金额
   - 协议设置铸造/借贷上限，单次攻击收益 < 滑点成本
   
2. **依赖资产特殊性**：
   - 价格源为深度极高的中心化交易所（需考虑跨链桥风险）
   - 标的资产为包装资产（WBTC/WETH）且协议仅支持该包装版本
   
3. **保护机制部分有效**：
   - 使用短周期 TWAP（5-10 分钟）且配合价格变动率限制
   - 预言机延迟更新但协议设有充足的超额抵押率（如 200%）
   
4. **影响范围受限**：
   - 仅影响协议的辅助功能（如积分计算、APY 展示）
   - 价格操纵后触发的清算需多步骤人工介入
   
5. **降级机制存在**：
   - 价格异常时自动切换到备用预言机
   - 存在紧急暂停功能且由多签/DAO 快速响应团队控制
