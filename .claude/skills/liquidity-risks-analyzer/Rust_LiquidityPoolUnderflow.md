# Rust_LiquidityPoolUnderflow - 流动性池下溢

**适用环境**: Solana、Sealevel（基于账户模型）  
**场景**: 流动性池、质押池、跨链桥资金池中流动性提取时账户余额下溢

## Details

**代码示例**：
```rust
pub fn withdraw_liquidity(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
    let pool = &mut ctx.accounts.pool;
    let user = &mut ctx.accounts.user;
    
    // 漏洞：直接减法可能下溢
    pool.liquidity -= amount;
    
    // 转账操作
    **ctx.accounts.pool_vault.to_account_info().try_borrow_mut_lamports()? -= amount;
    **ctx.accounts.user.to_account_info().try_borrow_mut_lamports()? += amount;
    Ok(())
}
```

**快速定位核心操作**（审计等级：**L2-跳读**）：
- 关注 `withdraw`、`remove_liquidity`、`redeem`、`claim` 等提取类函数
- 扫描算术运算符 `-`、`-=`、`sub`、`checked_sub` 的使用位置
- 定位 `lamports`、`amount`、`balance`、`liquidity` 等余额字段的修改点
- 优先检查 SPL Token `transfer` 或原生 `lamports` 转账前的状态更新逻辑

**快速定位保护机制**（审计等级：**L3-逐行读**）：
- 检查是否使用 `checked_sub()`、`saturating_sub()` 等安全运算方法
- 验证 `require!()` 或 `assert!()` 对余额充足性的前置校验（`pool.liquidity >= amount`）
- 确认 `AccountInfo::lamports()` 在转账前后的一致性校验
- 检查是否存在最小保留余额（`min_liquidity`、`MIN_RESERVE`）限制
- 追踪跨 CPI 调用时的余额状态同步机制

## Classify

**漏洞判定标准**：
- 使用 `-` 或 `-=` 且无溢出检查，且无前置余额校验 → **Critical漏洞**
- 使用 `wrapping_sub` 或 `overflowing_sub` 且不处理溢出标志 → **High漏洞**
- 余额校验与扣减操作非原子性，存在竞态窗口 → **Medium漏洞**

**误报排除**：
- 已使用 `checked_sub` 并正确处理 `None` 返回值
- 存在充分的 `require!(balance >= amount)` 前置条件且参数来源可信
- 使用 `saturating_sub` 且业务逻辑容许饱和行为（需二次确认业务合理性）

**代码异味**：
- 使用 `unwrap()` 处理 `checked_sub` 结果（虽能 panic 但缺少友好错误信息）
- 余额校验与业务逻辑分散在多个函数，增加审计复杂度

## Low risk

以下情况可降级为 **Low 风险**：
- 池子有管理员特权锁定机制，且仅管理员可触发提取（需确认权限管理安全）
- 存在外部预言机或时间锁限制单次提取上限，且上限远小于池总量
- 下溢时会触发 Rust panic 导致交易回滚，虽能防止状态损坏但影响可用性（DoS风险转化）
- 仅测试环境或非主网部署的代码
- 存在链下监控系统实时检测异常提取并能紧急暂停合约（需验证暂停机制可靠性）

## 审计专业技巧

### 1. 双账户验证法
**核心问题**：Solana账户模型中，状态存储和资金分离，需同时审查：
```rust
// ❌ 误区：仅检查状态账户的减法
pool.liquidity -= amount;  // 状态更新

// ✅ 正确做法：同步验证两个层面
// 层面1：业务状态（通常是u64）
require!(pool.liquidity >= amount, InvalidAmount);
pool.liquidity -= amount;

// 层面2：实际资金（Lamports）
let vault_balance = ctx.accounts.pool_vault.to_account_info().lamports();
require!(vault_balance >= amount, InsufficientFunds);
```
**审计技巧**：跟踪 `pool_vault` 账户，追踪其余额是否与 `pool.liquidity` 状态同步。如两者不一致，可能存在：
- 余额重入漏洞（状态先更新，资金后转账）
- 跨程序调用中的账户污染

### 2. 代数恒等式验证法
**真实漏洞案例**：Orca DEX曾在数学库中使用 `checked_mul` 但未验证乘积溢出场景
```rust
// ❌ 误报陷阱：代码看起来安全但业务逻辑缺陷
let fee = amount.checked_mul(fee_bps)?.checked_div(10000)?;
pool.liquidity = pool.liquidity.checked_sub(amount)?;  // 已检查

// ✅ 验证不变量：提取amount后，池总流动性应满足
// invariant: post.liquidity + fee <= pre.liquidity
require!(
    pool.liquidity.checked_add(fee).unwrap_or(u64::MAX) <= old_liquidity,
    MathError
);
```
**审计技巧**：对于复杂提取逻辑（含手续费、滑点、奖励），应验证资金守恒：
- 提取前总额 = 用户得到 + 手续费 + 池保留量
- 任何缺口都可能是漏洞

### 3. 泛型风险检测
**真实漏洞场景**：使用泛型Token时，不同精度导致的下溢
```rust
// ❌ 真实漏洞：未考虑Token精度
pub fn withdraw<T: TokenAmount>(amount: T) {
    pool.balance -= amount.to_u64();  // 丢失精度，可能导致下溢
}

// ✅ 正确做法：显式处理精度
pub fn withdraw<T: TokenAmount>(amount: T) {
    let normalized = amount.normalize_to_pool_decimals()?;
    require!(pool.balance >= normalized, Underflow);
    pool.balance -= normalized;
}
```
**审计技巧**：对于支持多种Token或链的流动性池：
- 列出所有涉及的数据类型和其精度定义
- 追踪类型转换边界，尤其是 `as u64`、`from()`、`into()` 调用

### 4. 重入与竞态窗口
**误报案例**：看起来存在下溢但实际由重入保护
```rust
// ❌ 看起来有问题：先检查后扣减
require!(pool.liquidity >= amount, Underflow);  // 检查
// ... 中间可能有CPI调用
pool.liquidity -= amount;  // 是否能到达？

// ✅ 正确做法：检查重入保护
#[access_control(not_reentering(&ctx.accounts.pool))]
pub fn withdraw_liquidity(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
    require!(pool.liquidity >= amount, Underflow);
    pool.liquidity -= amount;
    // CPI调用...
}
```
**审计技巧**：
- 搜索是否有 `ReentrancyGuard`、`reentrancy_guard!()` 或手动flag机制
- 检查CPI调用（`invoke*`）前后的状态修改顺序
- 绘制"检查-使用"（TOCTOU）的时序图

### 5. 溢出检查的虚假安全感
**真实漏洞**：Raydium曾因 `saturating_sub` 误用导致流动性被冻结
```rust
// ❌ 虚假安全：饱和操作隐藏了真实问题
pool.liquidity = pool.liquidity.saturating_sub(amount);
// 用户期望得到amount，但如果pool.liquidity不足，实际只转账0

// 检测方法：审计需验证返回值或后续转账
if pool.liquidity == 0 && amount > 0 {
    // 资金转账了吗？没有！这是bug
}

// ✅ 正确做法：显式处理
let previous = pool.liquidity;
pool.liquidity = pool.liquidity.saturating_sub(amount);
require!(pool.liquidity < previous, InsufficientLiquidity);  // 确保扣减了
```
**审计技巧**：对每个 `saturating_*` 操作，追踪其后续使用：
- 结果是否被直接作为转账金额？
- 是否存在业务断言验证扣减成功？

## 真实漏洞 vs 误报速查表

| 特征 | 真实漏洞 | 误报 |
|------|--------|------|
| **检查位置** | 无检查 OR 检查在CPI后 | 检查在扣减前，有guard保护 |
| **操作原子性** | 多个未同步的状态更新 | 单个原子操作或Tx级别原子 |
| **溢出处理** | wrapping/unwrap无验证 | checked_*配合正确的错误处理 |
| **金额来源** | 用户输入未验证 | 计算结果或合约常数 |
| **测试覆盖** | 无单元测试或测试有漏洞 | 有完整的fuzz测试和边界测试 |

## 常见误报模式

1. **假溢出警告**
```rust
// 看起来危险但实际安全
let safe_amount = min(user_input, pool.liquidity);
pool.liquidity -= safe_amount;  // 永远不会下溢
```

2. **条件分支漏分析**
```rust
// 初审觉得有问题，二审时需检查match完整性
match pool.pool_type {
    PoolType::Standard => pool.liquidity -= amount,  // 有检查
    PoolType::Emergency => /* 有冻结标志防止提取 */,
}
```

3. **权限隔离造成的假象**
```rust
// 不同权限级别的提取函数可能有不同的保护
pub fn user_withdraw() -> 需要完整检查
pub fn admin_withdraw() -> 可能因权限单独管理
```
