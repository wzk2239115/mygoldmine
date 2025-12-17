**Rust**（针对 EVM 或 WASM 智能合约运行环境，如 Solana/ArbOS/EVM 兼容链的 Rust 合约）  
常出现在跨合约调用、模块化逻辑加载或链上代码动态分发功能中，包括但不限于通过 invoke_call 指定 callee 并复用调用者上下文的方式：  
- 未验证的动态逻辑加载：动态加载并执行外部逻辑模块但未验证来源，允许恶意代码在调用者上下文中执行

## Details

**典型代码模式**：
```rust
// Solana 风格
invoke(&instruction, &[account_info1, account_info2])?;
// WASM 风格  
ext_contract.execute(data).with_attached_deposit(0);
// 或直接加载字节码
Program::deploy(&wasm_bytes).call();
```

**核心操作定位技巧（L2-L3）**：
- 搜索 `invoke`、`invoke_signed`、`cross_program_invocation`、`ext_contract`、`call_with_gas` 等跨合约调用关键字
- 关注 `Program::deploy`、`load_program`、`execute_wasm` 等动态加载函数
- 追踪 `Pubkey`/`AccountId`/`ProgramId` 类型参数的数据流来源（用户输入/存储读取/硬编码）
- 检查是否存在 `account.is_signer`、`account.owner` 等前置校验

**保护机制定位技巧（L1-L2）**：
- 白名单验证：搜索 `ALLOWED_PROGRAMS`、`whitelist`、`authorized_callee`、硬编码的程序地址对比
- 所有权检查：`require!(callee.owner == &PROGRAM_ID)` 或 `assert!(account.owner == expected)`
- 权限验证：`is_admin`、`has_permission`、`only_governance` 等访问控制
- 签名验证：`is_signer` 检查或多签方案
- 缺失上述任一机制即为高危信号

## Classify

**确认漏洞**：
- 目标合约地址/程序 ID 完全由外部输入控制且无白名单验证
- 仅校验调用者身份但未校验被调用方身份
- 动态加载的字节码/WASM 模块来源不可信且无哈希/签名校验

**判定误报**：
- 被调用程序 ID 硬编码或存储在不可变配置中且初始化时已验证
- 存在完整白名单机制且白名单本身由 governance/多签管理
- 调用前已验证目标账户的 owner/program_id 属于可信系统合约

**代码异味**：
- 白名单可由单签管理员单方面修改（存在中心化风险但非直接漏洞）
- 校验逻辑依赖链下预言机数据（可能存在时间窗口）
- 使用 `unchecked_` 前缀的底层调用但有其他上层防护

## Low risk

**以下场景降低风险等级**：
- 功能仅对特权角色开放（如 governance/multisig）且角色管理机制健全
- 调用目标虽可指定但执行上下文隔离（无共享状态/仅只读权限）
- 存在速率限制、金额上限、时间锁等二级防护机制
- 目标合约集合范围极小（如仅限同一协议内的 2-3 个已审计模块）
- 调用失败会触发回滚且无状态残留（原子性保证）
- 测试网/实验性功能且已明确标注风险警告

## 审计专业技巧

**1. 数据流溯源三层法**：
- **源头确认**：追踪目标地址/ProgramId 的初始赋值，区分以下来源：
  - 硬编码常量（最安全）→ 检查编译期固定值
  - 部署时初始化参数（需验证初始化权限）→ 检查 initialize 函数的权限控制
  - 运行时存储变量（中等风险）→ 检查谁可以修改该变量
  - 交易参数/函数参数（最危险）→ 检查调用链路中是否有校验
- **传播路径**：确认中间是否存在校验节点（条件分支、断言、require 宏）
- **消费点**：在实际调用处（invoke/call）确认有无二次校验

**2. 白名单有效性评估矩阵**：
```
┌─────────────────────┬──────────────┬──────────────────┐
│ 白名单存储位置       │ 修改权限     │ 风险等级          │
├─────────────────────┼──────────────┼──────────────────┤
│ 编译期常量          │ 无法修改     │ ✓ 安全           │
│ 程序数据(初始化)    │ governance   │ ✓ 通常安全       │
│ 全局账户存储        │ 管理员       │ ⚠️ 需检查权限    │
│ 用户账户存储        │ 用户控制     │ ✗ 高危           │
└─────────────────────┴──────────────┴──────────────────┘
```

**3. 实际漏洞 vs 误报的典型案例**：

**真实漏洞案例**（确认标准）：
```rust
// ❌ 真实漏洞：完全无验证的 invoke
pub fn execute_external_logic(
    program_id: &Pubkey,  // 直接来自交易参数
    accounts: &[AccountInfo]
) -> Result<()> {
    invoke(&Instruction {
        program_id: *program_id,  // 无任何校验！
        accounts: vec![...],
        data: data,
    }, &[accounts])?;
    Ok(())
}
// 攻击：调用者可传入恶意合约地址

// ❌ 真实漏洞：存在校验但不完整
let mut targets = load_targets_from_storage()?;  // 可由管理员修改
invoke(&targets[0], accounts)?;  // 缺少多签防护
// 风险：单个恶意管理员可修改白名单后攻击

// ❌ 真实漏洞：检查对象错误
require!(callee_account.owner == &caller, "Wrong owner");  // 检查调用者而非被调用者！
invoke(callee_account.key, accounts)?;
```

**误报案例**（错误识别为漏洞）：
```rust
// ✓ 正常代码（常被误报）：参数化的目标但有完整验证
const ALLOWED_PROGRAMS: &[Pubkey] = &[
    Pubkey::new_from_array([...]),  // Program A
    Pubkey::new_from_array([...]),  // Program B
];

pub fn execute_validated(
    program_idx: u8,  // 索引，非地址
    accounts: &[AccountInfo]
) -> Result<()> {
    let program_id = ALLOWED_PROGRAMS.get(program_idx as usize)
        .ok_or(ProgramError::InvalidArgument)?;
    // ✓ 关键：通过索引限制选择范围
    invoke(&Instruction {
        program_id: *program_id,
        ...
    }, &[accounts])?;
    Ok(())
}
// 这是安全的模式

// ✓ 正常代码：动态检查配置账户的权限
pub fn call_configured_program(
    program_account: &AccountInfo,
    accounts: &[AccountInfo]
) -> Result<()> {
    require!(program_account.owner == &GOVERNANCE_ID, "Not governed");
    require!(program_account.is_signer, "Must sign");  // ✓ 验证签名

    let program_id = Pubkey::new_from_slice(&program_account.data)?;
    invoke(..., program_id, &[accounts])?;
    Ok(())
}
// 这不是漏洞，因为有完整权限验证
```

**4. 区分标准速查表**：
| 特征 | 真实漏洞 | 误报 |
|------|--------|------|
| 目标来自用户输入 | 直接使用，无校验 | 通过哈希/索引限制，或有白名单验证 |
| 目标可动态修改 | 任意权限修改，或无权限控制 | 仅 governance/multisig 修改，有锁定期 |
| 调用时验证 | 缺失或不完整 | 有 require!、assert!、match 等完整检查 |
| 账户所有权 | 未验证或验证对象错误 | 验证目标账户的 owner 属于信任方 |
| 上下文隔离 | 跨域访问共享状态 | 调用受限于只读或隔离账户 |

**5. 常见陷阱识别**：
- **陷阱1**：看到 `invoke` 调用直接标记为漏洞 → 需检查前置条件，许多是误报
- **陷阱2**：白名单存在就认为安全 → 要检查白名单谁能修改，修改前是否有时间锁/多签
- **陷阱3**：验证了调用者身份就认为安全 → 关键是验证**被调用方**的身份或来源
- **陷阱4**：访问了 `owner` 或 `is_signer` 就认为有防护 → 需确认验证的是目标账户而非调用者
- **陷阱5**：架构看起来分层就认为安全 → 每层都需逐个验证，链路中任一环节缺失即可利用
