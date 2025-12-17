# Solidity_SingleSourcePriceFeed

**漏洞类型**：单一来源价格喂送  
**语言**：Solidity  
**场景**：价格预言机、借贷利率计算、清算阈值判定、DEX价格获取

## Details

**代码示例**：
```solidity
// 典型漏洞模式
function getPrice() public view returns (uint256) {
    return IOracle(oracleAddress).latestPrice(); // 单点依赖
}

function liquidate(address user) external {
    uint256 price = getPrice(); // 无验证直接使用
    uint256 collateralValue = userCollateral[user] * price;
    require(collateralValue < debtValue[user], "healthy");
    // 执行清算...
}
```

**快速定位核心操作技巧**（L2-L3）：
- 搜索价格获取函数：`getPrice`, `latestAnswer`, `latestRoundData`, `consult`, `peek`
- 定位外部调用：`IOracle`, `IPriceFeed`, `IAggregator`, `IUniswapV2Pair.getReserves()`
- 追踪价格使用点：清算函数、铸造函数、兑换函数、抵押率计算
- 检查是否仅调用一次外部预言机：无多源聚合、无fallback机制

**快速定位保护机制技巧**（L1-L2）：
- 关键词扫描：`median`, `average`, `aggregat`, `multi`, `fallback`, `secondary`
- 检查是否存在：多预言机数组遍历、中位数计算、价格偏差检查、时间戳验证
- 验证是否有断路器：`circuitBreaker`, `maxDeviation`, `priceStale`
- 检查是否仅依赖单一`address`变量存储预言机地址

## Classify

**归类为漏洞**：
- 关键金融操作（清算、铸币、兑换）完全依赖单一预言机地址
- 无任何价格偏差检查或时间戳验证
- 预言机地址不可变且无治理升级机制
- 高价值资产定价依赖单一Uniswap池或Chainlink单节点

**归类为误报**：
- 存在多源价格聚合逻辑但位于库合约或继承的基类中
- 虽使用单源但有严格的价格波动限制（如最大5%偏差）
- 测试网或演示合约明确标注
- 使用Chainlink多节点聚合器（本质已是多源）

**归类为代码异味**：
- 有多源机制但聚合算法过于简单（如仅取首个可用值）
- 预言机可升级但缺乏时间锁或多签控制
- 非关键路径使用单源价格（如UI展示、统计功能）

## Low risk

**适用场景**：
- 预言机为Chainlink官方聚合器合约（内部已多源）
- 价格仅用于非金融核心逻辑（事件记录、展示层）
- 存在有效的断路器且触发阈值合理（如24小时内偏差>10%暂停）
- 受保护的低流动性资产且有严格铸造上限
- 多源预言机中的单源仅作fallback使用且有明确降级策略

## 审计专业技巧

### 1. 多层验证技术

**区分真实漏洞的五步检验法**：
```solidity
// 第一步：追踪参数流向
uint256 price = getPrice();        // 来源
liquidateUser(price);               // 使用

// 第二步：检查参数校验
require(price > 0, "Invalid price");  // 基础检查，不足以防护
require(price <= maxPrice, "Price spike"); // 边界检查

// 第三步：查找聚合逻辑
// 真实保护：价格过时检查 + 偏差校验
uint256 age = block.timestamp - lastUpdate;
require(age < 3600, "Price stale");  // 时间戳验证
require(price.ratio(prevPrice) < 1.05e18, "Price jump"); // 动态检查
```

**误报陷阱**：仅有`require(price > 0)`判断的合约，初看是单源风险，但若该合约是**代理合约的实现版本**，实际保护在代理层或上游调用者处。需检查：
- `delegatecall`路由是否包含额外验证
- 调用上下文的caller权限检查

### 2. 真实漏洞的特征指纹

**High Risk信号**（三个同时出现即确认漏洞）：
1. **金融敏感路径** + **单源读取** + **无时间检查**
   ```solidity
   // 高风险：清算路径完全信任单个预言机
   function liquidate(address account) external {
       uint256 price = oracle.latestPrice();  // 无年龄检查
       uint256 health = calcHealth(account, price);
       require(health < 1e18, "Not liquidatable");
       _executeCleanup(account);
   }
   ```

2. **预言机地址可被治理更新** + **无时间锁** + **高权限账户**
   ```solidity
   // 真实漏洞：管理员可瞬间切换到恶意预言机
   function setOracle(address newOracle) external onlyOwner {
       oracle = newOracle;  // 立即生效，无时间锁
   }
   ```

3. **DEX闪电贷攻击向量** + **同块价格使用** + **可操纵流动性**
   ```solidity
   // 易被攻击：借入大额资产→操纵Uniswap→执行清算
   uint256 price = uniswapV2Pair.getReserves();
   // 同一块内的价格已被闪电贷操纵
   ```

### 3. 常见误报场景的识别

**误报 Case 1：继承链隐藏的聚合逻辑**
```solidity
// 子合约看似单源
contract LendingPool is PriceProvider {
    function getPrice() public view returns (uint256) {
        return super.getPrice();  // 继承了多源聚合
    }
}

// 基类中的真实实现
contract PriceProvider {
    function getPrice() internal view returns (uint256) {
        uint256[] memory prices = new uint256[](3);
        prices[0] = chainlink.latestPrice();
        prices[1] = uniswap.consultPrice();
        prices[2] = balancer.getSpotPrice();
        return _median(prices);  // 多源处理在这里
    }
}
```
**审计技巧**：必须追踪`super`调用和继承树，不能只看表面函数

**误报 Case 2：Chainlink Aggregator被误认为单源**
```solidity
// 这是MULTI-SOURCE，虽然看似单个地址
IChainlinkAggregator aggregator = IChainlinkAggregator(address);
(,int256 price,,,) = aggregator.latestRoundData();
// 内部已包含 30+ Chainlink节点的聚合
```
**审计技巧**：检查合约是否在Chainlink官方部署列表中，调用`aggregator.answeredInRound()`验证节点共识

**误报 Case 3：上游调用者的保护被忽视**
```solidity
// 看起来单源
function _getPriceInternal() internal view returns (uint256) {
    return oracle.latestPrice();
}

// 但所有public调用都通过保护入口
function getPrice() external view returns (uint256) {
    uint256 price = _getPriceInternal();
    require(price.ratio(prices[currentRound-1]) < 1.1e18);  // 在此做了偏差检查
    return price;
}
```
**审计技巧**：映射所有`_getPriceInternal()`的调用点，确认每个路径都经过验证

### 4. 风险分层评估矩阵

| 预言机类型 | 单源 | 有时间检查 | 有偏差检查 | 有时间锁 | 综合风险 |
|----------|------|----------|---------|--------|--------|
| Chainlink官方 | ✓ | 内置 | 内置 | N/A | Low |
| Uniswap V3 TWAP | ✓ | ✓ | 可选 | N/A | Low-Med |
| 单个DEX池 | ✓ | ✗ | ✗ | ✗ | **High** |
| 自建聚合器 | ✗ | ✓ | ✓ | ✓ | Low |
| 可升级单源 | ✓ | ✗ | ✗ | ✓ | **Medium** |

### 5. 漏洞确认的实战检查清单

**在报告漏洞前必须验证**：
- [ ] 确认该价格值被用于**金融决策**（转账、清算、铸币），不是仅作日志
- [ ] 追踪该价格从**源到汇**的完整路径，确认无中间校验
- [ ] 验证调用者**是否有权限控制**（任何人都能触发还是仅管理员）
- [ ] 检查是否存在**交易原子性破坏**（价格读取和行动之间有gap）
- [ ] 确认预言机地址**是否可改变及改变机制**（永久、多签、时间锁）

**高置信度标志**：
- 存在已知的漏洞利用PoC（如Fortress AAVE清算）
- 价格波动与合约内操作存在**可测量的时序关联**
- 预言机维护者已发出风险警告
