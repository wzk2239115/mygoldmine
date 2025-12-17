# Move_LiquidityReserveDrain

**流动性储备耗尽漏洞**（适用于 Aptos、Sui）

常出现在资源型流动性池（如 coin swap pool）或共享资金库实现中，由于未正确管理 pooled_coin 资源、未在 withdraw 时验证 reserve ratio、允许零流动性状态持续运行等导致池子储备被完全提取。

---

## Details

**典型代码模式：**

```move
// 漏洞示例：未验证储备比例的提取函数
public entry fun withdraw_liquidity<CoinA, CoinB>(
    account: &signer,
    pool: &mut LiquidityPool<CoinA, CoinB>,
    lp_amount: u64
) {
    let reserve_a = coin::value(&pool.reserve_a);
    let reserve_b = coin::value(&pool.reserve_b);
    let total_supply = pool.lp_token_supply;
    
    // 计算可提取数量
    let amount_a = (lp_amount * reserve_a) / total_supply;
    let amount_b = (lp_amount * reserve_b) / total_supply;
    
    // 危险：直接提取，未检查剩余储备是否足够维持池子运行
    let coin_a = coin::extract(&mut pool.reserve_a, amount_a);
    let coin_b = coin::extract(&mut pool.reserve_b, amount_b);
    
    coin::deposit(signer::address_of(account), coin_a);
    coin::deposit(signer::address_of(account), coin_b);
    pool.lp_token_supply = pool.lp_token_supply - lp_amount;
}
```

**快速定位核心操作技巧（L2-L3）：**
- 搜索关键函数：`withdraw`、`remove_liquidity`、`extract`、`coin::extract`、`coin::take`
- 定位资源操作：查找 `&mut LiquidityPool`、`&mut Coin<T>` 参数的函数
- 追踪储备字段：`reserve_a`、`reserve_b`、`balance`、`pooled_coin` 的修改点
- 检查计算逻辑：关注 `total_supply`、除法运算、比例计算是否允许耗尽

**快速定位保护机制技巧（L3-L4）：**
- 最小流动性检查：搜索 `MINIMUM_LIQUIDITY`、`MIN_RESERVE`、`assert!` 配合余额判断（L3）
- 储备比例验证：查找 `reserve_ratio`、`k = reserve_a * reserve_b` 恒定性检查（L3）
- 零值防护：检查 `amount == 0`、`reserve == 0` 的 `abort` 或 `assert!` 语句（L2）
- 锁定期限制：搜索 `timestamp`、`lock_until`、时间相关的提取限制（L3）
- 跨模块追踪：若使用独立 `math` 或 `safe_withdraw` 模块，需跟踪其实现（L4）

---

## Classify

**判定为漏洞的条件：**
- 提取函数可将储备降至零或极小值（如 < 1000 最小单位），导致后续交易失败或除零错误
- 缺失最小流动性锁定机制，初始流动性提供者可完全撤出
- 计算逻辑允许最后一个 LP 提取全部资产而无剩余保护

**误报情况：**
- 存在 `assert!(reserve_after >= MINIMUM_LIQUIDITY, E_RESERVE_TOO_LOW)` 等硬性检查
- 使用 `coin::extract_with_reserve` 等自带保护的函数
- 合约设计明确为一次性资金池（如 vesting 或特定场景的 escrow）

**代码异味（需人工确认）：**
- 有最小流动性常量定义但未在关键路径调用
- 仅在 swap 中检查而在 withdraw 中缺失
- 依赖外部 oracle 或 admin 权限进行储备管理（中心化风险）

---

## Low risk

**以下情况评为低风险：**

1. **已有部分保护但阈值偏低**：如 `MINIMUM_LIQUIDITY = 1` 仅防除零但不防经济攻击
2. **仅特权账户可触发**：withdraw 函数限定为 admin 或多签调用，非公开接口
3. **池子类型特殊**：非公共流动性池，如单向质押池、时间锁金库等不需要持续流动性
4. **存在紧急暂停机制**：虽然可能耗尽但 admin 可通过 `pause()` 及时冻结操作
5. **经济上不可行**：提取需支付高额手续费或锁定期过长，攻击成本超过收益
