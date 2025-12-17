# Move 闪电贷 - 资源销毁未确认漏洞

**漏洞概述**
Aptos/Sui 闪电贷实现中，在偿还阶段仅检查 `Coin` 资源是否存在和销毁，但未验证销毁量与借出量的一致性。攻击者可通过 `coin::split` 拆分 Coin，仅归还部分金额，剩余代币逃逸，导致闪电贷协议资金损失。

## Details

**代码示例特征**
```move
module flash_loan {
    use aptos_framework::coin::{Self, Coin};

    /// 闪电贷结构：应该是 drop 和 copyable 的，强制在同一交易内使用
    struct FlashLoanReceipt<phantom T> {
        amount: u64,
        borrowed_at: u64,
    }

    // 危险：FlashLoanReceipt 未声明 drop/copy，但逻辑上应该是 drop 的
    // 或者 drop ability 存在但 repay 时未强制检查金额

    public fun borrow<T>(
        pool: &mut LiquidityPool<T>,
        amount: u64,
    ): (Coin<T>, FlashLoanReceipt<T>) {
        let coin = coin::extract(&mut pool.reserve, amount);
        let receipt = FlashLoanReceipt { amount, borrowed_at: timestamp::now_seconds() };
        (coin, receipt)
    }

    // 危险的偿还函数：仅检查 Coin 存在性，未验证金额
    public fun repay<T>(
        pool: &mut LiquidityPool<T>,
        payment: Coin<T>,
        receipt: FlashLoanReceipt<T>,
    ) {
        // 致命漏洞点 1：仅获取 coin 的价值，但未与 receipt.amount 比较
        let payment_amount = coin::value(&payment);

        // 致命漏洞点 2：即使检查金额，也可能被拆分 Coin 绕过
        // 攻击者可以：
        // 1. 借入 100 个 Coin
        // 2. 通过 coin::split 拆分为 50 + 50
        // 3. 偿还其中 50 个 Coin（满足 value 检查）
        // 4. 另外 50 个 Coin 在交易后期被攻击者转走

        assert!(payment_amount == receipt.amount, EInsufficientRepayment);

        coin::merge(&mut pool.reserve, payment);

        // receipt 虽然被销毁（implicit drop），但无法验证所有 Coin 都被归还
    }

    // 缺陷：如果 receipt 包含 drop ability，则可被任意丢弃，无法强制归还
    // 缺陷：即使没有 drop，repay 中也未彻底验证借出与归还的一致性
}

// 攻击者代码示例：
script {
    use flash_loan::FlashLoan;
    use aptos_framework::coin;

    fun exploit() {
        // 1. 借出 100 个代币
        let (loan, receipt) = FlashLoan::borrow<USDC>(&mut pool, 100);

        // 2. 拆分借来的 Coin
        let (repay_coin, attacker_coin) = coin::split(&loan, 50);

        // 3. 合并归还部分：虽然调用 repay，但实际只还 50
        // 4. 剩下的 50 个代币在攻击者控制下
        FlashLoan::repay<USDC>(&mut pool, repay_coin, receipt);

        // 5. 攻击完成，attacker_coin（50 个代币）已获得
        // 原本应该归还的 50 个代币被攻击者保留
    }
}
```

**快速定位核心操作**（审计等级：**L3-逐行读**）
- 关键函数：`borrow`, `repay`, `repay_with_interest` 等闪电贷相关函数
- 定位技巧：检查 `FlashLoanReceipt` 结构体的定义，查看是否声明了 `drop`, `copy`, `store` abilities
- 危险信号：repay 函数中仅检查 `coin::value()` 或 `coin::type_info()`，未与借出量精确比较
- Move 特性：搜索 `coin::merge`, `coin::extract`, `coin::split` 的使用，检查是否在 repay 中被完整验证

**快速定位保护机制**（审计等级：**L2-跳读**）
- 寻找借贷凭证机制：`FlashLoanReceipt` 是否被标记为 `drop: false`（强制消费）
- 寻找金额校验：repay 函数中是否有 `assert!(coin::value(&coin) == borrowed_amount, ...)`
- 寻找回调机制：是否通过回调函数方式强制原子性（Sui 的 `borrow -> callback -> repay` 模式）
- Move 专属：检查是否使用了 `Capability` 或 `Witness` 模式强制操作流程

## Classify

**漏洞判定**
满足以下条件组合即为高危漏洞：①FlashLoanReceipt 可被 drop 或 repay 中金额检查不完整；②Coin 可被通过 `split` 或其他方式部分偿还；③攻击者可在同一交易内保留部分借出的 Coin。

**误报识别**
以下场景非漏洞：①FlashLoanReceipt 不可 drop，必须通过 repay 消费，且 repay 中的金额校验严格（bit-perfect 比较）；②协议使用了 Witness 模式确保每笔借贷都必须通过认证的 repay 路径；③所有 Coin 操作都在原子事务内完成，中间任何 split 都会导致类型检查失败。

**代码异味**
灰色地带：repay 中虽有金额校验但通过 `>=` 而非 `==` 比较，允许偿还超额（虽然看似保守但可能隐藏设计缺陷）。

## Low risk

**低风险场景**
- **严格类型检查**：FlashLoanReceipt 中包含借贷时的 `Coin<T>` 类型 hash，repay 时必须提交完全相同的 Coin 类型和 amount，split 后的 Coin 类型会变化导致验证失败
- **Witness 模式**：借贷和偿还都需要特定的 Witness 凭证，攻击者无法伪造或部分使用
- **回调强制**：采用 Sui 的闪电贷标准库（`sui::balance::split` + 回调模式），框架层面强制原子性
- **审计锁定**：即使存在理论漏洞，但闪电贷池容量极小（< 1000 USDC）或单笔借贷上限被严格限制
- **多层校验**：repay 时除了验证金额，还验证 Coin 的铸造者地址、burn 时间戳等多个维度

## Audit Checklist

- [ ] 检查 FlashLoanReceipt 的 abilities 定义，确认 drop 为 false（如存在）
- [ ] 验证 borrow 函数中 receipt 和 Coin 的绑定关系
- [ ] 检查 repay 函数中的金额验证：是否使用 `==` 严格比较或 `>=` 宽松比较
- [ ] 追踪 Coin 在 borrow 后、repay 前的所有操作：split, merge, extract, deposit 等
- [ ] 验证是否有机制防止 Coin 被 split 后仅部分偿还（如类型变化检查）
- [ ] 检查是否使用了 Capability 或 Witness 模式强制偿还流程
- [ ] 执行单元测试，尝试 split Coin 后仅偿还部分的攻击场景
- [ ] 验证交易原子性：闪电贷的借贷-使用-偿还是否在单一交易内必须完成
- [ ] 检查是否有事件日志记录借贷和偿还的金额，便于链下监控

## References

- [Move Coin Module](https://aptos.dev/en/build/sdks/ts-sdk/reference/generated/index.html#coin)
- [Aptos Coin Standard](https://github.com/aptos-labs/aptos-core/blob/main/aptos-move/frameworks/aptos-framework/sources/coin.move)
- [Sui Balance Module](https://github.com/MystenLabs/sui/blob/main/crates/sui-framework/packages/sui-framework/sources/balance.move)
