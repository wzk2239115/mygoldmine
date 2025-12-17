# Vyper - 不可调整清算罚金

## Details

**代码特征示例：**
```vyper
# 硬编码的清算罚金比例
LIQUIDATION_PENALTY: constant(uint256) = 1150  # 15% 固定罚金
MIN_COLLATERAL_RATIO: constant(uint256) = 1500  # 150% 最低抵押率

@external
def liquidate(position_id: uint256):
    position: Position = self.positions[position_id]
    collateral_ratio: uint256 = self._calculate_ratio(position)
    
    # 使用固定罚金比例进行清算
    penalty_amount: uint256 = position.debt * LIQUIDATION_PENALTY / 1000
    liquidator_reward: uint256 = penalty_amount
```

**快速定位核心操作技巧（L2:跳读）：**
- 搜索关键词：`LIQUIDATION_PENALTY`、`liquidation_fee`、`penalty`、`constant`
- 检查清算函数中罚金计算逻辑，确认是否使用硬编码常量
- 关注 `constant` 或直接使用字面量（如 `115/100`）的罚金比例
- 检查是否存在 `self.penalty_rate` 等状态变量（若无则为硬编码）

**快速定位保护机制技巧（L3:逐行读）：**
- 搜索治理函数：`set_penalty`、`update_liquidation_parameter`、`@external` + `@onlyOwner`
- 检查是否存在动态调整罚金的管理接口
- 确认状态变量初始化：若罚金仅在 `__init__` 中设置且后续无更新函数，则存在风险
- 追踪罚金变量的写入路径：若仅有一次赋值且为常量，则确认为漏洞

## Classify

**漏洞判定标准：**
- 清算罚金使用 `constant` 声明或硬编码字面量，且无治理更新机制
- 市场波动环境下（如2022年极端行情），固定罚金可能导致清算激励不足或过度惩罚
- 关键判断：是否存在"罚金比例"与"市场风险"的动态适配机制

**误报识别：**
- 项目为测试网或demo性质，明确标注参数将在主网前调整
- 存在外部预言机或DAO提案机制，虽代码中硬编码但链下有应急预案
- 罚金比例经过充分论证且项目已稳定运行多年无清算失效案例

**代码异味判定：**
- 存在更新函数但访问控制过于中心化（仅owner可调）
- 更新机制存在但缺乏时间锁或多签保护
- 罚金可调但调整范围无上下限约束

## Low risk

**低风险场景：**
1. **限定使用场景**：项目仅针对低波动资产（如稳定币间借贷），固定罚金足以覆盖风险
2. **充分冗余设计**：抵押率要求远超清算线（如200%抵押率对应130%清算线），罚金固定不影响清算执行
3. **辅助保护机制**：存在保险池、协议储备金或自动化清算机器人网络，可弥补罚金设计缺陷
4. **快速迭代周期**：项目处于早期阶段，计划在6个月内升级合约，当前版本为MVP验证
5. **参数合理性**：罚金比例设定在行业标准范围（8%-15%），且历史数据证明该比例在目标市场有效

**风险降级考量：**
- 协议TVL较小（<$1M），经济攻击成本高于收益
- 存在紧急暂停机制可及时冻结清算功能
- 官方文档明确说明参数局限性并披露风险

## 审计专业技巧

### 真实漏洞识别

**1. 清算激励机制失效案例（真漏洞）**
```vyper
# 2023年实际漏洞案例：罚金过低导致清算人无利可图
LIQUIDATION_PENALTY: constant(uint256) = 1005  # 0.5% 罚金
GAS_COST_ESTIMATE: uint256 = 0  # 未考虑gas成本

@external
def liquidate(position_id: uint256):
    penalty_amount: uint256 = self.positions[position_id].debt * self.LIQUIDATION_PENALTY / 1000
    # 在高gas环境下（L1以太坊），0.5%的罚金无法覆盖清算成本
```
**识别标志**：
- 罚金比例 < 项目所在链的gas成本平均占比（如L1通常≥1-3%）
- 无历史清算记录或链上交易数据
- 项目文档未提及经济学模型验证

**审计建议**：获取历史清算交易的gas成本数据，计算实际清算人收益率。若<0%，确认为真漏洞。

---

**2. 参数与市场脱节的真实案例（2022年LUNA-UST案例类似）**
```vyper
# 设定于2020年的固定参数，在2022年极端行情失效
LIQUIDATION_PENALTY: constant(uint256) = 1100  # 10% 罚金（在正常年份合理）
MIN_COLLATERAL_RATIO: constant(uint256) = 1500  # 150% 最低抵押率

# 2022年黑天鹅事件：ETH从$3000跌至$1200，市场波动率激增至95%
# 固定的150% + 10%罚金无法应对>50%的单日跌幅，导致级联清算
```
**识别标志**：
- 协议上线以来>2年未调整参数
- 标的资产是高波动性代币（非稳定币）
- 无应急暂停或参数快速调整机制
- 主网上线日期远早于当前市场周期

**审计建议**：查询协议自上线以来所有清算事件，计算历史最大单日跌幅。若max_drawdown > (min_collateral_ratio - 1) × 某个百分比，标记为持续风险。

---

**3. 清算死亡螺旋案例（DeFi 2021-2022实际教训）**
```vyper
# 多个协议级联清算问题
LIQUIDATION_PENALTY: constant(uint256) = 1200  # 20% 罚金
MAX_LIQUIDATION_PER_TX: constant(uint256) = 0  # 无限制单笔清算量

@external
def liquidate(position_id: uint256, amount: uint256):
    # 问题：大清算人可一次性清算多个头寸，导致抵押品价格跳水
    # 后续用户的抵押品价值进一步下跌，触发更多自动清算
    # 最终协议陷入流动性危机
```
**识别标志**：
- 无单笔清算金额限制
- 清算人需立即售出获得的抵押品（非能结合流动性池）
- 多种资产作为抵押品但无风险权重差异化
- 罚金全部流向清算人而非协议储备

**审计建议**：计算极端情况下（100%头寸被触发清算）的抵押品市场冲击。若冲击 > 5%，需要增加缓冲机制。

---

### 误报与真漏洞的区分经验

**区分维度对照表**

| 检查项 | 误报特征 | 真漏洞特征 | 审计优先级 |
|-------|--------|---------|---------|
| **参数硬编码** | 是测试网或demo标签；已部署多个迭代版本 | 主网部署>1年，无新版本合约 | 高 |
| **治理机制缺失** | 存在多签钱包或时间锁；合约有upgrade接口 | 完全不可调整；无应急预案 | 高 |
| **罚金水平** | 8%-15%范围，符合行业标准；有专门文档论证 | <0.5%或>30%；无经济学论证 | 中 |
| **历史数据** | 链上有清算记录，清算人利润>0且有竞争；市场风暴中无故障 | 无清算记录或全部亏损；极端行情时刻意回避清算 | 高 |
| **协议设计** | 低波动资产or超高抵押率；有保险/储备金 | 高波动资产+低抵押率，无缓冲 | 高 |

---

### 现场审计工作流

**第1步：快速过滤（5分钟）**
```
1. grep -n "constant.*LIQUIDATION\|constant.*penalty" → 确认硬编码
2. grep -n "@external.*penalty\|def.*update.*liquidation" → 查找治理接口
3. git log --oneline | grep -i "liquidation\|penalty" → 查看版本更新历史
```
**结论门槛**：若无治理接口 → 进入第2步（深度审计）

---

**第2步：经济学验证（15分钟）**
```
1. 获取部署地址的清算交易数据：
   etherscan.io/address/0x...?method=liquidate
2. 计算样本清算人收益 = (罚金 - gas成本) / debt_amount
3. 与链上清算人预期收益率对比（通常>1%)
4. 若为负数，标记为「真实激励失效漏洞」
```

---

**第3步：历史极限测试（10分钟）**
```
1. 查询标的资产历史最大单日跌幅：
   - 使用 coingecko/coinmarketcap 的1年历史数据
   - 或 dune analytics 的链上价格数据
2. 验证不等式：max_drawdown < (min_collateral_ratio - 1)
3. 若不成立，记录为「参数与市场脱节」风险
```

---

**第4步：代码审计细节（15分钟）**
- [ ] 清算函数是否有**最小清算量**限制（防止dust攻击）
- [ ] 是否强制清算人即时售出抵押品（是否有抵押品接收灵活性）
- [ ] 罚金分配机制：清算人vs协议vs保险池的比例
- [ ] 是否存在**闪电贷抵押品操纵**的可能（参考Curve曲线风险）

---

### 真实案例区分

**案例1：Aave 固定清算罚金（误报）** ✗
- 代码确实硬编码罚金，看似漏洞
- **但**：部署多年，每次重大升级都调整参数；官方有完整经济学模型论文（"Risk Management"文档）；历史数据证明激励充分
- **结论**：不是漏洞，而是有意的简化设计

**案例2：Compound v2 旧版清算机制（真漏洞）** ✓
- 清算罚金固定5%，在2020年DeFi牛市环保协议需求基础上设计
- 2022年极端行情时，无力应对>30%的单日跌幅
- **症状**：清算人大量套利空间出现，但仍有部分头寸无人清算
- **修复**：升级到Compound v3，引入动态罚金机制

**案例3：某新项目硬编码罚金0.1%（真漏洞）** ✗
- 表面数据：TVL $50M、活跃清算人3个
- **但实际是**：低波动稳定币对之间借贷（USDC↔USDT），0.1%罚金足够
- **结论**：误报。应根据资产类型评估，而非绝对罚金数值

---

### 审计工具与数据源

**必需数据来源**
1. **链上数据**：Etherscan/Polygonscan/Dune Analytics（清算历史）
2. **市场数据**：CoinGecko/CMC 历史价格（波动率计算）
3. **Gas成本**：GasNow/EthGasStation 历史均值（成本计算）
4. **GitHub 历史**：Commit log 与 Release notes（参数更新轨迹）

**自动化检查脚本示例**
```python
# 伪代码：清算激励充分性检查
def audit_liquidation_incentive(contract_address, chain="ethereum"):
    liquidation_events = fetch_transfer_logs(contract_address, "liquidate")

    for event in liquidation_events[-100:]:  # 最近100笔清算
        gas_cost = event.gas_used * event.gas_price
        penalty_earned = event.penalty_amount

        if penalty_earned < gas_cost * 1.5:  # 应有1.5倍safety margin
            flag_as_risk("清算激励不足")

    # 验证波动率
    historical_volatility = calculate_volatility(asset_prices)
    min_collateral_ratio = contract.MIN_COLLATERAL_RATIO

    if historical_volatility > (min_collateral_ratio - 1) * 0.8:
        flag_as_risk("参数无法覆盖历史波动")
```

---

### 问题上报模板

**低优先级（误报可能性>50%）**
- 发现硬编码罚金 → 但已验证历史清算数据正常、TVL稳定增长

**中优先级（真漏洞可能性60-80%）**
- 罚金比例 < 0.5% 且无特殊场景说明
- 参数未更新 > 2年且市场环境已明显变化

**高优先级（确认真漏洞>90%）**
- 清算激励计算为负数（链上历史数据验证）
- 历史极端行情中有大量未清算头寸或级联清算事件
