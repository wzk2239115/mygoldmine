# Rust 无界迭代 DoS (Unbounded Iteration)

**漏洞类型：** 拒绝服务攻击（DoS）  
**影响链：** Solana、Substrate、NEAR、SUI (Rust-based)  
**核心成因：** 指令/交易处理中迭代账户、向量、映射等数据结构时未设置明确上限，导致计算单元（CU）或 Gas 耗尽

---

## Details

### 代码示例

```rust
// 漏洞示例：Solana 程序中无界账户迭代
pub fn process_batch_update(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    data: &[u8],
) -> ProgramResult {
    let account_iter = &mut accounts.iter();
    
    // 危险：直接迭代所有传入账户，无上限检查
    for account in account_iter {
        // 执行状态更新操作
        update_account_state(account)?;
    }
    
    Ok(())
}

// 漏洞示例：Vec/HashMap 无界迭代
pub fn distribute_rewards(ctx: Context<Distribute>) -> Result<()> {
    let reward_pool = &ctx.accounts.reward_pool;
    
    // 危险：迭代全部用户列表，列表长度不受控
    for user in reward_pool.users.iter() {
        calculate_and_transfer(user)?;
    }
    Ok(())
}
```

### 快速定位核心操作 **(L2-L3)**

**关键模式识别：**
- `for` 循环迭代 `accounts.iter()` 且无 `.take(n)` 限制
- 循环迭代 `Vec`/`HashMap` 且集合大小由外部输入决定
- 循环内包含 CU 密集操作：CPI 调用、PDA 派生、加密计算、序列化
- `while` 循环条件依赖外部状态且无计数器保护

**审计锚点：**
1. 搜索 `accounts.iter()` 或 `remaining_accounts` 使用点
2. 检查循环前是否有 `require!(accounts.len() <= MAX)` 断言
3. 追踪迭代对象来源：是否为用户可控的动态数组
4. 评估单次循环 CU 消耗：是否调用 `invoke`、`create_account` 等高成本操作

### 快速定位保护机制 **(L1-L2)**

**有效防护特征：**
- 显式长度检查：`require!(vec.len() <= MAX_SIZE)`
- 使用 `.take(n)` 分页限制：`iter().take(MAX_BATCH_SIZE)`
- 计算预算断言：使用 `solana_program::compute_budget` 监控
- 批处理设计：函数参数显式限定 `max_count: u8`

**审计技巧（L1）：**
- 关键词扫描：`MAX_`, `LIMIT_`, `require!(.*len()`, `.take(`, `ComputeBudget`
- 若发现上述防护，跳读验证常量定义是否合理（< 50 通常安全）

---

## Classify

### 确认为漏洞
1. **迭代对象完全由用户控制**：accounts 数组、剩余账户列表、用户提交的索引集合
2. **循环内 CU 消耗 ≥ 5000**：包含 CPI、PDA 查找、系统调用等重操作
3. **无上限验证**：函数入口无长度检查，内部无 `.take()` 分页
4. **可构造 PoC**：攻击者可通过传入大量账户（如 30+ 个）使交易失败

### 判定为误报
1. **迭代对象为常量数组**：如 `const VALIDATORS: [Pubkey; 5]`
2. **已有隐式上限**：Solana 交易账户数上限 256，且单次迭代 CU < 100
3. **管理员权限保护**：需 `admin` 签名且函数文档明确标注仅内部调用

### 代码异味（需重点标注）
1. **迭代上限过大**：如 `MAX_USERS = 200`，虽有保护但接近 CU 极限
2. **防护位置不当**：在循环中检查计数器而非函数入口验证
3. **依赖外部状态**：上限从链上账户读取，攻击者可能先修改该状态

---

## Low Risk

### 低风险场景认定标准

1. **低频管理员函数**  
   - 需多签或 DAO 投票触发，攻击者无法随意调用
   - 函数语义明确为"批量管理"，且文档注明 Gas 风险

2. **自然成本限制**  
   - 迭代对象需支付高额存储费用（如 Solana Rent、Substrate 存储押金）
   - 攻击者需先质押大量资金才能构造攻击条件

3. **轻量级迭代**  
   - 单次循环仅读取简单类型（`u64`/`bool`），无写操作或外部调用
   - 经测算即使迭代上限（256 账户）仍在 CU 预算 80% 内

4. **已有业务层限制**  
   - 上层业务逻辑已限制参与用户数（如"最多 10 人的多签钱包"）
   - 前置检查已过滤列表（如"仅处理 active 状态用户"）

5. **分页机制存在但不完善**  
   - 存在 `offset`/`limit` 参数，但上限设置略高
   - 建议优化但不影响当前安全性

**评级建议：** 满足以上任一条件可标记 Low，但需在报告中明确依赖前提（如"需管理员权限"），避免后续权限变更导致升级为 High。
