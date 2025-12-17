**Move - 不必要的 Vector 操作**  
常出现在资源转移、能力（capability）管理、模块初始化、批量数据处理等业务逻辑实现中。表现为使用低效的 vector 操作（如频繁 push/pop、循环查找、重复遍历）而非更高效的数据结构（如 Table、SimpleMap）。

## Details

**代码示例：**
```move
// 反模式：频繁的 vector 遍历查找
public fun remove_user(addr: address) {
    let users = borrow_global_mut<UserList>(@admin);
    let len = vector::length(&users.list);
    let i = 0;
    while (i < len) {  // 每次删除都需 O(n) 遍历
        if (*vector::borrow(&users.list, i) == addr) {
            vector::remove(&mut users.list, i);
            break
        };
        i = i + 1;
    }
}

// 反模式：循环中反复 push/pop
public fun batch_process(items: vector<Item>) {
    let results = vector::empty<Result>();
    while (!vector::is_empty(&items)) {
        let item = vector::pop_back(&mut items);  // gas 累积消耗
        vector::push_back(&mut results, process(item));
    }
}
```

**快速定位核心操作技巧 (L2-跳读)：**
- 扫描 `vector::` 命名空间调用，重点关注循环体内的 `push_back`、`pop_back`、`remove`、`borrow`
- 定位 `while`/`loop` 配合 `vector::length` 的模式，检查是否为线性查找
- 搜索批量操作场景（`batch_`、`multi_`前缀函数），检查是否对每个元素都触发独立 vector 操作

**快速定位保护机制技巧 (L3-逐行读)：**
- 检查是否使用 `Table<K,V>` 或 `SimpleMap<K,V>` 替代 vector 做键值查找（O(1) vs O(n)）
- 验证是否有 `vector::length` 上限检查（如 `assert!(len <= MAX_SIZE, E_TOO_LARGE)`）
- 确认批量操作是否有 gas 优化设计（如预分配容量 `vector::empty_with_capacity`、批量借用）
- 查看是否避免在 storage 层面反复读写 vector（应先 borrow_global_mut 后批量修改）

## Classify

**漏洞判定：**
- 无界循环 + vector 线性查找且无 gas 上限保护 → 可导致交易 gas 耗尽，拒绝服务（DoS）
- 高频调用路径中的 O(n²) vector 嵌套循环 → 严重性能问题，经济攻击面

**代码异味判定：**
- 低频管理接口（如 admin 操作）使用 vector 线性查找 → 可接受但不优雅
- vector 长度始终 < 10 的固定场景 → 影响有限，优先级低

**误报排除：**
- vector 仅用于函数内部临时存储，不涉及 storage 层 → 非持久化场景，影响极小
- 已有明确长度限制（如 `MAX_VALIDATORS = 100`）且业务合理 → 风险可控

## 审计专业技巧

### 真实漏洞的明确特征

**特征 1：无界输入导致无限循环**
```move
// 危险！用户可控 items 长度，无上限检查
public fun process_items(items: vector<Item>) {
    let i = 0;
    while (i < vector::length(&items)) {
        // 用户提交 10000 个元素，循环执行 10000 次
        expensive_operation(vector::borrow(&items, i));
        i = i + 1;
    }
}
```
**误报识别**：若调用者是合约内部且 items 来源明确受限（如固定事件队列，最多 50 元素），则非漏洞。

**特征 2：嵌套 O(n²) 或 O(n³) 操作的高频路径**
```move
// 真实漏洞：流动性池交易路径中的双层遍历
public fun swap_with_all_pools(user_tokens: vector<TokenType>) {
    // 外层：用户可提交任意数量 token 类型
    let i = 0;
    while (i < vector::length(&user_tokens)) {
        let pool_list = borrow_global<PoolRegistry>(@app).pools;
        // 内层：对每个 token，遍历所有流动性池（可能数百个）
        let j = 0;
        while (j < vector::length(&pool_list)) {
            match_and_swap(...);  // gas 消耗呈平方级增长
            j = j + 1;
        };
        i = i + 1;
    }
}
```
**误报识别**：若外层 vector 长度被强制限制 ≤ 5，且内层池数量稳定 ≤ 20，则为可控场景，非漏洞。

**特征 3：Storage 层重复读写导致的持久化成本爆发**
```move
// 危险：循环内频繁修改 storage
public fun batch_claim_rewards(users: vector<address>) {
    let i = 0;
    while (i < vector::length(&users)) {
        let user_data = borrow_global_mut<UserBalance>(@app, users[i]);
        // 每次循环都写回 storage，gas 成本 × 元素数
        user_data.claimed = true;
        i = i + 1;
    }
}
```
**审计要点**：检查 `borrow_global_mut` 是否在循环外执行（应收集操作后批量处理）。

### 常见误报场景与规避方法

**误报 1：「内存临时 vector」被标记为漏洞**
```move
// 通常被标记为问题，但实际无害
public fun sort_items(input: vector<Item>): vector<Item> {
    let sorted = vector::empty();
    // 这是个冒泡排序，O(n²)，但仅在内存，不涉及 storage
    // 且调用方需承担 gas，形成自然限制（不会故意排序百万元素）
    while (!vector::is_empty(&input)) {
        let min_idx = find_min_idx(&input);
        vector::push_back(&mut sorted, vector::remove(&mut input, min_idx));
    }
    sorted
}
```
**判断标准**：vector 仅作函数局部变量，未被存储到全局 storage 中，且在单个交易内执行，自然受 gas 上限保护。

**误报 2：「业务链路强制限制」被忽视**
```move
// 模块设计：最多支持 10 个活跃的交易对
const MAX_PAIRS: u64 = 10;

public fun list_all_pairs(): vector<PairInfo> {
    let registry = borrow_global<Registry>(@app);
    // 循环遍历所有交易对（最多 10 个）
    // 审计时需检查 registry.pairs 是否始终满足长度约束
    vector_utils::filter(&registry.pairs, |p| p.active)
}
```
**规避方法**：
1. 寻找常量定义（如 `MAX_PAIRS = 10`）
2. 检查是否有初始化时的断言（如 `assert!(vector::length(&pairs) <= MAX_PAIRS)`）
3. 验证后续操作是否遵守该约束（如 add_pair 时检查）

**误报 3：「单个低频管理操作」被视为高危**
```move
// Admin 初始化操作（部署时执行一次）
public fun initialize_validators(validators: vector<address>) {
    assert!(signer::address_of(&admin) == @app, E_UNAUTHORIZED);
    assert!(vector::length(&validators) <= 100, E_TOO_MANY);  // ✓ 有上限

    // 虽然是 O(n) 操作，但仅在部署时执行一次，非持续威胁
    let i = 0;
    while (i < vector::length(&validators)) {
        register_validator(vector::borrow(&validators, i));
        i = i + 1;
    }
}
```
**判断准则**：
- 函数是否 `#[init]` 或明确标记为一次性
- 权限控制是否严格（only admin）
- 使用频率是否为低频（部署期间，非交易路径）

### 审计检查清单

| 检查项 | 真实漏洞信号 | 误报信号 |
|--------|------------|---------|
| **循环长度来源** | 用户输入，无检查 | 常量/固定数组，有 assert 上限 |
| **操作频率** | 高频交易路径（swap/transfer） | 低频 admin 操作 |
| **Storage 改动** | 循环内 borrow_global_mut | 仅内存操作，loop 外修改 |
| **嵌套深度** | 2+ 层循环，内层长度可变 | 单层循环，或内层长度 ≤ 10 |
| **时间复杂度** | O(n²) 及以上的业务关键路径 | O(n)，且 n ≤ 100 |
| **成本来源** | 合约主动分配，用户无补偿 | 用户为操作成本承担者 |

### 实战案例分析

**案例：Aptos DEX 流动性池登记（真实漏洞）**
- 问题：`register_pool` 被称为数百次时，`get_all_pools` 的遍历从 O(1) 变为 O(n)
- 根本原因：使用 vector 存储池列表，查询时必须遍历
- 修复：改用 `Table<address, PoolInfo>` + 单独维护活跃池索引

**案例：Sui 对象删除（误报避免）**
- 表现：删除对象时遍历 vector 查找旧值
- 被标记为问题的原因：O(n) 操作
- 真实情况：仅限 object 所有者操作，频率低，且 Sui 有原生优化
- 结论：误报，业务合理

## Low risk

- **长度硬编码上限 ≤ 100**：在代码中明确限制 vector 最大元素数量且有断言保护
- **仅 admin 权限调用**：操作受权限控制，普通用户无法触发，攻击面有限
- **一次性初始化操作**：仅在模块部署或首次配置时执行，非高频路径
- **内存临时变量**：vector 不持久化到 storage，仅作为函数内局部变量使用
- **业务场景已验证 gas 消耗**：通过测试确认实际使用中 gas 成本在可接受范围内（< 0.5% 交易 gas 上限）
