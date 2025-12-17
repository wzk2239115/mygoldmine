# C｜信号处理竞态

## Details

### 漏洞成因
POSIX 信号异步到达时，处理函数与主循环共享全局状态（标志位、计数器、缓冲区指针），若未使用 `sig_atomic_t` 或原子操作，就可能在任意指令间打断导致竞态。此外，信号处理函数只能调用异步信号安全（async-signal-safe）的接口；错误地在 handler 中调用 `malloc`、`printf`、`pthread_mutex_lock` 等函数，会破坏锁状态、造成重入死锁或内存错误。典型场景包括：用信号唤醒线程处理任务、捕获 `SIGCHLD` 更新子进程列表、捕获 `SIGALRM` 更新超时标志。

### 代码示例

**易受攻击示例：**
```c
volatile int reload_config = 0;  // 仅使用 volatile

void on_signal(int sig) {
    reload_config = 1;          // 非原子写
    log_message("signal received\n"); // 非异步安全调用
}

int main() {
    signal(SIGUSR1, on_signal);
    while (running) {
        if (reload_config) {    // 可能读取到部分写入
            reload_config = 0;
            reload_configuration();
        }
    }
}
```

**安全写法示例：**
```c
static volatile sig_atomic_t reload_flag = 0;

void on_signal(int sig) {
    reload_flag = 1;
}

int main() {
    struct sigaction sa = { .sa_handler = on_signal };
    sigaction(SIGUSR1, &sa, NULL);
    for (;;) {
        if (atomic_load_explicit(&reload_flag, memory_order_relaxed)) {
            atomic_store_explicit(&reload_flag, 0, memory_order_relaxed);
            pthread_mutex_lock(&cfg_mutex);
            reload_configuration();
            pthread_mutex_unlock(&cfg_mutex);
        }
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `signal`, `sigaction`, `SIG`, `handler`, `volatile`, `sig_atomic_t`, `alarm`.

**定位步骤：**
1. 搜索信号注册位置，记录处理函数名称。
2. 跳读（L2）处理函数，识别是否写全局变量、调用非 async-signal-safe 函数。
3. 检查主线程读取标志时是否加锁、使用原子操作或调用 `sigprocmask` 保护。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `sig_atomic_t` 或 `std::atomic` 用于标志位。
- 主线程在读取前禁用信号或持有锁。
- 使用 `signalfd`、`eventfd`、`pipe` 将信号转化为安全事件。
- handler 内仅设置标志或写入 pipe，无复杂逻辑。

**定位技巧：**
1. 若 handler 中调用 `printf`, `malloc`, `pthread_mutex_lock`，立即标记为高风险。
2. 逐行读（L3）主线程读取标志处，确认是否存在 ABA 问题或并发写。
3. 跨模块追踪（L4）对共享变量的所有读写路径，确保同步一致。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| handler 仅设置 `sig_atomic_t`，主线程锁内读取 | **L0（快速跳过）** | 无明显风险 |
| handler 写简单标志但主线程未加锁 | **L2（跳读）** | 需快速确认 |
| handler 调用非安全函数或写复杂结构 | **L3（逐行读）** | 高风险场景 |
| 信号与多线程/异步结合 | **L4（跨模块追踪）** | 必须全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. handler 与其他线程同时读写非原子变量。
2. handler 调用非 async-signal-safe API，可能破坏锁或内存。
3. 出现死锁、崩溃、配置错乱等可复现问题。

#### 误报
1. handler 仅设置 `sig_atomic_t` 标志并在安全环境中读取。
2. 使用 `signalfd`、`eventfd` 将信号转化为正常 IO 事件。
3. 处理函数在安装时屏蔽重复信号并确保单线程执行。

#### 代码异味
1. 使用 `volatile int` 代替原子或 sig_atomic_t。
2. handler 中包含日志或自定义锁操作，虽然暂未出问题。
3. 缺乏对信号屏蔽、嵌套信号的说明文档。

## Low risk

### 低风险评级场景

#### 1. 退出流程信号
- 场景：仅在程序退出时触发的信号，handler 将标志设为 true。
- 评估：影响有限，可标为低风险。

#### 2. 幂等标志
- 场景：handler 写入幂等布尔值，主线程加锁检查。
- 评估：风险较低，可暂缓修复。

#### 3. 信号极少触发
- 场景：进程生命周期短或信号几乎不用。
- 评估：短期可降级，但需记录并提醒未来维护者。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 信号仅退出使用 | 影响有限 | 低 |
| 标志幂等且主线程锁保护 | 行为稳定 | 低 |
| 信号几乎不触发 | 概率低 | 中 |

