# Move - 时间锁金库操纵 (TimeLockedVaultManipulation)

## Details

**代码示例**：
```move
public entry fun withdraw(vault: &mut Vault, ctx: &mut TxContext) {
    let now = timestamp::now_seconds();  // Aptos
    // let now = clock::timestamp_ms(&clock);  // Sui
    assert!(now >= vault.unlock_time, E_LOCKED);
    coin::transfer(vault.balance, tx_context::sender(ctx));
}

public fun create_vault(amount: u64, unlock_time: u64) {
    assert!(unlock_time > timestamp::now_seconds(), E_INVALID);
    // 无缓冲期、无容差机制
}
```

**快速定位核心操作** (L2: 跳读)：
- 搜索时间获取：`timestamp::now_seconds()` / `clock::timestamp_ms()` / `aptos_framework::timestamp`
- 定位比较运算：`>=` / `>` / `<` / `<=` 与时间戳变量的直接比较
- 追踪资金操作：`coin::transfer` / `coin::withdraw` / `balance::split` / `transfer::public_transfer`
- 关注条件判断：`assert!` / `if` / `require` 中的时间条件
- 检查结构体字段：`unlock_time` / `deadline` / `lock_until` / `vesting_start`

**快速定位保护机制** (L3: 逐行读)：
- 缓冲窗口：`unlock_time + BUFFER` / `deadline + GRACE_PERIOD`
- 时间范围：`MIN_LOCK_DURATION` / `MAX_LOCK_DURATION` 常量检查
- 双重验证：同时检查区块高度 `block::get_current_block_height()`
- 多步骤锁：请求-等待-执行模式，两次时间检查
- 事件预警：`event::emit` 在临界点前触发通知
- 紧急机制：`emergency_withdraw` / `admin_override` 函数存在性

## Classify

**漏洞判定**：
- 单一时间戳比较直接控制资金流动、权限切换或利率变更
- 验证者时间操纵窗口（±3-10秒）可产生显著套利空间
- 临界点前后存在经济激励差异（首个解锁奖励、费率跳变）

**误报识别**：
- 时间戳仅用于日志、展示或非强制性冷却
- 时间粒度 > 1小时，验证者操纵影响可忽略
- 已实现区块高度 + 时间戳双重条件
- 配合链下预言机或多签延迟机制

**代码异味**：
- 存在时间依赖但业务容忍度高（社交功能、统计展示）
- 操纵成本 > 收益（质押惩罚机制覆盖）
- 时间窗口宽松（≥24小时缓冲期）

## 审计专业技巧

### 1. 差分分析：虚警vs真漏洞

**真实漏洞的标志**：
- **经济损失可量化**：时间操纵可直接导致提前解锁、费用豁免或套利空间
- **原子性关键**：单个交易内时间戳被固定，验证者无法在中间调整
- **激励不对称**：操纵成本 < 预期收益，验证者有动机在 mempool 中延迟/加速区块
- **无缓冲机制**：`unlock_time == withdrawal_time` 精确匹配，容错度为 0
- **依赖可操纵参数**：`block::get_current_block_number()` / `timestamp::now_seconds()` 直接驱动业务逻辑

**误报的关键特征**：
- **时间仅作展示**：时间戳用于 event 日志或 UI 展示，不影响状态转移
- **粗粒度时间**：以周/月为单位，验证者 ±10 秒操纵被完全吸收
- **多层防护**：同时检查时间戳 + 区块高度 + 外部预言机信号
- **经济反馈**：操纵成本（交易费、MEV 建立者掠取）≥ 操纵收益
- **社交/非金融场景**：投票冷却、内容发布禁用期、实现延迟，无资金直接流动

### 2. 代码审计检查清单

**第一步：资金流审计**（L2 跳读，2分钟）
```move
// 反模式：直接资金转移
assert!(now >= unlock_time, error);
coin::transfer(vault.balance, recipient);  // ❌ HIGH RISK

// 正向模式：分阶段检查
assert!(now >= unlock_time, error);
assert!(block_height >= unlock_block, error);  // ✅ 降低风险
let amount = coin::withdraw(&mut vault.balance, requested_amount);
coin::transfer(amount, recipient);
```

**第二步：时间窗口量化**（L3 逐行，5分钟）
- 计算 `unlock_time - current_time`（秒级精度）
- 验证是否存在 `LOCK_DURATION < 3600`（<1小时）
- 检查是否有 `deadline + buffer >= deadline`（缓冲非零）
- 搜索所有时间常量：`const GRACE_PERIOD = ?`

**第三步：验证者攻击面映射**（深度分析，10分钟）
- 验证者能否延迟区块 N 秒？操纵时间戳 ±秒数？
- 在延迟期间，用户无法提取资金，能否造成真实伤害？
- 若有 MEV 机制（如掠取者费用），验证者能否提取不对等价值？

**第四步：上下文理解**（业务逻辑，5分钟）
- 这是真正的金融锁定还是虚拟"锁定"？
- 是否有外部系统依赖（Dapp、中心化交易所）？
- 用户能否通过其他路由绕过此时间检查？

### 3. 真实案例对比

**案例 A：Aptos DeFi Pool - 真漏洞**
```move
// 上下文：LP 解锁时立即扣费，利率与解锁时间相关
public fun unlock_liquidity(pool: &mut Pool, unlock_time: u64) {
    assert!(timestamp::now_seconds() >= unlock_time, E_LOCKED);
    let fee_rate = if (timestamp::now_seconds() < unlock_time + 3600) {
        50  // 早期解锁费 5%
    } else {
        0   // 超期解锁费 0%
    };  // ❌ 验证者可延迟 3600 秒，白嫖 5% 费用
    let fee = (pool.balance * fee_rate) / 1000;
    withdraw_with_fee(&mut pool, fee);
}
```
**判定**：CRITICAL - 经济损失 5%，验证者有强动机操纵

**案例 B：Sui Voting - 误报**
```move
public fun vote(proposal: &mut Proposal, vote: u8, ctx: &mut TxContext) {
    let now = clock::timestamp_ms(&clock);
    assert!(now < proposal.vote_deadline, E_VOTING_CLOSED);
    vector::push_back(&mut proposal.votes, vote);
    event::emit(VoteEvent { timestamp: now, voter: sender(ctx) });  // ✅ 仅日志
}
```
**判定**：LOW - 时间戳仅用于事件记录，vote 计数逻辑无时间依赖

### 4. 常见误判陷阱

| 误判类型 | 表现 | 纠正方法 |
|---------|------|--------|
| **时间戳日志混淆** | event 中有 timestamp，误认为逻辑依赖 | 检查 assert 条件，忽略事件数据 |
| **多签延迟机制** | 合约有时间检查，但需多签批准 | 确认多签流程是否真的阻止操纵 |
| **外部预言机** | 有时间检查 + chainlink 预言机 | 预言机是否覆盖所有操作路由？ |
| **演示代码** | 存在 TODO/mock 时间检查 | 搜索实际部署版本，勿审核测试代码 |
| **并行操作** | 不同 Move module 中时间检查不同步 | 追踪跨合约调用的时间一致性 |

### 5. Aptos vs Sui 时间差异审计

**Aptos (`aptos_framework::timestamp`)**
- `now_seconds()` 返回 Unix 秒级时间戳，精度 1 秒
- 验证者可操纵范围：±3-5 秒（共识安全范围）
- 缓冲建议：最少 60 秒（1 分钟）

**Sui (`sui::clock`)**
- `timestamp_ms()` 返回毫秒级时间戳，精度 1 毫秒
- Sui 全球网络时间同步更严格（<1秒），验证者操纵难度高
- 缓冲建议：≥ 1000 毫秒（1 秒）即可

## Low risk

**降级场景**：
- 锁定周期 > 30天且无清算/利率突变等敏感机制
- 缓冲窗口 ≥ 1小时
- 资金规模 < $1000 或测试环境部署
- 混合验证：`(now >= unlock_time) && (block_height >= unlock_block)`
- 链下监控 + 暂停开关实时响应异常时间戳
- 非原子操作但无 MEV 可提取价值
