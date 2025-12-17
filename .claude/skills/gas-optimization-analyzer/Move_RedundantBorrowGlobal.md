# Move_RedundantBorrowGlobal

**Gas 优化：冗余 borrow_global**  
多次借用同一全局资源但未缓存引用，导致重复的存储访问开销。常见于资源转移、capability 管理、跨函数调用场景。

## Details

**代码示例：**
```move
public fun process_order(addr: address) acquires Market, OrderBook {
    let market = borrow_global<Market>(addr);
    let price = market.price;
    
    // ... 中间逻辑 ...
    
    let market_again = borrow_global<Market>(addr); // 冗余借用
    let fee = market_again.fee;
}
```

**快速定位核心操作（L2：跳读）**
- 扫描 `borrow_global` 和 `borrow_global_mut` 关键字出现频率
- 检查函数内同一地址参数的多次借用
- 关注 `acquires` 声明与实际借用次数的对应关系
- 追踪临时变量的作用域，查看引用是否被提前丢弃

**快速定位保护机制（L1：关键词扫描）**
- 查找是否存在引用缓存变量（如 `let resource_ref = &...`）
- 检查是否使用 `let` 绑定来延长引用生命周期
- 确认条件分支是否复用同一引用而非重新借用
- 扫描函数签名中的 `&` 参数传递，避免内部重复借用

## Classify

**漏洞判定标准：**
- 同一函数内对相同地址+类型的资源重复 `borrow_global` ≥2 次
- 前一次借用的引用在作用域内仍可访问，但未复用
- 无中间状态修改（如 `move_to`/`move_from`）导致的必要重新借用

**误报场景：**
- 两次借用间有 `move_from` 或结构体字段所有权转移
- 跨 `assert!` 异常处理边界的重新借用（确保状态一致性）
- 不同条件分支中互斥的借用路径

**代码异味：**
- 借用次数=2 且函数简短（<20行），优化收益不明显但建议修改
- 跨多个辅助函数的隐式重复借用，需重构为传引用

## Low risk

**低风险评级条件：**
1. **低频调用路径**：仅在初始化、管理员操作或罕见异常处理中触发
2. **微小gas开销**：冗余借用≤2次 且 资源结构体字段数≤3
3. **明确设计权衡**：为代码可读性或安全边界检查故意采用的重复借用
4. **临界作用域**：两次借用间隔跨越 `if/else` 大分支，缓存引用会导致借用检查器复杂度上升
5. **不可变借用**：仅涉及 `borrow_global` 而非 `borrow_global_mut`，且无并发资源竞争风险

## 审计专业技巧

### 真实漏洞的特征识别

**1. 高置信度漏洞特征（需立即标记）**

- **连续同址高频借用**：在热路径（交易主流程）中相同资源地址连续借用≥3次，无逻辑屏障
  ```move
  public fun swap(user: address) acquires Pool, UserAccount {
      let pool1 = borrow_global_mut<Pool>(POOL_ADDR);  // 借用1
      let bal1 = pool1.balance;

      let user_acc = borrow_global_mut<UserAccount>(user);
      user_acc.execute_swap(&pool1);

      let pool2 = borrow_global_mut<Pool>(POOL_ADDR);  // 借用2（冗余）
      pool2.update_state();  // 借用3（冗余）
  }
  ```

- **可变借用重复**：`borrow_global_mut` 多次针对同一资源，存在修改不一致风险

- **跨越事件发射的重复借用**：在 `event::emit` 前后重新借用，可能导致状态不同步

**2. 成本分析模型**

实际gas损耗 = 存储读取成本 × 借用次数 × 调用频率

- 高频函数（每块>100次调用）：冗余借用×3 = 明显影响链性能
- 中等频率（10-100次）：≥4次冗余借用才构成漏洞等级问题
- 低频操作：优化收益 < 代码复杂性增加的成本

### 常见误报陷阱与区分技巧

**误报类型1：受控的re-borrow（不是漏洞）**

```move
public fun safe_transfer(from: address, to: address) acquires Balance {
    // 第一次借用：验证余额
    let from_balance = borrow_global_mut<Balance>(from);
    assert!(from_balance.amount >= AMOUNT, ERR_INSUFFICIENT);
    from_balance.amount -= AMOUNT;
    drop(from_balance);  // 显式释放，解除借用约束

    // 第二次借用：写入接收端
    let to_balance = borrow_global_mut<Balance>(to);
    to_balance.amount += AMOUNT;
}
```
**判断标准**：存在显式 `drop()` 或作用域边界（`}`）时，两次借用之间已断开依赖，不是冗余

**误报类型2：跨分支互斥路径**

```move
public fun conditional_access(addr: address) acquires Resource {
    let resource = if (condition) {
        borrow_global_mut<Resource>(addr)  // 路径A
    } else {
        borrow_global_mut<Resource>(addr)  // 路径B（不是冗余，条件互斥）
    };
    // 使用resource
}
```
**判断标准**：控制流分析，确认借用在 `if/else` 的不同分支中，只有一条执行路径会运行

**误报类型3：所有权转移导致的必要re-borrow**

```move
public fun process_with_move(addr: address) acquires Table {
    let entry = borrow_global_mut<Table>(addr);
    let data = move entry.data;  // 所有权转移，原引用失效

    // 必须重新借用来修改table本身
    let new_entry = borrow_global_mut<Table>(addr);
    new_entry.metadata = update_metadata();
}
```
**判断标准**：检查资源字段是否被 `move` 关键字转移所有权，转移后原引用作用域已结束

### 审计检查清单

| 检查项 | 确认方法 | 权重 |
|------|--------|------|
| **引用缓存可行性** | 检查两次借用间是否修改了资源结构体本身的成员（非转移） | 高 |
| **借用互斥性** | 追踪借用变量的生命周期，确认前一个引用是否仍在作用域 | 高 |
| **资源大小影响** | 资源结构体字段数×借用次数，>100字段视为显著优化机会 | 中 |
| **调用频率影响** | 通过事件日志或模拟估算函数日均调用量 | 中 |
| **异常处理边界** | 检查 `assert!` 和 `abort` 之间的借用，确认是否需要重置 | 低 |

### 真实案例区分

**✓ 真实漏洞（应该修复）**
```move
// Diem Move漏洞：账户初始化时重复借用
public fun init_account(account: &signer) acquires AccountStore {
    let acc_store = borrow_global_mut<AccountStore>(signer::address_of(account));
    acc_store.created_at = now();

    let acc_store2 = borrow_global_mut<AccountStore>(signer::address_of(account));
    acc_store2.version += 1;  // 可以缓存acc_store直接修改
}
```

**✗ 误报（不需修复）**
```move
// Aptos CoinStore：允许借用来获取独立引用以支持嵌套调用
public fun transfer<CoinType>(from: address, to: address) acquires CoinStore {
    let from_coin = borrow_global_mut<CoinStore>(from);
    let amount = from_coin.balance.value;

    execute_burn(from_coin);  // 内部函数借用了from_coin

    // 必须重新借用，因为execute_burn消耗了引用
    let from_coin_new = borrow_global_mut<CoinStore>(from);
    from_coin_new.version += 1;
}
```
