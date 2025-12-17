# Rust CPI Reentrancy（跨程序调用重入）

## Details

**典型代码模式：**

```rust
// 易受攻击的代码模式
pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
    let user_account = &mut ctx.accounts.user_account;
    
    // 1. 检查余额
    require!(user_account.balance >= amount, ErrorCode::InsufficientFunds);
    
    // 2. 执行 CPI 调用（危险点：状态未更新）
    token::transfer(
        CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.vault.to_account_info(),
                to: ctx.accounts.user_token.to_account_info(),
                authority: ctx.accounts.authority.to_account_info(),
            },
        ),
        amount,
    )?;
    
    // 3. 更新状态（太晚！）
    user_account.balance -= amount;
    
    Ok(())
}
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索 `invoke`、`invoke_signed`、`CpiContext::new` 等 CPI 调用关键字
- 追踪 CPI 前后的状态变量修改顺序，重点关注：账户余额、授权标志、计数器等
- 识别 CPI 调用前是否存在"可重复利用"的状态窗口（Checks → CPI → Effects 模式）
- 特别注意回调型 CPI（如 SPL Token 的 `transfer` 调用可能触发接收方的 token hook）

**快速定位保护机制技巧（L2-跳读 + L4-跨模块追踪）：**
- **L2** - 检查是否在 CPI 之前完成状态更新（CEI 模式：Checks-Effects-Interactions）
- **L2** - 查找重入锁标志：`is_locked`、`reentrancy_guard`、`ReentrancyGuard` 等命名
- **L2** - 验证账户约束是否包含 `#[account(mut, constraint = !user.is_locked)]`
- **L4** - 跨账户验证：追踪 `remaining_accounts` 是否可能指向同一程序的其他指令
- **L4** - 检查程序派生地址（PDA）的 seeds 设计是否允许同一指令重复实例化

## Classify

**判定为漏洞：**
- CPI 调用前状态检查通过，但状态更新在 CPI 之后，且被调用程序可回调原程序
- 跨程序调用链路中存在可重入的指令处理器（instruction handler），无互斥保护
- 使用 `remaining_accounts` 或动态账户解析时，未校验账户唯一性

**判定为误报：**
- 仅调用只读程序（如预言机读取），无状态修改权限
- CPI 目标为系统程序（System Program、Token Program 的非回调指令），无重入路径
- 已验证被调用程序为已审计的白名单程序，且确认无回调机制

**判定为代码异味：**
- 虽遵循 CEI 模式，但状态更新与 CPI 逻辑混杂，可读性差
- 存在多层嵌套 CPI 调用，未清晰标注调用链依赖关系

## Low risk

**以下场景可评为低风险：**
- CPI 仅调用不可变（immutable）操作，如查询余额、读取配置
- 被调用程序为去中心化治理锁定的不可升级合约，且已经过严格审计
- 虽存在 CEI 顺序问题，但业务逻辑天然互斥（如账户 nonce 单调递增机制已强制执行）
- 重入攻击的经济收益小于 Solana 交易费用成本（需量化计算）
- 程序仅在测试网部署或实验性功能，未处理实际资产

## 审计专业技巧与误报区分

### 实战区分方法论

**真实漏洞特征（必须同时满足以下条件）：**

1. **可回调路径验证**
   - CPI 目标程序确实可以触发对原程序的反向调用（直接或间接）
   - 反向调用目标是可修改状态的指令处理器，而非只读查询
   - 攻击者控制的账户参与了 CPI 及回调链路的传递

2. **状态窗口存在性**
   - CPI 执行时，被检查的状态值与实际状态之间存在可观测的不一致窗口
   - 该不一致窗口在单个区块内可被多次访问（Solana 单块 CU 限制下检验可行性）

3. **经济激励可行性**
   - 量化计算：重入操作能获得的资产利益 > 所需交易费 + 程序 CU 消耗
   - 检查是否存在 slippage tolerance、price oracle 延迟等可被利用的价格偏差

**常见误报案例与区分要点：**

| 代码特征 | 看似风险 | 实际情况 | 判定标准 |
|---------|--------|--------|---------|
| CPI 前读、CPI 后写 | 有重入风险 | Token Program 不回调用户程序 | 验证 CPI 目标是否为系统程序 |
| 使用 `remaining_accounts` | 灵活度高、难验证 | 若程序显式验证账户签名或所有权，重入无效 | 追踪账户验证逻辑，检查 signer 约束 |
| 涉及 PDA 账户 | 派生地址易冲突 | 若 seeds 包含用户特定信息（如 user pubkey），无法重用 | 分析 PDA seeds 构成元素 |
| 链式 CPI 调用 | 调用链复杂 | 需判断终点是否真的可回调 | 完整追踪 CPI 链的终点程序 |

### 高级审计技巧

**账户约束分析（L3 精细化）：**
```rust
// 案例 1：虚假保护（误报陷阱）
#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut, constraint = user.balance > 0)]  // ⚠️ 仅检查>0，CPI后余额可能<0
    user: Account<'info, UserState>,
}

// 案例 2：真实保护
#[account(mut, constraint = user.balance >= amount @ ErrorCode::Overflow)]
// ✅ 强约束 + 自定义错误，减少逻辑错误

// 案例 3：重入锁保护（黄金标准）
#[account(mut, constraint = !user.is_locked)]
user: Account<'info, UserState>,
// CPI前：user.is_locked = true; CPI后：user.is_locked = false
```

**信号灯识别法（3 秒快速判断）：**
- 搜索文件中 `invoke` / `invoke_signed` 的出现次数
  - 0 次：无 CPI 调用，跳过重入检查
  - 1-2 次：逐一检查
  - 3+ 次：深入分析调用依赖关系，绘制 CPI 图谱

**链上数据追踪（L4 关键）：**
- 若漏洞涉及代币转账，追踪 vault 账户所有权
  - 若 vault 由程序控制（PDA），则程序可拦截重入
  - 若 vault 由用户控制，重入极易发生
- 检查事件日志（emit）是否在 CPI 前后进行了状态同步提示

### 常见陷阱与规避

**陷阱 1：假设 SPL Token Program 安全**
- SPL Token 本身不会主动回调，但若涉及 Token Extensions（2024+ 新特性）中的 hook 机制，则可回调
- 审计策略：检查 mint 账户是否启用了 `TransferHook` 扩展

**陷阱 2：过信任"已审计程序"**
- 即使被调用程序已审计，若其在升级程序（upgradeable_loader），风险链条仍存在
- 规避方法：强制要求被调用程序使用 `#[account(owner = pubkey!("..."), constraint = ...)]` 绑定版本

**陷阱 3：忽视 nonce 或时间戳的并发性**
- Solana 单块内可出现相同 nonce（若 nonce 机制仅基于内存计数器而未持久化）
- 实际防护：验证 nonce 是否写入持久化账户，且在 CPI 前更新

### 误报复核清单（3 步确认法）

1. **能否回调？** 在代码中找到被调用程序对原程序指令的直接或间接调用证据
   - 答：是 → 继续步骤 2
   - 答：否 → **判为误报**

2. **有无保护？** 检查原程序是否存在互斥锁、信号量或状态版本号
   - 答：无 → 继续步骤 3
   - 答：有 → 验证保护有效性，可能为 **低风险** 或 **误报**

3. **有利可图？** 估算重入成本与收益
   - 答：收益 > 成本 → **真实漏洞**
   - 答：否 → **低风险或理论漏洞**
