# Rust_UnverifiedOracleSigner - 未验证的预言机签名者

**适用场景**：基于 Solana/Substrate 的 DeFi 项目，涉及链下签名喂价、账户验证、外部数据注入

## Details

**代码特征示例**：
```rust
// Solana 典型场景
pub fn update_price(ctx: Context<UpdatePrice>, price: u64, timestamp: i64) -> Result<()> {
    let oracle_account = &ctx.accounts.oracle_data;
    // 危险：直接接受价格数据，未验证签名者身份
    oracle_account.price = price;
    oracle_account.last_update = timestamp;
    Ok(())
}

// Substrate 典型场景
pub fn submit_price(origin: OriginFor<T>, price: u128) -> DispatchResult {
    let who = ensure_signed(origin)?;
    // 危险：未检查 who 是否为授权的预言机节点
    <Prices<T>>::insert(who, price);
    Ok(())
}
```

**快速定位核心操作技巧**（L2-跳读）：
- Solana: 搜索 `update_price`、`submit_data`、`push_feed` 等函数名，关注 `Context` 结构体中账户约束
- Substrate: 搜索 `#[pallet::call]` 宏下的外部调用函数，重点审查 `ensure_signed` 后是否有权限校验
- 定位模式：`*.price =`、`*.set(`、`.insert(` 等状态写入操作

**快速定位保护机制技巧**（L3-逐行读）：
- **必查项**：账户约束 `#[account(constraint = ...)]`、签名验证逻辑、白名单映射
- **Solana 保护信号**：
  - `has_one = authority` 约束存在
  - `signer.key() == expected_pubkey` 显式比对
  - `is_signer` 标记配合角色检查
- **Substrate 保护信号**：
  - `ensure!(AuthorizedOracles::<T>::contains_key(&who), Error::Unauthorized)`
  - `T::OracleOrigin::ensure_origin(origin)` 自定义源验证
  - `pallet_collective::EnsureMember` 委员会成员检查
- **审计等级**：
  - L1（关键词扫描）：`signer`、`authority`、`authorized`、`whitelist`
  - L4（跨模块追踪）：引用外部 pallet 或 CPI 调用时，需追踪权限传递链

## Classify

**确认为漏洞的条件**：
1. 状态修改函数可被任意地址调用且无业务逻辑阻断
2. 缺失签名验证或仅验证签名有效性但未校验签名者身份
3. 权限检查依赖可伪造的客户端参数（如未签名的 `Pubkey`）

**判定为误报的情形**：
1. 多签或治理合约已在上层统一校验调用者
2. 该函数为内部 `cpi::invoke` 调用，caller 已受约束
3. 存在时间锁或经济惩罚机制使恶意提交成本大于收益

**降级为代码异味**：
1. 权限验证存在但实现松散（如仅检查非零地址）
2. 依赖链下 off-chain worker 的隐式信任而非链上证明
3. 测试网环境尚未部署生产级权限控制

## Low risk

**可接受的低风险场景**：
1. **沙盒环境**：预言机数据仅用于仪表盘展示或非金融计算
2. **冗余验证**：后续业务逻辑中有价格合理性检查（偏差阈值、时间窗口、多源比对）
3. **经济激励对齐**：质押-罚没机制使作恶成本显著高于潜在收益
4. **有限影响范围**：价格数据仅影响次要功能，不涉及资产转移或铸造
5. **临时状态**：处于迁移期的向后兼容逻辑，已规划升级路径并有明确时间表

## 审计专业技巧与真实漏洞识别

### 现场审计的关键问题清单

1. **追踪签名验证的完整链路**
   - 当发现 `ensure_signed(origin)` 时，不要停留在"签名有效"层面
   - 必须追问：签名后的 `who` 有无与白名单、授权映射、管理员列表交叉验证？
   - 真实案例：某项目在 `submit_price()` 中正确验证了签名，但忘记检查 `AuthorizedOracles` 映射，导致任意地址可提交价格
   - 检查代码：`ensure!(AUTHORIZED[&who], Error::Unauthorized)` 或类似的权限查询必须存在

2. **区分"签名有效"与"签名者授权"的陷阱**
   - **误报常见原因**：审计员看到 `has_one = authority` 就认为安全，实际忽略了 `authority` 初始化的漏洞
   - **真实漏洞**：`authority` 可被任意初始化账户设置为攻击者地址，或缺少所有权验证导致权限泄露
   - 必查：权限的初始化函数、迁移、升级逻辑中是否有 owner 校验
   - 代码审查模式：搜索所有涉及 `authority` 字段的写入操作，验证每一处都受保护

3. **时间戳与重放攻击的隐蔽性**
   - Solana 中 `clock.unix_timestamp` 的 epoch 只精确到秒，多个区块可能时间戳相同
   - 误报陷阱：如果代码仅检查 `last_update < now - threshold`，不同区块的相同时间戳可能被利用
   - 真实漏洞识别：观察是否有 nonce、sequence number 或每区块唯一标识符（Solana 的 `blockhash`）防护
   - Substrate 的 `frame_system::pallet_prelude::BlockNumber` 才是防重放的正确选择

4. **CPI 调用与权限继承的隐形漏洞**
   ```rust
   // 危险示例：调用外部程序但未验证调用方权限
   invoke_signed(
       &instruction,
       accounts,
       seeds  // 即使用了 PDA 种子签名，也要检查调用方本身的权限
   )?;

   // 应该在调用前显式校验权限
   require_keys_eq!(ctx.accounts.oracle_authority.key(), AUTHORIZED_ORACLE);
   ```
   - 常见误报：看到 `invoke_signed` 就认为使用了 PDA 签名因此安全，忽视了 PDA 权限本身的初始化漏洞
   - 真实漏洞：PDA 的种子包含用户控制的参数，或 PDA 账户的权限字段未正确初始化

5. **多签与治理合约的虚假安全感**
   - 误报观察：某些项目声称"多签控制价格更新"，审计员直接标记为安全
   - 真实漏洞检查清单：
     * 多签合约的签名阈值是否真的是 N/M？搜索代码中的具体数值
     * 多签成员的白名单是否可被任意修改（后门权限）？
     * 时间锁机制是否有绕过（如 `execute_now` 特殊权限）？
     * 多签合约本身是否可被升级，且升级权限未受约束？

6. **白名单机制的常见绕过**
   - **误报**：代码中存在 `AUTHORIZED_ORACLES: BTreeMap<Pubkey, bool>` 就认为安全
   - **真实漏洞**：
     * 白名单初始化时缺少所有权验证，可被任意地址注册
     * 白名单移除逻辑缺失，曾被授权的恶意地址永久有效
     * 白名单本身的修改函数缺少权限控制
   - 完整检查：定位所有修改白名单的函数，验证每个都受 `admin_only` 或 `authority_only` 约束

7. **数值精度与价格操纵的隐蔽性**
   - 某些漏洞存在于业务逻辑而非访问控制：未验证签名者虽然是形式漏洞，但如果价格有 1% 偏差限制，实际风险降级
   - 审计技巧：搜索价格使用的所有地方（借贷计算、清算触发、套利检测），确认存在防护阈值
   - 真实案例：某项目虽然缺少签名验证，但在所有涉及价格的算术运算前都有 `require!(abs(new_price - old_price) < old_price / 100)` 检查

8. **测试网 vs 生产网的权限差异**
   - 误报点：代码在测试网中注释掉了权限检查以方便测试，审计员认为缺少保护
   - 真实判断方法：
     * 检查是否有 `#[cfg(not(feature = "testnet"))]` 条件编译
     * 查看 Cargo.toml 中是否定义了 testnet feature，且主网构建中该 feature 被禁用
     * 确认 testnet 代码路径不会进入生产构建

9. **链下签名服务的隐式信任**
   - 某些项目将权限验证转移到链下 off-chain worker，声称"由可信的签名服务保证只有授权节点能签名"
   - 此时判定：
     * 如果链上代码完全无验证逻辑 → **真实漏洞**，即使链下有保护也不够
     * 如果链上至少验证了签名有效性（Secp256k1/Ed25519）→ **代码异味**，可接受但需文档说明
     * 如果链上直接验证了特定公钥或多个公钥之一 → **安全设计**

10. **紧急管理员权限的后门**
    - 搜索所有包含 `emergency`、`pause`、`admin` 关键字的函数
    - 检查这些函数是否可绕过常规权限流程，如果可以 → **真实漏洞**
    - 完整检查：紧急权限的触发条件、时间锁延迟、事件记录是否齐全

### 实战案例：误报 vs 真实漏洞的对比

**案例1：表面上的访问控制缺失**
```rust
// 看起来危险的代码
pub fn set_price(origin: OriginFor<T>, price: u128) -> DispatchResult {
    let who = ensure_signed(origin)?;
    <CurrentPrice<T>>::put(price);  // 直接修改全局价格
    Ok(())
}

// 深度审查后的发现：
// 1. 如果 CurrentPrice 在初始化时已设置为固定值，且没有修改函数 → 误报（实际不可改）
// 2. 如果同时存在 pallet_scheduler 的自动调用 → 可能是授权设计
// 3. 关键：在 pallet 的 Config trait 中检查是否定义了 OracleOrigin，如果有 T::OracleOrigin::ensure_origin(origin)? 存在 → 验证逻辑在上层
```

**案例2：权限检查位置的迷惑**
```rust
// 一个看起来缺少权限的函数
pub fn update_price(ctx: Context<UpdatePrice>, price: u64) -> Result<()> {
    let oracle = &ctx.accounts.oracle;
    oracle.price = price;  // 无权限检查
    Ok(())
}

// 但实际审查时发现：
// 1. UpdatePrice 这个 Context 中的约束定义如下：
#[derive(Accounts)]
pub struct UpdatePrice<'info> {
    #[account(has_one = authority, mut)]
    pub oracle: Account<'info, OracleData>,
    pub authority: Signer<'info>,
    ...
}
// 2. has_one = authority 意味着 oracle 账户中存储的 authority 字段必须与 Signer 匹配
// 3. 这是 REAL PROTECTION，不是漏洞，是误报
```

**案例3：真实漏洞的隐蔽形式**
```rust
// 看起来有权限检查
pub fn set_authority(ctx: Context<SetAuthority>, new_authority: Pubkey) -> Result<()> {
    require_keys_eq!(ctx.accounts.oracle.authority, ctx.accounts.admin.key());
    ctx.accounts.oracle.authority = new_authority;
    Ok(())
}

// 但真实漏洞存在于初始化：
#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = payer, space = 8 + 32)]
    pub oracle: Account<'info, OracleData>,
    #[account(mut)]
    pub payer: Signer<'info>,
}
pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
    ctx.accounts.oracle.authority = ctx.accounts.payer.key();  // 任何 payer 都能成为 authority
    Ok(())
}
// REAL VULNERABILITY：oracle 初始化权限无约束，任何人都能创建 oracle 并设置自己为 authority
```
