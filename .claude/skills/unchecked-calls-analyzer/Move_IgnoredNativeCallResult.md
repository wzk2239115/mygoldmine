# Move_IgnoredNativeCallResult

**漏洞类型**：未检查 Native 调用结果

**常见场景**：与外部模块交互或使用 `native` 函数调用系统资源时，包括但不限于 `coin::transfer`、`aptos_framework::account`、`table` 操作、事件发射等跨账户或跨模块操作未验证执行结果。

## Details

**代码示例**：

```move
public entry fun withdraw(account: &signer, amount: u64) {
    let addr = signer::address_of(account);
    // 未检查 transfer 返回值，可能静默失败
    coin::transfer<AptosCoin>(account, @recipient, amount);
    // 后续逻辑假设转账成功继续执行
    update_balance(addr, amount);
}

public fun register_resource(account: &signer) {
    // 未检查 move_to 是否成功
    move_to(account, UserData { value: 0 });
    emit_event(&mut global_events, RegisterEvent {});
}
```

**快速定位核心操作**（L2-L3）：
- 扫描 `coin::transfer`、`coin::withdraw`、`account::create_signer_with_capability` 等 native 调用点
- 检查 `move_to`、`move_from`、`borrow_global_mut` 等资源操作是否在 `try-catch` 或条件判断中
- 关注返回 `bool` 或 `Result<T, E>` 类型的 native 函数是否被赋值或 `assert` 验证
- 使用正则搜索：`(coin::|account::|table::)\w+\([^)]+\);(?!\s*(assert|let|if))` 定位未处理返回值的调用

**快速定位保护机制**（L2-L3）：
- 查找 `assert!(result, error_code)` 或 `abort` 语句紧随 native 调用
- 检查是否使用 `try` 宏包裹（Aptos Move 部分支持）：`try! { ... }`
- 验证是否通过 `acquires` 声明明确资源依赖并配合前置检查：`exists<T>(addr)`
- 审查是否有全局状态回滚机制或事务性保证（Move 本身不支持手动回滚，依赖虚拟机）

## Classify

**漏洞判定**：
- Native 调用失败会导致后续逻辑基于错误状态执行（如余额更新、权限变更）
- 资源操作失败但程序继续执行可能导致双花、权限绕过或状态不一致
- 跨合约调用返回值被忽略，攻击者可利用失败回退进行重入或状态攻击

**误报识别**：
- Native 函数已通过 `abort` 机制保证失败时自动中断（如 `coin::withdraw` 内部会 abort）
- 调用后立即有显式 `assert` 或 `abort` 验证相关状态
- 调用的 native 函数文档明确标注为"infallible"（不会失败）

**代码异味**：
- 返回值被忽略但通过其他状态变量间接验证（降低可读性）
- 过度依赖 Move VM 的隐式错误处理而非显式检查
- 缺少错误码或错误消息的 `abort`，难以追踪失败原因

## Low risk

**低风险场景**：
- Native 调用失败后 Move VM 自动回滚整个交易，无持久化副作用
- 调用的是只读 native 函数（如 `vector::length`、`signer::address_of`），不影响状态
- 操作针对 view 函数或测试代码，不在关键路径中
- 已通过模块级 `acquires` 和前置 `exists` 检查保证资源可访问性
- 失败场景被明确文档化且业务逻辑允许静默失败（如可选的事件发射）

## 审计专业技巧

### 实战区分真实漏洞与误报

#### 1. 调用上下文分析法
**核心思路**：不只看单行代码，分析调用前后的完整业务流程。

**真实漏洞特征**：
- `coin::transfer` 后紧跟数据库更新（如 `update_balance`），未验证转账成功
- 多步骤操作中间步失败，后续步骤仍基于前一步成功的假设继续执行
- 跨模块调用返回值被忽略，但调用方据此修改关键状态（如权限位、余额）
- 事件发射失败不影响业务流程，但导致链下系统与链上状态不同步

**误报特征**：
- 调用失败时 Move VM 会 abort，无法继续到后续代码
- 操作仅为日志/事件发射，无关键状态修改
- Getter 类只读操作，返回值若被忽略也不改变状态

#### 2. Native 函数特征分析法
**关键清单**（应记住常见 native 函数的失败行为）：

| 函数 | 失败行为 | 处理方式 |
|------|--------|--------|
| `coin::transfer` | 返回 false 或 abort | 需检查返回值或 catch |
| `coin::withdraw` | abort（有余额检查） | 通常安全，但需核对版本 |
| `table::add` | abort（重复 key） | 需 `contains` 前置检查 |
| `move_to` | abort（资源已存在） | 需 `!exists` 检查 |
| `move_from` | abort（资源不存在） | 需 `exists` 检查 |
| `borrow_global_mut` | abort（资源不存在） | 需 `exists` 前置检查 |
| `event::emit` | 失败不 abort | 可安全忽略（链下影响） |

**审计要点**：查阅该 Move 框架版本的官方文档确认 abort vs return false 行为。

#### 3. 状态一致性追踪法
**流程**：
1. 标记所有涉及外部操作的 native 调用
2. 追踪这些调用的返回值或副作用影响范围
3. 检查失败场景下状态机是否处于一致状态

**实例**：
```move
// 高风险：转账未验证，后续修改数据库
coin::transfer<AptosCoin>(from, to, amount);  // ❌ 未检查
update_user_balance(to_addr, amount);          // 基于转账成功假设

// 低风险：操作本身有失败保证
let balance = coin::withdraw<AptosCoin>(account, amount);  // abort if fail
update_user_balance(addr, amount);  // 安全：前面 abort 了
```

#### 4. 代码审视速查表

| 问题类型 | 高危特征 | 快速检测 |
|--------|--------|--------|
| 转账后修改余额 | 无 assert/check | grep: `coin::transfer.*update_balance` |
| 资源操作不安全 | 无 exists/contains 检查 | grep: `move_to/move_from` 前后行 |
| 权限变更未验证 | 权限操作后无 assert | grep: `permission.*=.*native_call()` |
| 跨合约返回值忽略 | 冒号结尾+新语句 | grep: `\)[;:]` 后接赋值语句 |

### 常见误判陷阱与对策

#### 陷阱 1：误认为所有 native 调用都会 abort
**错误思路**：看到 `native_call();` 就报告，假设一定会失败且 abort。

**纠正方法**：
- 查 Aptos 官方 stdlib 源码，确认该函数是否有显式 `abort` 还是返回 `bool`/`Result`
- `coin::transfer` 在不同版本行为不同，需版本检查
- 优先查官方 API 文档或源代码注释

#### 陷阱 2：误认为有 try-catch 就安全
**错误思路**：看到 `try!` 或 try-catch 就认为已处理，不审查 catch 块。

**纠正方法**：
- 检查 catch 块的实际处理逻辑，是否只是吞掉异常（antipattern）
- 验证 abort 后的状态回滚是否完整（Move 通常自动回滚）
- 区分"异常被捕获"和"错误被处理"

#### 陷阱 3：忽视操作顺序问题
**错误思路**：分别看每条语句，不关注执行顺序。

**纠正方法**：
```move
// ❌ 高风险：先扣余额后转账
update_balance(addr, amount);
coin::transfer(account, recipient, amount);  // 失败时已修改了 balance

// ✓ 安全：先转账（失败自动 abort）后扣余额
coin::transfer(account, recipient, amount);  // abort if fail
update_balance(addr, amount);
```

#### 陷阱 4：对"跨合约调用"的理解不足
**错误思路**：所有跨模块 native 调用都视为高风险。

**纠正方法**：
- Aptos 框架的 coin/account/table 操作已被广泛审计，内部有完善的 abort 机制
- 关键是**调用方**是否正确处理失败
- 第三方合约（非官方框架）的 native 调用才是重点审查对象

### 实战案例

**案例 1：真实漏洞**
```move
public fun swap(user: &signer, amount_in: u64) {
    let coin = coin::withdraw<USDC>(user, amount_in);  // ✓ 内部 abort
    let amount_out = calculate_output(amount_in);
    coin::transfer<USDT>(user, @DEX, coin);            // ❌ 返回 bool，未检查！
    // 如果转账失败，calculate_output 已基于假设执行
    update_user_swap_count(user);  // 状态已修改
}
```

**案例 2：误报示例**
```move
public fun emit_trade_log(from: address, to: address, amount: u64) {
    // ✓ 安全：event::emit 失败不影响业务，只是链下丢失日志
    event::emit(TradeEvent { from, to, amount });
}
```

### 审计检查清单
- [ ] 是否有 native 调用直接后跟状态修改，未验证返回值
- [ ] 跨模块调用失败时，前置状态是否已修改（不可回滚）
- [ ] 权限/金额相关操作是否有对应的 assert 或 exists 检查
- [ ] try-catch 块的 catch 分支是否仅吞异常（需标记为审计注释）
- [ ] 多步操作中，关键操作的顺序是否正确（先通过原子操作，后修改状态）
- [ ] 官方框架函数行为是否与代码注释一致（版本相关性）
