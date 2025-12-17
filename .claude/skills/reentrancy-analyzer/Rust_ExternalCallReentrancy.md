# Rust 外部调用重入（External Call Reentrancy）

## Details

典型代码模式：
```rust
// Solana 程序示例
pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
    let user_balance = ctx.accounts.user_account.balance;
    
    // 外部 CPI 调用在状态更新前执行
    token::transfer(
        CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.vault.to_account_info(),
                to: ctx.accounts.user.to_account_info(),
                authority: ctx.accounts.authority.to_account_info(),
            },
        ),
        amount,
    )?;
    
    // 状态更新滞后，允许重入攻击
    ctx.accounts.user_account.balance -= amount;
    Ok(())
}
```

**快速定位核心操作技巧**（审计等级：L2 跳读 → L3 逐行读）：
- 搜索关键词：`invoke`、`invoke_signed`、`CpiContext::new`、`call`、`build().call()`
- 定位资金流动点：`transfer`、`withdraw`、`send_lamports`、`close_account`
- 追踪账户余额/状态变更：变量赋值、字段修改操作
- 检查操作序列：外部调用与状态更新的先后顺序

**快速定位保护机制技巧**（审计等级：L1 关键词扫描 → L3 逐行读）：
- 互斥锁标识：`is_locked`、`reentrancy_guard`、`status` 枚举字段
- 先检查后执行（CEI）模式：状态更新在外部调用前
- 账户约束检查：`#[account(mut, constraint = !account.is_locked)]`
- 单次调用限制：`require!(!ctx.accounts.state.processing)`
- 不可重入标记：函数开始设置标志位，结束时清除

## Classify

**漏洞判定标准**：
1. 状态更新滞后于外部调用（CPI、invoke、跨程序调用）
2. 外部调用目标可被攻击者控制或影响
3. 状态变量影响关键业务逻辑（余额、权限、配额）
4. 缺乏重入保护机制（互斥锁、状态标志位）

**误报识别**：
1. 外部调用为只读操作（查询、读取数据）
2. 状态更新与外部调用无因果依赖关系
3. 调用目标为可信系统合约（Token Program、System Program）且无回调
4. 存在完整的重入锁且正确实施

**代码异味**：
1. 存在保护但实现不完整（锁未覆盖所有路径）
2. 状态更新与调用混杂，逻辑顺序不清晰
3. 依赖外部合约的行为假设而非显式保护

## Low risk

以下情况可评为低风险：
1. **只读外部调用**：CPI 仅查询数据，不触发状态变更或回调
2. **非关键状态影响**：重入仅影响日志、计数器等非财务数据
3. **受限调用目标**：外部调用目标写死为官方程序（SPL Token、System）且无自定义逻辑
4. **天然单次保证**：账户关闭操作（`close_account`）执行后账户不可再用
5. **价值隔离**：每次调用操作独立资源，无累积效应（如固定金额铸币）
6. **时间/区块锁定**：存在冷却期或区块高度限制，重入收益低于成本
7. **部分保护**：虽存在重入窗口，但攻击条件苛刻（需多重签名、时间窗口极短）

## 审计专业技巧

### 1. 漏洞与误报的区分经验

**真实漏洞的典型特征**：
- 状态读写**在同一账户**上发生（如 `user_account.balance`）
- 外部调用**可被攻击者控制**：目标地址来自用户输入或不受信账户
- **状态更新滞后性明显**：读取值 → 外部调用 → 更新值，中间有业务逻辑
- **回调入口存在**：外部程序可通过特殊账户、CPI 返回或事件触发重入
- **多步操作序列依赖该状态**：如先读余额、后扣款、再转账，每步都信任之前的余额

**常见误报场景**：
```rust
// ❌ 误报 1：状态无关的重入
pub fn log_event(ctx: Context<Log>) -> Result<()> {
    external_call(&ctx)?;  // 外部调用
    ctx.accounts.event_log.count += 1;  // 只是计数，业务无关
    Ok(())
}

// ❌ 误报 2：调用目标受信且无回调
pub fn swap(ctx: Context<Swap>) -> Result<()> {
    invoke(
        &token::transfer_ix(...),  // 直接调用官方 Token Program
        &[ctx.accounts.token_program.to_account_info()],
    )?;
    ctx.accounts.user.balance -= amount;
    Ok(())  // Token Program 无法回调本程序
}

// ❌ 误报 3：资源已消费，重入无利可图
pub fn close_vault(ctx: Context<CloseVault>) -> Result<()> {
    let balance = ctx.accounts.vault.lamports();
    **ctx.accounts.vault.lamports_mut() = 0;  // 立即清空
    **ctx.accounts.rent_payer.lamports_mut() += balance;
    Ok(())  // 账户已关闭，再调用 close_vault 会因账户不存在而失败
}
```

### 2. 审计过程中的关键问题清单

**第一轮：快速判定是否存在明显重入向量**
- [ ] 是否存在 `invoke*`、`CpiContext` 或外部程序调用？
- [ ] 调用发生**前**还是**后**进行状态更新？（前 = 安全，后 = 风险）
- [ ] 被调用的外部程序是否有可能回调本程序？

**第二轮：确认状态更新的影响范围**
- [ ] 更新的状态是否在**再次调用时会被读取**？
- [ ] 该状态是否影响**权限验证、金额计算、执行逻辑**？
- [ ] 是否存在**依赖于该状态的后续操作**？

**第三轮：评估攻击者控制能力**
- [ ] 外部调用的目标地址来自**用户输入**还是**硬编码**？
- [ ] 攻击者能否**创建恶意程序**完成回调？
- [ ] 重入攻击需要的**前置条件是否现实**（如特定账户权限、时间窗口）？

**第四轮：验证现有防护**
- [ ] 互斥锁是否**在外部调用前就已设置**？
- [ ] 锁的覆盖范围是否包含**所有重入入口**（多个函数调用同一模块）？
- [ ] 锁的释放是否使用 `Result` 或 `Drop` 确保**异常时也能释放**？

### 3. Solana/Rust 生态的重入陷阱

**陷阱 1：CPI 调用后的账户数据失效**
```rust
// ⚠️ 陷阱示例
let user_balance = ctx.accounts.user.balance;  // 缓存余额
invoke_external_cpi(&ctx)?;
// 此时 ctx.accounts.user 的内存值可能已过期（如果外部程序修改了该账户）
ctx.accounts.user.balance -= amount;  // 使用过期数据
```
**审计提示**：外部调用后务必重新加载账户数据，或确保不再信任缓存值。

**陷阱 2：约束检查失效**
```rust
#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut, constraint = user_account.balance >= amount)]
    pub user_account: Account<'info, TokenAccount>,
}
// 约束仅在反序列化时检查一次，外部调用可能改变 balance
```
**审计提示**：关键约束应在操作关键点重新验证，特别是在外部调用前后。

**陷阱 3：递归程序调用**
```rust
// 程序 A 调用程序 B，程序 B 再调用回程序 A
// Rust/Solana 允许这样的链式调用
invoke(
    &ix_call_program_b,
    &[ctx.accounts.program_b],  // Program B 可能再次调用 Program A
)?;
```
**审计提示**：跟踪外部调用链，构建程序间调用图，识别潜在的循环。

### 4. 实战例子：真实漏洞 vs 误报

**真实漏洞（Reentrancy Guard 缺失）**：
```rust
// 🔴 高风险：典型的闪电贷漏洞
pub fn borrow(ctx: Context<Borrow>, amount: u64) -> Result<()> {
    ctx.accounts.pool.borrowed_amount += amount;  // 记录借出额

    // 恶意接收者通过自己的程序回调 borrow，此时 borrowed_amount 已更新
    invoke_transfer_to_user(&ctx, amount)?;

    ctx.accounts.user.debt += amount;  // 更新债务状态
    Ok(())
}
// 攻击：回调中再次调用 borrow，因为 borrowed_amount 已增加，可突破上限
```

**误报（虚假的重入关注）**：
```rust
// 🟢 低风险：状态与外部调用无依赖
pub fn mint_nft(ctx: Context<MintNFT>) -> Result<()> {
    invoke_create_token(&ctx)?;  // 创建新代币

    ctx.accounts.collection.nft_count += 1;  // 仅统计，不影响创建逻辑
    emit!(NftMinted { id: ctx.accounts.token.key() });  // 仅日志
    Ok(())
}
// 即使重入，也只是重复计数，新 invoke 会创建新代币，互相独立
```
