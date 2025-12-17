# Rust｜Tokio RefCell 竞态

## Details

### 漏洞成因
在 Tokio 异步环境中，`Rc<RefCell<T>>` 或 `Cell<T>` 适用于单线程，但一旦将其跨任务共享（`Rc` 克隆到多个 `tokio::spawn` 中），或在 `async` 函数中持有 `RefMut` 跨越 `await`，就会触发运行时 panic（borrow 规则违背）或潜在数据竞争。常见于缓存、上下文状态、插件系统使用 `Rc<RefCell>` 以避免 `Arc<Mutex>` 的开销。

### 代码示例

**易受攻击示例：**
```rust
let state = Rc::new(RefCell::new(HashMap::new()));
for id in ids {
    let state_clone = state.clone();
    tokio::spawn(async move {
        state_clone.borrow_mut().insert(id, fetch(id).await); // panic: already borrowed
    });
}
```

**安全示例：**
```rust
let state = Arc::new(Mutex::new(HashMap::new()));
for id in ids {
    let state_clone = state.clone();
    tokio::spawn(async move {
        let value = fetch(id).await;
        state_clone.lock().await.insert(id, value);
    });
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `Rc<RefCell`, `Cell`, `RefCell::borrow_mut`, `tokio::spawn`, `async move`, `RefCell`。

**定位步骤：**
1. 搜索 `Rc<RefCell>` 声明；
2. 跳读（L2）查看是否在 `tokio::spawn`、`async` 闭包中克隆 `Rc`；
3. 检查 `borrow_mut` 调用是否跨 `await`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `Arc<Mutex>`、`Arc<RwLock>` 替代；
- 单线程 runtime (`current_thread`) 并确认不会转换为多线程；
- `RefCell` 仅在同步代码中使用，异步部分使用 `Mutex`。

**定位技巧：**
- 逐行读（L3）确认 `RefMut` 生命周期是否包裹 `await`；
- 检查 `spawn_local` / `LocalSet` 等场景是否保证单线程；
- 跨模块追踪（L4）当状态通过 channel 传递时是否保持在同一线程。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 `Arc<Mutex>` 或单线程运行 | **L0（快速跳过）** | 风险低 |
| 部分路径仍使用 `RefCell` | **L2（跳读）** | 需确认是否跨任务 |
| `Rc<RefCell>` 克隆到多个任务 | **L3（逐行读）** | 高风险 |
| 状态在多模块间共享且环境不确定 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. `Rc<RefCell>` 在 `tokio::spawn` 或多线程 runtime 中共享；
2. 持有 `RefMut` 跨 `await`，可能 panic；
3. 影响关键状态（缓存、配置、session）。

#### 误报
1. 应用运行在单线程 runtime (`LocalSet`) 且明确不会迁移；
2. `RefCell` 仅在同步代码使用，异步部分使用 `Mutex`；
3. 状态只读或在任务内部复制后使用。

#### 代码异味
1. 注释说明“暂时安全”，缺乏验证；
2. 混合使用 `Rc`/`Arc`，逻辑混乱；
3. 缺少 panic 处理或恢复策略。

## Low risk

### 低风险评级场景

#### 1. 状态仅用于缓存
- 场景：数据错误不会破坏业务；
- 评估：可降级，但建议加锁。

#### 2. 单线程 LocalSet 并确认不会更改
- 场景：部署环境固定单线程；
- 评估：风险较低，但需记录。

#### 3. 正在迁移到 `Arc<Mutex>` 或 actor 模式
- 场景：有计划改造并已排期；
- 评估：可标低风险，跟踪进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键缓存 | 影响有限 | 低 |
| 单线程环境 | 无并发 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

