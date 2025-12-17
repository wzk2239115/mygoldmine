**Rust (e.g., Solana programs)**  
Rust 编写的区块链程序（如 Solana）本身不提供 `selfdestruct` 语义，但若通过关闭账户（close account）并转移剩余 lamports 实现类似效果，则可能引入等效风险。常出现在可关闭状态账户、一次性指令处理器等业务逻辑中，包括但不限于关闭用户状态账户、任务完成后的资源回收等方式：账户关闭作为自毁，程序通过关闭账户（将 lamports 转移并清零数据）模拟 selfdestruct，但未验证关闭条件或目标地址。

## Details

**代码示例特征：**
```rust
// 典型漏洞模式
pub fn close_account(ctx: Context<CloseAccount>) -> Result<()> {
    let account = &mut ctx.accounts.target_account;
    let dest = &mut ctx.accounts.destination;
    
    // 危险：直接转移 lamports 并关闭账户，无权限/状态校验
    **dest.lamports.borrow_mut() += **account.to_account_info().lamports.borrow();
    **account.to_account_info().lamports.borrow_mut() = 0;
    
    Ok(())
}
```

**快速定位核心操作（L2：跳读）：**
- 搜索 `lamports.borrow_mut()` + 赋值 `0` 组合：账户余额清零是关闭信号
- 检索 `realloc(0, false)` 或 `assign(&system_program::ID)`：数据/所有权清除操作
- 关注 `close = ` 约束或自定义 `close_account` 函数：显式关闭逻辑入口
- Anchor 框架查找 `#[account(close = xxx)]` 属性宏

**快速定位保护机制（L3：逐行读）：**
- 关闭前置检查：是否验证 `account.authority == signer`（权限控制）
- 状态门禁：是否要求 `account.status == Closed` 或余额归零前提（防提前关闭）
- 目标地址校验：destination 是否限定为授权地址或原所有者（防资金盗取）
- 重入防护：账户关闭前是否设置 `is_closing` 标志位（防重入利用）
- 依赖检查：是否验证无其他合约/账户持有该账户引用（防悬空指针）

## Classify

**漏洞判定条件（同时满足）：**
- 存在任意调用者可触发的关闭路径（权限缺失或可绕过）
- 目标地址可控或未经授权验证，导致资金流向恶意地址
- 关闭后状态可被重新初始化复用，形成逻辑重入或双花

**误报识别特征：**
- 仅合约所有者/管理员可调用关闭功能，且目标地址硬编码为协议金库
- 关闭前已完成所有业务清算，账户余额理论为零，仅做垃圾回收
- 使用 Anchor `#[account(close = authority)]` 宏且正确约束 `constraint = authority == owner`

**代码异味标记：**
- 关闭逻辑分散在多个指令中，缺乏原子性保证（状态机不完整）
- 注释标注 "临时方案" 或 "TODO: 添加权限检查"
- 关闭后未销毁 PDA seeds 映射，理论上可重建同地址账户

## Low risk

**低风险场景：**
- 账户为纯计算缓存（无资金、无状态依赖），关闭仅释放租金
- 关闭需多签批准（M-of-N）且目标地址为预设白名单
- 账户生命周期与单次交易绑定（临时账户），关闭在交易结束前完成，无跨交易复用
- 使用 Solana 官方 `close_account` 系统调用且 destination 经过 PDA 派生验证
- 关闭触发全局事件日志（可链下监控异常）且有 24 小时时间锁

## 审计专业技巧与经验

### 1. 关键漏洞与误报的区分标准

**真实漏洞的信号灯（High Confidence）：**
- **权限边界失守**：`ctx.accounts.authority` 或权限字段在 `close_account` 指令中完全缺失或仅做虚假检查（如 `require!(authority.is_signer)`，未验证密钥匹配）
- **目标地址可外部输入**：`destination` 账户由调用者直接传入且无硬编码黑名单或白名单约束
- **缺乏预条件校验**：直接 close 而未检查账户状态（如是否已被锁定、是否存在待清算数据）
- **重入场景**：同一账户的数据字段在关闭前后仍被其他指令读取（导致 use-after-close 语义）

**误报的常见触发点（False Positive Red Herrings）：**
- 仅在 governance 或 multi-sig 上下文中调用的关闭函数，权限由外部合约保证
- 小额临时账户（如 bump seed 存储账户），涉及金额 < 0.001 SOL，风险可接受
- Anchor 框架自动生成的 `close = authority` 约束，已由框架层做权限检查
- 关闭后账户地址理论上无法重建（PDA seeds 包含时间戳或随机数）

### 2. 实战审计流程与代码模式识别

**第一层：快速筛选法（5 分钟定性）**
```rust
// Pattern A: 高风险标记 - 直接转移无约束
pub fn close_account(ctx: Context<CloseAccountAny>) -> Result<()> {
    // ⚠️ destination 由调用者指定
    let dest_lamports = ctx.accounts.destination.lamports.borrow_mut();
    *dest_lamports += **ctx.accounts.account.to_account_info().lamports.borrow();
    **ctx.accounts.account.to_account_info().lamports.borrow_mut() = 0;
    Ok(())
}

// Pattern B: 低风险标记 - 明确权限和目标
pub fn close_account(ctx: Context<CloseAccountSafe>) -> Result<()> {
    // ✓ 权限检查
    require_eq!(ctx.accounts.authority.key(), ctx.accounts.vault.authority);
    // ✓ 目标地址硬编码
    let protocol_treasury = Pubkey::from_str("11111...").unwrap();
    require_eq!(ctx.accounts.destination.key(), protocol_treasury);

    // Transfer & close
    Ok(())
}
```

**第二层：依赖图分析（10 分钟追踪调用链）**
- 从 `close_account` 指令向上追踪：谁可以调用？权限检查在何处？
- 向下追踪：关闭后还有哪些指令可访问该账户？是否存在 use-after-close？
- 检查 PDA 派生：若账户地址 = `derive_pda(&[user_key, "state".as_bytes()])`, 同一用户可重建

**第三层：状态机验证（15 分钟逻辑审查）**
```rust
// 健全的状态转移
#[account]
pub struct VaultState {
    authority: Pubkey,
    status: VaultStatus,  // enum { Active, Locked, Closing }
    balance: u64,
}

pub fn close_vault(ctx: Context<CloseVault>) -> Result<()> {
    let vault = &mut ctx.accounts.vault;

    // 必须序列化通过所有前置条件
    require_eq!(vault.authority, ctx.accounts.signer.key());
    require_eq!(vault.status, VaultStatus::Locked);  // 只能在特定状态关闭
    require_eq!(vault.balance, 0);  // 资金已提出

    vault.status = VaultStatus::Closing;  // 原子标记
    // ... transfer & close ...
    Ok(())
}
```

### 3. 常见陷阱与绕过的历史案例

**案例 A：Phantom "多签检查"（2023 年某项目）**
```rust
// ❌ 误认为是安全的代码
pub fn close(ctx: Context<Close>) -> Result<()> {
    // 检查 multisig 账户，但未验证签名者是否为该 multisig 拥有者
    let multisig = &ctx.accounts.multisig;
    require_eq!(multisig.num_signers, 3);  // 虚假检查

    // 实际上调用者可以伪造 multisig 账户
    // ...
}
```
**教训**：权限检查必须验证 `ctx.accounts.signer.key() == multisig.authority`，不能仅检查账户字段值。

**案例 B：竞态窗口（Race Condition）**
```rust
// ❌ 两个指令间的竞态
pub fn withdraw(ctx: Context<Withdraw>) -> Result<()> {
    let vault = &ctx.accounts.vault;
    let amount = vault.balance;  // T1: 读取余额
    // T2: 另一笔交易并发调用 close_account，清空余额
    vault_transfer(amount)?;     // 实际转移 0
    Ok(())
}
```
**教训**：关键账户操作需加 `is_closing` 标志或事务锁，防止并发。

**案例 C：PDA 重建攻击**
```rust
// ❌ PDA seeds 过于简单
let (pda, _) = Pubkey::find_program_derived_address(
    &[b"user_vault"],  // 所有用户共享相同 seeds！
    &program_id
);

// ✓ 正确做法：包含用户标识
let (pda, _) = Pubkey::find_program_derived_address(
    &[b"user_vault", user_key.as_ref()],
    &program_id
);
```

### 4. 审计清单（Audit Checklist）

| 检查项 | 方法 | 高风险信号 |
|--------|------|-----------|
| **权限控制** | 检查 `require_eq!(signer, authority)` | 权限检查缺失或在条件分支中 |
| **目标地址** | 目标地址是否可配置 | `destination` 由调用者指定且无白名单 |
| **原子性** | 关闭前是否标记状态 | 无 `is_closing` 标志，允许并发操作 |
| **数据一致性** | 关闭前是否完成清算 | 余额、债务等仍未结算 |
| **PDA 唯一性** | PDA seeds 是否唯一 | Seeds 中缺少用户/时间/随机数标识 |
| **事件日志** | 是否发出关闭事件 | 无事件日志，无法链下审计 |
| **时间锁** | 关闭是否延迟执行 | 立即关闭，无 cool-down 期 |
| **依赖检查** | 是否验证账户引用计数 | 未检查是否有其他账户依赖 |

### 5. 工具辅助方案

**使用 Anchor 框架最佳实践：**
```rust
#[derive(Accounts)]
pub struct SafeClose<'info> {
    #[account(mut, close = treasury)]
    pub vault: Account<'info, Vault>,
    #[account(mut)]
    pub treasury: UncheckedAccount<'info>,
    pub authority: Signer<'info>,
}
```
- Anchor 的 `close = xxx` 宏自动转移 lamports，减少手工实现的漏洞
- 仍需通过 `#[account(constraint = ...)]` 约束权限和目标地址

**链下验证工具：**
- 使用 `solana-tool` 列出所有关闭账户事件：`grep -r "CloseAccount" *.events`
- 检查交易历史中的异常资金流向（destination 非预期地址）
