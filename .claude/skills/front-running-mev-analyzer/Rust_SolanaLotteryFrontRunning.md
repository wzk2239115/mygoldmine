# Solana 抽奖抢跑（Lottery Front Running）

## Details

**代码示例特征：**
```rust
pub fn draw_winner(ctx: Context<DrawWinner>) -> Result<()> {
    let lottery = &mut ctx.accounts.lottery;
    let clock = Clock::get()?;
    // 漏洞：使用可预测的链上状态作为随机源
    let winner_index = (clock.slot % lottery.participants.len() as u64) as usize;
    lottery.winner = lottery.participants[winner_index];
    // 直接发放奖励，无延迟或commit-reveal机制
    invoke_transfer(&lottery.prize_pool, &lottery.winner)?;
    Ok(())
}
```

**快速定位核心操作技巧（L2:跳读）：**
- 关键函数名：`draw_*`, `select_winner`, `random_*`, `lottery`, `raffle`
- 随机源标识：`Clock::get()`, `slot`, `blockhash`, `timestamp`, `unix_timestamp`
- 状态依赖：直接使用账户余额、参与者顺序、最近的区块哈希
- 即时奖励分配：检查是否在同一交易内完成选择与转账

**快速定位保护机制技巧（L3:逐行读）：**
- Commit-Reveal模式：是否存在两阶段提交（先提交哈希，后揭示）
- VRF随机数：检查是否集成Chainlink VRF或Pyth Entropy
- 延迟执行：是否有时间锁、多签确认、或延迟N个slot后才能claim
- Slot限制：是否限制同一slot内只能处理一个参与者
- MEV保护：是否使用Jito bundles或私有RPC防止抢跑可见性

## Classify

**漏洞判定：**
- 随机源完全依赖公开链上状态（slot、blockhash、timestamp）且无延迟机制
- 攻击者可通过模拟预测结果并选择性提交交易
- 资金价值显著（奖池 > 攻击成本：交易费+失败交易浪费）

**误报识别：**
- 使用VRF或可验证延迟函数（VDF）但审计员误读实现
- 存在外部Oracle随机数但未正确识别调用链
- 已有多签或DAO治理介入但代码注释不明确

**代码异味：**
- 使用伪随机但奖池金额极小（< 0.1 SOL），经济攻击不可行
- 测试网或demo代码，明确标注"仅供演示"
- 抽奖结果影响非金融状态（如NFT元数据、积分排名）

## Low risk

**降级为低风险的场景：**
1. **经济不可行性**：攻击成本（高优先级费用+失败交易）超过预期收益（小额奖池）
2. **时间窗口极短**：使用当前slot的未来哈希，攻击者无法在同一slot内获取并提交
3. **混合熵源**：虽用slot但组合用户输入的不可预测部分（需验证用户输入是否可操控）
4. **权限限制**：仅白名单地址可参与，且已KYC验证，声誉机制降低作恶动机
5. **结果延迟生效**：抽奖后需等待多个epoch且期间任何新交易都会改变最终随机数
6. **无直接经济激励**：结果仅影响链下积分系统，链上不持有实际资金

## 审计专业技巧与经验指南

### 1. 真实漏洞的核心特征识别

**高危信号清单（所有项皆需满足）：**
```rust
// 真实漏洞的三要素同时出现
// ✗ 1. 完全可预测的随机源
let seed = Clock::get()?.slot;  // 攻击者知道当前slot
// ✗ 2. 同一交易内完成"随机"与分配
let winner = participants[seed % count];
transfer_to_winner(winner)?;   // 无延迟
// ✗ 3. 奖励足以覆盖攻击成本
// 总奖池 = 1000 SOL，单次交易费 = 0.00025 SOL，ROI: 400万倍
```

**审计问卷（排查真实漏洞）：**
- 随机源是否在攻击者提交交易之前就已完全确定？（是=高危）
- 是否存在任何中间状态（pending slot、未finalize的块）？（否=高危）
- 攻击者能否通过MEV抢先执行改变随机输入？（能=高危）
- 防护机制是否需要攻击者*不知道*即将的状态？（是=真正防护）

### 2. 常见误报案例与精准判断

**误报案例A：VRF调用识别不足**
```rust
// 看起来像伪随机的"高危"代码
let seed = Clock::get()?.slot;
let vrf_output = request_vrf_oracle(&seed)?;  // 关键！
let winner = participants[vrf_output % count];
```
**正确判断流程：**
1. 搜索`request_vrf` / `Chainlink` / `oracle_program_id`
2. 验证VRF请求是否真实调用链下服务（检查CPI日志）
3. 确认结果返回延迟（不在同一交易）
4. **结论**：虽用slot但真实随机源是VRF → 低风险

**误报案例B：时间戳与slot混淆**
```rust
// 审计员误认为高危，但实际是安全的
let current_slot = Clock::get()?.slot;
let future_slot = current_slot + DELAY_SLOTS;  // DELAY_SLOTS = 100
// 后续检查
require!(Clock::get()?.slot >= future_slot)?;  // 强制延迟
```
**精准判断方法：**
- Solana slot生成速度：~2.5秒/个（不可加速）
- DELAY_SLOTS = 100意味着强制等待4分钟
- 在此期间链上任何新交易都改变后续哈希
- **结论**：延迟足够 + 时间锁 → 实际可防止抢跑

**误报案例C：DAO多签判断错误**
```rust
require_eq!(ctx.accounts.proposer.key(), ADMIN_MULTISIG)?;
// 错误判断：误认为没有验证
// 正确判断：需检查ADMIN_MULTISIG的实现
```
**核实清单：**
- ADMIN_MULTISIG 是否真的是 Squads/Marinade 多签？
- 多签阈值（M-of-N）是多少？
- 是否有时间锁（timelock）约束？
- 若3-of-5多签+72小时锁 → 可信度高

### 3. 经济可行性计算（区分理论vs现实）

**审计计算模板：**
```
攻击成本 = 高优先级费用 + 失败交易浪费 + 滑点成本
        = 0.01 SOL + (尝试次数 × 0.00025 SOL) + 交换损耗
        ≈ 0.05 SOL 保守估计

可获收益 = (奖池金额 - 失败概率损失) × 攻击成功率
        = 10 SOL × 95% × 100%  (确定性漏洞)
        = 9.5 SOL

ROI = 9.5 / 0.05 = 190倍 → 高度经济可行（标记为真实漏洞）

对比：
- 奖池 = 0.05 SOL，攻击成本 0.05 SOL → ROI = 1，*不值得*（降级为低风险）
```

### 4. 代码审计的"指纹识别"技巧

**确认是否真实集成VRF的代码标志：**
```rust
// ✓ 高概率真实VRF标志
mod pyth_entropy;  // 官方导入
use solana_program::instruction::Instruction;
// 跨程序调用检查
invoke(
    &instruction,
    &[account_info, vrf_program.clone()],  // 明确的CPI
)?;
```

**确认commit-reveal机制的代码标志：**
```rust
// ✓ 真实两阶段
pub fn commit(&mut self, commit_hash: [u8; 32]) -> Result<()> {
    self.phase = Phase::Committed;
    self.commit_hash = commit_hash;  // 阶段1：存储承诺
}

pub fn reveal(&mut self, secret: [u8; 32]) -> Result<()> {
    require_eq!(self.phase, Phase::Committed)?;  // 强制两阶段顺序
    require_eq!(hash(&secret), self.commit_hash)?;  // 验证承诺
}
```

**检查时间戳操纵防护：**
```rust
// ✓ Solana特定防护
require!(clock.slot > self.locked_slot + MIN_SLOT_DELAY)?;
// slot增长比timestamp更难篡改（由网络共识驱动，不可逆序）
// timestamp可被验证器调整±25秒（更危险）
```

### 5. 文档与代码不一致的识别

**高危不一致案例：**
```rust
// 注释声称使用VRF，但代码无调用
/// Uses Chainlink VRF for secure randomness
pub fn draw_winner(ctx: Context<DrawWinner>) -> Result<()> {
    let seed = Clock::get()?.slot;  // 实际上完全没用VRF！
    // → 这是虚假安全声明，记为高危
}
```

**审计建议：**
- 搜索所有"oracle"、"VRF"、"random"相关注释
- 交叉验证实际代码是否真的调用了这些服务
- 检查编译依赖（Cargo.toml）中是否包含VRF库
- 分析账户输入是否包含VRF程序ID

### 6. 风险升降级的客观标准

**升级为高危的补充条件：**
- 存在已知的历史抢跑事件或社区投诉
- 竞争对手或已知的MEV机器人活跃在该网络
- 抽奖结果与DeFi产品联动（如流动性挖矿奖励）

**降级为低风险的充分条件（至少满足一项）：**
- 总锁定价值 < $10,000 且无主动宣传
- 经过Slowmist/Certik等级别审计且通过
- 集成了行业标准的VRF（Pyth Entropy、Switchboard）并有第三方验证
- 源代码开源3个月无提交记录（已弃用项目）
