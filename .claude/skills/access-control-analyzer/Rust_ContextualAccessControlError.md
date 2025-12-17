# 上下文权限错误（Rust - Solana/Sui）

**漏洞描述：** 访问控制逻辑未正确使用或验证 Context 结构中的约束条件，导致权限检查可被绕过

## Details

**对应代码示例：**
```rust
// lib.rs - 风险示例 (Anchor框架)
#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    #[account(mut)]
    pub config: Account<'info, Config>,
    pub authority: Signer<'info>,
    // 缺少约束：未验证 authority 是否为 config.admin
}

pub fn update_config(ctx: Context<UpdateConfig>, new_value: u64) -> Result<()> {
    let config = &mut ctx.accounts.config;
    // 仅检查是否为 Signer，未校验身份匹配
    config.value = new_value;
    Ok(())
}

// 正确示例应包含约束：
// #[account(mut, has_one = authority @ ErrorCode::Unauthorized)]
```

**快速定位核心操作的技巧（L2:跳读）：**  
- 扫描 `#[derive(Accounts)]` 结构体，重点关注包含 `#[account(mut)]` 的状态账户修改操作
- 检查涉及敏感操作的指令处理函数：`initialize`、`update_authority`、`withdraw`、`mint`、`close_account`
- 定位 `Signer<'info>` 字段，确认其是否仅用于签名验证而未关联业务权限
- 追踪跨 CPI 调用路径：`invoke`、`invoke_signed` 中传递的账户列表是否包含未验证的 signer

**快速定位保护机制的技巧（L3:逐行读）：**  
- 在账户约束中查找权限校验关键字：`has_one`、`constraint`、`seeds` + `bump`、`@` 错误码标注
- 检查 Context 结构体是否使用 `#[account(address = EXPECTED_PUBKEY)]` 限制特权账户地址
- 确认函数内部是否手动执行身份比对：`require!(ctx.accounts.authority.key() == ctx.accounts.config.admin, ErrorCode::Unauthorized)`
- 搜索 `signer` 约束使用情况：仅有 `Signer<'info>` 而无额外约束时为高风险信号
- 对于 Native Rust 程序，检查 `AccountInfo::is_signer` 调用后是否有身份匹配逻辑

## Classify

**漏洞判定：**  
- Context 结构体中 Signer 字段与被操作账户间无约束关联（缺少 `has_one`、`constraint` 或手动 `require!` 验证）
- 敏感操作（转账、权限变更、资源销毁）依赖 Context 参数传递，但账户约束声明不完整
- 跨程序调用时，传入的 signer 权限未在目标程序 Context 中重新验证

**误报判定：**  
- 操作仅修改调用者自身拥有的账户（如 `#[account(init, payer = authority, seeds = [authority.key().as_ref()])]`）
- Context 约束已正确使用 `has_one` 或等价的手动校验逻辑，且测试覆盖未授权访问场景
- 指令为只读查询操作，无状态修改或资产转移

**代码异味判定：**  
- Context 约束部分缺失，但函数内部包含补充校验（建议统一至 Context 声明）
- 使用过于宽松的约束（如 `constraint = authority.key() != Pubkey::default()`），技术上满足但语义不明确
- 权限检查分散在多个 helper 函数中，跨文件追踪困难

## Low risk

- **自主账户操作：** 所有修改操作仅限于 signer 自身初始化或拥有的 PDA 账户，且 seeds 派生中包含 signer 公钥
- **只读上下文：** Context 结构体仅用于数据查询，不包含 `mut` 修饰的账户，无状态变更可能
- **协议级沙箱隔离：** 程序运行在受限环境（如 Solana 的账户租金机制），即使权限检查缺失，攻击者无法窃取已存入的资产
- **双重验证机制：** 除 Context 约束外，业务逻辑额外在链下签名、时间锁、多签钱包中实施二次授权

## 审计专业技巧

### 1. 真实漏洞的判断指标

**关键特征识别（必须同时满足以下至少2项）：**
- **权限链缺失**：Signer 账户与被操纵关键数据间无直接引用关系。例如，`authority` 签名了交易，但 `config` 账户的存储数据未声明与 `authority` 的绑定关系
- **可任意指定账户**：调用方可在指令中自由传入任意账户地址，程序未验证该账户身份。典型表现为 `mint: Account<'info, Mint>` 未带 `address =` 约束
- **状态被动式修改**：程序仅检查签名合法性，未校验操作执行者是否有权修改被操纵账户的内容。如 `withdraw` 函数允许任何签名者提取任意 vault 内资金

**漏洞评估检查清单：**
```
1. 被操作账户是否在 PDA seeds 中包含权限账户标识？
   ✗ 无此标识 → 高风险
   ✓ seeds = [b"vault", authority.key().as_ref()] → 低风险

2. Context 约束是否绑定权限账户？
   ✗ pub admin: Signer<'info> （无约束）
   ✓ #[account(has_one = admin)] 或 #[account(mut, has_one = admin)]

3. 多签名场景中，是否所有签名者均已验证？
   ✗ 仅检查 signer 总数
   ✓ 逐个验证每个 signer 身份或使用多签钱包地址绑定

4. CPI 调用是否转发了未验证的签名者权限？
   ✗ invoke(&ix, &[signer_account.clone(), untrusted_account.clone()])
   ✓ 仅转发验证过的账户或增加额外权限验证
```

### 2. 常见误报陷阱及排除法

**误报案例 A：PDA 自动隐含权限**
```rust
// 审计时容易误判为漏洞：
#[account(init, payer = authority, space = 8 + 32)]
pub user_state: Account<'info, UserState>,

pub authority: Signer<'info>,  // 无约束看起来可疑

// 但实际上 seeds 中包含了隐式绑定：
#[account(init, payer = authority, seeds = [b"user", authority.key().as_ref()], bump)]
```
**排除技巧**：在 `initialize` 或 `new` 函数上方查找是否有 seeds 派生，若存在 `authority.key().as_ref()` 则权限已隐式绑定。

**误报案例 B：超级管理员设计模式**
```rust
#[derive(Accounts)]
pub struct AdminOperation<'info> {
    #[account(address = PROGRAM_ADMIN_PUBKEY @ ErrorCode::Unauthorized)]
    pub admin: Signer<'info>,
    // 直接限制为硬编码地址
}
```
**排除技巧**：若 `#[account(address = ...)]` 指向全局常量或多签钱包，则集中权限的设计虽然不优雅，但权限检查完整。搜索该常量定义位置确认是否真的为固定地址。

**误报案例 C：嵌套授权验证**
```rust
pub fn protected_op(ctx: Context<ProtectedOp>, data: Vec<u8>) -> Result<()> {
    // Context 看起来缺少约束，但函数内部验证
    let expected_admin = ctx.accounts.config.admin;
    require!(ctx.accounts.caller.key() == expected_admin, ErrorCode::Unauthorized);
    // ... 执行操作
}
```
**排除技巧**：逐行扫描函数体前 5-10 行，若发现 `require!` 或 `assert_eq!` 进行了身份匹配检查，则不是漏洞，但应标记为"代码异味"（建议移至 Context）。

### 3. 真实与误报的分界线案例

**真实漏洞案例（Solana lending 协议）：**
```rust
#[derive(Accounts)]
pub struct Liquidate<'info> {
    pub obligation: Account<'info, Obligation>,
    pub reserve: Account<'info, Reserve>,
    pub liquidator: Signer<'info>,  // 任何签名者都可执行
}

pub fn liquidate(ctx: Context<Liquidate>, amount: u64) -> Result<()> {
    ctx.accounts.obligation.borrow_mut().status = ObligationStatus::Liquidated;
    // 没有检查 liquidator 是否有权发起清算
    Ok(())
}
```
**确认方式**：构造交易用任意钱包签名，传入受害者 obligation，成功执行 → **确认漏洞**

**非漏洞对比（正确设计）：**
```rust
#[derive(Accounts)]
pub struct Liquidate<'info> {
    #[account(mut, has_one = liquidator_authority)]  // 绑定权限
    pub obligation: Account<'info, Obligation>,
    pub reserve: Account<'info, Reserve>,
    #[account(address = ALLOWED_LIQUIDATOR_PROGRAM)]  // 或限制为特定地址
    pub liquidator: Signer<'info>,
}
```

### 4. 审计工作流与优先级

**第一阶段：快速过滤（5分钟/函数）**
1. 扫描函数签名中的 Signer 账户数量
2. 查看 Context 约束行数（<5 行通常为高风险信号）
3. 标记所有 `#[account(mut)]` 和 `#[account(init)]` 的账户

**第二阶段：深度分析（15分钟/漏洞候选）**
1. 跟踪 PDA seeds 的完整派生，确认是否包含权限标识
2. 搜索同名函数的不同版本（如 `withdraw` vs `admin_withdraw`），比较权限检查差异
3. 审计 CPI 调用的账户列表，手工模拟恶意交易

**第三阶段：确认与分类**
1. 编写 PoC 测试用例验证理论漏洞
2. 若不能构造成功的非授权访问交易，归类为误报
3. 文档记录漏洞根因、修复建议、测试方法

### 5. 常见业务场景中的权限模式

| 场景 | 正确模式 | 风险模式 | 审计重点 |
|------|--------|--------|--------|
| **单用户状态** | seeds 包含 user 地址 | 任意地址初始化 | PDA 派生规则 |
| **管理员操作** | `#[account(address = ADMIN)]` 或 has_one | 仅 Signer 无额外约束 | 常量定义、多签验证 |
| **资金转账** | 接收地址由权限者指定 | 接收地址作为参数 | 参数源头验证 |
| **权限委托** | 显式授权、有过期时间 | 隐式全局权限 | 授权数据结构、有效期检查 |
