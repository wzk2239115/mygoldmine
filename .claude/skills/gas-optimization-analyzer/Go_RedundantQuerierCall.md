**Go_RedundantQuerierCall**（针对 CosmWasm 合约）  

在 CosmWasm 合约中，通过 QuerierWrapper 多次查询相同链上数据但未缓存结果，导致不必要的查询开销和 gas 消耗增加。

## Details

**典型代码示例：**
```rust
pub fn execute_process(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
) -> Result<Response, ContractError> {
    // 第一次查询
    let balance1 = deps.querier.query_balance(&info.sender, "uatom")?;
    
    // 业务逻辑处理
    do_something();
    
    // 第二次查询相同数据
    let balance2 = deps.querier.query_balance(&info.sender, "uatom")?;
    
    // 第三次查询相同数据
    if deps.querier.query_balance(&info.sender, "uatom")?.amount > threshold {
        // ...
    }
}
```

**快速定位核心操作（L2：跳读）**  
扫描函数内所有 `deps.querier.query_*()` 调用点，统计相同查询参数的调用次数。重点关注：
- `query_balance()` / `query_all_balances()` - 余额查询
- `query_wasm_smart()` - 智能合约查询
- `query_supply()` - 供应量查询
- 在循环、条件分支中的重复查询模式

**快速定位保护机制（L1：关键词扫描）**  
检索是否存在缓存机制：
- 局部变量缓存：查询结果赋值给变量并复用
- `let cached_* = ` 模式
- Map/HashMap 数据结构存储中间结果
- `once_cell` 或 `lazy_static` 延迟初始化模式

## Classify

**漏洞条件：**
- 同一执行路径中，对相同参数的 querier 调用 ≥2 次
- 两次调用间无状态变更操作（无 `store.save()`、`send()`、`execute()` 等）
- 查询结果未被修改或可证明返回值相同

**误报场景：**
- 两次查询间存在可能改变链上状态的操作（跨合约调用、消息发送）
- 查询不同的区块高度（`QueryRequest::Custom` 带时间参数）
- 故意刷新数据以验证状态一致性（需代码注释说明）

**代码异味：**
- 查询次数为 2 次且间隔代码少于 20 行（可能是重构遗留）
- 跨模块传递 querier 而非查询结果（设计问题而非安全问题）

## Low risk

**评级为低风险的情况：**
- 冗余查询发生在低频执行的管理函数中（如 `update_config`、`migrate`）
- 查询的数据量极小（单个余额查询，非批量查询）
- 合约整体查询调用次数 <5 次（简单合约）
- 冗余出现在错误处理分支且触发概率 <1%
- 测试/调试代码中的冗余（需确认未部署到主网）

## 审计专业技巧

### 1. 控制流分析法（确定查询间的依赖关系）

**核心原则：** 两次查询之间若存在可能改变链上状态的操作，则不算冗余。

**判断清单：**
```
- SubMsg::reply_always() 或 SubMsg::new() → 立即执行（状态可能改变）
- cosmwasm_std::Response 中包含 CosmosMsg::*() → 发送消息（状态改变）
- deps.storage.set() / remove() 调用 → 本地状态改变
- 嵌套函数调用 → 需递归检查内部逻辑
```

**真实案例1（真漏洞）：**
```rust
let user_balance = deps.querier.query_balance(&user, "uatom")?;
if user_balance.amount >= min_amount {
    let msg = CosmosMsg::Bank(BankMsg::Send { ... });
    resp = resp.add_message(msg);  // ← 这里触发转账，但没有等待结果
}
let user_balance_2 = deps.querier.query_balance(&user, "uatom")?;
// 此时查询返回的余额仍是转账前的值（查询在链上已处理）
```
➜ **判定：真漏洞**。消息会排队执行但在当前执行上下文中查询不会立即反映。

**真实案例2（误报）：**
```rust
let balance1 = deps.querier.query_balance(&sender, "uatom")?;
// 直接用 deps.storage 本地存储（不涉及链上状态）
deps.storage.set(b"temp", &balance1.encode())?;
let balance2 = deps.querier.query_balance(&sender, "uatom")?;
```
➜ **判定：误报**。链上余额未改变，两次查询将返回相同结果，但存储操作不影响查询的有效性。

### 2. 交叉引用验证法（排除伪装的冗余）

**关键信号识别：**
- `SubMsg { reply_on: ReplyOn::Always | ReplyOn::Success }` → 可能需要查询中间结果
- `execute()` 递归调用 → 需检查内部分支是否改变账户状态
- 条件分支中的冗余 → 不同分支可能触发不同的链上操作

**审计步骤：**
1. 定位第一次查询 → 记录查询对象与参数
2. 追踪到第二次相同查询
3. **中间路径追踪：** 列出两次查询间的所有函数调用和消息构造
4. **决策树验证：** 判断每条路径是否必然改变查询的目标状态

**真实案例3（复杂场景）：**
```rust
fn execute_swap(deps: DepsMut, info: MessageInfo) -> Result<Response> {
    let balance_before = deps.querier.query_balance(&info.sender, "uatom")?;

    if balance_before.amount < threshold {
        return Err(ContractError::InsufficientBalance);
    }

    let swap_msg = create_swap_message(&balance_before)?;  // 参数化消息（关键）
    let resp = Response::new().add_message(swap_msg);

    // 这里是第二次查询
    let balance_after = deps.querier.query_balance(&info.sender, "uatom")?;

    if balance_after.amount < balance_before.amount {
        // 验证余额确实下降
    }
    Ok(resp)
}
```
➜ **判定：误报或设计合理**。虽然有两次查询，但：
  - 第一次用于构造交易
  - 第二次用于验证（设计上必要）
  - 两次查询间的消息虽已排队但未在当前块执行

### 3. Gas成本量化法（优先级排序）

**计算公式：** `Gas节省 = 单次查询gas × 冗余次数 × 预计调用频率`

**常见操作的gas成本（CosmWasm基准）：**
| 操作 | Gas消耗 | 优先级 |
|-----|--------|-------|
| query_balance() | ~5,000 gas | 高 |
| query_all_balances() | ~10,000-50,000 gas | 高 |
| query_wasm_smart() | ~20,000-100,000 gas | 中 |
| query_supply() | ~3,000 gas | 低 |
| 本地Map缓存 + lookup | ~1,000 gas | N/A |

**优先级评估：**
- **高优先级：** 冗余 × gas成本 > 50,000 且日调用 > 1000 次
- **中优先级：** 冗余 × gas成本 > 10,000 或在热路径上
- **低优先级：** 管理函数、低频操作

**真实案例4（成本对比）：**
```
场景：NFT合约查询用户余额3次，日均10,000次执行
成本差异：
- 缓存方案：10,000 × 1 × 5,000 = 50M gas/天
- 冗余方案：10,000 × 3 × 5,000 = 150M gas/天
- 节省效果：100M gas/天 = 约50 ATOM（单价$10）/天
```

### 4. 源代码提示法（自动化检测辅助）

**需要手工验证的警告信号：**
```rust
// 模式A：循环内重复查询（通常真漏洞）
for item in items {
    let val = deps.querier.query_*(args)?;
    process(val);
}

// 模式B：异常捕获内重复查询（可能误报）
let result = match query1() {
    Ok(v) => v,
    Err(_) => query1()?,  // 可能需要重试
};

// 模式C：版本检查后重复查询（误报概率高）
if CONTRACT_VERSION != stored_version {
    let data1 = query()?;
    migrate();
    let data2 = query()?;  // 可能在migrate()中已缓存
}
```

### 5. 链上行为追踪法（最终确认）

对于关键交易：
1. **部署到测试网** 并执行目标函数
2. **启用Cosmos SDK debug日志** 检查实际消息执行顺序
3. **比对查询返回值** 是否一致（相同返回值 = 真冗余）

**Cosmos SDK CLI验证：**
```bash
# 观察详细的查询和消息执行日志
cosmwasm-cli contract execute ... --trace --log-level debug
```

## 常见误判案例库

| 案例 | 表面现象 | 实际原因 | 判定 | 建议 |
|-----|--------|--------|-----|-----|
| 交换函数前后查询 | 2次相同查询 | 验证交换结果 | 误报 | 保留，添加注释 |
| 迁移函数中重复查询 | 数据版本不同 | 向后兼容检查 | 误报 | 拆分变量名区分 |
| 错误处理重试 | 同函数重复查询 | 容错机制 | 误报/合理设计 | 改用try_query包装 |
| 跨合约调用后查询 | 子消息链中重复 | 订购确认 | 视情况而定 | 用事件替代 |
| 条件分支查询相同 | 不同branch重复 | 逻辑简化不完整 | 真漏洞 | 提前查询 + 条件分支变量 |
