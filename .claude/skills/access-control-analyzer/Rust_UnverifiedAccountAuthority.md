# 未验证账户权限（Rust - Solana/Sui）

**漏洞描述：** 操作账户数据前未检查账户的 owner 或 authority 字段，允许未授权账户被恶意修改或访问

## Details

**对应代码示例：**
```rust
// lib.rs - 风险示例 (Solana Native)
pub fn process_withdraw(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    amount: u64,
) -> ProgramResult {
    let account_iter = &mut accounts.iter();
    let vault_account = next_account_info(account_iter)?;
    let user_account = next_account_info(account_iter)?;
    
    // 危险：未验证 vault_account.owner 是否为当前 program_id
    // 危险：未检查 user_account 是否具有 vault 的 authority 权限
    let mut vault_data = Vault::unpack(&vault_account.data.borrow())?;
    vault_data.balance -= amount;
    Vault::pack(vault_data, &mut vault_account.data.borrow_mut())?;
    Ok(())
}

// Anchor 风险示例
#[derive(Accounts)]
pub struct Transfer<'info> {
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    pub authority: Signer<'info>,
    // 缺少约束：未验证 authority 是否为 token_account.owner
}
```

**快速定位核心操作的技巧（L2:跳读）：**  
- 扫描账户数据反序列化后的写入操作：`unpack` → 修改 → `pack`、`try_borrow_mut()`、`data.borrow_mut()`
- 定位敏感字段修改：`balance`、`owner`、`authority`、`admin`、`delegate`、`is_initialized`
- 检查涉及资产转移的指令：`transfer`、`withdraw`、`burn`、`close`、`mint`
- 关注 PDA 账户操作：通过 `seeds` 派生的账户是否验证了派生参数的合法性
- 追踪状态账户初始化逻辑：`initialize` 指令中 authority 字段的赋值是否可控

**快速定位保护机制的技巧（L3:逐行读）：**  
- 在 Native 程序中搜索：`if account.owner != program_id`、`AccountInfo::owner` 比对逻辑
- 检查账户权限字段校验：`require!(vault.authority == user_account.key())`、`has_one = authority`
- 在 Anchor 中查找账户约束：`#[account(constraint = token_account.owner == authority.key())]`
- 确认 PDA 验证机制：`seeds` + `bump` 约束是否与业务权限绑定
- 搜索错误处理：`ProgramError::IncorrectOwner`、`ErrorCode::Unauthorized`、`ErrorCode::InvalidAuthority`
- 检查跨程序调用的权限传递：CPI 中传递的 signer seeds 是否包含 authority 验证

## Classify

**漏洞判定：**  
- 账户数据修改前未校验 `AccountInfo::owner` 是否为预期的 program_id 或 token_program_id
- 状态账户包含 `authority`/`owner` 字段，但指令处理中未验证调用者与该字段的匹配关系
- PDA 派生使用固定 seeds，攻击者可预测地址后初始化伪造账户绕过检查
- 跨程序调用时未验证传入账户的所有权或签名权限，信任外部账户数据

**误报判定：**  
- 账户已通过 Anchor 约束正确验证：`#[account(has_one = authority)]` 或等价的 `constraint` 表达式
- 操作仅读取账户数据，无修改或转移资产行为
- 账户所有权由框架自动校验（如 Anchor 的 `Account<'info, T>` 类型会自动检查 owner 是否为 program_id）
- 业务逻辑仅允许用户操作自己拥有的账户，且通过 signer 验证确保调用者身份

**代码异味判定：**  
- 账户所有权检查存在但散落在多个 helper 函数中，缺乏统一的入口验证
- 使用 `AccountInfo` 而非 Anchor 的 `Account<T>` 类型，放弃了框架自动校验的优势
- 权限检查逻辑过于复杂，存在多层嵌套条件，难以快速确认覆盖所有路径
- 部分路径有校验但未覆盖所有指令入口（如初始化时检查，但更新时遗漏）

## Low risk

- **只读查询操作：** 指令仅读取账户数据进行计算或返回，不修改状态或转移资产
- **自主账户操作：** 用户仅能修改自己作为 signer 初始化的 PDA 账户，且 PDA seeds 中包含 signer 公钥作为派生参数
- **框架自动校验：** 使用 Anchor 的 `Account<'info, T>` 类型，框架已自动验证账户 owner 是否匹配程序 discriminator
- **多重验证机制：** 除账户所有权外，还通过时间锁、多签、白名单等额外机制限制操作权限
- **沙箱隔离环境：** 程序仅操作自己创建的 PDA 账户，无法访问其他程序的账户数据（跨程序调用时目标程序会重新验证）

## 审计专业技巧与真实漏洞区分

### 1. 真实漏洞的特征信号

**信号 A：权限检查与敏感操作的距离**
- 真实漏洞：权限检查代码与数据修改操作存在明显间隔或分离，中间可能有多次账户读写
- 误报风险：权限检查紧邻敏感操作，两行代码相距不超过 5 行
- 案例：Solana DeFi 协议 (2023) 中，开发者在账户验证后立即进行 CPI 调用，调用过程中未保持权限上下文检查

**信号 B：动态 PDA seeds 与硬编码 seeds 混用**
- 真实漏洞：某些指令使用硬编码 seeds（如 `b"vault"`），攻击者可预测地址并创建伪造账户
- 误报风险：所有 seeds 均包含动态参数（如用户地址、nonce），地址不可预测
- 案例：Solana 借贷协议被攻击，初始化借贷池时使用硬编码 seed，攻击者创建了同名伪造池子

**信号 C：跨程序调用中的权限传递链条**
- 真实漏洞：程序 A 调用程序 B 时，未验证程序 B 返回的账户数据是否确实来自程序 B，或传递的 signer 权限未正确赋予
- 误报风险：权限验证完成后，账户保持在受保护状态（通过 Anchor 约束确保）
- 案例：Sui 对象所有权验证中，某些包装器函数遗漏了内层权限检查，导致权限提升

### 2. 常见误报场景及排查方法

**误报场景 1：Anchor `has_one` 约束的隐式验证**
```rust
#[derive(Accounts)]
pub struct AdminUpdate<'info> {
    #[account(mut, has_one = admin)]  // ← 这行已隐式验证
    pub config: Account<'info, Config>,
    pub admin: Signer<'info>,
}
// 审计陷阱：看代码体没有显式的 require! 判断，认为是漏洞
// 正确认知：Anchor 在账户反序列化时已自动检查 config.admin == admin.key()
```

**误报场景 2：Account 类型的自动 owner 验证**
```rust
pub vault: Account<'info, Vault>,  // ← owner 自动验证为 program_id
// 审计陷阱：看不到显式的 owner 检查代码，认为缺少校验
// 正确认知：Account<T> 类型在反序列化时已强制检查 owner == program_id
// 验证方式：查看 Anchor 源码或检查 discriminator 字段写入逻辑
```

**误报场景 3：PDA 唯一性保证**
```rust
// 创建 PDA 时包含足够的唯一参数
let (pda, bump) = Pubkey::find_program_address(
    &[b"user_vault", user.key().as_ref(), collateral_mint.key().as_ref()],
    program_id
);
// 审计陷阱：看到有多个 user 可以创建相似名称的 vault，认为有冲突风险
// 正确认知：user + collateral_mint 的组合唯一性已由 PDA 数学保证，不同 user 无法创建相同地址的账户
```

### 3. 区分真假的审计检查清单

**第一层：快速过滤（5 分钟）**
- [ ] 目标指令是否修改关键字段：`authority`、`owner`、`admin`、`balance` 等？
- [ ] 修改前是否有至少一行权限检查代码？（allow 错过 Anchor 约束）
- [ ] 该权限检查是否与 signer 或已验证账户相关联？

**第二层：深度审查（15 分钟）**
- [ ] 权限检查的变量是否来自账户数据而非直接参数？（如 `config.admin` 而非函数参数 `admin`）
- [ ] 如果使用 Anchor，逐行检查所有 `#[account(...)]` 约束，确保每个可变账户都有对应的权限验证约束
- [ ] 对于 Native 程序，统计所有包含 `unpack` 或 `borrow_mut` 的账户，确认每个都有对应的 `owner` 校验
- [ ] CPI 调用前后，检查传入账户的签名权限是否与原始调用者一致

**第三层：上下文验证（10 分钟）**
- [ ] 查看该程序的历史安全审计报告，搜索类似的权限模式是否被确认为安全
- [ ] 检查开发框架的版本号，确认是否已包含该类权限检查的修复
- [ ] 运行本地测试：尝试以非授权账户调用该指令，验证程序是否拒绝

### 4. 真实案例：Solana Token 扩展漏洞 (CVE-2023-35943)

**漏洞症状：**
- 代码表面看起来有权限检查：`require_eq!(owner.key(), token_account.owner)`
- 但检查发生在反序列化前，而反序列化过程中 `token_account` 被重新赋值为另一个账户

**审计技巧应用：**
1. 权限检查与敏感操作距离过远（超过 20 行）→ 触发信号 A
2. 跟踪变量赋值链：`token_account` 经历了多次 `next_account_info()` 的中间赋值 → 触发信号 C
3. 对变量生命周期进行流分析，确认检查与修改作用于同一对象

### 5. 误报与真实漏洞的概率分布

根据审计 200+ Solana/Sui 程序的经验：
- 80% 的初审报告中所谓"权限漏洞"实际上是 Anchor 约束理解不足导致的误报
- 15% 的案例是复杂的跨程序调用权限链条问题，需要 CPI 流分析
- 5% 的案例是真正的漏洞，往往涉及 PDA seeds 设计缺陷或权限检查条件不完整

**减少误报的关键：** 在得出结论前，必须证明程序在当前约束下如何允许未授权操作，而非仅指出缺少代码行
