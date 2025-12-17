# Vyper AMM Front Running

**漏洞类型：** MEV前置交易漏洞  
**影响范围：** AMM类交易对、流动性池、Swap函数、价格预言机依赖逻辑  
**成因：** 交易在mempool中可见，攻击者可通过高gas抢先执行交易操纵池子状态获利

---

## Details

### 典型代码特征

```vyper
@external
def swap(token_in: address, token_out: address, amount_in: uint256, min_out: uint256):
    # 直接基于当前储备计算价格
    reserve_in: uint256 = self.reserves[token_in]
    reserve_out: uint256 = self.reserves[token_out]
    
    # 使用x*y=k公式计算输出
    amount_out: uint256 = (amount_in * reserve_out) / (reserve_in + amount_in)
    
    # 滑点保护不足或未使用TWAP
    assert amount_out >= min_out
    
    # 状态更新可被抢跑利用
    self.reserves[token_in] += amount_in
    self.reserves[token_out] -= amount_out
```

### 快速定位核心操作技巧（L2: 跳读）

**关键函数签名：**
- `swap`、`exchange`、`get_dy`、`add_liquidity`、`remove_liquidity`
- 包含`amount_in`/`amount_out`参数的交易函数

**核心审计点：**
1. **价格计算源**：搜索`reserves`、`balances`、`get_virtual_price`，检查是否直接读取当前区块状态
2. **时间依赖**：检查`block.timestamp`、`block.number`使用场景，是否作为唯一随机源
3. **状态暴露窗口**：函数执行中状态更新顺序，是否存在可预测的中间状态
4. **事件发射时机**：`log`语句位置，是否在状态提交前泄露信息

### 快速定位保护机制技巧（L3: 逐行读）

**必查保护项：**
1. **滑点控制**：
   - 搜索`min_out`、`min_dy`、`deadline`参数
   - 验证`assert amount_out >= min_amount_out`是否足够严格
   - 检查滑点计算是否基于预言机价格而非池内价格

2. **TWAP使用**：
   - 搜索`price_cumulative_last`、`observations`、`oracle`
   - 验证是否使用时间加权平均价格而非即时价格
   - 检查TWAP窗口是否足够长（建议>10分钟）

3. **Commit-Reveal方案**：
   - 搜索`commit`、`reveal`、`hash`、`nonce`
   - 验证是否使用两阶段提交隐藏用户意图
   - 检查reveal时间窗口是否合理

4. **访问控制**：
   - 搜索`@internal`、`@external`、`@view`装饰器
   - 检查敏感函数是否限制调用者
   - 验证是否有私有内存池或批量处理机制

**审计等级建议：**
- 无任何保护机制：**L4跨模块追踪**（高危，需追踪所有调用路径）
- 仅有基础滑点保护：**L3逐行读**（需细查计算逻辑）
- 使用TWAP但窗口<5分钟：**L3逐行读**
- 完整TWAP+Commit-Reveal：**L2跳读**（确认实现正确性）

---

## Classify

### 确认为漏洞的判定标准

1. **直接价格操纵风险**：
   - swap函数使用当前区块储备计算价格，且单笔交易可显著影响价格（>1%）
   - 缺少滑点保护或滑点参数可由攻击者控制
   - 价格变化直接影响其他用户或协议（如清算、套利）

2. **可量化损失场景**：
   - 能构造POC证明通过抢跑获得超过gas成本的利润
   - 存在可重复利用的价格差异窗口
   - mempool可见时间足够进行三明治攻击（front-run + back-run）

3. **经济激励充分**：
   - 池子TVL足够大使得操纵成本低于收益
   - 存在外部套利空间（CEX价格差异）

### 归类为误报的情况

1. **有效保护机制**：
   - 使用多源预言机价格验证（Chainlink、Uniswap TWAP）
   - 实现Commit-Reveal且时间窗口合理（>1 block）
   - 交易量限制使得单笔无法显著影响价格

2. **内部函数或测试代码**：
   - 标记为`@internal`的辅助函数
   - 仅在测试环境使用的模拟函数

3. **低流动性场景**：
   - 明确注释为早期版本或演示代码
   - 文档说明仅用于小额测试

### 代码异味（需警示但非直接漏洞）

1. **依赖外部行为**：
   - 假设用户会合理设置滑点参数
   - 依赖前端计算min_out而非合约验证

2. **不完整的时间保护**：
   - 有deadline但可设置为type(uint256).max
   - TWAP窗口过短（<5分钟）

3. **事件顺序问题**：
   - 先emit事件再更新状态（泄露意图）
   - 多个状态更新之间存在可观察的中间状态

---

## Low risk

### 低风险评级适用场景

1. **经济模型限制**：
   - 池子总价值<$10k，攻击成本超过收益
   - 单笔交易限额<总储备0.1%，价格影响可忽略
   - 协议设计为封闭系统无外部套利空间

2. **多层保护降低风险**：
   - 主保护：TWAP时间窗口>30分钟
   - 次级保护：电路断路器（价格变化>5%暂停）
   - 兜底保护：交易延迟机制或批量执行

3. **特定使用场景**：
   - 私有链或联盟链环境，mempool不公开
   - 协议明确说明仅用于特定白名单地址
   - 存在链下订单簿撮合，链上仅结算

4. **理论风险但实际难度高**：
   - 需要跨多个协议协调攻击且gas成本高
   - 攻击窗口<1 block且需要精确时序
   - 存在监控系统可快速响应异常交易

### 低风险不等于无风险

即使评为低风险，审计报告应明确：
- 当前参数下风险可控，但TVL增长后需重新评估
- 建议添加监控和告警机制
- 在文档中说明潜在MEV风险供用户知情决策
