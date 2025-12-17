# Move 池资源不一致漏洞

**适用范围**：Aptos、Sui  
**漏洞场景**：资源型流动性池（如 coin swap pool）或共享资金库实现中，流动性池的资源状态与实际储备不匹配，导致提取或兑换失败。

---

## Details

### 代码示例特征

```move
// 典型漏洞模式：储备量与资源不一致
struct LiquidityPool<phantom X, phantom Y> has key {
    coin_x: Coin<X>,
    coin_y: Coin<Y>,
    reserve_x: u64,  // 声明的储备量
    reserve_y: u64,
    lp_supply: u64
}

public fun swap<X, Y>(pool: &mut LiquidityPool<X, Y>, input: Coin<X>): Coin<Y> {
    let input_amount = coin::value(&input);
    coin::merge(&mut pool.coin_x, input);
    // 未同步更新 pool.reserve_x，造成不一致
    let output_amount = calculate_output(input_amount, pool.reserve_x, pool.reserve_y);
    coin::extract(&mut pool.coin_y, output_amount)
}
```

### 定位核心操作技巧 **[L3-L4]**

**关键函数**（L3：逐行读）：
- `swap`/`add_liquidity`/`remove_liquidity`：所有修改池资源的入口函数
- `coin::merge`/`coin::extract`/`coin::split`：实际资源操作点
- 储备变量赋值：搜索 `reserve_x =`、`reserve_y =`

**追踪路径**（L4：跨模块追踪）：
- 跟踪 `Coin<T>` 的实际余额与 `reserve_*` 字段的更新时序
- 检查 `borrow_global_mut<Pool>` 后的所有分支是否同步更新
- 验证 `coin::value(&pool.coin_x)` 是否始终等于 `pool.reserve_x`

### 定位保护机制技巧 **[L2-L3]**

**状态验证**（L2：跳读）：
- 搜索 `assert!` 检查储备一致性：`coin::value(&pool.coin_x) == pool.reserve_x`
- 查找 `invariant` 注释或验证函数（如 `check_reserves()`）
- 扫描 `spec` 规范中的 `ensures` 子句

**零流动性防护**（L3：逐行读）：
- 检查 `lp_supply > 0` 或 `reserve_x > 0 && reserve_y > 0` 的前置条件
- 确认 `remove_liquidity` 是否允许清空池但保留资源对象
- 验证初始化函数是否强制最小流动性（如 `MINIMUM_LIQUIDITY` 常量）

---

## Classify

### 确认为漏洞
1. **状态分叉**：储备变量更新路径与资源操作路径不同步，存在 revert 前的不一致窗口
2. **数学误差累积**：使用整数除法导致 `reserve` 与实际 `coin::value` 产生系统性偏差且无修正机制
3. **竞态条件**：并发调用时未使用事务性更新，`reserve` 计算基于过期快照

### 误报判定
1. **显式异步设计**：文档明确说明延迟同步机制（如批量结算），且有兜底校验
2. **测试环境伪代码**：mock 实现或测试桩未实现完整逻辑
3. **已废弃代码**：标记为 `deprecated` 且主网不可达

### 代码异味
1. **冗余字段**：同时存储 `reserve` 和 `coin` 但仅用于日志或显示，不参与业务逻辑
2. **单向不一致**：仅在非关键路径（如查询接口）存在不一致，不影响资产安全

---

## Low risk

### 低风险场景
1. **保护性过度储备**：`reserve` 始终 <= `coin::value`，不一致仅导致少量资金锁定，不影响偿付能力
2. **原子性保证**：Move VM 的事务性确保单次调用内不可能观察到中间状态，不一致仅理论存在
3. **管理员手动修正**：存在特权函数可同步储备（需评估权限安全性），且有监控告警
4. **有界误差**：不一致上限被常量限制（如 `MAX_DUST = 100`），对流动性池规模占比可忽略
5. **仅影响视图函数**：不一致字段仅用于 `view` 函数返回，链上逻辑始终读取 `coin::value`
