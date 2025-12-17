**Rust**（针对 EVM 或 WASM 智能合约运行环境，如 Solana/ArbOS/EVM 兼容链的 Rust 合约）  
常出现在跨合约调用、模块化逻辑加载或链上代码动态分发功能中，包括但不限于通过 invoke_call 指定 callee 并复用调用者上下文的方式：  
- WASM 中的 Delegate Call 等效操作：在 WASM 环境中使用类似 delegatecall 的机制但未验证目标，导致上下文被污染

## Details

**代码示例特征：**
```rust
// Solana CPI 或 CosmWasm invoke 中的危险模式
invoke_signed(&ix, &[account_info], &[signer_seeds])?;  // 未验证 program_id
call_indirect(func_idx, params);  // WASM 直接调用未检查的函数表索引
Program::invoke(&instruction, accounts)?;  // 目标 program_id 来自外部输入
```

**快速定位核心操作技巧（L3-逐行读）：**
- 搜索关键字：`invoke_signed`、`invoke`、`call_indirect`、`Program::invoke`、`execute_call`
- 关注参数来源：检查 `program_id` 或 `callee_address` 是否来自外部输入（instruction_data、账户字段）
- 检查是否复用调用者上下文：观察 `signer_seeds` 传递或 `context.sender` 是否保持原值
- WASM 特有：检查 `table.get()` 或函数表索引是否可控

**快速定位保护机制技巧（L2-跳读）：**
- 白名单验证：搜索 `require!(program_id == WHITELISTED_PROGRAM)`、`assert_eq!(callee, AUTHORIZED_ADDRESS)`
- 类型检查：查找 `AccountInfo.owner` 校验、`is_signer`、`is_writable` 断言
- 上下文隔离：确认是否有 `msg::sender()` 重写、临时权限降级、`original_caller` 保存逻辑
- 访问控制列表：检查 `admin_list.contains()`、`program_data.authority == signer`

## Classify

**漏洞判定：**
- 目标地址完全可控且无白名单 → 高危漏洞（可篡改状态、窃取签名权限）
- 调用者上下文（msg.sender/signer）在委托调用中未隔离 → 严重漏洞
- 函数表索引可控且无范围检查（WASM）→ 任意代码执行漏洞

**误报识别：**
- 目标地址硬编码为系统合约（SPL Token、System Program）
- 调用前有完整的 program_id 白名单校验
- 使用 `invoke` 而非 `invoke_signed`（不传递签名权限）且仅读取操作

**代码异味：**
- 目标地址从配置加载但配置更新缺少时间锁
- 调用链路复杂，难以追踪最终 callee 来源
- 注释标注"TODO: add validation"但未实现

## Low risk

**低风险场景判定标准：**
1. **受限调用集**：目标合约仅限 2-3 个已审计的官方协议（如 Serum、Raydium 固定地址）
2. **只读委托**：delegatecall 等效操作仅查询状态，不修改 storage 或转账
3. **临时权限**：调用前降级 signer 权限，调用后立即撤销，且有事件日志记录
4. **沙箱环境**：运行在隔离子账户，资产价值 < 阈值（如测试网或限额 < 100 USD）
5. **多重验证**：虽目标可配置，但需多签 + 时间锁 + 链下监控三重保护

## Audit Professional Techniques - 真实漏洞 vs 误报区分

### 1. 真实漏洞的关键特征识别

**signature pattern 1: 无限制的 program_id 加载**
```rust
// 真实漏洞案例
pub fn execute_delegate(ctx: Context<Delegate>) -> Result<()> {
    let target = Pubkey::new_from_array(ctx.accounts.target_program.key().to_bytes());
    let ix = Instruction { program_id: target, ... };  // target 来自 accounts，可控
    invoke_signed(&ix, &[signer_seeds])?;  // 签名权限被转移
}
```
**审计技巧**：
- 检查 `program_id` 是否直接来自 instruction_data 或账户输入，无中间赋值限制
- 追踪 signer_seeds 的构造，看是否包含调用合约的 PDA seeds（若包含则权限真正被委托）
- 关键：搜索 `let ... = ctx.accounts.xxx.key()` 后紧跟 invoke_signed，中间无 assert 校验

**signature pattern 2: 调用链路混淆**
```rust
// 易被误报的复杂链路
let program_id = load_program_id_from_pda(&pda_address)?;  // 通过 PDA 间接加载
invoke(&instruction)?;  // 最后调用
```
**区分真假的步骤**：
1. 定位 `load_program_id_from_pda` 的实现，查看 PDA 地址的来源
2. 若 PDA 地址为硬编码或通过固定的 seeds 导出 → 可能为误报（白名单隐式存在）
3. 若 PDA 是从 instruction 输入构造 → 真实漏洞

### 2. 常见误报陷阱及排除规则

**误报陷阱 A: 被包装的 invoke_signed**
```rust
// 误报：实际上在白名单内部验证了
pub fn safe_invoke_signed(program_id: &Pubkey, ...) -> Result<()> {
    require!(TRUSTED_PROGRAMS.contains(program_id), CustomError::Unauthorized);
    Program::invoke_signed(...)?;
}

// 调用处看起来可控，但已通过函数层白名单保护
safe_invoke_signed(&ctx.accounts.target_program.key(), ...)?;
```
**排除技巧**：必须跟踪函数定义，查看被调用函数内部的校验逻辑，不能只看调用点

**误报陷阱 B: 账户约束的隐式验证**
```rust
// 程序级别的约束可能被遗漏
#[account(address = APPROVED_PROGRAM @ CustomError::InvalidProgram)]
pub target_program: AccountInfo<'info>,

// 代码中虽然未显式写 assert，但由框架保证
invoke_signed(&ix, &[target_program], ...)?;
```
**排除技巧**：检查账户声明上是否有 `#[account(...)]` 宏约束，特别是 `address` 或 `owner` 字段

**误报陷阱 C: 单向数据流的受限调用**
```rust
// Solana 特有：某些场景中权限并未实际转移
invoke(&ix)?;  // 使用 invoke 而非 invoke_signed，不传递签名者
```
**排除技巧**：区分 `invoke` 和 `invoke_signed`，后者才是高危

### 3. 现场审计技巧速查表

| 检查项 | 真实漏洞特征 | 误报特征 | 审计方法 |
|--------|------------|--------|---------|
| **目标加载** | 直接来自 input、account 无处理 | 通过常量、配置、框架约束 | grep -n "program_id.*accounts\|instruction_data" |
| **权限转移** | invoke_signed + signer_seeds 包含 caller 信息 | invoke only 或 seeds 不含权限信息 | 检查 signer_seeds 的 seed 数组内容 |
| **验证链路** | 无 assert/require，直接调用 | 函数参数有约束、宏有验证、外层有检查 | 跟踪被调用函数、展开宏定义 |
| **调用参数** | 参数完全可控 | 参数通过白名单过滤后传入 | 搜索参数来源，向上追踪 2-3 个赋值步骤 |

### 4. 实战案例：Solana CPI 漏洞识别

**案例 1（真实漏洞 - Serum Dex 历史漏洞）**：
```rust
// 历史背景：缺少对 program owner 的验证
pub fn execute_swap(...) -> Result<()> {
    let dex_program = ctx.accounts.dex_program.clone();  // 完全可控的账户
    invoke_signed(&create_instruction(dex_program.key), ...)?;
}
```
**审计结论**：
- `dex_program` 来自账户输入，无任何约束 → **真实漏洞**
- 攻击者可替换为恶意合约 → 可窃取用户授权

**案例 2（误报 - OpenBook 安全设计）**：
```rust
// 设计模式：使用静态地址常量
const AUTHORIZED_PROGRAMS: &[Pubkey] = &[RAYDIUM_PROGRAM, ORCA_PROGRAM];

pub fn execute_route(program_id: Pubkey) -> Result<()> {
    require!(AUTHORIZED_PROGRAMS.contains(&program_id), CustomError::Unauthorized);
    invoke(&instruction)?;
}
```
**审计结论**：
- 虽有 invoke，但 program_id 受白名单约束 → **误报**（安全）
- 调用者试图传入恶意 program_id 会直接返回错误

### 5. 链上验证技巧

**实时验证方法**（针对生产环境漏洞确认）：
1. **查看链上配置**：通过 Solana RPC 获取合约的 PDA 数据，查看是否存在可更新的 program_id 存储
   ```bash
   solana account <PDA_ADDRESS> -u mainnet-beta
   ```
2. **权限检查**：确认谁有权限修改 program_id（若只有多签则降低风险）
3. **交易历史追踪**：查看过去是否有恶意 program_id 被加载调用的迹象

### 6. 审计检查清单 - 降低误报率

- [ ] 已读取完整的调用函数定义，包括所有宏展开
- [ ] 已追踪目标地址的所有赋值点，确认最终来源
- [ ] 已检查账户声明中的约束条件（`#[account(...)]`）
- [ ] 已验证 signer_seeds 的具体内容，确认权限转移范围
- [ ] 已检查是否有外层调用者的权限验证（如果是库函数）
- [ ] 已查证该调用模式在官方文档中的安全指南
- [ ] 对高风险发现，已通过链上数据验证漏洞可利用性
