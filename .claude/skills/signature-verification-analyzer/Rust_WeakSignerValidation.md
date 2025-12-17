# Rust 弱签名者验证 (Weak Signer Validation)

**漏洞成因**: 签名者身份验证逻辑不完整或可被绕过，允许未授权方执行特权操作。常见于 Substrate pallet、Solana program、链下签名验证等场景，核心问题是验证签名有效性后未检查签名者是否具备操作权限。

## Details

**典型代码模式**:

```rust
// Substrate: 仅验证签名有效但未检查 origin 权限
pub fn withdraw(origin: OriginFor<T>, amount: Balance, signature: Signature) -> DispatchResult {
    let who = ensure_signed(origin)?;  // ⚠️ 仅验证签名有效
    // 直接执行敏感操作，未检查 who 是否有权限
    Self::do_withdraw(who, amount)?;
    Ok(())
}

// Solana: 未验证 signer 是否为预期账户
pub fn process_instruction(accounts: &[AccountInfo], data: &[u8]) -> ProgramResult {
    let account_iter = &mut accounts.iter();
    let operator = next_account_info(account_iter)?;
    // ⚠️ 未检查 operator.is_signer，任意账户可调用
    // ⚠️ 未检查 operator.key 是否匹配预期授权地址
    invoke_privileged_action(operator)?;
    Ok(())
}

// 链下签名: 验证签名但未绑定 signer 与权限
pub fn verify_off_chain_authorization(msg: &[u8], sig: &Signature, pubkey: &PublicKey) -> bool {
    if !pubkey.verify(msg, sig) {  // ⚠️ 仅验证密码学有效性
        return false;
    }
    // ⚠️ 缺失: 检查 pubkey 是否在授权白名单中
    true
}
```

**快速定位核心操作技巧** (L2-L3):
- **Substrate**: 搜索 `ensure_signed`/`ensure_root`/`T::Origin` + 状态变更函数（`insert`/`remove`/`mutate`/`transfer`），定位权限检查点
- **Solana**: 搜索 `is_signer` 检查缺失 + `AccountInfo` 迭代器使用，关注账户访问控制
- **签名验证函数**: 搜索 `verify`/`recover`/`ed25519`/`sr25519`/`secp256k1` + 返回值处理，确认是否关联权限列表

**快速定位保护机制技巧** (L1-L4):
- **(L1) 关键词扫描**: 搜索 `ensure!`/`require!`/`is_authorized`/`whitelist`/`authorized_accounts`，快速排查是否存在权限检查
- **(L2) 跳读签名流**: 在签名验证成功后，追踪 5-10 行内是否有 `==` 比对签名者地址、角色查询（`Role`/`Permission`）、状态查询（`owner`/`admin`）
- **(L3) 逐行读关键路径**: 对于多签/代理场景，逐行检查签名验证后是否枚举所有签名者、验证阈值、检查每个签名者身份
- **(L4) 跨模块追踪**: 若权限检查委托给 `AuthModule::check_permission(signer)`，需跨文件追踪该函数实现，确认是否正确查询链上授权状态（如 `Storage::get(AUTHORIZED_LIST)`）或硬编码白名单

## Classify

**漏洞判定条件**:
- 签名验证成功后直接执行敏感操作（转账/铸币/权限变更/状态删除），且无任何签名者身份或权限检查
- 签名者身份检查存在但可绕过：如用未初始化变量、错误的逻辑分支、错误的比较操作符（`!=` 误写为 `==`）
- 权限检查依赖客户端传参（如 `is_admin: bool` 参数），而非链上状态

**误报场景**:
- 权限检查在上层调用者已完成（需确认调用链路无公开入口）
- 操作为只读查询或日志记录，不涉及状态变更或资产转移
- Substrate 中 `ensure_root(origin)` 等强制性 origin 检查已限制调用者为治理/sudo

**代码异味**:
- 权限检查存在但逻辑复杂（多层嵌套 if/match），易因重构引入漏洞
- 权限白名单硬编码在代码中而非存储在链上状态，无法动态更新
- 使用自定义签名方案替代标准库函数，未经密码学审计

## Low risk

**低风险评级条件**:
- 操作已被其他机制限制：如时间锁（timelock）、冷却期（cooldown）、金额上限（cap）等，即使签名者验证弱化也无法造成直接损失
- 签名者验证弱但操作仅影响自身账户状态（如用户设置昵称/偏好），不影响他人资产或全局状态
- 测试或开发环境代码，未部署到主网，且有明确注释标注（`// TODO: Add auth check before mainnet`）
- 权限范围极小：如仅能触发事件（event）而无实际状态变更，或操作已被后续交易撤销机制保护（如乐观 rollup 的挑战期）

## 审计专业技巧

### 1. 多层次检查框架

**第一层：签名验证完整性扫描**
- 在审计报告中区分 **密码学验证** 与 **权限检查** 两个维度，误报常源于混淆两者
- 使用正则模式快速定位：`verify.*\|.*is_signer.*\|.*recover_signer` 但**不停留**在单个函数，必须追踪返回值流向
- 关键问题：签名有效 ≠ 签名者有权执行；需检查 `verify()` 后 5 行内是否进行身份绑定

**第二层：权限映射链路追踪**
```rust
// 真实漏洞示例（Polkadot 相关审计）
pub fn execute_proposal(origin: OriginFor<T>, proposal_hash: T::Hash) -> DispatchResult {
    let who = ensure_signed(origin)?;  // Step 1: 验证签名有效
    // ⚠️ 问题：跳过了 Step 2、3
    // ❌ 缺失：let is_voter = Self::voters::<T>(who)?;
    // ❌ 缺失：ensure!(is_voter, Error::NotAuthorized);
    Self::do_execute(&proposal_hash)?;
    Ok(())
}

// 正确的多层检查
pub fn execute_proposal(origin: OriginFor<T>, proposal_hash: T::Hash) -> DispatchResult {
    let who = ensure_signed(origin)?;                    // Layer 1: 签名验证
    let voter = Self::voters::<T>(&who)?;               // Layer 2: 身份查询
    ensure!(voter.weight > 0, Error::InsufficientWeight); // Layer 3: 权限检查
    Self::do_execute(&proposal_hash)?;
    Ok(())
}
```
- **审计技巧**：在代码中标记 Layer 1/2/3 缺失的位置，定量描述漏洞范围

### 2. 真实漏洞 vs 误报区分清单

**案例 1: Solana 多签账户混淆（真实漏洞）**
```rust
// ❌ 真实漏洞：未验证 authority 是否为预期多签地址
pub fn withdraw_token(accounts: &[AccountInfo], amount: u64) -> ProgramResult {
    let token_account = next_account_info(&mut accounts.iter())?;
    let authority = next_account_info(&mut accounts.iter())?;

    if authority.is_signer {  // 仅检查是否签名，未检查身份
        token::transfer(CpiContext::new(
            token_program,
            Transfer { from: token_account.clone(), to: dest, authority: authority.clone() }
        ), amount)?;
    }
    Ok(())
}

// 误报风险：如果 Solana 程序所有者（owner）公开可知，且 authority 必须被 CPI 验证，
// 则仍可能是安全的。但通常审计应标记为 Medium，除非确认 CPI 校验逻辑。
```

**区分要点**：
- **真实漏洞**: `is_signer=true` 但未验证 `authority.key == expected_authority` → 可被任意签名者利用 → **Critical**
- **误报**: `is_signer=true` 且后续 CPI 调用会隐式验证 authority 匹配 → **低风险或需进一步确认**

**案例 2: Substrate 权限检查延迟（常见误报来源）**
```rust
// 疑似漏洞代码
pub fn transfer_ownership(origin: OriginFor<T>, new_owner: T::AccountId) -> DispatchResult {
    let _who = ensure_signed(origin)?;  // 看似仅验证签名
    let owner = Self::current_owner();
    // ⚠️ 如果审计者此时认定为漏洞，可能误报
    ensure!(owner == _who, Error::NotOwner);  // 权限检查在后
    Self::set_owner(&new_owner);
    Ok(())
}

// 审计技巧：不能因为 ensure! 在签名验证之后就认定为漏洞，
// 需检查是否正确关联了权限。此例中权限检查正确，应评为安全。
```

**区分要点**：
- 权限检查位置不影响安全性，只要逻辑正确即可
- 关键是检查内容（是否查询了正确的权限字段）而非顺序

**案例 3: 硬编码 vs 存储授权（中风险判定**）
```rust
// 代码 A：硬编码白名单（代码异味，但可能安全）
const ALLOWED_SIGNERS: &[&[u8]] = &[b"admin1", b"admin2"];

pub fn privileged_action(origin: OriginFor<T>, action: Action) -> DispatchResult {
    let who = ensure_signed(origin)?;
    ensure!(ALLOWED_SIGNERS.contains(&who.as_ref()), Error::Unauthorized);
    // ✓ 权限检查正确，但可升级性差
    execute(action)?;
    Ok(())
}

// 代码 B：存储授权（最佳实践）
#[pallet::storage]
pub type AuthorizedSigners<T> = StorageMap<_, Blake2_128Concat, T::AccountId, ()>;

pub fn privileged_action(origin: OriginFor<T>, action: Action) -> DispatchResult {
    let who = ensure_signed(origin)?;
    ensure!(AuthorizedSigners::<T>::contains_key(&who), Error::Unauthorized);
    execute(action)?;
    Ok(())
}

// 审计判定：代码 A 的硬编码方案应标记为"代码异味"而非漏洞，
// 除非确认部署后无法更新授权，否则风险等级为 Low。
```

### 3. 审计检查清单（Audit Checklist）

在审计报告中使用以下清单逐项检查，提高覆盖率和可复现性：

| 检查项 | 真实漏洞标志 | 误报风险指标 |
|--------|-----------|-----------|
| 签名验证存在 | `verify()` 调用存在 | 仅有密码学验证，缺权限检查 |
| 身份提取 | 从签名中提取地址/公钥 | 身份未被后续使用 |
| 权限查询 | 查询 `Storage::get(AUTH_LIST)` | 权限列表为空或查询失败未处理 |
| 权限对比 | `ensure!(auth == caller)` | 对比操作符正确 (`==` 不是 `!=`) |
| 失败处理 | 权限验证失败返回 `Error` | 错误未被优雅捕获，可能 panic |
| 操作范围 | 权限适用于特定操作 | 权限校验应用于所有关键路径 |

### 4. 跨版本漏洞演变模式

**Substrate pallet 演变案例**：
- **v1.0**: 仅 `ensure_signed(origin)` → 漏洞严重
- **v2.0**: 添加 `origin.is_root()` 检查，但条件反向 (`!is_root()`) → 仍为漏洞
- **v3.0**: 正确使用 `ensure_root(origin)` → 修复

**审计启示**：版本号不保证安全，需逐版本审计关键函数。

### 5. 常见漏报陷阱

- **套用他人审计报告**：不同项目授权模型差异大，Curve 的管理权限模型不适用于 Aave
- **过度信任注释**：代码注释如 `// Already checked in caller` 需逐一验证，追踪完整调用链
- **忽视 feature gate**：Rust 的条件编译可能导致某些权限检查在特定场景被关闭
- **链下签名验证**：易误认为密钥恢复成功 = 授权完成，忽视 nonce/时间戳绑定
