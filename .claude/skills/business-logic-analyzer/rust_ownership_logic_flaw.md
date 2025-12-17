# Rust 资源所有权转移逻辑缺陷

## Details

**漏洞成因**：在异步/并发场景下，资源所有权转移时机控制不当，导致多个任务/线程对同一资源的访问顺序或状态产生竞态，或者转移后的资源生命周期管理出现逻辑不一致。

**代码示例场景**：
```rust
// 场景1: 异步任务中的资源转移竞态
async fn process(mut user: User) {
    tokio::spawn(async move {
        user.balance -= 100; // 所有权已转移到闭包
    });
    user.balance += 50; // 编译错误但揭示逻辑意图
}

// 场景2: Arc/Mutex 配合不当导致的逻辑竞态
let data = Arc::new(Mutex::new(Resource::new()));
let d1 = data.clone();
tokio::spawn(async move {
    let mut r = d1.lock().unwrap();
    r.state = State::Processing;
    // 长时间持有锁
    expensive_operation().await;
    r.state = State::Done;
});
// 其他任务可能在 Processing 期间读取到中间状态

// 场景3: 跨 await 点的所有权假设
async fn transfer(from: &mut Account, to: &mut Account, amount: u64) {
    from.balance -= amount;
    external_verify().await; // 可能失败但 from 已扣款
    to.balance += amount;
}
```

**快速定位核心操作**：
- 搜索 `tokio::spawn`、`thread::spawn`、`async move`、`.await` 组合
- 关注 `Arc<Mutex<T>>`、`Arc<RwLock<T>>` 的 `.lock()` 和 `.clone()` 配对
- 查找跨 `.await` 的状态修改操作
- 检索资金/权限相关字段（balance、status、permission）在异步块中的修改

**快速定位保护机制**：
- 查找事务性封装（transaction、rollback、commit 关键词）
- 检查 `Drop` trait 实现中的清理逻辑
- 寻找显式的状态回滚代码（if/else 中的反向操作）
- 验证是否使用 `tokio::select!` 或 `try_join!` 等错误传播机制
- 确认锁的作用域是否最小化（`{ let _guard = lock; }` 模式）

**审计等级**：
- **L1**：关键词扫描 - 快速过滤无异步/并发的纯同步代码
- **L2**：跳读 - 有 `async`/`Arc` 但业务逻辑简单（日志、只读操作）
- **L3**：逐行读 - 涉及状态修改的异步流程，需验证每个 `.await` 前后的状态一致性
- **L4**：跨模块追踪 - 资源在多个模块间传递（如支付流程），需追踪完整生命周期

## Classify

**确认为漏洞**：
1. 资金/积分等关键资源在 `.await` 前后未做原子性保证，可导致中间状态被观测或重复操作
2. 状态转移缺少回滚机制，外部调用失败后资源已不可恢复
3. 多个异步任务对共享资源的操作顺序依赖运行时调度，可被竞态利用（TOCTOU）
4. 锁持有期间包含异步操作，导致其他任务长时间等待或死锁

**判定为误报**：
1. 资源为只读访问，多任务并发读取不影响业务
2. 竞态仅影响性能（如重复计算）但不影响数据一致性
3. 已通过更高层的分布式锁或数据库事务保证一致性
4. 使用了通道（channel）等消息传递机制，所有权转移是单向且明确的

**代码异味**：
1. 过度使用 `Arc<Mutex<T>>` 包裹简单类型，无实际并发场景
2. 锁的粒度过大但尚未实际观测到性能/业务问题
3. 异步函数中有同步阻塞操作但业务量级小

## Low risk

**低风险场景**：
1. 涉及的资源为非关键业务数据（统计计数、缓存更新），不一致可接受或可自愈
2. 并发度极低的场景（内部管理工具、定时任务），实际冲突概率趋近于零
3. 资源已通过业务层限流或队列串行化处理，异步并发仅用于 I/O 优化
4. 状态不一致的窗口期极短（微秒级）且影响范围可控（单用户）
5. 系统已有监控和告警，异常状态可被快速检测并人工介入