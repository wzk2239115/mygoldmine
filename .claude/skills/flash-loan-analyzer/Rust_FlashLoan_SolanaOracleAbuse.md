# Rust_FlashLoan_SolanaOracleAbuse

**漏洞类型：** Solana 闪电贷预言机操纵  
**语言：** Rust  
**场景：** 基于 Solana 账户模型的 DeFi 应用，利用闪电贷操纵 DEX 储备量影响预言机价格

## Details

**代码示例特征：**
```rust
// 典型漏洞模式
pub fn process_swap(ctx: Context<Swap>, amount: u64) -> Result<()> {
    // 1. 执行大额交换操作
    token::transfer(ctx.accounts.into(), amount)?;
    
    // 2. 使用储备量计算价格 - 漏洞点
    let reserve_a = ctx.accounts.pool.reserve_a;
    let reserve_b = ctx.accounts.pool.reserve_b;
    let price = reserve_b.checked_div(reserve_a).unwrap();
    
    // 3. 将价格写入预言机账户或用于后续计算
    ctx.accounts.oracle.update_price(price)?;
}
```

**快速定位核心操作技巧（L3：逐行读）：**
- 扫描 `token::transfer` / `invoke` / `invoke_signed` 后紧跟价格计算逻辑
- 查找 `account.amount` / `reserve` 字段直接参与除法/比例运算
- 追踪 `get_price()` / `calculate_rate()` 函数内是否读取可被单笔交易大幅影响的链上状态
- 检查 CPI 调用链：`Program::invoke()` → DEX 操作 → 同一交易内的价格读取

**快速定位保护机制技巧（L2：跳读）：**
- 搜索 `Clock::get()` / `Slot` / `timestamp` 检查是否存在 TWAP（时间加权平均价格）
- 定位 `require!()` / `assert!()` 检查价格波动限制（如 `price_change < MAX_SLIPPAGE`）
- 查找 `previous_price` / `last_update` 字段验证多区块价格平滑机制
- 检查 `Signer` / `has_one` 约束确认预言机更新权限隔离

## Classify

**漏洞研判：**
- 价格计算直接依赖单笔交易可改变的储备量且无时间维度平滑 → **高危漏洞**
- 同一指令内完成：借款 → 操纵储备 → 触发价格读取 → 还款的完整闭环 → **可利用漏洞**

**误报识别：**
- 价格源自链下签名数据（Pyth/Switchboard）且验证签名有效性 → **误报**
- 储备量仅用于手续费计算而非清算/借贷核心逻辑 → **低影响误报**
- 存在多预言机中位数聚合（median of 3+ sources）且包含延迟源 → **误报**

**代码异味：**
- 使用即时储备量但有滑点保护且交易量上限严格 → **异味但风险可控**
- 预言机更新有权限控制但缺少价格合理性校验 → **架构异味**

## Low risk

**低风险场景：**
- **流动性门槛：** 池子规模 > 1000万美元且单笔交易上限 < 池子的 2%，攻击成本超过预期收益
- **非关键路径：** 价格仅用于前端展示或统计，不参与资产清算/铸造/分配等核心金融逻辑
- **延迟生效机制：** 价格更新后需等待 N 个 slot 才能被其他合约读取（时间锁保护）
- **沙盒环境：** 测试网或隔离的 AMM 池，与主流动性池无价格联动
- **冗余验证：** 虽存在即时价格读取但后续有链下服务二次校验并可撤销异常交易（中心化兜底）

## Audit Tips（审计专业技巧）

### 1. 真实漏洞迹象识别

**关键观察点（需同时满足3项以上判定为真实漏洞）：**

1. **储备量直接参与核心业务决策**
   ```rust
   // 真实漏洞特征：储备量影响用户资产安全
   let collateral_ratio = user_deposit / reserve_a;  // 用于清算判定
   if collateral_ratio < MIN_RATIO {
       liquidate_user()?;  // 立即执行清算
   }
   ```
   - 对比误报：`reserve_a` 仅用于统计或展示，不影响清算逻辑

2. **完整的原子操作链闭环**
   - 在单笔交易内：闪电贷借入 → 操纵 DEX 储备 → 价格计算 → 利用价格差异 → 还款
   - 验证方式：追踪指令签名序列，检查是否存在 CPI 回调防护或 ProgramGuard 检验

3. **缺少防护但有攻击门槛**
   - 无 TWAP 但有 MAX_PRICE_IMPACT 检查（可被绕过吗？）
   - 无权限控制但操作数额受限（上限是多少？与池子大小的比例？）

### 2. 常见误报模式与区分技巧

**模式A：链下数据与链上储备量混淆**
```rust
// 误报案例 - 价格源自 Pyth/Switchboard，不是 DEX 储备量
let price = oracle::get_price(Pyth)?;  // 链下签名，无法通过 DEX 操纵
let amount_out = amount_in * price / 10u64.pow(6);
```
- **真实漏洞**：直接读 `ctx.accounts.dex_pool.reserve` 进行计算
- **判别方法**：搜索账户签名验证 (`verify_signer()`) 和数据源标识

**模式B：保护机制识别不足**
```rust
// 误报案例 - 虽无 TWAP 但有滑点检查
let new_price = reserve_b / reserve_a;
let price_change = (new_price - last_price).abs() / last_price;
require!(price_change < 0.05, "Slippage limit exceeded");  // 5% 滑点限制
```
- **判别方法**：计算攻击成本 = 必须移动储备量 × 交易对手方损失率
  - 若攻击成本 > 预期收益，则风险可控
  - 例：要突破 5% 滑点需操纵 20% 的池子流动性，成本可能高于收益

**模式C：权限隔离与延迟机制**
```rust
// 误报案例 - 预言机更新有权限隔离
#[account(signer)]
oracle_admin: Signer,  // 仅管理员可更新

require!(ctx.accounts.oracle_admin.key == ADMIN_PUBKEY);
ctx.accounts.oracle.update(new_price)?;
```
- **真实漏洞**：任何账户可调用或权限检查缺陷（如 `has_one` 拼写错误）

### 3. 审计检查清单

**第一阶段：快速扫描（5分钟）**
- [ ] 搜索 `get_price()` / `calculate_rate()` 函数定义位置
- [ ] 确认价格数据源：是否读取自 `ctx.accounts.account.data` 或调用 `invoke()`
- [ ] 查找 `require!()` / `assert!()` 中的数值限制（价格波动、交易量上限等）

**第二阶段：深度追踪（15分钟）**
- [ ] 绘制数据流图：用户输入 → 价格读取 → 业务决策（清算/铸造/分配）
- [ ] 验证原子性：CPI 调用链中是否存在中断点或回滚机制
- [ ] 追踪账户约束：`has_one` / `signer` / `owner` 是否正确应用

**第三阶段：风险评估（10分钟）**
- [ ] 计算攻击成本：若无闪电贷，攻击者需自有资金多少？
- [ ] 评估收益：通过价格操纵能获得多少额外价值？
- [ ] 比较：若 `成本 > 收益 × 10`，则实际风险较低

### 4. 真实漏洞案例对照

**案例：SolendOracleManipulation（已补丁）**
- 特征：直接使用 DEX 储备量计算清算价格，无 TWAP 无权限控制
- 攻击路径：闪电贷 → 操纵 Orca DEX → 降低 SOL 价格 → 触发清算
- 修复：采用 Pyth 预言机 + 多源聚合 + 延迟生效

**案例：MarinadeMEV（低风险）**
- 特征：使用储备量计算 APY 显示，但实际清算由 Pyth 控制
- 为何低风险：攻击者无法改变清算条件，只能操纵前端显示

### 5. 报告撰写规范

**漏洞报告模板（包含区分说明）：**
```
标题：[价格操纵 / 误报确认]

数据流：[描述完整的攻击链条]
关键环节：[列出每一步的检查点]

风险判定理由：
1. 数据源验证：[ ]无法通过 DEX 操纵 / [X]可被 DEX 操纵
2. 防护机制：[缺少TWAP]  [缺少权限控制]  [缺少滑点检查]
3. 攻击成本：>$100K / <$10K / 无经济可行性
4. 利用难度：原子交易内完成 / 需多步操作 / 需自有资金垫底

结论：真实高危漏洞 / 低风险但可优化 / 误报
```

### 6. 常见漏洞指标速查表

| 指标 | 真实漏洞 | 可能误报 | 确定误报 |
|------|--------|--------|--------|
| 数据源 | DEX 储备量 | 储备量 + 滑点检查 | Pyth/Switchboard |
| 时间维度 | 无 / 仅 Slot | 有滑点但无 TWAP | 有 TWAP + 延迟 |
| 权限控制 | 无或缺陷 | 有但检查可绕过 | 严格隔离 + 多签 |
| 流动性规模 | <500万美金 | 500万-1000万 | >1000万 + 上限 |
| 执行原子性 | 单笔交易内 | 多步依赖 | 需外部调用间隔 |
