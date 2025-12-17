# Rust_PriceDeviationWithoutCircuitBreaker

**漏洞类型：** 价格偏差无熔断机制  
**适用场景：** Solana/Substrate DeFi 项目，链下签名喂价、Pyth/Switchboard 等预言机集成

---

## Details

### 典型代码特征

```rust
pub fn update_price(ctx: Context<UpdatePrice>, new_price: u64) -> Result<()> {
    let oracle = &mut ctx.accounts.oracle;
    oracle.price = new_price;  // 直接更新，无偏差检查
    oracle.last_update = Clock::get()?.unix_timestamp;
    Ok(())
}
```

### 快速定位核心操作 (L2: 跳读)

**扫描要点：**
- 搜索 `price` 字段赋值语句：`oracle.price = `, `state.price = `
- 关注 `update_price`, `set_price`, `refresh_oracle` 等函数名
- 查看 Pyth `Price::get_price_no_older_than()` 或 Switchboard `AggregatorAccountData` 的直接使用
- 检查 `Clock::get()` 后是否仅更新时间戳，无价格校验逻辑

**Solana 特有模式：**
- `AccountInfo` 反序列化后直接读取 `price` 字段
- `Anchor` 约束中缺少 `#[account(constraint = ...)]` 价格边界检查
- CPI 调用预言机后未对返回值做范围验证

### 快速定位保护机制 (L3: 逐行读)

**关键检查项：**
1. **偏差率计算：** 搜索 `abs()`, `checked_sub()`, `checked_div()` 组合，确认是否存在：
   ```rust
   let deviation = (new_price.abs_diff(old_price) * 100) / old_price;
   require!(deviation <= MAX_DEVIATION, ErrorCode::PriceSpike);
   ```

2. **熔断状态位：** 查找 `is_paused`, `circuit_breaker_triggered`, `emergency_mode` 布尔标志

3. **价格边界：** 检查 `MIN_PRICE`, `MAX_PRICE` 常量及对应 `require!` 断言

4. **时间窗口限制：** 确认是否有 `last_update` 时间差检查防止频繁更新

5. **多签验证：** 查看 `ctx.accounts.authority` 是否要求多签 PDA 或治理合约

**审计等级标注：**
- **L1 (关键词扫描)：** 若存在 `MAX_DEVIATION`, `circuit_breaker` 关键词 → 降级风险
- **L3 (逐行读)：** 确认偏差计算逻辑正确性，需防溢出、除零、精度丢失
- **L4 (跨模块追踪)：** 检查熔断后是否全局阻断交易/清算，追踪 `is_paused` 在其他指令中的使用

---

## Classify

### 确认为漏洞

1. **高影响场景：**
   - 清算/借贷协议：价格操纵直接导致不当清算或坏账
   - AMM/DEX：价格作为兑换率核心参数，无保护可引发套利攻击
   - 合成资产：铸造/赎回依赖价格，异常价格导致协议铸币权失控

2. **确认标准：**
   - 价格更新路径完全无偏差检查（数学计算、边界断言均缺失）
   - 预言机数据直接用于资金流转决策（transfer、mint、burn）
   - 无任何治理延迟或多签干预机制

### 误报判定

1. **已有外部保护：**
   - Pyth Network 的 `confidence interval` 在上层合约已验证
   - 前端/Keeper 层面做了价格合理性预检（需确认链上无法绕过）

2. **业务容错设计：**
   - 价格仅用于展示/统计，不影响资金安全
   - 协议内置冗余机制（如多预言机中位数聚合）

### 代码异味

1. **单点依赖：** 仅依赖单一预言机源但有基础校验（如时效性检查），建议增强但非紧急
2. **硬编码阈值：** 偏差阈值写死在代码中无法动态调整，灵活性不足但有基本保护

---

## Low risk

### 低风险评级条件

1. **低频低额场景：**
   - 测试网或教育性项目，无真实资金风险
   - 价格更新需多签且频率限制为日级别，攻击时间窗口极小

2. **多重防护层：**
   - 虽无熔断但有时效检查（`require!(now - last_update < 60s)`）+ 金额上限（单笔交易 cap）
   - 价格异常不直接触发资金转移，需额外人工/治理审批

3. **隔离影响面：**
   - 价格仅影响单个池子且 TVL < $10k
   - 协议有保险基金覆盖价格操纵损失（需验证保险合约逻辑）

4. **市场自然约束：**
   - 使用流动性极高的资产（BTC/ETH），市场价格操纵成本高于攻击收益
   - 价格偏差触发显著滑点，经济上不可行

### 评级依据

需同时满足：影响范围有限 + 攻击成本高 + 存在兜底机制。仅满足单一条件仍应评中危及以上。
