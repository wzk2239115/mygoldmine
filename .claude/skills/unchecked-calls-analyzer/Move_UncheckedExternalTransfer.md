# Move: 未检查外部转账 (UncheckedExternalTransfer)

调用 `coin::transfer`, `aptos_account::transfer`, `0x1::aptos_coin::transfer` 等外部转账函数后，未捕获或断言执行结果，导致转账失败时业务逻辑继续执行，引发状态不一致。

## Details

**典型代码模式：**

```move
public entry fun withdraw_reward(account: &signer) {
    let addr = signer::address_of(account);
    let amount = get_user_reward(addr);
    
    // 危险：未检查转账是否成功
    coin::transfer<AptosCoin>(account, TREASURY, amount);
    
    // 状态已更新，但转账可能失败
    clear_user_reward(addr);
}
```

**快速定位核心操作 (L2-跳读):**  
- 扫描 `coin::transfer`, `aptos_account::transfer`, `account::transfer_coins`
- 定位跨账户资金移动：`withdraw`, `send_to`, `payout`, `distribute`
- 关注函数调用后立即修改状态的模式（余额清零、状态变更）

**快速定位保护机制 (L3-逐行读):**  
- 检查转账调用是否在 `assert!()` 内或紧跟断言
- 确认是否使用 `try-catch` 或 `acquires` 注解进行资源检查
- 验证是否先扣除余额再执行转账（Check-Effects-Interaction 模式）
- 检查是否通过 `coin::balance<T>()` 验证转账前后余额差

## Classify

**漏洞条件：**  
1. 状态变更依赖转账成功（如余额清零、权限变更）
2. 转账失败不回滚状态，导致资金损失或权限错乱
3. 外部合约调用失败时无异常处理

**误报判定：**  
1. 转账前已通过 `coin::balance()` 预检查，且失败自动 abort
2. 使用 `transfer_coins` 系列函数，内部已包含断言
3. 转账失败不影响核心业务逻辑（如日志记录、统计更新）

**代码异味：**  
1. 转账成功但未更新关键状态（遗留债务）
2. 多次转账但只检查最后一次结果

## Low risk

- 转账金额为 0 或极小值（测试/演示代码）
- 转账目标为合约自身账户（内部转移）
- 存在上层事务机制保证原子性（Move VM 自动回滚）
- 调用的外部函数已声明 `aborts_if` 条件，确保失败时中断
- 转账前通过 `coin::is_account_registered()` 验证接收方有效性

## 审计专业技巧

### 1. 真实漏洞特征识别

**典型真实漏洞案例（Aptos生态）：**

**案例 A：奖励系统的状态不一致**
```move
// 真实漏洞：分发失败但积分已扣
fun claim_batch_rewards(signer: &signer, recipients: vector<address>, amounts: vector<u64>) {
    assert!(recipients.length() == amounts.length(), ERR_LENGTH_MISMATCH);

    let i = 0;
    while (i < recipients.length()) {
        let amount = vector::borrow(&amounts, i);
        let recipient = vector::borrow(&recipients, i);

        // 风险：无条件修改状态，但转账可能abort
        coin::transfer<RewardToken>(signer, *recipient, *amount);
        decrement_user_points(signer, *amount);  // 已经扣除，转账失败则丢失

        i = i + 1;
    }
}
```
**此为真实漏洞**：虽然 `coin::transfer` 失败会abort整个交易，但如果使用 `try-catch` 包装，转账失败时状态已改变。

**案例 B：跨模块调用的隐性失败**
```move
// 真实漏洞：委托转账未验证
fun stake_and_delegate(account: &signer, amount: u64, pool: address) acquires StakingPool {
    let stake_table = borrow_global_mut<StakingPool>(pool);
    table::upsert(&mut stake_table.stakes, signer::address_of(account), amount);

    // 风险：coin::transfer 可能由于目标地址权限失败，但状态已改变
    coin::transfer<AptosCoin>(account, pool, amount);
}
```
**真实漏洞原因**：Aptos中 `coin::transfer` 在目标地址未注册token时会abort，但状态变更已生效。

### 2. 高效审计排查流程

**第一层筛选（快速排除9成的非问题）：**
1. **搜索转账函数调用模式**：`coin::transfer`, `aptos_account::transfer` 出现位置
2. **检查调用者权限**：判断是否为 `entry fun` 或公开函数（私有函数通常已有上层保障）
3. **追踪返回值使用**：是否有 `let _ = transfer()`（显式忽略）或完全未使用

**第二层深度分析（针对可疑点）：**
```move
// 审计检查清单：
// ✓ 转账前：检查余额、权限、接收方地址合法性
// ✓ 转账调用：是否在 assert!() 中 / try-catch 中 / 无保护
// ✓ 转账后：是否立即修改关键状态（如清空余额表、权限变更）
// ✓ 上下文：是否存在 acquires 关键字确保资源一致性
```

### 3. 真实漏洞 vs 误报区分标准

| 判定维度 | 真实漏洞 | 误报特征 |
|---------|--------|--------|
| **转账后的状态变更** | 修改核心资产数据（余额、权限、配置）| 只更新日志、统计、事件 |
| **转账失败的影响** | 资金卡死、权限错乱、双花 | 交易自动abort，无后续影响 |
| **执行上下文** | entry func 或跨模块public调用 | 内部私有函数，上层已验证 |
| **错误处理机制** | 无异常处理，或try-catch后仍执行状态变更 | try-catch后仅记录日志 |
| **接收方验证** | 无验证或仅检查addr有效性 | 事先通过 `is_account_registered()` 验证 |

### 4. 常见误报陷阱

**误报案例 1：内部转账被误判**
```move
// 不是漏洞：内部模块间转移
fun internal_rebalance(from: address, to: address, amount: u64) {
    // 虽然无返回值检查，但发送者和接收者都是合约地址（已注册）
    // 且核心业务逻辑不依赖此转账（只是账户间调度）
    coin::transfer<ManagedToken>(get_contract_signer(), to, amount);
}
```
**为何不报告**：合约控制的地址间转移，即使失败也能通过重试恢复，非资金损失路径。

**误报案例 2：防御性编程被误判**
```move
// 不是漏洞：二次检查模式
fun withdraw_with_safeguard(account: &signer, amount: u64) acquires Balance {
    let user_balance = borrow_global_mut<Balance>(signer::address_of(account));
    assert!(user_balance.coin >= amount, ERR_INSUFFICIENT_BALANCE);

    // 虽然无显式assert，但前置检查 + acquires 保证资源一致性
    coin::transfer<AptosCoin>(account, SAFE_WALLET, amount);

    user_balance.coin = user_balance.coin - amount;
}
```
**为何不报告**：`acquires` 声明确保资源锁定，转账失败会自动abort且回滚整个函数。

### 5. 现场审计高危信号（必须深入调查）

| 信号 | 优先级 | 检查方式 |
|------|--------|--------|
| 转账调用后紧跟 `move_from<>()` 或 `destroy<>()` | 🔴 P0 | 检查是否破坏关键资源 |
| 多个转账但仅最后一个有检查 | 🔴 P0 | 逐行追踪每个转账结果 |
| 转账在循环内，失败不break | 🟡 P1 | 验证循环逻辑是否容错 |
| 转账前检查余额，但转账后不更新状态 | 🟡 P1 | 判断是否存在债务 |
| entry函数直接调用transfer，无权限检查 | 🟡 P1 | 验证访问控制 |

### 6. 审计工具链与技巧

**静态分析工具使用：**
- **Move Prover**：`aborts_if` 前置条件验证，确认转账失败是否会abort整个函数
- **代码审计查询**：`grep -n "coin::transfer\|aptos_account::transfer" *.move` 快速定位所有转账点
- **符号执行**：追踪转账失败路径，确认是否存在非法状态组合

**手工审计技巧：**
1. 为每个 `transfer` 调用标记「是否被assert()包裹」
2. 绘制状态机图：转账前→转账中→转账后，标记每个阶段的状态版本
3. 反向追踪：从状态变更点回溯到转账调用，验证因果关系
