# Context 未复用 (CosmWasm)

**漏洞类型**: Gas 优化 - 资源浪费  
**适用范围**: CosmWasm 合约中的 Cosmos SDK context 对象操作

## Details

**典型代码模式**：
```go
// 问题代码：重复创建 context
fn handle_multi_transfer(deps: DepsMut, env: Env) {
    for recipient in recipients {
        let ctx = deps.api.clone_context(); // 每次循环创建新 context
        transfer(ctx, recipient);
    }
}

// 或在查询中
fn query_balances(deps: Deps) {
    for addr in addresses {
        let ctx = new_query_context(deps); // 重复实例化
        balances.push(query_balance(ctx, addr));
    }
}
```

**快速定位核心操作技巧（L2：跳读）**：
- 搜索 `clone()`, `.api.clone_context()`, `Context::new()` 在循环体内的调用
- 关注 `for`/`while` 循环中的 `deps.api`, `deps.storage` 重复解引用
- 检查 `execute`, `query` 入口函数内是否传递同一 context 对象至多次调用
- 扫描状态迁移逻辑中 `migrate()` 函数的批量操作部分

**快速定位保护机制技巧（L1：关键词扫描）**：
- 查找 `&mut deps` 参数传递（引用复用而非值拷贝）
- 检索 `cached_context`, `transient_ctx` 等命名模式
- 寻找 `#[inline]` 标记的辅助函数（编译器可能优化掉中间对象）
- 验证是否存在 context wrapper 结构体实现引用语义

## Classify

**漏洞判定**：
- 在高频操作中（循环、批量处理）重复创建 context 且累计分配成本超过 10% gas 消耗

**代码异味判定**：
- 低频操作（单次交易仅 2-3 次创建）或创建后立即释放不造成内存压力
- 使用 `Arc<Context>` 等智能指针但未跨线程实际共享

**误报判定**：
- 跨合约调用必须传递新 context（隔离性要求）
- 子消息（submessage）回调需独立 context 以支持事务回滚

## Low risk

**以下场景应评为低风险**：
- 单次交易内 context 创建次数 ≤ 5 且非嵌套循环
- 合约逻辑简单（总行数 < 500），context 分配开销占比 < 5%
- 已通过 `cargo bench` 验证性能影响 < 1000 gas/次
- 存在业务合理性：如隔离不同权限域、实现 MVCC 快照语义
- 团队已明确标注 `// OPTIMIZATION: deferred` 且在非关键路径

## 审计专业技巧

### 第一层：静态检查清单
1. **循环检测**：使用 AST 遍历或正则模式识别嵌套深度
   - `for`/`while` 循环内的 context 创建优先级最高
   - 记录循环的迭代上界（确定性次数 vs 动态大小）

2. **引用传递分析**：区分值拷贝 vs 引用复用
   - 函数签名中 `&mut` 表示引用语义（好）
   - 函数签名中无 `&` 表示值拷贝（坏）
   - 检查 `clone()` 显式调用的位置和频率

3. **编译器优化感知**：
   - 检查是否启用了 `-C opt-level=2` 以上（LLVM 可能消除死代码）
   - 查看 `#[inline]` 和 `#[inline(never)]` 注解

### 第二层：真实漏洞识别模式

**真实漏洞场景**：
```go
// 场景 1：批量操作中的重复 context（高风险）
fn batch_execute_messages(
    deps: DepsMut,
    messages: Vec<ExecuteMsg>,
) -> StdResult<Response> {
    let mut responses = vec![];
    for msg in messages {
        // 问题：每次迭代都创建新的存储访问上下文
        let store_ctx = StorageContext::new(&deps.storage);
        let result = execute_message(&store_ctx, msg)?;
        responses.push(result);
    }
    Ok(Response::default())
}
```
**影响评估**：如果 `messages` 包含 1000 个交易，每次创建 context 成本 50 gas，总计 50000 gas 浪费。

```go
// 场景 2：嵌套循环中的 context 三重创建（严重）
fn sync_all_validators(deps: DepsMut) {
    for stake_pool in pools {
        for delegator in delegators {
            for validator in validators {
                let ctx = deps.api.create_context(); // 三层嵌套！
                update_stake(ctx, stake_pool, delegator, validator);
            }
        }
    }
}
```
**复杂度分析**：O(n³) context 创建，与业务逻辑复杂度不成比例。

### 第三层：误报排查技巧

**常见误报 A：跨合约调用隔离**
```go
// 看似重复，实际必要
fn forward_to_pool(deps: DepsMut, pool_addr: Addr, msg: Binary) {
    // 每个子消息需独立 context，确保隔离性和原子性
    let ctx = DepsMut::new(&deps.storage, &deps.api, &deps.querier);
    let msg = CosmosMsg::Wasm(WasmMsg::Execute {
        contract_addr: pool_addr,
        msg,
        funds: vec![],
    });
}
```
**判断依据**：检查是否涉及 `CosmosMsg`, `submessage_callback`, 或跨越信任边界的调用。

**常见误报 B：业务隔离（权限域）**
```go
// 多个用户的 context 不能混用
fn multi_user_operation(deps: DepsMut, users: Vec<Addr>) {
    for user in users {
        // 这里的 context 隔离是为了实现权限检查，不是 gas 浪费
        let user_ctx = UserContext::from(user, &deps);
        validate_permissions(user_ctx)?;
    }
}
```
**判断依据**：检查是否有权限验证、消息签名检查或角色隔离的代码。

**常见误报 C：性能边界之外的优化**
```go
// 初始化时的 context 创建不是热路径
#[entry_point]
pub fn instantiate(deps: DepsMut, env: Env, info: MessageInfo) {
    let ctx = DepsMut::new(&deps.storage, &deps.api, &deps.querier);
    // instantiate 通常只执行一次，不值得优化
}
```
**判断依据**：检查函数是否在 `instantiate`, `migrate` 等非关键路径，或在测试代码中。

### 第四层：验证技巧

**技巧 1：基准测试对比**
```bash
# 在优化前后分别运行 benchmark
cargo bench --lib context_creation
# 输出应该显示 >= 10% 的 gas 改进才算真实漏洞
```

**技巧 2：火焰图分析**
```bash
# 使用 flamegraph 或 perf 工具定位 context 分配热点
perf record ./contract_test
perf report | grep -i context
```

**技巧 3：合约大小检测**
```bash
# 优化后的 WASM 二进制应该更小
ls -lh contract.wasm
# 注意：某些情况下如果 context 是栈分配，优化可能不改变二进制大小
```

**技巧 4：代码审查检查单**
- [ ] 所有 context 创建是否都有明确的业务原因注释？
- [ ] 是否存在可复用的 context 引用传递错误的地方？
- [ ] 循环的上界是否有文档说明（确定vs不确定）？
- [ ] 是否有性能基准来证实优化的必要性？

## 真实案例

**案例 1（真实漏洞）**：Staking 合约批量解委托操作
- **问题**：在 `unbond_batch` 函数中每次迭代创建独立的存储快照
- **影响**：100 个解委托请求 × 75 gas/snapshot = 7500 gas 浪费
- **修复**：将快照创建移到循环外，通过引用共享
- **验证**：benchmark 显示 gas 成本从 12500 降至 5000

**案例 2（误报）**：多重签名合约
- **假象**：每个签名者都创建一份 context
- **真相**：这是权限隔离的必要设计，不优化反而降低安全性
- **教训**：审计时必须理解权限模型，不能盲目优化
