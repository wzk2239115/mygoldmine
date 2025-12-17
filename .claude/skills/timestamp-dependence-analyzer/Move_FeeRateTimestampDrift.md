# Move 时间戳依赖 - 费率动态调整漂移

**漏洞概述**
Aptos/Sui DeFi 协议中，交易费率、奖励倍数等关键参数根据区块时间戳动态调整，但未设置粒度控制（如每天仅调整一次）。同一区块内不同交易可能看到不同的费率值，导致费率波动。攻击者可通过 MEV 机器人精心安排交易顺序，在低费率时执行有利交易，在高费率时执行对手方交易，实现套利。

## Details

**代码示例特征**
```move
module defi_protocol {
    use aptos_framework::timestamp;
    use aptos_framework::math64;

    /// 漏洞模式：费率直接依赖时间戳，无粒度控制
    struct FeeConfig {
        base_fee: u64,           // 基础费用
        dynamic_multiplier: u64, // 动态倍数（依赖时间戳）
        last_update_time: u64,
    }

    /// 危险的费率计算函数
    public fun calculate_swap_fee(
        config: &FeeConfig,
        amount: u64,
    ): u64 {
        let now = timestamp::now_seconds();

        // 致命漏洞点 1：每次调用都根据当前时间戳计算费率
        // 没有粒度控制，同一区块内的多笔交易会看到不同的时间戳
        let time_diff = now - config.last_update_time;

        // 费率随时间线性增加（这仅是示例，实际可能更复杂）
        let multiplier = config.dynamic_multiplier + (time_diff / 3600);  // 每小时增加 1

        // 费用 = 金额 * 费率，同一区块不同时间戳 = 不同费用
        let fee = (amount as u128) * (multiplier as u128) / 1000_000 as u64;

        // 危险：没有 round 操作，可能存在舍入漏洞
        fee
    }

    /// 另一个例子：奖励倍数随时间戳变化
    public fun get_reward_multiplier(): u64 {
        let now = timestamp::now_seconds();

        // 同样的漏洞：不同交易可能获得不同的奖励倍数
        if (now < 1000000) {
            200  // 200% 早期奖励
        } else if (now < 2000000) {
            150  // 150% 中期奖励
        } else {
            100  // 100% 晚期奖励
        }
    }

    // 攻击场景（通过 MEV）：
    // 时间进度：当前区块时间戳为 999999（费率 200% 奖励）
    // 下一区块时间戳会是 1000001（费率降至 150% 奖励）
    //
    // 攻击者的 MEV 策略：
    // 1. 观察到即将跨越 1000000 时间戳的边界
    // 2. 通过 MEV 机器人，在同一区块内精心排列交易：
    //    - 交易 A：执行前贿赂验证者设置时间戳为 999999，获得 200% 奖励
    //    - 交易 B：对手方交易，在时间戳 1000001 时执行（200% -> 150%），支付更低费用
    //    - 交易 C：套利交易，从 A 和 B 的价格差异中获利
    // 3. 结果：攻击者从低费率和高奖励的不对称中获利
}

/// 正确的实现（对比）：
module defi_protocol_correct {
    use aptos_framework::timestamp;

    struct FeeConfig {
        base_fee: u64,
        current_multiplier: u64,
        last_update_time: u64,
        UPDATE_INTERVAL: u64,  // 添加粒度控制
    }

    /// 改进方案 1：使用上次更新的费率，不实时更新
    public fun calculate_swap_fee_cached(
        config: &FeeConfig,
        amount: u64,
    ): u64 {
        // 使用 cached 费率而非实时计算
        let fee = (amount as u128) * (config.current_multiplier as u128) / 1000_000 as u64;
        fee
    }

    /// 改进方案 2：定期更新费率（例如每小时更新一次）
    public fun update_fee_multiplier(config: &mut FeeConfig) {
        let now = timestamp::now_seconds();

        // 仅在足够时间间隔后才更新
        if (now - config.last_update_time >= config.UPDATE_INTERVAL) {
            // 计算新的倍数
            config.current_multiplier = calculate_new_multiplier(now);
            config.last_update_time = now;
        }
    }

    /// 改进方案 3：基于区块高度而非时间戳
    // （某些链支持）确保粒度为 1 区块，不存在同区块内的波动
}
```

**快速定位核心操作**（审计等级：**L3-逐行读**）
- 关键函数：涉及 `timestamp::now_seconds()` 的费用、奖励、利率计算
- 定位技巧：搜索直接使用时间戳进行 if-else 判断或数学计算的代码
- 危险信号：同一笔交易中多次调用 `timestamp::now_seconds()`，可能得到不同的值（虽然通常相同但在区块边界可能变化）
- Move 特性：检查是否存在缓存机制（如 `cached_fee`, `last_multiplier` 等字段）

**快速定位保护机制**（审计等级：**L2-跳读**）
- 寻找更新粒度控制：`UPDATE_INTERVAL`, `MIN_INTERVAL_BETWEEN_UPDATES` 等常数
- 寻找缓存机制：是否保存了上次计算的费率并在区间内复用
- 寻找区块高度依赖：是否使用 `block::block_height()` 替代 `timestamp`
- Move 专属：检查是否有 `Capability` 或 `Witness` 限制费率更新权限

## Classify

**漏洞判定**
满足以下条件组合即为中危漏洞：①费率/奖励直接依赖 `timestamp::now_seconds()` 无粒度控制；②攻击者可通过 MEV 在同区块内精心排列交易以利用费率差异；③费率变化幅度足够大（> 5% 变化）使得套利空间显著。

**误报识别**
以下场景非漏洞：①使用缓存费率，仅在定期间隔（≥ 1 天）更新一次；②费率变化极小（< 0.1%），套利空间不足以覆盖 gas 成本；③使用区块高度而非时间戳，粒度为 1 区块；④所有参与者看到的时间戳相同（在区块出块后立即冻结）。

**代码异味**
灰色地带：存在时间戳依赖但费率更新粒度为 1 小时，虽然不如完美但相对较安全；或者 MEV 利用的收益极小（< 10 美元）。

## Low risk

**低风险场景**
- **粗粒度控制**：费率每小时或每天更新一次，同一区块内所有交易使用相同费率
- **区块高度**：使用 `block::block_height()` 或 `epoch::current_epoch()` 代替 `timestamp`
- **缓存机制**：费率在内存中缓存，仅在 EndBlocker 或类似机制中定期更新
- **小费率波动**：费率变化 < 0.5%，相对套利空间可忽略
- **社区监控**：异常的费率变化会被链下监控立即发现
- **锁定机制**：关键操作需 timelock，无法立即执行，削弱了 MEV 的时间优势

## Audit Checklist

- [ ] 检查所有涉及费用、奖励、利率计算的函数，识别 `timestamp::now_seconds()` 的使用
- [ ] 确认是否存在粒度控制机制（UPDATE_INTERVAL 等）
- [ ] 验证费率更新的频率是否足够低，防止同区块内的波动
- [ ] 检查是否使用了缓存机制，费率是否在区间内保持一致
- [ ] 评估费率变化幅度，计算潜在的 MEV 利用空间
- [ ] 检查是否存在权限控制，仅特定账户可更新费率
- [ ] 执行单元测试，模拟时间戳变化对费率的影响
- [ ] 验证 MEV 机器人是否可通过交易排序套利，计算潜在收益
- [ ] 检查是否有事件日志记录费率变化，便于链下监控

## References

- [Move Timestamp Module](https://github.com/aptos-labs/aptos-core/blob/main/aptos-move/frameworks/aptos-framework/sources/timestamp.move)
- [MEV and Ordering Vulnerabilities](https://arxiv.org/abs/1904.05234)
- [DeFi Fee Structures](https://docs.uniswap.org/concepts/protocol/fees)
