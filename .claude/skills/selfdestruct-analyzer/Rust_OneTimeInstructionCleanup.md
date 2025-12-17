# Rust_OneTimeInstructionCleanup - 一次性指令清理漏洞

**漏洞成因**：指令执行后关闭账户回收租金，但未妥善处理账户间依赖关系，导致悬空引用或重入风险。

## Details

**代码示例特征**：
```rust
// 危险模式：先执行业务逻辑，后关闭账户
pub fn process_and_close(ctx: Context<ProcessAndClose>) -> Result<()> {
    // 执行转账、状态更新等操作
    transfer_tokens(...)?;
    
    // 关闭账户，转移剩余 lamports
    close_account(ctx.accounts.state_account, ctx.accounts.beneficiary)?;
    Ok(())
}
```

**快速定位核心操作技巧**（L2-L3 跳读至逐行）：
- 搜索关键函数：`close_account`、`realloc(0)`、`try_borrow_mut_lamports`、`AccountInfo::close()`
- 定位账户清零模式：检查 `**account.lamports.borrow_mut() = 0` 或 `data.len() == 0` 赋值
- 关注指令末尾的账户操作：close 操作通常在函数返回前执行
- 追踪 `is_signer` 和 `mut` 权限：可变且签名的账户具备 close 能力

**快速定位保护机制技巧**（L3-L4 逐行至跨模块）：
- 检查关闭前置条件：寻找 `require!` 或 `assert!` 验证状态完整性
- 验证依赖账户检查：确认引用该账户的其他账户是否先执行清理
- 查找重入保护标志：搜索 `is_closed`、`status == Closed` 等状态字段
- 跨指令依赖分析（L4）：追踪该账户在其他指令中的使用，确认是否存在悬空引用风险
- CPI 调用检查：若关闭前有跨程序调用，验证被调用程序是否会再次访问该账户

## Classify

**漏洞判定标准**：
- 账户关闭前存在外部调用（CPI），且被调用方可能回调访问已关闭账户 → 漏洞
- 多个账户存在依赖关系，关闭顺序不当导致悬空指针 → 漏洞
- 关闭后未更新相关状态标记，后续指令可能访问已释放账户 → 漏洞

**误报情况**：
- 账户在关闭前已完成所有状态同步，且无其他指令依赖 → 误报
- 使用 Anchor 框架的 `#[account(close = beneficiary)]` 宏，框架自动处理关闭时序 → 可能误报（需确认版本）

**代码异味**：
- 在同一交易内关闭并重新创建同名账户 → 异味（易引发逻辑混淆）
- 关闭逻辑分散在多个辅助函数中，缺乏统一控制流 → 异味

## Low risk

**低风险场景**：
- 账户为完全隔离的临时缓冲区，无跨指令引用
- 关闭操作在所有状态变更和 CPI 调用**之后**执行，且有明确的状态封印检查
- 使用原子化的 close-and-transfer 模式，单条指令内无重入路径
- 账户仅由单一签名者控制，关闭不影响协议全局状态
- 测试覆盖了账户关闭后的访问场景，且有明确的错误处理

## 审计专业技巧

### 真实漏洞案例识别

**案例1：状态悬挂的关闭漏洞**
```rust
// ❌ 真实漏洞：关闭后状态仍被引用
pub fn liquidate_and_close(ctx: Context<Liquidate>) -> Result<()> {
    let collateral = &mut ctx.accounts.collateral;
    let debt_account = &mut ctx.accounts.debt;

    // 执行清算逻辑
    process_liquidation(collateral, debt_account)?;

    // 关闭抵押品账户
    collateral.lamports = 0;
    collateral.data.borrow_mut().fill(0);

    // ⚠️ 危险：debt_account 仍持有指向 collateral 的引用
    // 后续 CPI 调用可能触发回调访问已清零的 collateral
}
```
**识别特征**：跨账户操作后立即关闭，未验证所有依赖账户的一致性检查

**案例2：并发关闭导致重复提取**
```rust
// ❌ 真实漏洞：两个平行指令争夺同一账户关闭
pub fn redeem_and_close(ctx: Context<Redeem>) -> Result<()> {
    require!(ctx.accounts.vault.total > 0, VaultEmpty);

    // 转移资产
    transfer_out(ctx.accounts.vault, ctx.accounts.user)?;

    // 关闭但未原子标记
    close_account(&mut ctx.accounts.vault);
    // 多个 redeem 指令可同时执行，导致重复关闭同一账户
}
```
**识别特征**：缺少状态机检查（如 `is_redeemed` 标志），多个指令可能竞争同一资源

### 误报陷阱及区分方法

**误报1：使用 Anchor 框架自动关闭**
```rust
// ✅ 安全：框架处理关闭时序
#[program]
pub mod safe_program {
    use super::*;

    pub fn process(ctx: Context<ProcessClose>) -> Result<()> {
        ctx.accounts.state.data = 0;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct ProcessClose<'info> {
    #[account(mut, close = beneficiary)]  // ← Anchor 宏保证关闭时序
    pub state: Account<'info, State>,
    #[account(mut)]
    pub beneficiary: SystemProgram,
}
```
**区分方法**：查看账户声明中是否含 `close = ` 属性，确认 Anchor 版本 ≥ 0.24.0

**误报2：单指令隔离关闭**
```rust
// ✅ 安全：完全隔离的临时账户
pub fn atomic_swap_close(ctx: Context<AtomicSwap>) -> Result<()> {
    // 1. 验证初始状态
    require!(ctx.accounts.temp_vault.initialized, NotInitialized);

    // 2. 执行原子交换
    swap_tokens(
        &ctx.accounts.input,
        &ctx.accounts.output,
        &ctx.accounts.temp_vault,
    )?;

    // 3. 验证交换完成
    require!(ctx.accounts.temp_vault.balance == 0, BalanceNotZero);

    // 4. 关闭临时账户（此时无其他指令依赖）
    ctx.accounts.temp_vault.lamports = 0;
    Ok(())
}
```
**区分方法**：追踪该账户是否在其他指令签名中出现，若无则为隔离关闭

### 高级审计检查清单

**L2 级别快速审计**：
1. 搜索 `close_account`、`realloc(0)` 关键字
2. 检查关闭前是否有 CPI 调用
3. 确认没有后续指令依赖该账户

**L3 级别深度审计**：
1. 绘制账户依赖图：标注哪些账户在关闭前被其他账户引用
2. 追踪状态转移：确认关闭前所有状态已同步
3. 检查错误分支：goto 或 early return 是否导致部分账户未关闭

**L4 级别跨合约审计**：
1. 分析所有 CPI 目标程序的回调逻辑
2. 检查是否存在漏斗式关闭（多个账户依赖同一根账户）
3. 审查交易模拟与实际执行的差异（Oracle 更新问题）

**真实审计经验建议**：
- **黄金规则**：关闭前必须验证该账户在当前交易内不会再被访问
- **红色标志**：任何关闭操作前出现 `invoke_signed`、`invoke` 或外部程序调用
- **绿色指标**：存在显式的 `require!(not_used_after)` 或状态机终态验证
- **灰色地带**：账户池化场景中，关闭需结合全局锁来防止重复使用
