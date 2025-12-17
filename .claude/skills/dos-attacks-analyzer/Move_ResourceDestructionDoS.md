# Move 资源销毁 DoS

批量销毁 Move 资源时未分批处理，单次操作遍历大量元素并执行销毁，导致 Gas 消耗超限交易失败，用户资产锁死。

## Details

**代码示例：**

```move
module owner::vault {
    use std::vector;
    
    struct TokenVault has key {
        tokens: vector<Token>
    }
    
    struct Token has store { value: u64 }
    
    // 漏洞：批量销毁所有 token，无长度限制
    public entry fun destroy_all_tokens(account: &signer) acquires TokenVault {
        let vault = borrow_global_mut<TokenVault>(signer::address_of(account));
        while (!vector::is_empty(&vault.tokens)) {
            let token = vector::pop_back(&mut vault.tokens);
            let Token { value: _ } = token; // 销毁
        }
    }
    
    // 漏洞：遍历 Table 销毁所有条目
    public fun clear_table(table: &mut Table<address, NFT>) {
        let keys = table::get_all_keys(table);
        vector::for_each(keys, |key| {
            let nft = table::remove(table, key);
            destroy_nft(nft);
        });
    }
}
```

**快速定位核心操作（L3-逐行读）：**
- 搜索 `vector::pop_back` + `while` 组合，检查循环边界
- 查找 `table::remove` 在循环中调用且无批次限制
- 定位 `for_each` / `map` 操作资源集合的函数
- 识别资源析构模式 `let Struct { field: _ } = resource`

**快速定位保护机制（L2-跳读）：**
- 检查函数参数是否有 `limit: u64` / `batch_size` 参数
- 查看是否存在 `assert!(vector::length() <= MAX_BATCH)` 断言
- 确认是否有分页参数 `start_index` / `end_index`
- 搜索 `ABORT_BATCH_TOO_LARGE` 等错误常量定义

## Classify

**漏洞：** 满足以下条件
- 用户可触发批量销毁操作且无输入规模限制
- 集合大小可无限增长（由累积存款/铸造等操作驱动）
- Gas 消耗随集合规模线性/超线性增长，存在理论上限（如 100+ 元素即失败）

**误报：** 以下场景排除
- 集合大小有硬编码上限（如 `MAX_SIZE = 10`）
- 仅管理员可调用且文档明确说明需离线模拟 Gas
- 销毁操作轻量（如仅修改单个字段，无递归调用）

**代码异味：** 边界情况
- 当前集合大小受业务限制（如每用户最多 50 个），但未在合约中强制
- 存在理论风险但触发成本极高（需恶意堆积）

## Low risk

以下情况降级为低风险：
- **集合已有实际上限**：如 NFT 总供应量 1000 且全部销毁测试通过
- **经济成本防护**：每次添加元素需支付高额费用（0.1 ETH/条），攻击不经济
- **离线可恢复**：合约提供管理员紧急救援函数，可分批提取后销毁
- **双路径设计**：正常流程有批量销毁，但同时提供单个销毁接口作为降级方案

## 审计专业技巧

### 1. 真实漏洞识别特征

**关键信号组合（高置信度判定）：**

- **循环深度 + 资源操作** = 风险
  - 嵌套循环遍历集合元素（`for_each` 嵌套 `while`）
  - 每次迭代调用重资源操作（字段修改、动态查询、事件发射）
  - 示例：`for_each(keys, |k| { table::remove; update_state; emit_event })`

- **无限集合 + 同步销毁** = 临界漏洞
  - 集合大小由用户操作累积（铸造、存款、转账）
  - 销毁函数遍历整个集合但无批次参数
  - 实测：Sui 上 ~500 NFT 销毁需 1.5B gas（单个交易限额 2B）

- **权限假设失效** = 误报转漏洞
  - 函数标记 `public entry` 但文档声称"仅管理员"
  - 实际权限校验在模块内部（`assert!(is_admin())`）但可被低级账户绕过
  - 审计经验：见过权限 check 在 `vector::pop_back` 循环**后**执行的案例

### 2. 误报常见陷阱

**正常设计被误判的场景：**

| 代码特征 | 误判原因 | 区分方法 |
|---------|--------|--------|
| `vector::for_each(items, \|x\| { simple_drop(x) })` | 看似遍历 | 实测 1000 元素销毁 gas<50M |
| `if vector::length() > 100 return` | 看似有保护 | 查询上层是否真正执行到此分支 |
| `Table<u64, Coin>` with `get_all_keys` | 看似批量操作 | Coin 有 Drop 自动销毁，不需遍历 |
| 管理员权限 with no explicit `assert` | 权限遗漏 | 检查 type-level 权限（如 `AdminCap` 类型参数）|

**典型误报案例：**
- Aptos Move 1.0 引入 `drop()` 语言能力后，显式销毁循环变成反模式——自动销毁使循环成为冗余设计，但仍保持原有接口
- Sui 的 `table::remove` 可能隐含调用删除操作，审计者计算 gas 时重复计算

### 3. 现场审计技巧

**第一步：快速风险评分**
```
1. 检查是否存在 *参数化批处理*
   find_in_code("batch_size", "limit", "count")
   → 无 = 继续深度审计
   → 有 = 验证是否真正限制循环次数

2. 确认 *集合增长来源*
   grep -r "vector::push_back\|table::add"
   → 内部模块生成 = 可能有上限
   → 用户触发 = 需检查无限性

3. 量化 *单次销毁成本*
   测试 gas: destroy_empty_vector() vs destroy_1000_element_vector()
   → 差异 <10M = 不构成漏洞
   → 差异 >100M = 确认漏洞
```

**第二步：实验验证**

操作步骤：
1. 在本地测试网部署易受攻击的合约
2. 铸造/积累 N 个元素（N=100/500/1000）
3. 调用批量销毁函数，观察 gas 消耗曲线
4. 计算：单位元素成本 = (gas_1000 - gas_empty) / 1000
5. 判定：若单位成本 * MAX_REALISTIC_SIZE > TX_GAS_LIMIT，则为真实漏洞

**第三步：风险上下文**

提问清单：
- 该操作会触发多少次外部调用（`call`, `transfer` 等）？（每次 ~5000 gas 基础开销）
- 集合在极端情况下最大能增长到多少？（检查所有增量操作）
- 是否存在"安全停止点"（如 `break` 语句、重试机制）？
- 是否有链外工具或多签恢复？（降低实际风险等级）

### 4. 真实案例对标

**案例 A：真实漏洞（Sui Move）**
```move
// 漏洞：向量销毁无限制
public fun drain_vault(vault: &mut Vault) {
    while (!vector::is_empty(&vault.items)) {
        let item = vector::pop_back(&mut vault.items);
        destroy_expensive_item(item);  // 每次 ~2M gas
    }
}
// 风险：100 元素 = 200M gas（单 tx 上限 2B，勉强），
//      1000 元素 = 2B gas（超限失败）
// 修复：添加 batch_size 参数，返回 bool 指示是否完成
```

**案例 B：误报（Aptos Move）**
```move
// 看似有风险，实际无风险
public fun clear_balances(registry: &mut Registry) {
    let keys = table::keys(&registry.balances);
    for_each(keys, |addr| {
        let coin = table::remove(&mut registry.balances, addr);
        coin::burn(coin);  // Coin 实现 Drop，这里冗余但不危险
    });
}
// 原因：Coin<T> 本身 Drop，显式 burn 是代码冗余而非漏洞
// gas 成本恒定，不随元素增长
```

### 5. 审计报告撰写要点

漏洞确认时务必包含：
- **重现步骤**：具体的调用序列和参数值
- **Gas 消耗证明**：实测数据或理论计算公式
- **触发难度**：攻击者需要多少投入（时间、经济成本）
- **影响范围**：是否影响多个用户或全网

误报排除时应说明：
- **为何排除**：引用代码行号和具体的防护机制
- **替代风险**：是否存在其他 DoS 向量
- **建议**：即使无漏洞，是否建议优化（如加上 batch_size 参数提升 UX）
