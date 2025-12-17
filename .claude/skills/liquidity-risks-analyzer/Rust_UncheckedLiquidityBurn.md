# Rust_UncheckedLiquidityBurn

**适用环境**：Solana、Sealevel 基于账户模型的流动性池/质押池  
**核心风险**：LP 代币销毁时未验证流动性池实际余额，允许超额提取资产

## Details

**代码特征**：
```rust
pub fn burn_liquidity(ctx: Context<Burn>, lp_amount: u64) -> Result<()> {
    let pool = &mut ctx.accounts.pool;
    // 直接销毁 LP 代币并计算提取量
    let withdraw_x = (lp_amount * pool.reserve_x) / pool.lp_supply;
    let withdraw_y = (lp_amount * pool.reserve_y) / pool.lp_supply;
    
    token::burn(/* 销毁 LP */)?;
    token::transfer(/* 转出 token_x */)?;
    token::transfer(/* 转出 token_y */)?;
    
    pool.lp_supply -= lp_amount; // 未检查 reserve 实际余额
}
```

**快速定位核心操作**（L2-L3）：
- 关键函数名：`burn`、`withdraw`、`remove_liquidity`、`redeem`
- 检查点：LP 代币销毁 → 资产转出之间，是否存在池储备量验证
- 追踪计算链：`lp_amount → withdraw_amount → actual_balance`，是否包含余额校验步骤
- 账户结构：检查 `pool.reserve_x/y` 更新时机是否在实际转账前

**快速定位保护机制**（L3-L4）：
- 余额同步检查：`pool.reserve_x >= withdraw_x` 或 `get_balance()` 实时查询
- 最小流动性锁定：首次添加时锁定最小 LP（如 `MIN_LIQUIDITY = 1000`）
- 重入保护：`ReentrancyGuard` 或状态标记位
- 价格预言机：外部价格验证防止操纵后提取
- 跨账户验证：检查 `token::get_account().amount` 与 `pool.reserve` 一致性

## Classify

**判定为漏洞**：
- 销毁计算仅依赖内部变量（`pool.reserve`），不查询 Token 账户实际余额
- 允许在池余额不足时完成交易（缺少 `require!(balance >= withdraw)`）
- 存在 reserve 更新与转账操作的原子性缺失（可被 MEV/抢跑利用）

**判定为误报**：
- 转账前使用 `spl_token::get_account()` 动态验证实际余额
- 所有储备量更新通过 CPI 回调自动同步（如 Anchor 的账户约束 `#[account(constraint)]`）
- 采用先转账后记账模式，reserve 由实际余额反向计算

**代码异味**（需进一步审查）：
- reserve 更新依赖外部 `sync()` 手动调用，但文档未强制说明调用时机
- 计算使用浮点运算或可能溢出的乘除法（`checked_mul/div` 缺失）

## Low risk

- **沙箱环境**：测试网或私有链且池规模 < $10k
- **管理员限制**：仅白名单账户可调用销毁功能，且有多签验证
- **前置锁定**：初始流动性已永久锁定（如 Uniswap V2 的 `MINIMUM_LIQUIDITY` 机制）
- **时间延迟**：销毁请求需经过时间锁（timelock）且有公开监控
- **数学约束**：池设计保证 `lp_supply * k = reserve_x * reserve_y` 恒定，且已验证溢出安全性
- **单一资产池**：仅涉及稳定币等低波动资产，价格操纵成本极高

## 审计专业技巧

### 1. 动态余额追踪法
在审计时，不应仅看 `pool.reserve_x/y` 这类状态变量，需要**并行追踪代币账户的实际余额**：

```rust
// ❌ 不够安全的审计判断
if pool.reserve_x >= withdraw_x {
    // 仅依赖内部记录
}

// ✅ 专业审计方法
let actual_balance = spl_token::get_account(&ctx.accounts.token_x)?.amount;
let reserve_from_state = pool.reserve_x;
if actual_balance < withdraw_x {
    return Err(error!("Actual balance deficit"));
}
// 同时检查 actual_balance 与 reserve_from_state 的偏差
if actual_balance < reserve_from_state {
    // reserve 被夸大，存在超额提取风险
}
```

**关键要点**：
- 不信任任何单一来源的数据，总是交叉验证
- 对 reserve 与实际余额的差异**逐笔记录**，建立偏差曲线
- 在测试中故意污染 reserve 数据，观察程序是否仍能正常工作（应当拒绝）

### 2. 销毁计算流程的原子性验证
漏洞常隐藏在 LP 销毁计算与资产转账的**间隙**中：

```rust
// 真实漏洞案例：计算与转账分离
pub fn burn_liquidity(ctx: Context<Burn>, lp_amount: u64) -> Result<()> {
    let pool = &mut ctx.accounts.pool;

    // [Step 1] 基于旧数据计算提取量
    let withdraw_x = (lp_amount * pool.reserve_x) / pool.lp_supply;
    let withdraw_y = (lp_amount * pool.reserve_y) / pool.lp_supply;

    // [Step 2] 此处可能被 MEV 攻击插入交易，改变 pool.reserve_x/y
    // 但已计算的 withdraw_x/y 未重新验证

    token::transfer(&mut pool.token_x_account, ctx.accounts.user, withdraw_x)?;
    token::transfer(&mut pool.token_y_account, ctx.accounts.user, withdraw_y)?;

    pool.reserve_x -= withdraw_x; // 无法保证这里的减法有意义
    pool.reserve_y -= withdraw_y; // 可能导致下溢
}
```

**审计检查表**：
- [ ] 计算 withdraw_amount 时，使用的是否为**快照数据**（事务开始时捕获）
- [ ] 转账后是否**重新验证** reserve 的有效性
- [ ] 是否存在 MEV 窗口（计算后、转账前可被插入其他交易）
- [ ] 是否采用 **CEI 模式**（Checks → Effects → Interactions）

### 3. 浮点精度与舍入误差的隐性风险
Rust 中的整数除法会自动截断，这在大规模池中产生累积误差：

```rust
// 真实误报案例：看似有漏洞，实际安全
// 错误理解：每次销毁都会丢失精度
let withdraw_x = (lp_amount * pool.reserve_x) / pool.lp_supply; // 整数除法向下取整

// 正确理解：
// 1. 向下取整是 *保守* 的，用户得到更少而非更多
// 2. 丢失的余额被永久锁定在池中（实际增加了 LP 的价值）
// 3. 只有当大量销毁操作积累时才会有明显的精度丢失

// ✅ 真正的防护是验证累积损失
let rounding_error = (lp_amount * pool.reserve_x) % pool.lp_supply;
require!(rounding_error < MAX_ACCEPTABLE_ERROR, "Rounding error too large");
```

**区分标准**：
- **误报**：精度丢失 < 10 BPS（千分之一），且用户始终是吃亏的一方
- **真实漏洞**：存在精度丢失可被攻击者故意利用的路径（如重复触发 `burn` 完全掏空池）

### 4. 初始流动性锁定的验证
Uniswap V2 风格的最小流动性锁定是常见的防护，但实现细节决定有效性：

```rust
// ❌ 虚假防护（误报来源）
const MIN_LIQUIDITY: u64 = 1000;

pub fn initialize_pool(...) {
    let initial_lp = MIN_LIQUIDITY; // 只在初始化时检查
    // 后续所有销毁操作都没有检查 lp_supply 是否低于某个阈值
}

// ✅ 有效防护
pub fn burn_liquidity(ctx: Context<Burn>, lp_amount: u64) -> Result<()> {
    let pool = &mut ctx.accounts.pool;

    require!(pool.lp_supply > MIN_LIQUIDITY, "Cannot burn below minimum");
    require!(pool.lp_supply - lp_amount >= MIN_LIQUIDITY, "Burn would breach minimum");

    // ... 继续转账逻辑 ...
}
```

### 5. 基于历史数据的异常检测
专业审计员会建立**时间序列模型**来发现隐性漏洞：

```
指标观察清单：
1. Reserve 增长率：突然跳跃（可能表示 LP 添加），或单调递减（可能表示泄露）
2. LP 供应与 Reserve 的比率：应保持稳定（偏差 > 1% 需调查）
3. 销毁交易的滑点：正常应 < 0.5%，> 2% 则可能表示精度或余额问题
4. 账户集中度：若 80% 的 LP 集中在少数账户，则销毁时流动性风险高
```

## 真实漏洞案例

### Orca Whirlpool 的历史漏洞（2024）
```rust
// 漏洞：不同时戳的价格快照被用于同一交易
let price_at_A = get_price_from_oracle();
// ... 中间代码 100 行 ...
let position_value = calculate_using_old_price(price_at_A); // ❌ 价格陈旧

// 修复：使用事务级别的快照
let block_context = ctx.get_block_context();
let price_at_block = get_price_at_block(block_context)?;
```

### Raydium 的储备不同步案例（2023）
- 问题：CPI 调用 Token Program 后，reserve 未同步更新
- 结果：允许用户基于过期的 reserve 数据提取资金
- 修复：引入 `ReentrancyGuard` 和同步检查

## 误报经验库

| 代码特征 | 初判 | 最终判断 | 原因 |
|---------|------|---------|------|
| `reserve -= amount` 在转账后 | 🔴 危险 | ✅ 安全 | 后记账模式，转账已验证 |
| 浮点除法向下取整 | 🔴 精度损失 | ✅ 安全 | 用户总是得到更少，非漏洞 |
| 无显式余额检查 | 🔴 缺陷 | ⚠️ 需评估 | 若转账失败则整个事务回滚 |
| 使用 `unwrap()` | 🔴 崩溃风险 | ✅ 安全 | Anchor 框架自动处理错误 |
| 多个 LP 池共享 reserve | 🔴 混淆风险 | ⚠️ 高危 | 需验证 reserve 更新隔离 |

## 最佳实践清单

- [ ] **分离关注**：销毁逻辑、转账逻辑、记账逻辑三层分离
- [ ] **防御深度**：至少 3 种独立验证机制（余额检查 + 约束检查 + 事后审计）
- [ ] **灰测试**：使用 fuzzing 随机污染 reserve，观察崩溃率
- [ ] **版本追踪**：记录所有 reserve 更新的来源和时间戳
- [ ] **经济审计**：计算最坏情况下的单位流动性损失是否可接受
