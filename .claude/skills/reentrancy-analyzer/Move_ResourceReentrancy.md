# Move 资源重入漏洞审计

## Details

**代码特征：**
资源转移流程中存在外部调用（跨模块函数调用、回调、事件触发），在资源状态变更前或变更中调用不可信代码，典型模式：

```move
public fun withdraw_and_callback<CoinType>(account: &signer, amount: u64, callback: address) {
    let coin = coin::withdraw<CoinType>(account, amount);  // 资源提取
    callback::execute(callback, &coin);                      // 外部调用 ⚠️
    // 状态更新在外部调用后或分散在多个步骤
}
```

**快速定位核心操作技巧（L2：跳读）：**
- 搜索关键函数：`withdraw`、`transfer`、`borrow_global_mut`、`move_from`、`move_to`
- 关注资源操作符：`<T: key>`、`<T: store>`、带 `Resource` 或 `Capability` 泛型的函数
- 追踪 `acquires` 声明：标记了全局资源访问的函数更易受影响
- 识别跨模块调用：函数签名中包含 `address` 参数且后续用于模块调用

**快速定位保护机制技巧（L3：逐行读）：**
- **L1（关键词扫描）** 检查是否存在：`assert!`、`abort`、`ReentrancyGuard`、`locked`、`flag` 等状态锁
- **L3（逐行读）** 验证 CEI 模式（Checks-Effects-Interactions）：
  - 检查：权限验证在最前
  - 状态变更：资源数量/余额更新在外部调用前完成
  - 交互：外部调用在最后
- **L4（跨模块追踪）** 对于 capability 模式，追踪 capability 的借用和返还逻辑，确认外部代码无法在持有期间重入原模块

## Classify

**漏洞研判标准：**
1. **确认漏洞：** 资源状态变更与外部调用交错，且无锁保护，攻击者可通过回调在不一致状态下重复操作（提取、铸造、销毁）导致资金损失或状态破坏
2. **误报场景：** 
   - 外部调用的模块是受信任的系统模块（如标准库、官方预言机）
   - 资源操作使用 Move 原生原子性保证（如单一 `transfer` 调用，无中间状态）
   - 存在有效的全局锁或重入标志，且锁在外部调用前设置
3. **代码异味：** 虽有保护但设计复杂，如锁逻辑分散、依赖多层 capability 传递、外部调用结果未验证

## Low risk

**低风险评级条件：**
1. **只读回调：** 外部调用仅执行日志记录、事件发射、查询操作，不修改共享状态
2. **受限权限：** callback 对象不具备操作核心资源的 capability，即使重入也无法执行敏感操作
3. **原子性保障：** 整个流程包裹在 Move VM 的事务原子性内，且无中间状态持久化（如使用临时局部变量）
4. **金额/次数限制：** 存在单次交易上限、冷却期、速率限制等二级防护措施，将损失控制在可接受范围

## 审计专业技巧与误报区分

### 真实漏洞特征识别

**真实重入漏洞的红旗信号：**

1. **状态分离模式（State Separation Anti-Pattern）**
   - 余额/数量更新与实际资源转移分离在多步骤
   - 示例：先记账 `user_balance[addr] -= amount`，再调用外部转账，外部调用再次申请提取时余额未减少
   - 审计关键：用依赖图追踪资源转移的各环节，找出与检查不同步的更新点

2. **Capability 持有期延长**
   - 函数获取可变引用后长期持有，期间调用不可信代码
   - 真实案例：获取 `borrow_global_mut<Balance>(addr)` 后在持有期内调用 callback，callback 通过另一路径获取同一资源引用（失败）
   - 关键：Move 的单引用规则阻止这类攻击，但如果使用不安全模式（特殊权限模块）可能绕过

3. **事件发射前状态变更**
   - 部分游戏/DeFi 合约在事件发射前修改状态，期间允许外部交互
   - 审计方法：按时间顺序列举 `emit Event`, `move_from`, `move_to` 的调用序列

**常见真实案例场景：**
- Diem/Aptos 的某些早期 AMM 实现：先将币从池转出，后才更新流动性储备（LP holders 可通过价格预言机回调重入套利）
- 跨链桥接：验证状态更新完成再调用外部验证器，验证器可能执行恶意流程

### 误报高频场景与区分技巧

**场景 1：受信任的系统模块调用**
- **误报信号：** `coin::transfer`, `aptos_framework::token::transfer` 等标准库函数
- **区分方法：**
  - 检查被调用模块的来源：是否为官方预编译模块（0x0, 0x1 命名空间）
  - 验证该模块是否在当前链的安全模块白名单中
  - 标准库函数本身是原子的，不会触发合约级重入
- **正确判断：** 标准库直接调用 → 低风险（仅需检查参数）

**场景 2：capability 权限隔离（真正的解决方案）**
- **误报信号：** 看似外部调用，但 callback 接收到的对象已被限制权限
  ```move
  public fun safe_withdraw<CoinType>(account: &signer, amount: u64) -> Coin<CoinType> {
      assert!(exists<WithdrawCapability<CoinType>>(signer::address_of(account)), E_NO_CAP);
      // 内部完成所有状态更新
      let coin = coin::withdraw<CoinType>(account, amount);
      // 只返回资源，不执行外部调用，调用者负责 callback
      coin
  }
  ```
- **区分要点：** 函数仅返回资源，不进行额外的交互；caller 获得资源所有权，任何后续操作由 caller 保证安全
- **正确判断：** 如果 callback 是传入的 address 参数但未被该函数调用 → 低风险

**场景 3：事务原子性保证**
- **误报信号：** 虽有外部调用，但在单个事务内所有副作用要么全成功要么全失败
  ```move
  public fun atomic_swap<T, U>(user: &signer, in_amount: u64, out_type: address) {
      // 所有状态变更在事务范围内，外部调用结果会影响整个事务的 commit/abort
      let out_coin = external_price_oracle::get_price(out_type);  // 外部调用
      let out_amount = calculate(in_amount, out_coin);
      if (out_amount == 0) abort E_INSUFFICIENT_RETURN;  // 外部数据影响，但不重入
      deposit<T>(user, in_amount);
  }
  ```
- **区分要点：** 检查外部调用的返回值是否影响后续状态变更；关键是调用顺序和错误处理
- **正确判断：** 外部调用仅用于获取参数/数据，返回后控制流不再涉及资源修改 → 中低风险

**场景 4：重入防护的假象（真实误报）**
- **常见错误：** 依赖局部变量标志而非全局状态锁
  ```move
  public fun fake_protected_withdraw(account: &signer, amount: u64) {
      let flag = false;
      if (!flag) {  // 这个检查无意义！flag 总是 false
          flag = true;
          let coin = coin::withdraw<CoinType>(account, amount);
          external_callback::notify(&coin);  // 重入风险依然存在
          flag = false;
      }
  }
  ```
- **区分要点：** 局部变量不能跨函数调用保存状态，真正的重入防护需要全局 `Mutex` 或 `ReentrancyGuard` 资源
- **审计方法：** 搜索 `let XXX_flag = ...` 的定义和使用范围，确认其作用域是否仅限函数内部

**场景 5：多签合约的假安全**
- **误报信号：** 函数声明需要多个签名者权限
  ```move
  public fun protected_transfer(signer1: &signer, signer2: &signer, amount: u64) {
      // 看似有权限检查保护
      assert!(is_authorized(signer1) && is_authorized(signer2), E_UNAUTH);
      external_callback::execute(signer1);  // 但 signer1 本身可能是攻击合约
  }
  ```
- **区分要点：** 多签要求降低单点风险，但不能完全消除重入；需要同时检查 signer 是否为攻击者可控的地址
- **正确判断：** 需要结合权限来源，而非仅看多签数量

### 审计流程检查表

**第一阶段：快速识别风险候选（30 秒）**
- [ ] 搜索关键词：`callback`, `execute`, `dispatch`, `hook` 的函数名
- [ ] 检查这些函数是否接收 `address` 参数用于跨模块调用
- [ ] 追踪参数在函数中的使用位置

**第二阶段：细致状态变更分析（2 分钟）**
- [ ] 绘制该函数的状态变更流程图（哪些 `move_from`, `move_to`, `borrow_global_mut` 调用）
- [ ] 标记外部调用的位置
- [ ] 验证所有资源相关的状态是否在外部调用前完成

**第三阶段：权限隔离确认（1 分钟）**
- [ ] 检查被调用的外部模块是否为官方标准库
- [ ] 如为自定义模块，追踪其实现，检查是否真的修改了共享状态
- [ ] 确认函数返回的资源是否具有完整权限或已被限制

**第四阶段：锁机制验证（1 分钟）**
- [ ] 若声称有重入保护，搜索 `Mutex`, `Lock`, `ReentrancyGuard` 等保护资源
- [ ] 验证锁的获取/释放是否覆盖整个临界区
- [ ] 检查是否存在死锁风险（获取多个锁时的顺序）

### 真实漏洞案例对标

**高危案例：Aptos DEX 初期设计**
```move
// 不安全的兑换实现
public fun swap<X, Y>(input_coin: Coin<X>, user: address) -> Coin<Y> {
    let input_amount = coin::value(&input_coin);
    // 1. 计算输出（可能调用外部预言机）
    let output_amount = calculate_output(input_amount);  // 外部调用风险
    // 2. 更新流动性池
    let pool = borrow_global_mut<Pool<X, Y>>(POOL_ADDR);
    pool.reserve_x += input_amount;
    // 3. 转移币给用户
    transfer_coin_to_user(user, coin::mint<Y>(output_amount));
    // 漏洞：step 1 和 2 之间有窗口，攻击者可在 callback 中再次调用 swap
}
```

**修复方案：检查-生效-交互（CEI）模式**
```move
public fun swap<X, Y>(input_coin: Coin<X>, user: address) -> Coin<Y> {
    // 检查：验证权限和参数
    let input_amount = coin::value(&input_coin);
    assert!(input_amount > 0, E_ZERO_AMOUNT);

    // 生效：所有状态变更在一处完成
    let pool = borrow_global_mut<Pool<X, Y>>(POOL_ADDR);
    let output_amount = pool.calculate_and_update(input_amount);
    pool.reserve_x += input_amount;
    pool.reserve_y -= output_amount;

    // 交互：外部调用放在最后，且结果不再影响状态
    coin::deposit<X>(POOL_ADDR, input_coin);
    coin::withdraw<Y>(POOL_ADDR, output_amount)
}
```

### 误报陷阱总结表

| 特征 | 真实漏洞 | 误报 | 区分方法 |
|------|--------|------|--------|
| 有外部调用 | ✓ | ✓ | 检查调用前后的状态一致性 |
| 涉及资源转移 | ✓ | ✓ | 验证所有转移在外部调用前完成 |
| 使用 callback 参数 | ✓ | ✓ | callback 是否被限制权限或仅读 |
| 有全局锁保护 | ✗ 风险低 | ✓ | 验证锁覆盖所有临界区 |
| 标准库函数调用 | ✗ 风险低 | ✓ | 确认是否为 0x0 或 0x1 命名空间 |
| 返回资源不再交互 | ✗ 风险低 | ✓ | 函数返回后是否有额外副作用 |
