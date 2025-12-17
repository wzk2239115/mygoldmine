# Vyper_SlippageBypassLiquidity

**漏洞类型：** 滑点绕过流动性  
**风险等级：** High  
**常见场景：** DEX、AMM、收益聚合器流动性池

## Details

**典型代码示例：**

```vyper
@external
def swap(
    token_in: address,
    token_out: address,
    amount_in: uint256,
    min_amount_out: uint256
) -> uint256:
    # 计算输出金额
    amount_out: uint256 = self._calculate_output(token_in, token_out, amount_in)
    
    # 问题：直接执行交换，未验证 min_amount_out
    assert amount_out > 0
    
    self._transfer_tokens(token_in, msg.sender, self, amount_in)
    self._transfer_tokens(token_out, self, msg.sender, amount_out)
    
    return amount_out
```

**快速定位核心操作技巧（L2-L3 审计等级）：**
- 搜索关键函数：`swap`、`exchange`、`add_liquidity`、`remove_liquidity`
- 关注计算输出量的函数：`get_dy`、`calc_token_amount`、`_calculate_output`
- 检查价格更新点：`self.reserve0`、`self.reserve1`、`self.balanceOf`
- 追踪 K 值维护：`self.reserve0 * self.reserve1`、恒定乘积公式

**快速定位保护机制技巧（L3-L4 审计等级）：**
- 滑点检查关键词：`min_amount_out`、`max_amount_in`、`slippage`、`min_dy`
- 验证逻辑：`assert amount_out >= min_amount_out`、`require()`
- 时效性保护：`deadline`、`block.timestamp`、`assert block.timestamp <= deadline`
- 价格预言机：`get_price`、`twap`、`price_cumulative_last`
- 流动性深度检查：池余额与交易量比例、`assert amount_in < reserves / MAX_RATIO`
- 若缺失上述任一机制需逐行审查计算逻辑，升级至 L4 跨模块追踪价格来源

## Classify

**漏洞判定标准：**
- 接受用户输入金额但完全忽略 `min_amount_out` 参数
- 滑点参数存在但验证逻辑被注释或条件可绕过（如 `min_amount_out == 0` 时跳过检查）
- 计算输出使用过期价格或可被操纵的即时价格，无 TWAP 或多区块平均
- 允许单笔交易抽干池子显著比例流动性（>10%）且无分批限制

**误报识别：**
- 内部调用函数无滑点检查，但上层入口已验证
- 仅用于查询的 view 函数（`@view`/`@pure`）无需滑点保护
- 协议级操作（如治理、管理员紧急提款）有权限控制可豁免

**代码异味：**
- 滑点参数设为硬编码常量而非用户指定
- 滑点容忍度过大（>5%）但有其他补偿机制
- 使用近似算法导致精度损失，但在可接受范围（<0.1%）

## Low risk

**低风险场景：**
- 池子流动性深度极大（TVL>$1B），单笔最大交易量被严格限制为流动性的 0.1% 以下，价格偏移可忽略
- 存在多层价格偏差检测：链上预言机对比、历史波动率阈值、多池价格交叉验证
- 白名单交易模式，仅允许预先审核的做市商/机器人交易，且有离链监控熔断机制
- 交易量与时间锁绑定，大额交易需多区块分批执行，单区块滑点攻击收益低于 Gas 成本
- 已部署自动化套利机器人监控该池，价格偏离立即被纠正，攻击窗口<1 个区块

## 审计专业技巧：真实漏洞 vs 误报区分

### 1. 上下文追踪法（Context Tracing）
**核心原则：** 单个函数的判断必须结合完整的调用链路

**真实漏洞特征：**
```vyper
# 业务流程：用户直接调用 swap() → 无滑点检查
@external
def swap(amount_in: uint256) -> uint256:
    amount_out = self._get_amount_out(amount_in)  # 即时价格
    # 缺少 min_amount_out 参数和验证
    return self._execute_swap(amount_in, amount_out)
```

**误报情况：**
```vyper
# 业务流程：用户调用 swap_with_slippage() → swap() 有验证
@external
def swap_with_slippage(amount_in: uint256, min_out: uint256) -> uint256:
    assert min_out > 0, "Slippage too high"
    return self.swap(amount_in, min_out)

@internal
def swap(amount_in: uint256, min_out: uint256) -> uint256:
    amount_out = self._get_amount_out(amount_in)
    assert amount_out >= min_out  # 验证已做
    return amount_out
```
**审计建议：** 从 `@external` 入口倒推，确认所有用户可调用路径都经过滑点检查

### 2. 价格来源分类法（Price Source Classification）

| 价格来源类型 | 风险等级 | 判定依据 |
|---------|---------|---------|
| 即时现货价格（`balanceOf` 比值） | **HIGH** | 同区块MEV操纵 |
| 单区块价格累积（`price_cumulative_last`） | **MEDIUM** | 需验证更新频率 |
| Chainlink 预言机（延迟2-60秒） | **LOW** | 但需检查 `stalePriceFeed` 处理 |
| TWAP（8+ 区块平均） | **LOW** | 前提：32秒内未遭24小时操纵 |
| 多链路三角套利验证 | **LOW** | 池流动性差异可导致误报 |

**审计技巧：** 在代码中搜索 `_calculate_output`、`get_dy` 时，立即查看其依赖的 reserves 何时更新——同 Tx 更新=高风险，前块更新=低风险

### 3. 滑点参数有效性检查（Slippage Parameter Validity）

**真实漏洞指标：**
- 函数签名有 `min_amount_out` 但内部硬编码为 `0`
- 滑点校验存在但条件可绕过：`if min_amount_out > 0: assert ...` （允许跳过）
- 用户输入的滑点在 10% 范围内时忽略检查

**误报高发点：**
- 批量操作（`add_liquidity_multi()`）中，某些 token pair 不需滑点保护（如稳定币对）
- Flash Loan 回调函数(`_executeOperation`) 天然允许临时价格偏离，只需还款时检查

**代码片段审查清单：**
```vyper
# ✗ 直接传入 min_amount_out 但未使用
def swap(token_in, token_out, amount_in, min_amount_out):
    output = calculate(token_in, token_out, amount_in)  # 跳过了 min_amount_out
    return output

# ✓ 正确使用
def swap(token_in, token_out, amount_in, min_amount_out):
    output = calculate(token_in, token_out, amount_in)
    assert output >= min_amount_out, "Slippage exceeded"
    return output
```

### 4. Deadline 陷阱识别（Deadline Trap Detection）

**常见误报：**
- 函数有 `deadline` 参数但仅用于日志，未实际验证
- 验证逻辑：`assert block.timestamp <= deadline` 存在，但 deadline 默认值为 0（永不过期）

```vyper
# ✗ 误报：deadline 参数形同虚设
def swap(..., deadline: uint256):
    # ... 交易逻辑 ...
    log Swap(deadline)  # 只记录，不验证

# ✓ 真实漏洞：deadline 存在但条件颠倒
def swap(..., deadline: uint256):
    assert block.timestamp >= deadline  # 应该是 <=！

# ✓ 正确实现
def swap(..., deadline: uint256):
    assert deadline > 0
    assert block.timestamp <= deadline
```

### 5. 流动性深度启发式（Liquidity Depth Heuristics）

**量化判定标准（实战经验）：**
- 单笔交易 ≤ 0.1% 流动性：多数情况无需担心（假设无 Flash Loan）
- 单笔交易 0.1-1% 流动性：需验证是否有 TWAP 或分批机制
- 单笔交易 > 1% 流动性：必须有多层防护或交易限制

**误报常见案例：**
```vyper
# 看似有风险的代码，实际安全
@external
def large_swap(amount_in: uint256) -> uint256:
    # 虽然无显式滑点检查，但通过费用和交易验证池流动性
    assert self.total_liquidity > amount_in * 100  # 强制100倍流动性要求
    output = self._swap(amount_in)
    return output
```

### 6. 精度损失 vs 实际漏洞（Precision Loss vs Real Bugs）

**误报识别：**
- 因四舍五入导致 `amount_out` 与 `min_amount_out` 差异 <0.01%
- 多步骤计算产生的累积误差在可接受范围（<0.1%）
- 使用 `uint256` 整数除法造成的舍去，但余数 <token decimals 最小单位

**真实漏洞：**
- 精度损失 >1%，且无补偿机制
- 舍入方向故意向下（损害用户），无向上舍入的补偿

```vyper
# ✗ 真实风险：精度偏向协议
output = (input * 997 * reserve_out) // (reserve_in * 1000 + input * 997)
# 下舍入导致用户永远收到最小值

# ✓ 安全：使用向上舍入保护用户
output = (input * 997 * reserve_out) // (reserve_in * 1000 + input * 997)
if (input * 997 * reserve_out) % (reserve_in * 1000 + input * 997) > 0:
    output += 1
```

### 7. 跨合约调用风险评估（Cross-Contract Call Risk）

**审计检查点：**
- 外部调用返回值是否被信任（如 Uniswap 返回值直接用于计算）
- 是否存在重入窗口（滑点检查与转账之间有外部调用）
- 依赖的预言机合约是否已审计

**真实漏洞案例：**
```vyper
# ✗ 风险：预言机可能被操纵
price = IOracle(oracle).getPrice(token)
output = amount_in * price // 1e18
# 如果 oracle 依赖 Uniswap V2，同一区块可被 Flash Loan 操纵
assert output >= min_amount_out
```

## 实战案例库

### 案例 1：Curve Finance 风险评估
**结论：** Low Risk
**理由：**
- 使用多步 TWAP，防护力强
- 流动性 TVL > $2B，单笔交易限制 0.05%
- 有多个独立套利机器人监控

### 案例 2：假设协议 XYZ Swap
**红旗：** `min_amount_out` 参数存在但从不被使用
**判定：** **真实漏洞**
**建议修复：** 在计算后立即加入 `assert output >= min_amount_out`
