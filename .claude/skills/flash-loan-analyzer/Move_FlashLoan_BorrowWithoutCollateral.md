# Move 闪电贷：无抵押借贷漏洞

**漏洞类型**：闪电贷实现缺陷  
**影响范围**：Aptos/Sui 生态 AMM、借贷池合约  
**核心问题**：允许无抵押借出资产且未确保同一交易内原子性归还

---

## Details

### 典型代码特征

```move
public fun borrow<CoinType>(
    pool: &mut LendingPool<CoinType>,
    amount: u64,
    ctx: &mut TxContext
): Coin<CoinType> {
    // ❌ 直接提取资产，无 Hot Potato 模式约束
    let borrowed = coin::split(&mut pool.reserve, amount, ctx);
    borrowed  // 返回可自由转移的 Coin
}

public fun repay<CoinType>(
    pool: &mut LendingPool<CoinType>,
    payment: Coin<CoinType>
) {
    coin::join(&mut pool.reserve, payment);
}
```

### 快速定位核心操作 **(L3: 逐行读)**
1. **关注函数返回值**：搜索 `public fun borrow`、`public entry fun flash_loan`
2. **返回类型检查**：若返回 `Coin<T>` 而非自定义 struct，存在风险
3. **Split/Extract 操作**：`coin::split`、`balance::split`、`coin::take` 后直接返回
4. **入口函数特征**：借贷函数标记为 `public` 或 `entry`，但归还函数独立存在

### 快速定位保护机制 **(L4: 跨模块追踪)**
1. **Hot Potato 模式**：检查是否返回无 `drop`/`store`/`key` 能力的自定义 struct
   ```move
   struct Receipt<phantom T> { amount: u64 }  // ✅ 强制归还
   ```
2. **能力约束**：`has drop` = 高危，`has store` = 可存储（延迟归还）
3. **回调验证**：查找 `assert!` 验证 `pool.reserve_before == pool.reserve_after`
4. **借贷凭证销毁**：搜索 `Receipt` 与 `repay` 函数的 `unpack`/消费关系
5. **事件日志交叉验证**：`emit(BorrowEvent)` 与 `emit(RepayEvent)` 是否配对检查

---

## Classify

### 确认为漏洞
- 借贷函数返回标准 `Coin<T>` 且无强制归还机制（Hot Potato）
- 借贷与归还可在不同交易中完成（缺乏原子性）
- 借贷凭证具有 `store` 或 `drop` 能力，可被丢弃或长期持有
- 借贷后仅依赖链下监控或后续交易检查余额（非同步验证）

### 误报场景
- 借贷函数返回 Receipt 结构体且**必须**在当前交易内调用 repay 销毁
- 使用 Sui 的 `TransferPolicy` 或 Aptos 的 `withdrawal_proof` 机制强制回流
- 函数内部已有 `assert!(balance_before <= balance_after)` 且在同一作用域
- 仅限内部模块调用（`public(friend)` 且 friend 列表安全）

### 代码异味
- 借贷限额过低（如仅 1 APTOS）但机制设计本身脆弱
- 存在归还激励但未强制执行（依赖经济博弈而非代码约束）
- 多步骤操作（borrow → operate → repay）但缺少清晰文档说明原子性要求

---

## Low Risk

### 以下情况评级为低风险
1. **数额限制极小**：单笔借贷上限 ≤ $100 等值且有全局频率限制
2. **白名单机制**：借贷函数仅对 `AdminCap` 持有者或预授权地址开放
3. **超额抵押前置**：虽然设计有缺陷，但实际已要求抵押率 > 100%（冗余保护）
4. **冷启动阶段**：协议 TVL < $1k 且明确标注测试网/Alpha 版本
5. **已有外部监控**：配合链下清算机器人且延迟归还会触发罚金（需评估罚金是否足够）

**注意**：即使评为低风险，仍需在报告中说明潜在设计缺陷，建议采用 Hot Potato 模式重构。
