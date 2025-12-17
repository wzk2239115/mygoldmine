# 基于未验证历史的奖励 (Reward Based On Unverified History)

**漏洞类型**: Economic Model - 经济模型缺陷  
**适用语言**: Rust (Solana programs)  
**风险等级**: High / Critical

## Details

**典型代码模式**：

```rust
// 场景1: 直接使用账户存储的历史数据计算奖励
pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
    let user = &mut ctx.accounts.user_account;
    let pool = &ctx.accounts.reward_pool;
    
    // ⚠️ 直接使用用户账户中的历史数据，未验证真实性
    let rewards = user.accumulated_points * pool.reward_per_point;
    user.accumulated_points = 0;
    
    // 发放奖励...
}

// 场景2: 基于链下提交的历史活动计算奖励
pub fn submit_activity_proof(
    ctx: Context<SubmitProof>,
    activity_count: u64,
    merkle_proof: Vec<[u8; 32]>
) -> Result<()> {
    // ⚠️ 仅验证merkle proof格式，未验证数据来源和时效性
    require!(merkle_proof.len() > 0, ErrorCode::InvalidProof);
    
    let user = &mut ctx.accounts.user_account;
    user.pending_rewards += activity_count * REWARD_RATE;
}

// 场景3: 使用未防护的历史快照计算增量奖励
pub fn calculate_staking_rewards(ctx: Context<Calculate>) -> Result<()> {
    let stake_info = &mut ctx.accounts.stake_info;
    let current_time = Clock::get()?.unix_timestamp;
    
    // ⚠️ last_claim_time 可被用户操控或重置
    let time_elapsed = current_time - stake_info.last_claim_time;
    let rewards = stake_info.staked_amount * time_elapsed * RATE;
    
    stake_info.last_claim_time = current_time;
}
```

**快速定位核心操作** (L3-L4)：
- 搜索奖励计算函数：`claim`, `distribute`, `calculate.*reward`, `mint.*reward`
- 关注历史数据读取：`last_claim_time`, `accumulated_*`, `historical_*`, `total_*`
- 追踪账户数据来源：检查 `user_account`, `stake_info` 等结构体的字段更新路径 (L4)
- 查看谁有写权限：`#[account(mut)]` + `has_one` / `constraint` 组合，确认是否仅协议可写
- 检查时间戳依赖：`Clock::get()` 相关计算，关注时间差值是否可被操控

**快速定位保护机制** (L2-L3)：
- 链上验证逻辑：`verify_proof`, `validate_merkle`, `check_signature` 等函数 (L2)
- 快照哈希校验：寻找 `hash`, `commitment`, `snapshot_root` 等字段及其验证 (L2)
- 防重放机制：`nonce`, `claimed_bitmap`, `last_claim_epoch` 等防重复领取标记 (L3)
- 数据源信任模型：检查是否使用 Oracle/PDA/程序派生地址保护历史数据 (L3)
- 时间窗口限制：`require!(elapsed < MAX_PERIOD)` 防止长时间累积 (L2)
- 上限保护：`min(calculated, MAX_PER_CLAIM)` 单次奖励上限 (L1)

## Classify

**确认为漏洞**的充分条件：
- 奖励计算依赖用户可控账户的历史字段，且该字段无签名保护或PDA约束
- 历史数据可通过关闭重开账户、跨合约调用等方式被重置或伪造
- 链下提交的历史证明仅做格式校验，未验证签名、时间戳、链上事件对应关系
- 快照哈希或merkle root由用户提供且未在链上锚定

**判定为误报**的情形：
- 历史数据存储在PDA中且仅程序自身可修改（通过 `seeds` 和 `bump` 保护）
- 所有历史累积通过链上事件完成，奖励计算可溯源到每笔链上交易
- 使用多签或时间锁保护的全局快照，且快照更新有治理机制
- 奖励上限极低（如测试网环境）且有总量封顶，经济激励不足

**代码异味**但风险可控：
- 历史数据有Oracle签名但未验证签名时效性，可能存在旧数据重放
- 奖励计算有上限保护但上限值过大，仍有刷量套利空间
- 存在速率限制但限制周期过长（如每月一次），短期内可被利用

## Low risk

以下场景可评估为低风险或信息级：

1. **中心化受控环境**：项目明确为许可链或内部测试网，用户账户由运营方白名单管理
2. **奖励池有限且可快速耗尽**：总奖励池 ≤ 攻击成本（如需多次交互的Gas费），经济上不可行
3. **历史数据仅影响非金融指标**：如积分排名、徽章等无直接经济价值的虚拟物品
4. **存在有效的链下监控**：运营方有实时监控系统，能够在损失扩大前暂停合约
5. **组合保护措施**：虽然单点存在问题，但多层保护（如白名单+速率限制+人工审核）使实际风险可控
6. **已知的设计权衡**：文档明确说明为了用户体验采用乐观验证，且有保险基金或损失补偿机制

**降级评估要点**：需同时满足"低经济激励"+"有补偿措施"+"可快速响应"三个条件，否则应维持中高风险评级。
