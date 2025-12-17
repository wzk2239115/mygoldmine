# C++｜双重检查锁竞态

## Details

### 漏洞成因
双重检查锁（Double-Checked Locking）常用于懒加载单例：外层判断实例指针是否为空，内层持锁再次判断并构造对象。然而如果实例指针不是原子类型，或缺乏内存屏障，编译器与 CPU 可能在构造完成前就将指针写入内存，其他线程随即读取到未初始化的对象，引起崩溃或数据错乱。C++11 之前标准未定义内存模型，即便在现代 C++，手动管理 `new`/`delete` 的实现也容易遗漏细节。

### 代码示例

**易受攻击的实现：**
```cpp
Foo* Foo::instance = nullptr;
std::mutex g_mutex;

Foo* Foo::getInstance() {
    if (instance == nullptr) {                 // 非原子读
        std::lock_guard<std::mutex> lock(g_mutex);
        if (instance == nullptr) {
            instance = new Foo();              // 构造与发布指针可能乱序
        }
    }
    return instance;                           // 其他线程可能看到半初始化对象
}
```

**安全实现示例：**
```cpp
Foo& Foo::getInstance() {
    static Foo instance; // C++11 起线程安全
    return instance;
}

// 或使用 call_once
Foo* Foo::getInstance() {
    static std::once_flag flag;
    static Foo* instance = nullptr;
    std::call_once(flag, []() { instance = new Foo(); });
    return instance;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `double checked`, `singleton`, `instance == nullptr`, `static Foo*`, `lazy`.

**定位步骤：**
1. 搜索双重检查模式的代码。
2. 跳读（L2）确认指针类型是否为 `std::atomic`，是否使用 `std::memory_order`。
3. 检查构造函数中是否持有外部资源，是否可能抛异常。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `std::call_once` + `std::once_flag`。
- 函数内静态局部变量（C++11 以后线程安全）。
- `std::atomic<Foo*>` 并使用 `memory_order_acquire` / `memory_order_release`。
- `std::shared_ptr` 与 `atomic_load`、`atomic_store`。

**定位技巧：**
1. 若使用普通指针，逐行读（L3）确认是否有 `atomic_thread_fence`。
2. 检查不同模块是否复制了同样的懒加载逻辑。
3. 若使用自定义智能指针或内存池，确认其线程安全保证。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 `std::call_once` 或函数内静态变量 | **L0（快速跳过）** | 线程安全保证充分 |
| 指针为 `std::atomic` 并配合内存序 | **L2（跳读）** | 快速确认实现正确 |
| 普通指针实现 DCLP | **L3（逐行读）** | 高危场景 |
| 多模块复制 DCLP 模式 | **L4（跨模块追踪）** | 必须全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 双重检查锁中使用普通指针或缺乏内存屏障。
2. 线程间可能观察到未完成构造的对象。
3. 压力测试或代码审计显示潜在崩溃、竞态。

#### 误报
1. 采用 `std::call_once`、函数内静态变量、`std::atomic<std::shared_ptr>` 等安全方案。
2. 单例在单线程阶段就完成构造，之后仅只读访问。
3. 使用宿主框架（如 Qt、Boost）提供的线程安全单例封装。

#### 代码异味
1. 实现依赖编译器/平台特性而非标准。
2. 有 DCLP 模式但未提供理由或注释。
3. 构造函数复杂，失败后缺乏恢复逻辑。

## Low risk

### 低风险评级场景

#### 1. 单例封装只读配置
- 作用：对象只提供常量数据，即使偶发竞态，影响有限。
- 评估：可暂定低风险，但建议改用安全模式。

#### 2. 初始化仅发生在启动阶段
- 作用：程序在多线程启动前完成初始化。
- 评估：短期风险小，但需验证部署流程。

#### 3. 有明确迁移计划
- 作用：团队已计划改造为 `std::call_once` 或依赖注入。
- 评估：可列低风险，但必须跟踪进展。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 只读用途 | 影响有限 | 中 |
| 启动阶段初始化 | 运行期无竞态 | 中 |
| 重构计划明确 | 临时容忍 | 低 |

