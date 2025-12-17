# Solidity - 不可信 TWAP 预言机

**漏洞类型**：Oracle Manipulation  
**风险等级**：Critical/High  
**成因**：直接使用单个 DEX 的 TWAP 价格作为价格来源，未做多源聚合或异常检测，导致攻击者可通过闪电贷或大额交易操纵现货池，进而影响 TWAP 计算窗口内的价格。

---

## Details

### 代码示例

```solidity
// 典型漏洞模式
contract VulnerableLending {
    IUniswapV2Pair public pricePair;
    
    function getCollateralValue(address token, uint256 amount) public view returns (uint256) {
        (uint112 reserve0, uint112 reserve1, ) = pricePair.getReserves();
        // 直接使用即时储备量计算价格
        uint256 price = (reserve1 * 1e18) / reserve0;
        return amount * price / 1e18;
    }
    
    function borrow(uint256 collateralAmount) external {
        uint256 collateralValue = getCollateralValue(msg.sender, collateralAmount);
        // 基于操纵价格执行借贷逻辑
    }
}

// 或使用 Uniswap V2 TWAP
contract TWAPOracle {
    IUniswapV2Pair public pair;
    uint256 public price0CumulativeLast;
    uint32 public blockTimestampLast;
    
    function update() external {
        (uint256 price0Cumulative, , uint32 blockTimestamp) = 
            UniswapV2OracleLibrary.currentCumulativePrices(address(pair));
        
        uint32 timeElapsed = blockTimestamp - blockTimestampLast;
        // 单一 DEX 的 TWAP，窗口期过短时易被操纵
        uint256 priceAverage = (price0Cumulative - price0CumulativeLast) / timeElapsed;
    }
}
```

### 快速定位核心操作（审计等级：L2-L3）

**关键函数特征**：
- 搜索关键词：`getReserves()`, `price0Cumulative`, `price1Cumulative`, `observationCardinalityNext`, `observe()`
- 定位价格读取点：通常在 `getPriceFrom*`, `quote*`, `get*Value`, `calculate*` 等函数中
- 检查调用链：价格获取 → 金融决策（借贷/清算/铸造/兑换）之间是否在同一交易内完成

**审计检查清单**（L2-跳读）：
1. 是否仅从单一 DEX 池读取价格？
2. TWAP 时间窗口是否小于 30 分钟？（一般认为 < 10 分钟高危）
3. 价格使用前是否在同一区块/交易内可被操纵？
4. 是否存在 `observe()` 调用但未检查返回的 `tickCumulatives` 数组长度？

### 快速定位保护机制（审计等级：L3-L4）

**防护措施检查点**：

1. **多源聚合机制**（L3-逐行读）：
   - 搜索：`Chainlink`, `AggregatorV3`, `latestRoundData()`, 中位数计算、多价格源数组
   - 验证：至少 3 个独立数据源 + 偏差检测逻辑

2. **时间窗口验证**（L2-跳读）：
   - 检查：`timeElapsed >= MIN_PERIOD`、`observationCardinality` 是否 >= 所需采样点
   - Uniswap V3：验证 `secondsAgo` 数组跨度是否 >= 1800 秒

3. **价格变动熔断**（L3-逐行读）：
   - 搜索：`maxPriceDeviation`, `priceThreshold`, `require(newPrice * 100 < oldPrice * 110)`
   - 验证：相邻更新价格偏差限制（如 ±10%）

4. **跨模块追踪**（L4）：
   - 追踪 `update()` 调用频率和触发条件
   - 检查价格更新是否可被外部任意触发（DoS 风险）
   - 验证闪电贷检测：`require(blockNumber > lastUpdateBlock)`

**缺失防护的红旗**：
- 仅调用 `pair.getReserves()` 无其他验证
- TWAP 更新间隔由外部控制且无最小间隔限制
- 无价格合理性范围检查（如历史价格偏差 >50% 仍接受）

---

## Classify

### 确认为漏洞的判定标准

1. **单一来源 + 金融决策**：价格数据仅来自一个 DEX 池，且直接用于借贷、清算、铸造等高价值操作
2. **时间窗口不足**：TWAP 窗口 < 10 分钟或采样点 < 20 个（Uniswap V3）
3. **可原子操纵**：攻击者可在单笔交易内完成：操纵池价格 → 调用受害合约 → 恢复池价格
4. **缺乏异常检测**：无价格偏差阈值、熔断器或多源校验

### 误报的典型场景

1. **只读场景**：价格仅用于前端展示或统计，不影响资产转移
2. **已有外部验证**：合约在链下或另一合约中已通过 Chainlink 等验证价格，当前读取仅为辅助
3. **沙盒环境**：测试网或受限调用（如仅管理员可触发的非金融功能）
4. **二次验证存在**：虽然直接读取 TWAP，但后续有独立的 sanity check（需逐行确认检查逻辑的有效性）

### 代码异味（潜在风险）

1. **时间窗口中等**（10-30 分钟）：有一定抵抗能力但成本可控时仍可攻击
2. **单向依赖**：仅在清算时使用 TWAP，正常借贷使用 Chainlink（清算时的风险较低）
3. **流动性充足池**：使用 WETH/USDC 等深度极高的池（操纵成本高但非不可能）
4. **历史未出事**：主网运行多年无事故但代码逻辑确实存在缺陷（应标记为 Medium 并建议重构）

---

## Low Risk

以下情况可评定为低风险，但仍应在报告中提及：

1. **超高流动性池 + 长窗口**：使用 Uniswap WETH/USDC 主池 + TWAP 窗口 > 24 小时，操纵成本极高（百万美元级别）且需持续多区块
   
2. **辅助参考而非唯一依据**：价格作为多个输入之一，其他参数（如用户信用评分、抵押率限制）可限制风险敞口
   
3. **低价值资产**：合约管理的资产总价值 < $10k，攻击成本与收益不成正比
   
4. **严格的全局限制**：存在独立的风控层，如单笔借贷上限、全局债务上限、用户级别限流，即使价格被操纵也无法大额获利
   
5. **时效性限制**：价格数据有延迟使用机制（如更新后需等待 N 个区块才能用于金融操作），打破原子操纵的可能性
   
6. **只读视图函数**：价格查询函数被标记为 `view`/`pure` 且仅在链下调用，不参与状态变更逻辑

**注意**：即使评为低风险，也应建议项目方迁移到多源预言机方案（如 Chainlink + TWAP 双验证），以应对未来流动性变化或新型攻击手法。
