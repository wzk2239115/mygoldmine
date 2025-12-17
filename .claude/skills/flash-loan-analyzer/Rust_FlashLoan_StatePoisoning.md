# Rust 闪电贷状态污染漏洞审计指南

**漏洞概述**  
常见于 Solana 等账户模型 DeFi 应用，闪电贷执行期间账户状态被临时修改（余额、债务、份额等），后续逻辑基于被污染状态做出错误决策，导致价格操纵、清算绕过或资金窃取。

## Details

**典型代码示例：**

```rust
pub fn calculate_collateral_ratio(ctx: Context<CheckHealth>) -> Result<()> {
    let pool = &ctx.accounts.pool;
    let user = &ctx.accounts.user;
    
    // ❌ 直接读取账户余额，未校验闪电贷状态
    let collateral_value = pool.token_account.amount * pool.oracle_price;
    let debt_value = user.borrowed_amount * pool.borrow_rate;
    
    require!(
        collateral_value * 100 / debt_value >= pool.min_collateral_ratio,
        ErrorCode::UnderCollateralized
    );
    Ok(())
}

pub fn flash_loan(ctx: Context<FlashLoan>, amount: u64) -> Result<()> {
    // 临时增加余额但未标记状态
    token::transfer(ctx.accounts.vault, ctx.accounts.borrower, amount)?;
    
    // ❌ CPI 调用期间 token_account.amount 被污染
    invoke_signed(&callback_instruction, &[...])?;
    
    // 还款校验
    token::transfer(ctx.accounts.borrower, ctx.accounts.vault, amount)?;
    Ok(())
}
```

**【L3】快速定位核心操作：**  
1. 搜索闪电贷入口函数：`flash_loan`、`borrow_flash`、`flash_borrow`  
2. 追踪资金转移后的 CPI 调用链：`invoke`、`invoke_signed`、`CpiContext::new`  
3. 检查状态变更时机：资金转出后、回调前是否设置 `is_flash_loaning` 标志  
4. 关注跨指令状态读取：其他指令读取余额/TVL 时是否检查闪电贷状态

**【L4】快速定位保护机制：**  
1. **状态标记检查**（L2 跳读）：搜索 `flash_loan_in_progress`、`is_locked`、`reentrancy_guard` 布尔字段  
2. **快照机制**（L3 逐行）：在转账前是否保存 `pre_balance`，回调后对比 `post_balance >= pre_balance + fee`  
3. **同 Slot 检查**（L4 跨模块）：使用 `Clock::get()?.slot` 记录闪电贷发起 Slot，其他指令拒绝同 Slot 操作  
4. **账户冻结**（L3 逐行）：检查 `AccountInfo::is_writable` 或自定义 `freeze` 标志在 CPI 期间是否禁止状态修改  
5. **Oracle 防护**（L2 跳读）：价格来源是否使用 TWAP 或多来源聚合，避免单点瞬时价格

## Classify

**漏洞判定标准：**  
- **确认漏洞**：闪电贷回调期间，存在可被外部调用的指令依赖污染状态（余额、价格、份额）做关键决策（清算、铸造、提现），且无有效隔离机制  
- **误报情形**：状态读取仅用于日志记录或前端展示；受污染的计算结果被后续正确校验覆盖；CPI 调用仅限白名单合约且已审计  
- **代码异味**：闪电贷存在但所有依赖状态的操作已通过标志位/快照保护，但代码注释不足，增加后续维护者误判风险；保护逻辑分散在多个模块，可读性差

**研判流程：**  
1. 确认状态修改的原子性边界（单指令内 vs 跨指令）  
2. 枚举所有可能在闪电贷激活期间被调用的公开指令  
3. 逐个分析这些指令对污染状态的依赖程度（直接读取 vs 间接计算）  
4. 验证保护机制的时序正确性（标志位先置后清，快照在修改前记录）

## Low risk

**以下场景可评为低风险：**  
- **经济不可行**：利用成本（Gas、流动性要求）超过可窃取价值，且无连环攻击放大路径  
- **有限影响范围**：状态污染仅影响单一用户自身账户，不影响协议全局状态或其他用户  
- **冗余保护**：虽存在状态污染窗口，但关键操作（如提款）额外依赖链下签名、多签或时间锁  
- **暂态不一致**：污染仅导致临时视图错误（如前端显示 TVL 异常），不影响实际价值转移或权限验证  
- **测试环境特有**：漏洞仅存在于 devnet/testnet 的调试模式配置中，主网已强制启用保护机制

**降级条件：**
攻击需要满足多个低概率前提（特定 Oracle 延迟 + 高波动时段 + 大额流动性），且协议已部署紧急暂停机制，响应时间低于攻击窗口期。

## Audit Professional Tips

### 真实漏洞特征识别

**1. 状态污染的逻辑链路分析**
- 查看转账后、回调前是否存在**未保护的状态读取操作**（对比：有保护的情况下状态读取被 guard 或快照机制阻止）
- 追踪污染数据的**传播路径**：`token::transfer()` → `invoke_signed()` → CPI 内部指令读取 `TokenAccount.amount` 或 Pool.tvl
- 确认污染数据是否被用于**关键决策**（提现权限、清算触发、价格计算），还是仅作为日志或中间缓存

**示例对比（真实 vs 误报）**
```rust
// ❌ 真实漏洞：status 在闪电贷期间被污染，直接影响清算逻辑
pub fn liquidate(ctx: Context<Liquidate>) -> Result<()> {
    let user_collateral = ctx.accounts.pool.get_total_balance(); // 含闪电贷余额
    if user_collateral < liquidation_threshold {
        // 执行清算 - 基于污染状态
    }
}

// ✅ 误报：status 被污染但有有效防护
pub fn liquidate(ctx: Context<Liquidate>) -> Result<()> {
    require!(!ctx.accounts.pool.is_flash_loaning, ErrorCode::FlashLoanActive);
    let user_collateral = ctx.accounts.pool.get_total_balance(); // 安全
}

// ✅ 误报：status 被污染但仅用于非关键操作
pub fn get_pool_info(ctx: Context<PoolInfo>) -> Result<PoolData> {
    Ok(PoolData {
        total_supply: ctx.accounts.pool.total_supply, // 污染但仅用于事件记录
        last_update: Clock::get()?.unix_timestamp,
    })
}
```

**2. 防护机制的完整性校验**
- **时间窗口检查**：标志位设置（`is_flash_loaning = true`）与清除（`is_flash_loaning = false`）是否在同一指令内且原子执行？
  - 风险：多条指令间设置/清除，中间被其他交易插入
- **账户隔离检查**：CPI 调用的目标账户是否与读取账户完全独立？
  - 风险：污染账户直接作为 CPI 的 `writable` 账户输入
- **快照完整性**：保存快照时是否包含所有状态变量（不仅仅是余额，还需 oracle_price、user_shares 等）？

**3. Oracle 依赖分析（高风险点）**
- 搜索 `oracle_price`、`get_price()` 等调用，检查是否存在：
  ```rust
  // ❌ 高风险：单次 Oracle 查询，易被闪电贷价格操纵
  let price = oracle.get_latest_price(token)?;

  // ✅ 较安全：TWAP 或延迟 Oracle
  let price = oracle.get_twap_price(token, 30)?; // 30s 时间加权
  ```
- 验证 Oracle 更新延迟是否长于闪电贷执行时间（Solana 通常 Slot 时间 400ms）

### 误报常见陷阱

**1. "状态污染但被覆盖"陷阱**
```rust
// 常被误判为漏洞的场景
let dirty_balance = ctx.accounts.token.amount; // 包含闪电贷余额
let correct_balance = ctx.accounts.user_state.balance; // 另一个状态存储真实余额

// 关键决策基于 correct_balance，dirty_balance 仅作为本地变量，最后丢弃
if correct_balance > threshold {
    process_withdrawal();
}
```
**审计建议**：追踪变量生命周期，确认污染数据是否被**最终使用**还是**路径上遗弃**。

**2. "CPI 调用但目标已审计"陷阱**
```rust
// invoke_signed 虽然存在，但目标是已知安全的 Token 程序
token::transfer(ctx.accounts.vault, ctx.accounts.user, amount)?;
// Token 程序不会反向调用我们的指令，无法利用污染状态
```
**审计建议**：不能仅因为有 CPI 就判定为漏洞，需验证 CPI 目标是否存在**反向调用风险**。

**3. "同 Slot 限制下的误报"**
```rust
// Solana 特性：Flash Loan 和其他操作若在同一 Slot 无法实现
// 因为指令执行是单线程串行的
pub fn flash_loan(...) -> Result<()> {
    let current_slot = Clock::get()?.slot;
    // ... 转账
    invoke_signed(&user_callback, ...)?; // 用户回调在同 Slot 执行
    // 即使有漏洞，攻击者无法在同 Slot 另起一个交易利用污染状态
}
```
**审计建议**：理解区块链的执行模型，Solana 单 Slot 串行特性天然防护某些闪电贷攻击。

### 实战审计 Checklist

| 检查项 | 操作 | 风险等级 |
|--------|------|--------|
| 闪电贷转账后是否立即设置标志位 | `grep -n "is_flash_loaning\|flash_loan_in_progress"` 并查看位置 | L2 |
| 所有读取资金池状态的指令是否检查标志位 | 静态分析所有公开指令的第一行 | L2 |
| 快照机制是否包含全部状态（余额、债务、份额） | 逐行对比转账前后的快照覆盖范围 | L3 |
| Oracle 来源是否单点？是否存在延迟 | 查看 Oracle 初始化和价格查询逻辑 | L2 |
| CPI 目标是否存在回调风险 | 追踪 `invoke` 的目标程序 ID | L3 |
| 是否存在跨交易的状态污染窗口 | 确认保护逻辑是否在单指令内原子执行 | L1 |
| 清算、提现等关键操作的权限验证是否在污染数据之前 | 查看 `require!` 语句的顺序 | L2 |

### 真实案例对标

**Solend 闪电贷清算绕过（2022）**
- **特征**：清算函数读取污染的抵押品余额，而非存储的债务记录
- **根因**：缺少 `is_flash_loaning` 标志位检查
- **检测方式**：在清算函数入口处搜索 guard 防护，发现缺失即可锁定漏洞

**本地变量污染但无影响（常见误报）**
- **特征**：闪电贷污染的余额被存入局部变量，但后续关键决策使用链上存储的正确值
- **根因**：状态污染与使用不在同一代码路径
- **检测方式**：追踪污染变量 v 的**所有使用点**，若均为日志/事件，则判定为误报
