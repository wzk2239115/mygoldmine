# Solidity DEX Front Running 审计指南

**漏洞类型**：MEV 抢跑攻击  
**影响范围**：DEX swap、流动性添加/移除、限价单、滑点保护不足的交易函数  
**成因**：公开内存池中交易可见，攻击者通过更高 Gas 优先执行，操纵价格后使受害者交易以不利价格成交

---

## Details

### 代码示例

```solidity
function swap(address tokenIn, address tokenOut, uint256 amountIn, uint256 minAmountOut) external {
    uint256 amountOut = getAmountOut(tokenIn, tokenOut, amountIn);
    require(amountOut >= minAmountOut, "Slippage");
    
    // 转入代币
    IERC20(tokenIn).transferFrom(msg.sender, address(this), amountIn);
    // 转出代币
    IERC20(tokenOut).transfer(msg.sender, amountOut);
    
    // 更新储备量
    _updateReserves(tokenIn, tokenOut);
}
```

**典型抢跑场景**：
1. 用户提交大额 swap 交易到 mempool，设置 minAmountOut=950（滑点 5%）
2. MEV bot 检测到该交易，抢先执行大额买入拉高价格
3. 用户交易以更差价格成交（接近 minAmountOut）
4. MEV bot 卖出获利（sandwich attack）

### 快速定位核心操作技巧 **[L2-L3]**

**关键函数签名**：
- `swap*` / `swapExact*` / `exchange*`
- `addLiquidity*` / `removeLiquidity*`
- `execute*` / `fill*Order`

**核心检查点**：
- 价格计算逻辑：查找 `getAmountOut` / `getPrice` / `quote` 函数调用
- 状态依赖：检查价格依赖当前区块的 `reserves` / `balanceOf` 而非历史快照
- 时序敏感：交易顺序会影响最终结果的函数（价格计算基于可变状态）
- 大额交易影响：计算公式是否为 `x*y=k` 类型（恒定乘积会产生滑点）

**快速识别模式**：
```solidity
// 高风险模式
amountOut = reserve_out * amountIn / (reserve_in + amountIn);  // 基于当前储备量
price = token1Balance / token0Balance;                          // 实时价格
```

### 快速定位保护机制技巧 **[L1-L2]**

**保护关键词扫描**：
- ✅ `minAmountOut` / `minReturn` / `deadline` 参数
- ✅ `slippage` / `maxPriceImpact` 限制
- ✅ `commit` / `reveal` 两阶段提交
- ✅ `private mempool` / `flashbots` 备注
- ✅ `TWAP` / `oracle` 价格参考
- ✅ `maxTxAmount` 单笔限额

**保护强度评估**：
```solidity
// 弱保护（易抢跑）
require(amountOut >= minAmountOut);  // 仅检查但滑点设置权在用户

// 中等保护
require(amountOut >= minAmountOut && priceImpact <= 5%);  // 硬编码限制

// 强保护
require(getCurrentPrice() <= oraclePrice * 102 / 100);  // 外部价格锚定
```

**审计等级判定**：
- **L1**：有明确的 `minAmountOut` + `deadline` + 低滑点限制（<3%）→ 快速扫描确认
- **L2**：有滑点保护但限制宽松（>5%）→ 跳读评估实际风险
- **L3**：无明确保护或保护可绕过 → 逐行分析交易执行路径
- **L4**：涉及多池路由/跨合约调用 → 跨模块追踪所有价格依赖点

---

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 核心交易函数（swap/add/remove liquidity）无任何滑点保护
2. 滑点保护参数默认值过大（>10%）且用户难以自定义
3. 价格计算可被同一区块内前序交易显著影响（>3% 偏移）
4. 大额交易无额外限制（无单笔上限、无价格冲击检查）

**误报情况**：
1. 存在有效的 TWAP 或 Chainlink 预言机价格验证
2. 使用 commit-reveal 模式或私有内存池提交
3. 协议设计为批量撮合（如 CoW Protocol）而非即时成交
4. 函数仅供管理员或白名单调用（非公开交易函数）
5. 已集成 Flashbots Protect 或类似 MEV 保护服务

**代码异味**：
1. 有滑点保护但文档未明确建议前端设置合理值
2. 缺少 `deadline` 参数导致交易可能长期挂起后以过时价格成交
3. 前端默认滑点设置过高（虽合约允许自定义但用户体验差）
4. 仅在事件日志中体现价格但未在交易中验证

---

## Low Risk

### 降级为低风险的场景

1. **流动性充足场景**：  
   池子深度极大（如主流稳定币对），单笔交易价格影响<0.1%，抢跑获利空间不足以覆盖 Gas 成本

2. **低价值代币**：  
   交易代币总市值<10 万美元，MEV bot 通常不监控此类资产

3. **有效滑点保护但限制适中**：  
   存在 `minAmountOut` 且前端默认设置 0.5%-1% 滑点，虽理论可抢跑但实际获利空间有限

4. **非原子性攻击难度高**：  
   需要多步操作且涉及外部依赖（如需先在其他 DEX 建仓），攻击复杂度高、成本高

5. **已公开但用户可选择避免**：  
   文档明确说明抢跑风险，并提供替代方案（如限价单、私有 RPC），用户可自主选择

6. **历史数据表明无实际利用**：  
   协议运行 6 个月以上，链上数据未发现明显的 sandwich attack 模式

7. **受监管或 KYC 环境**：  
   许可链或需 KYC 的交易环境，攻击者身份可追溯，威慑力较强

**注意**：即使评为低风险，仍应在报告中披露抢跑可能性，由项目方评估是否需要额外缓解措施。
