# Move 时间戳依赖 - 治理投票截止时间依赖

**漏洞概述**
Aptos/Sui 生态的 DAO 治理合约中，投票截止时间直接依赖区块时间戳（block timestamp），验证者可通过调整出块时间在一定范围内操纵投票窗口。攻击者可能在关键提案投票时延迟出块以拉长投票期、或加速出块提前关闭投票，改变投票结果。

## Details

**代码示例特征**
```move
module governance {
    use aptos_framework::timestamp;
    use aptos_framework::coin::Coin;

    /// 漏洞模式：投票截止完全依赖链上时间戳
    struct Proposal<phantom T> {
        proposer: address,
        title: vector<u8>,
        description: vector<u8>,

        // 致命漏洞点：投票期限直接以时间戳表示
        voting_start_time: u64,
        voting_end_time: u64,  // 这个值可被验证者在一定范围内操纵

        for_votes: u64,
        against_votes: u64,
        abstain_votes: u64,

        status: u8,  // 0 = pending, 1 = active, 2 = closed, 3 = passed
    }

    /// 创建提案时设置投票期限
    public fun create_proposal<T>(
        proposer: &signer,
        title: vector<u8>,
        description: vector<u8>,
        voting_period: u64,  // 以秒为单位
    ): Proposal<T> {
        let now = timestamp::now_seconds();

        // 危险：使用 now_seconds 直接计算截止时间
        // 由于验证者可在约 30 秒内调整时间戳，
        // 投票期可被人为缩短或延长
        let voting_end_time = now + voting_period;

        Proposal {
            proposer: signer::address_of(proposer),
            title,
            description,
            voting_start_time: now,
            voting_end_time,  // 致命漏洞：这个截止时间可被操纵
            for_votes: 0,
            against_votes: 0,
            abstain_votes: 0,
            status: 0,
        }
    }

    /// 投票函数
    public fun vote<T>(
        proposal: &mut Proposal<T>,
        voter: &signer,
        vote: u8,  // 0 = for, 1 = against, 2 = abstain
        voting_power: u64,
    ) {
        let now = timestamp::now_seconds();

        // 检查投票是否在进行中
        // 致命漏洞：这个检查完全依赖可被操纵的时间戳
        assert!(now >= proposal.voting_start_time, EVotingNotStarted);
        assert!(now < proposal.voting_end_time, EVotingEnded);

        // 记录投票
        match vote {
            0 => proposal.for_votes = proposal.for_votes + voting_power,
            1 => proposal.against_votes = proposal.against_votes + voting_power,
            2 => proposal.abstain_votes = proposal.abstain_votes + voting_power,
            _ => abort 99,
        };
    }

    /// 执行提案（检查投票结果）
    public fun execute_proposal<T>(
        proposal: &mut Proposal<T>,
        resolver: &signer,
    ) {
        let now = timestamp::now_seconds();

        // 依然依赖可被操纵的时间戳
        assert!(now >= proposal.voting_end_time, EVotingNotEnded);

        // 判断提案是否通过（根据投票数）
        if (proposal.for_votes > proposal.against_votes) {
            proposal.status = 3;  // 通过
            // 执行提案...
        } else {
            proposal.status = 2;  // 未通过
        }
    }

    // 攻击场景：
    // 情景 1：关键提案正在进行最后投票，反对者占多数
    //   - 攻击者贿赂验证者延迟出块 30 秒
    //   - 投票截止时间被延长 30 秒
    //   - 支持者争取到额外时间，可能翻转投票结果
    //
    // 情景 2：关键提案即将在下一个区块超时
    //   - 攻击者贿赂验证者加速出块
    //   - 投票截止时间被提前
    //   - 关键的反对票未能被记录，提案被迫通过
}
```

**快速定位核心操作**（审计等级：**L3-逐行读**）
- 关键函数：`create_proposal`, `vote`, `execute_proposal` 等涉及时间检查的函数
- 定位技巧：搜索 `timestamp::now_seconds()` 的使用，检查是否与投票截止时间比较
- 危险信号：直接计算 `deadline = now + duration` 而无缓冲机制
- Move 特性：检查是否存在 `timestamp` 依赖，以及是否有时间锁机制

**快速定位保护机制**（审计等级：**L2-跳读**）
- 寻找时间缓冲：`deadline + MIN_BUFFER_TIME` 或 `voting_period >= 24 hours` 等
- 寻找区块高度依赖：是否使用 `block::block_height()` 代替时间戳（更难被操纵）
- 寻找多签确认：投票执行是否需要多签或时间锁确认
- Move 专属：检查是否使用了 `epoch` 而非 `timestamp`（某些链的 epoch 相对更稳定）

## Classify

**漏洞判定**
满足以下条件组合即为中危或高危漏洞：①投票截止完全依赖 timestamp；②验证者可通过调整时间戳改变投票窗口（通常 ±30 秒）；③存在经济激励使验证者有动机操纵时间；④关键提案的投票结果可被时间操纵改变。

**误报识别**
以下场景非漏洞：①投票期限足够长（≥ 7 天），时间戳波动（30 秒）相对无足轻重；②存在时间锁确保提案执行需要等待额外时间；③使用区块高度而非时间戳进行检查；④投票结果需多签确认，单一验证者无法通过时间操纵改变结果。

**代码异味**
灰色地带：虽然存在时间戳依赖但投票期足够长（24+ 小时），时间戳的典型波动不足以改变结果；或者关键提案有社区制衡机制，难以通过时间操纵单方面推进。

## Low risk

**低风险场景**
- **充足缓冲**：投票期限 ≥ 7 天，时间戳的典型波动（±30 秒）相对百分比 < 0.001%
- **区块高度替代**：使用 `block::block_height()` 而非 `timestamp` 进行检查
- **时间锁存在**：提案通过后还需等待 1+ 天的额外时间锁才能执行
- **多签确认**：提案执行不仅需投票通过，还需多签钱包（≥ 3/5）确认
- **社区监控**：社区成员实时监控提案投票，异常时间延长会被立即发现和制止
- **小额提案**：影响范围有限（仅涉及 < 1% 的协议资金），攻击收益不足以覆盖贿赂成本

## Audit Checklist

- [ ] 检查所有与投票相关的时间检查，识别对 `timestamp::now_seconds()` 的依赖
- [ ] 验证投票期限是否足够长，相对时间戳波动的百分比 < 0.01%
- [ ] 检查是否存在时间锁或其他延迟机制确保关键决策的稳定性
- [ ] 审查是否有多签确认流程
- [ ] 验证是否使用了 block height 而非 timestamp
- [ ] 检查投票结果判定中是否存在缓冲（如需要 > 50% 而非 ≥ 50%）
- [ ] 执行单元测试，模拟时间戳波动（±30 秒）对投票结果的影响
- [ ] 检查事件日志，是否记录了投票的精确时间戳便于链下核验
- [ ] 审视协议的治理历史，是否曾出现过可疑的时间戳相关问题

## References

- [Aptos Timestamp Module](https://github.com/aptos-labs/aptos-core/blob/main/aptos-move/frameworks/aptos-framework/sources/timestamp.move)
- [Governance Best Practices](https://docs.aave.com/developers/governance/governance)
- [Time Locks in Governance](https://docs.uniswap.org/concepts/governance/governance-mechanics)
