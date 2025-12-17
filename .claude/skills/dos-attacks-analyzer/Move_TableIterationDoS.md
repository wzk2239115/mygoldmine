# Move_TableIterationDoS

**漏洞概述**  
在 Move 智能合约中，对 `Table`、`SmartTable` 等全局存储结构进行无限制遍历时，因 Gas 消耗超限导致交易失败，造成合约功能不可用。

## Details

**代码特征示例：**

```move
// 危险模式：无界遍历 Table
public entry fun process_all_users(account: &signer) acquires UserRegistry {
    let registry = borrow_global_mut<UserRegistry>(@contract);
    let users = &mut registry.users;
    
    // 遍历整个 Table，用户数量不可控
    table::for_each_ref(users, |addr, user| {
        // 处理每个用户...
        update_user_state(user);
    });
}

// 危险模式：批量操作未限制数组长度
public entry fun batch_mint(recipients: vector<address>, amounts: vector<u64>) {
    let len = vector::length(&recipients);
    let i = 0;
    while (i < len) {  // 未限制 len 上限
        mint_to(*vector::borrow(&recipients, i), *vector::borrow(&amounts, i));
        i = i + 1;
    }
}
```

**快速定位核心操作（L2 跳读）：**
- 关注 `table::for_each*`、`smart_table::for_each*` 等遍历函数
- 检查 `while` / `loop` 循环是否处理 Table/Vector 且缺少上限检查
- 定位 `vector::length()` 后的循环，查看长度来源是否受控
- 搜索 `borrow_global` + 迭代操作的组合模式

**快速定位保护机制（L3 逐行读）：**
- 验证是否存在 `assert!(len <= MAX_BATCH_SIZE, E_EXCEEDS_LIMIT)` 类长度断言
- 检查是否采用分页机制：`start_index`、`end_index`、`page_size` 参数
- 确认是否使用 `break` 或计数器限制迭代次数
- 查看函数权限：若仅 `admin` 可调用且文档明确风险，可降级风险等级

## Classify

**漏洞判定标准：**
- 公开函数中对动态大小集合（Table/Vector）进行完整遍历，且集合大小由外部输入或公开可增长
- 循环内存在复杂计算、跨合约调用、事件发射等高 Gas 操作
- 无明确上限限制或分页机制

**误报场景：**
- 遍历的集合大小由常量定义且小于合理阈值（如 `const MAX_ITEMS: u64 = 10`）
- 遍历仅在合约初始化等一次性操作中出现
- 已实现分页逻辑但审计工具未识别（需人工复核）

**代码异味：**
- 存在上限检查但阈值设置过高（如 1000+），可能在极端情况下仍触发 Gas 限制
- 管理员函数中的无界遍历（虽权限受限，但操作失败仍影响治理）

## Low risk

**低风险评级条件：**
- 仅 `admin`/`owner` 权限可调用，且项目方已明确知晓风险并接受（需书面确认）
- 集合大小受业务逻辑严格约束，理论上限远低于 Gas 上限（如固定成员数的白名单）
- 存在紧急暂停机制（`pause` 功能），可在发现问题时快速止损
- 链配置的 Gas 上限极高，且经压力测试验证当前数据规模下不会失败（需提供测试报告）
- 已实现分页接口但未强制使用，存在降级为全量调用的风险（建议移除全量接口）

## 审计专业技巧

### 真实漏洞 vs 误报的区分体系

**第一层：集合来源分析**
- **真实漏洞信号**：集合由 `borrow_global` 直接获取且未做长度校验，或参数为调用者传入的向量/数组
- **可能误报**：集合是常量结构（如 `const TOKENS: vector<address> = vector[...]`）或在编译时已确定大小
- **实战经验**：检查该集合是否在其他地方有增删操作，若从不修改则遍历成本有限

**第二层：循环成本评估**
- **高成本操作识别**：`coin::transfer()`、`token::transfer()`、事件发射、跨合约调用（任何有 `acquires` 的外部函数）
- **低成本操作**：纯计算、内存读写、简单的赋值操作
- **审计建议**：计算单次迭代的理论 Gas 成本（查看链的 Gas 计价表），乘以可能的最大迭代次数
  ```
  理论成本 = 单次迭代 Gas × 最大集合大小
  若 > 链 Gas 上限的 80%，则为真实高风险
  ```

**第三层：上限控制机制识别**
- **显式上限**：`assert!(vector::length(&input) <= 100, E_TOO_MANY_ITEMS)`
- **隐式上限**：
  - 集合由固定初始值定义，且程序逻辑确保不增长
  - 使用 `remove` 操作多于 `push` 操作，导致集合趋于缩小
  - 仅在私有函数中调用，由上层公开函数做限制（需追踪调用链）
- **分页机制**：参数中包含 `start: u64, page_size: u64`，且 `page_size` 受约束

**第四层：权限与时间限制**
- **权限判定**：
  - 若仅 `admin` 可调用：询问是否存在 admin 密钥管理规范，单签还是多签
  - 若 `public` 但需付费（如 `0x1::coin::withdraw` 在函数内）：成本本身成为制约
- **时间限制**：某些链的区块或交易有超时机制，理论上限就是超时时间

### 常见误报案例

**案例1：固定大小的白名单遍历**
```move
// 误报：虽有遍历但大小固定
struct Whitelist {
    addresses: vector<address>,  // 最多 10 个
}

public fun validate_all(whitelist: &Whitelist, addr: address): bool {
    table::for_each_ref(&whitelist.addresses, |_, item| {
        if (*item == addr) return true;
    });
    false
}
```
**判定方法**：查看 `Whitelist` 的创建函数，确认是否有 `assert!(len <= 10)` 或注释说明。若文档明确承诺 10 个成员的上限，此非漏洞。

**案例2：链上回调导致的假遍历**
```move
// 可能误报：看似无界，实际受制约
public fun process_requests(requests: vector<Request>) {
    for_each(requests, |req| {
        execute_callback(&req);  // 回调可能失败
    });
}
```
**判定方法**：检查 `execute_callback` 的实现，若其包含 `abort_if_insufficient_funds` 等守卫，则在资金耗尽时自动停止，实际并非无限遍历。

**案例3：分页逻辑隐藏在模块内部**
```move
// 容易误报：表面上的全遍历
public fun aggregate_stats(): Stats {
    let all_data = borrow_global<GlobalData>(@module);
    iterate_with_limit(&all_data.table, 1000)  // 内部有上限
}

fun iterate_with_limit(table: &Table, max: u64): Stats {
    let count = 0;
    table::for_each_ref(table, |_, item| {
        if (count >= max) break;
        count = count + 1;
        // 处理...
    });
}
```
**判定方法**：必须深入私有函数查看，不能仅从公开 API 推断。搜索所有直接调用该公开函数的地方。

### 实战审计检查清单

1. **快速筛查**（5 分钟）
   - 搜索 `for_each`、`while`、`loop` 关键字
   - 定位是否处理外部可控的集合

2. **深度分析**（15 分钟）
   - 追踪集合的来源：谁写入，谁删除，最大值是多少
   - 计算单次迭代的 Gas 成本：统计函数内调用的高成本操作数
   - 验证上限控制：断言、参数限制、分页

3. **风险度量**（10 分钟）
   - 评分：低（<100次迭代 × 低成本）、中（100-1000次 或 高成本）、高（>1000次 且 高成本）
   - 结合权限：公开高危 > 管理员中危 > 内部低危

4. **误报排除**
   - 查看 Git 历史，确认是否已知风险
   - 与项目方确认集合大小的真实上限
   - 要求提供压力测试报告（如何）

### 链特定的 Gas 参数参考

| 链        | Gas 上限 | 单次 transfer | 事件成本 | 建议最大迭代数 |
|----------|---------|--------------|---------|--------------|
| Aptos    | 4M      | ~1000        | ~100    | 1000-2000    |
| Sui      | 10M     | ~2000        | ~200    | 2000-3000    |
| Movement| 3M      | ~800         | ~80     | 500-1000     |

**应用方法**：若审计函数在单次迭代中有 2 次 transfer 和 3 次事件发射，成本约 2300 Gas/次，则 1000 次迭代需 2.3M，超过多数链的阈值 80% 线。
