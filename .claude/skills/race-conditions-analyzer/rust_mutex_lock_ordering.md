# Rust｜互斥锁顺序竞态

## Details

### 漏洞成因
在 Rust 中使用 `Arc<Mutex<T>>`/`RwLock<T>` 保护共享资源时，如果多个线程以不同顺序获取多个锁，就会产生死锁或竞态窗口；另外在持锁期间执行耗时操作、`await`、`sleep` 也会放大风险。虽然 Rust 编译器提供借用检查，但逻辑层面的锁顺序仍需开发者维护。常见于多资源组合更新、嵌套锁、跨模块持有锁等场景。

### 代码示例

**易受攻击示例：**
```rust
fn update(a: Arc<Mutex<Data>>, b: Arc<Mutex<Data>>) {
    let mut a_guard = a.lock().unwrap();
    let mut b_guard = b.lock().unwrap(); // 若另一线程先锁 b 再锁 a，将死锁
    do_update(&mut a_guard, &mut b_guard);
}
```

**安全示例：**
```rust
fn update(a: Arc<Mutex<Data>>, b: Arc<Mutex<Data>>) {
    let (first, second) = if Arc::as_ptr(&a) < Arc::as_ptr(&b) {
        (a, b)
    } else {
        (b, a)
    };
    let mut first_guard = first.lock().unwrap();
    let mut second_guard = second.lock().unwrap();
    do_update(&mut first_guard, &mut second_guard);
}

// 或使用组合锁/事务：一次性锁定多个资源
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `Arc<Mutex`, `RwLock`, `lock().unwrap`, `try_lock`, `tokio::sync::Mutex`, `async move`。

**定位步骤：**
1. 搜索多处使用相同锁的代码；
2. 跳读（L2）确认是否存在嵌套锁或不同顺序获取；
3. 检查是否在持锁期间执行阻塞 IO、`await`、`sleep`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 统一的锁顺序策略（基于地址排序、资源 ID）；
- 封装函数一次获取多个锁；
- 在 `async` 场景下使用 `tokio::sync::Mutex` 并避免持锁 `await`；
- 通过 `parking_lot`、`deadlock_detector` 等工具检测。

**定位技巧：**
- 逐行读（L3）确认 `drop(guard)` 是否及时释放；
- 检查异常/早返回路径是否释放锁；
- 跨模块追踪（L4）分析多模块对同一资源的锁顺序是否一致。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 锁顺序统一且封装良好 | **L0（快速跳过）** | 风险低 |
| 部分代码存在嵌套锁 | **L2（跳读）** | 需确认顺序 |
| 多个模块以不同顺序加锁 | **L3（逐行读）** | 高风险 |
| 锁在 `async` 上下文中跨 `await` | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 存在两段代码按不同顺序获取相同锁；
2. 持锁期间执行阻塞或 `await`，导致潜在死锁或性能问题；
3. 能复现死锁、延迟飙升、数据错乱。

#### 误报
1. 有统一锁管理器，所有调用遵循同一顺序；
2. 锁只在单线程 executor 中使用；
3. 使用 `try_lock` 并回退重试，保证不会进入死锁。

#### 代码异味
1. 大量 `unwrap()`、`expect()` 与锁混用未处理错误；
2. 在 `async` 环境中持有 `MutexGuard` 执行 `await`；
3. 缺乏注释说明锁顺序或封装。

## Low risk

### 低风险评级场景

#### 1. 资源非关键
- 场景：锁仅保护 debug 信息或指标；
- 评估：可降级，但记录风险。

#### 2. 并发度极低
- 场景：程序大部分时间单线程运行；
- 评估：短期风险小，但需说明。

#### 3. 已计划重构为无锁或细粒度锁
- 场景：团队准备改用事务、actor 模式；
- 评估：可标低风险，跟踪进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键资源 | 影响有限 | 低 |
| 低并发 | 概率低 | 中 |
| 重构计划明确 | 可暂缓 | 低 |

