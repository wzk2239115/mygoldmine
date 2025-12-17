# Rust_InflationRateUnchecked

**漏洞类型**: 经济模型 - 通胀率未校验  
**适用语言**: Rust (Solana programs)  
**业务场景**: 质押收益计算、代币通胀调控、协议收入再分配

## Details

**代码示例特征**：
```rust
pub fn update_inflation_rate(ctx: Context<UpdateInflation>, new_rate: u64) -> Result<()> {
    let config = &mut ctx.accounts.config;
    config.inflation_rate = new_rate;  // 直接赋值，无边界检查
    Ok(())
}

pub fn mint_rewards(ctx: Context<MintRewards>, amount: u64) -> Result<()> {
    let inflation_rate = ctx.accounts.config.inflation_rate;
    let reward = amount.checked_mul(inflation_rate).unwrap() / 10000;  // 未验证 inflation_rate 合法性
    // ... mint tokens
}
```

**快速定位核心操作** **(L2-L3)**：
- 关键词扫描：`inflation`, `rate`, `mint`, `supply`, `reward_rate`, `annual_yield`
- 重点审查：通胀参数的赋值语句，是否直接使用 `config.xx = new_value` 而无 `require!()` 或 `assert!()` 约束
- 追踪数据流：从参数更新函数 → 通胀计算逻辑 → 代币铸造调用，检查参数在整个链路中是否失控

**快速定位保护机制** **(L3-L4)**：
- 缺失信号：无 `require!(new_rate <= MAX_RATE, ErrorCode::InflationTooHigh)` 类边界校验
- 缺失信号：无 `has_one = authority` 或 `#[account(constraint = ...)]` 宏限制调用者身份
- 缺失信号：参数更新后无事件（`emit!`）记录，缺乏链上可审计性
- 跨模块检查：若通胀率存储在独立 PDA 账户，需追踪账户初始化时是否设定合理默认值及上下限

## Classify

**漏洞判定**：
- 通胀率可被任意修改至极端值（如 >100% 年化或负数），且无权限控制 → **高危漏洞**
- 通胀率有权限保护但无数值上限，治理可通过提案设置不合理参数 → **中危漏洞**

**误报排除**：
- 通胀率仅在 `initialize` 中设置一次且后续不可变更 → **非漏洞**
- 更新函数有明确 `require!(new_rate >= MIN && new_rate <= MAX)` 且常量合理 → **非漏洞**

**代码异味**：
- 通胀率上限过高（如 500%）但有权限控制 → **设计风险，需业务确认**
- 使用 `unwrap()` 而非 `checked_mul()` 处理通胀计算 → **潜在溢出风险**

## Low risk

以下情况可评为低风险：
1. **测试网环境**：代码明确标注为测试版本，且通胀率硬编码为固定值
2. **多重保护**：虽某函数缺校验，但调用链路的上层已强制验证（需确认上层逻辑不可绕过）
3. **时间锁保护**：通胀率修改需经过 Timelock 合约延迟执行，且有紧急暂停机制
4. **影响范围有限**：通胀率仅影响单一低价值代币，且总供应量有硬上限（cap）保护
5. **社区治理**：参数修改需 DAO 多签 + 公示期，实际攻击成本远高于收益

## 审计专业技巧

### 1. 动态分析与静态审查的结合

**真实漏洞特征**（需要同时满足）：
- ✓ 静态代码无边界检查 + 动态无调用约束 + 流动资金受影响
- ✓ 在历史审计或赏金猎人报告中出现过相同模式的漏洞（参考 Anchor 官方安全建议）

**常见误报陷阱**：
- 看到 `unwrap()` 就判定为漏洞，但该行的输入已在前置条件被校验
  - 例：`let amount = parse_input(user_input)?; amount.checked_mul(100).unwrap()`
  - 正确做法：追踪 `parse_input` 是否已确保 `amount` 不会导致溢出
- 认为任何参数修改函数都必须有 `require!()` 约束
  - 反例：某些参数的有效范围实际由链上账户状态机制隐式约束

### 2. 权限控制的隐式与显式区分

**显式权限校验** (明确标记为权限检查)：
```rust
// 正确示例
#[account(constraint = ctx.accounts.admin.key() == ADMIN_KEY)]
pub fn update_inflation_rate(ctx: Context<UpdateInflation>, rate: u64) -> Result<()> {
    require!(rate <= MAX_RATE, ErrorCode::RateTooHigh);
    ctx.accounts.config.inflation_rate = rate;
    Ok(())
}
```

**隐式权限保护** (需深度追踪)：
- 某账户作为 PDA，其种子包含治理合约地址 → 只有治理合约能调用
- 函数需要特定签名者或账户，间接限制了访问权
- **陷阱**：签名者限制可能由 `#[account(signer)]` 实现，需确认是否真的限制了修改权

### 3. 数值范围校验的深层检查

**需要验证的边界情况**：
1. **上界溢出**：`new_rate * user_balance` 是否会溢出 u64？
   - 审查：是否用 `checked_mul()` 或是否存在 `require!(new_rate <= u64::MAX / MAX_BALANCE)`
2. **下界**：通胀率为 0 或负数时的行为
   - 审查：是否允许 0%，若允许是否会导致无奖励分配的矛盾状态
3. **精度丢失**：定点运算中的舍入误差
   - 例：`reward = amount * rate / 10000` 中，rate 与 10000 的关系是否明确文档化

**现实案例**：
- Solana COPE token 事件：质押计算中未校验上界，导致代币超额发行
- 判断依据：构造输入 `(1u64, MAX_BALANCE, MAX_RATE_UNCHECKED)` 后，检查是否触发溢出或结果超预期

### 4. 误报与真漏洞的区分矩阵

| 情境 | 静态信号 | 动态约束 | 影响范围 | 判定 |
|-----|--------|--------|--------|------|
| 无 require 限制 + 任意调用者 | ❌ | ❌ | 全局代币供应 | **高危** |
| 无 require 限制 + 仅 admin 可调 | ❌ | ✓ | 取决于信任假设 | **中危** |
| 有 require 但上限太松（>50%） | ✓ | ✓ | 取决于业务设计 | **低危/设计风险** |
| Timelock + 多签 + 公示 | ❌ | ✓✓ | 实际风险低 | **低风险** |
| 测试网仅用 u32 演示代码 | ❌ | - | 不适用生产 | **误报** |

### 5. 日志与事件审计的缺失识别

**真漏洞信号**：
```rust
// 缺失关键事件
config.inflation_rate = new_rate;  // 无 emit!()
```

**审查清单**：
- [ ] 参数修改是否触发事件，链下应用能否检测？
- [ ] 事件是否记录修改者、时间戳、前后参数值？
- [ ] 是否存在防重放检查（nonce 或时间戳）？

**误报示例**：
- 函数末尾有 `Ok(())` 但没有 `emit!()` → 不一定是漏洞，取决于协议是否需要链下追踪

### 6. 审计工具的合理应用

**推荐工具链**：
1. **Anchor 官方检查**：`anchor build --detach` 检查编译时警告
2. **Verifalia/Soteria**：自动检查 CPI 调用、账户权限漏洞
3. **手工代码审查**：沿着数据流追踪，从输入参数到最终存储
4. **符号执行**（高级）：使用 Prusti 或 Seahorn 验证不变式（需要形式化规范）

**常见工具误判**：
- 静态分析工具报告"未使用的变量" → 可能是暂存值用于事件发出
- 报告"冗余条件" → 可能是防御性编程，需保留以提高可读性

### 7. 跨协议依赖的隐藏风险

**需要追踪的上下文**：
```rust
// 这个函数看起来安全，但需要确认 apply_config 的实现
config.inflation_rate = new_rate;  // 有 require!(rate <= MAX)
apply_config(&config)?;  // 这里可能存在绕过
```

**审查步骤**：
1. 查找 `apply_config` 的定义，是否存在二次修改 `inflation_rate`
2. 检查是否存在并发调用的竞态条件
3. 确认所有使用 `inflation_rate` 的地方都遵守相同的约束条件

### 8. 实战误报避坑

**常见5大误报**：
1. **假溢出**：看到 `checked_mul()` 就认为有风险，实际上已正确处理
   - 正确做法：查看是否正确处理了 `None` 返回值
2. **假权限漏洞**：函数本身无权限检查，但被调用方强制校验
   - 正确做法：追踪所有调用路径，确保没有绕过点
3. **假状态漏洞**：PDA 地址包含时间戳或用户ID，看似可重入，实则不可
   - 正确做法：构造具体例子验证地址碰撞可能性
4. **假审计不完整**：看到多个文件，就认为需要跨文件验证
   - 正确做法：只追踪当前审计范围内的数据流
5. **过度关注风格**：代码没有注释或文档就认为有问题
   - 正确做法：关注逻辑，不评审代码风格
