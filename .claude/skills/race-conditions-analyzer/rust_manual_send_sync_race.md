# Rust｜手工实现 Send/Sync 竞态

## Details

### 漏洞成因
当类型包含 `UnsafeCell`、裸指针、外部 FFI 资源时，开发者可能手工实现 `Send`/`Sync` trait，以允许跨线程共享。但如果内部未使用 `Mutex`/`Atomic` 保证同步，或忘记考虑生命周期，就会造成数据竞争或未定义行为（UB）。常见场景包括：封装 C 库句柄、全局单例、懒加载缓存，通过 `unsafe impl Send for Wrapper {}` 发布给多线程使用。

### 代码示例

**易受攻击示例：**
```rust
pub struct Globals {
    ptr: *mut c_void,
}

unsafe impl Send for Globals {}
unsafe impl Sync for Globals {}

impl Globals {
    pub fn set_ptr(&mut self, p: *mut c_void) {
        self.ptr = p; // 缺乏同步
    }
}
```

**安全示例：**
```rust
pub struct Globals {
    ptr: UnsafeCell<*mut c_void>,
    lock: Mutex<()>,
}

unsafe impl Send for Globals {}
unsafe impl Sync for Globals {}

impl Globals {
    pub fn set_ptr(&self, p: *mut c_void) {
        let _guard = self.lock.lock().unwrap();
        unsafe { *self.ptr.get() = p; }
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `unsafe impl Send`, `unsafe impl Sync`, `UnsafeCell`, `StaticMut`, `static mut`, `MaybeUninit`。

**定位步骤：**
1. 搜索所有 `unsafe impl`；
2. 跳读（L2）查看类型内部是否包含可变共享状态；
3. 判断是否有锁、原子或其它同步机制。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `Mutex`, `RwLock`, `Atomic*` 包裹可变数据；
- 仅在单线程上下文使用（`!Send`, `!Sync`）；
- FFI 回调由外部库保证线程安全并有文档证明。

**定位技巧：**
- 逐行读（L3）确认 `unsafe impl` 理由是否有注释；
- 检查 `Drop`/`Clone` 实现是否安全；
- 跨模块追踪（L4）类型是否在多线程环境被广泛使用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| `unsafe impl` 附带锁/原子说明 | **L0（快速跳过）** | 可接受 |
| 存在注释但实现复杂 | **L2（跳读）** | 需验证细节 |
| 没有同步手段或注释 | **L3（逐行读）** | 高风险 |
| 类型广泛共享且实现不明 | **L4（跨模块追踪）** | 全链路检查 |

## Classify

### 研判标准

#### 确认漏洞
1. `unsafe impl Send/Sync` 的类型内部含可变共享数据；
2. 缺乏锁或原子操作，可能产生数据竞争；
3. 可以构造示例导致崩溃或未定义行为。

#### 误报
1. 类型实际上只读，或同步由底层库保证且有文档；
2. 使用锁/原子包裹，可证明线程安全；
3. 类型仅在单线程 runtime 中使用（`!Send`/`!Sync`）。

#### 代码异味
1. `unsafe impl` 无注释解释；
2. 使用 `static mut` 或 `UnsafeCell` 暴露裸指针；
3. 依赖外部库“承诺线程安全”但缺乏证据。

## Low risk

### 低风险评级场景

#### 1. 类型用于调试或只读缓存
- 场景：即使竞态也不会破坏核心逻辑；
- 评估：可降级，但建议加锁。

#### 2. 部署在单线程 runtime
- 场景：Tokio 单线程运行，未计划扩展；
- 评估：短期风险小，但需记录约束。

#### 3. 重构计划在执行
- 场景：准备移除 `unsafe impl` 或使用 `once_cell` 等安全封装；
- 评估：可标低风险，跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非核心用途 | 影响有限 | 低 |
| 单线程环境 | 无并发 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

