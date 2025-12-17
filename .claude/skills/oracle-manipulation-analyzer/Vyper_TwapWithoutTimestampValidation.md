# TWAP 无时间戳验证 (Vyper)

## 漏洞概述
使用 TWAP（时间加权平均价格）计算平均价格但未验证时间窗口的有效性，允许使用过期或未来数据操纵价格预言机。

---

## Details

**代码示例：**

```vyper
# 缺陷：直接使用历史价格累加器计算 TWAP，未验证时间戳范围
@external
@view
def get_twap_price(token: address) -> uint256:
    current_cumulative: uint256 = self.price_cumulative[token]
    last_cumulative: uint256 = self.last_price_cumulative[token]
    time_elapsed: uint256 = block.timestamp - self.last_update_time[token]
    
    # 漏洞点：未验证 time_elapsed 是否在合理范围内
    # 未检查 last_update_time 是否过时
    return (current_cumulative - last_cumulative) / time_elapsed

@external
def update_price(token: address, price: uint256):
    self.price_cumulative[token] += price * block.timestamp
    self.last_update_time[token] = block.timestamp
```

**快速定位核心操作技巧：**（审计等级 **L2-L3**）
- 搜索 `cumulative`、`time_elapsed`、`twap`、`average_price` 等关键词
- 关注价格除以时间差的计算模式：`(price1 - price0) / (time1 - time0)`
- 定位所有使用 `block.timestamp` 做减法运算的价格计算函数
- 查找调用外部 DEX 的 `observeSingle` 或 `consult` 方法的位置

**快速定位保护机制技巧：**（审计等级 **L3-L4**）
- 检查是否存在 `MIN_TWAP_WINDOW`、`MAX_TWAP_AGE` 等时间边界常量
- 验证时间差计算前是否有 `assert time_elapsed >= MIN_PERIOD` 断言
- 确认是否检查 `last_update_time > block.timestamp - MAX_STALENESS`
- 追踪是否有 `require observationCardinality > 0` 类型的数据新鲜度校验
- 跨合约追踪：检查预言机提供方（如 Uniswap V3）的 `observe()` 调用是否传入有效的 `secondsAgo` 数组

---

## Classify

**确认为漏洞的条件：**
- TWAP 计算使用的时间戳差值无上下界限制，可接受任意过期或未来数据
- 缺少对预言机更新频率的校验，允许单次极端价格点长期影响均价
- 未验证历史数据点的时间戳顺序性（`t1 > t0`）
- 价格累加器可被置零或回滚但无时间窗口保护

**判定为误报的情况：**
- 代码注释明确标注该函数仅用于视图查询，不参与关键业务逻辑
- 调用的外部预言机（如 Chainlink、API3）自身已实现时间戳验证
- 上层调用方已完成时间窗口校验，当前函数仅作内部辅助计算

**代码异味标识：**
- 时间边界检查存在但阈值设置不合理（如允许 7 天以上的旧数据）
- 仅检查下界（最小窗口）未检查上界（最大陈旧时间）
- 使用硬编码的时间戳而非动态获取 `block.timestamp`

---

## Low risk

**以下场景可评为低风险：**
- 该价格仅用于非关键业务（如前端显示、统计报表），不影响资金转移
- 合约具有多源价格聚合机制，单一 TWAP 源失效有其他降级策略
- 价格偏差存在熔断机制（如超出 5% 阈值则拒绝交易）
- 合约已停用或处于测试网环境，无实际资产风险
- 时间窗口虽未验证但受限于极小范围（如强制 5 分钟内更新），实际操纵成本极高
- 仅管理员可调用价格更新函数且具有多签或时间锁保护

---

## 审计专业技巧

### 真实漏洞与误报的区分

**真实漏洞案例 1：数据陈旧导致套利**
```vyper
# 实际案例：Harvest Finance 被攻击场景模拟
@external
def get_pool_price(token_a: address, token_b: address) -> uint256:
    # 获取 7 天前的历史价格累加器快照
    old_snapshot = self.price_snapshots[token_a][block.timestamp - 7 * 86400]
    current_snapshot = self.price_cumulative[token_a]

    # 缺陷：未验证 old_snapshot 是否有效存在
    # 如果 7 天前无更新，返回的是初始化时的零值
    time_delta: uint256 = 7 * 86400
    return (current_snapshot - old_snapshot) / time_delta  # 可能除以零
```

**区分要点**：
- 检查时间差固定值是否大于合约的实际运行时间
- 追踪快照初始化时机，确认是否被写入有效数据
- 计算攻击收益：若价格差 10%，能在 flash loan 下完成套利吗？

**真实漏洞案例 2：时间戳回滚导致重复使用**
```vyper
@external
def settle_position(token: address, amount: uint256):
    require: self.last_update_timestamp[token] < block.timestamp

    # 缺陷：仅检查 < 而非 !=，允许同一区块内多次调用
    # 矿工可在同一区块内操纵多次，price_cumulative 不更新但时间戳相同
    self.user_collateral[msg.sender] -= amount
    self.price_history[token].append(self.get_current_price())
    self.last_update_timestamp[token] = block.timestamp
```

**区分要点**：
- 同一区块内重入是否被利用（检查 `reentrancy_guard`）
- 时间戳验证是否包含等号（`<=` vs `<`）的逻辑错误
- MEV 攻击者是否能在同一区块内多次改写价格

**真实漏洞案例 3：预言机故障导致除零**
```vyper
@external
def calculate_swap_amount(token_a: address, token_b: address) -> uint256:
    price_a: uint256 = self.get_twap_price(token_a)  # 可能返回 0
    price_b: uint256 = self.get_twap_price(token_b)

    # 缺陷：未检查 price_a 是否为 0
    # 当预言机长时间无更新时，time_elapsed 为 0，触发异常
    return amount * price_a / price_b
```

**区分要点**：
- 检查价格返回值的零值防护
- 追踪预言机更新频率与价格为零的临界条件
- 计算时间差的上界：若无更新 30+ 分钟，函数是否失败

### 审计检查清单（按优先级）

**P0 - 立即检查（必须验证）：**
1. **时间差是否可为零**：`time_elapsed = block.timestamp - last_update` 中，若两者相等会怎样？
2. **初始状态漏洞**：合约部署后首次调用 TWAP，`price_cumulative` 是否为 0？能否被利用？
3. **预言机数据来源**：TWAP 数据从何而来？是本合约维护还是外部合约？
4. **价格被调用位置**：追踪所有调用 `get_twap_price` 的函数，检查返回值是否被验证

**P1 - 深度检查（高风险信号）：**
1. 时间边界常量是否存在但数值不合理（如允许 30 天陈旧数据用于清算）
2. 多个时间戳检查是否存在顺序漏洞（如先检查下界后检查上界时发生状态变更）
3. 循环内的时间戳累加是否正确（避免溢出或精度丧失）

**P2 - 关联检查（上下文审计）：**
1. 该合约是否持有大额资产，预言机被操纵的经济激励有多大？
2. 调用链路中是否有权限检查被绕过的可能（如管理员更新价格函数权限校验不足）
3. 是否存在多签、时间锁等二级防护机制

### 误报常见模式

**误报 1：严格外部依赖的 TWAP**
```vyper
# 看似有漏洞但实际安全的例子
@external
def get_uniswap_v3_twap(token: address, seconds: uint256) -> uint256:
    # 调用 Uniswap V3 的 observe 函数
    # Uniswap V3 内部已完成时间戳验证和数据有效性检查
    observations: DynArray[tuple[uint32, int56, uint160, bool]] = IUniswapV3Pool(pool).observe(
        [seconds, 0]
    )
    return self._calculate_price_from_observations(observations)
```
**判定理由**：Uniswap V3 官方合约已实现完整的时间戳历史纪录机制，本合约仅封装调用。

**误报 2：防护机制在上层调用方**
```vyper
# 看似无验证的函数，但上层应用有保护
@internal
def _twap_internal(token: address) -> uint256:
    # 无时间戳验证，看起来是漏洞
    return (self.cumulative[token] - self.prev_cumulative[token]) / self.time_delta

@external
def swap(token_a: address, token_b: address, amount: uint256) -> uint256:
    require: block.timestamp >= self.last_swap_time + 60  # ← 关键保护在这里
    price: uint256 = self._twap_internal(token_a)
    # ... 交易逻辑
```
**判定理由**：内部函数 `_twap_internal` 虽无验证，但公开调用方 `swap` 强制 60 秒最小间隔。

**误报 3：不可变历史数据的 TWAP**
```vyper
# 使用链上确凿历史数据而非动态时间差
@external
def get_fixed_window_average(token: address, window_id: uint256) -> uint256:
    # window_id 对应固定的时间窗口（如某个小时）
    # 数据一旦提交则不可更改
    historical_sum: uint256 = self.window_sums[token][window_id]
    require: self.window_finalized[token][window_id]  # ← 关键：窗口已锁定
    return historical_sum / WINDOW_DURATION
```
**判定理由**：虽未显式验证时间戳，但数据锁定机制已保证时间窗口的不可变性。

### 攻击成本评估指南

在判定为 High Risk 前，评估现实可行性：

**评估维度 1：数据获取成本**
- 若 TWAP 依赖外部 DEX，需要多少笔交易才能显著扭曲价格？
- Flash loan 成本是否低于预期收益？

**评估维度 2：时间维度**
- 攻击是否需要跨越多个区块（被检测风险高）还是单区块内完成（MEV）？
- 时间窗口越长，操纵成本越高（长期维持虚假价格更困难）

**评估维度 3：经济激励**
- 若 TWAP 用于清算价格，清算的资产规模有多大？
- 攻击收益是否足以覆盖 gas 费与 oracle 操纵成本？
