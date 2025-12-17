# Go｜初始化 Once 竞态

## Details

### 漏洞成因
使用 `sync.Once` 或自定义布尔标志进行全局初始化时，如果初始化函数内包含长时间操作、外部 IO 或可能返回错误，而未正确处理失败，就可能导致多个 goroutine 同时尝试初始化或在失败后状态不一致。常见于单例客户端、懒加载配置、TLS 证书更新等场景。手动使用 `if !inited { init(); inited = true }` 模式更容易发生竞态。

### 代码示例

**易受攻击示例：**
```go
var (
    client *Client
    inited bool
    mu sync.Mutex
)

func GetClient() *Client {
    mu.Lock()
    defer mu.Unlock()
    if !inited {
        client = NewClient()       // 可能 panic 或返回错误
        inited = true              // 即使失败也会标记
    }
    return client
}
```

**安全示例：**
```go
var (
    client     *Client
    initOnce   sync.Once
    initErr    error
)

func GetClient() (*Client, error) {
    initOnce.Do(func() {
        client, initErr = NewClient()
    })
    return client, initErr
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `sync.Once`, `once.Do`, `initialized`, `if !ready`, `initClient`, `lazyInit`。

**定位步骤：**
1. 搜索一次性初始化模式；
2. 跳读（L2）检查初始化过程中是否调用外部服务、读取配置、可能返回错误；
3. 判断是否存在自定义 `inited` 标志位或多处初始化逻辑。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `sync.Once` 搭配错误返回值；
- 使用 `atomic.Value` 或 `sync.Mutex` 包裹初始化；
- 失败后会重置状态并允许重试；
- 在测试中使用 `testing.Init` 或 `sync.OnceFunc`。

**定位技巧：**
- 逐行读（L3）确认 `once.Do` 内不会 panic；若会，需要恢复并重置；
- 自定义布尔标志需验证是否有锁/原子操作；
- 跨模块追踪（L4）确保多个单例不会循环依赖导致死锁。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用标准 `sync.Once` 并处理错误 | **L0（快速跳过）** | 安全性好 |
| `sync.Once` 内操作可能失败 | **L2（跳读）** | 确认失败处理 |
| 手写 `if !inited` 模式 | **L3（逐行读）** | 高风险 |
| 多模块互相初始化 | **L4（跨模块追踪）** | 需全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 初始化失败后仍标记成功或没有重试；
2. 多个 goroutine 能够同时执行初始化逻辑；
3. 单例资源对业务关键，错误会导致 panic 或脏状态。

#### 误报
1. 使用 `sync.Once` 并正确处理错误，提供返回值；
2. 初始化在单线程启动阶段完成，后续不再并发调用；
3. 资源幂等，可重复初始化不影响正确性。

#### 代码异味
1. 忽略初始化错误，仅记录日志；
2. 在 `once.Do` 内启动 goroutine，容易导致竞态；
3. 初始化逻辑副作用复杂，没有注释说明。

## Low risk

### 低风险评级场景

#### 1. 初始化只加载只读配置
- 场景：即便重复初始化也不会产生副作用；
- 评估：可标低风险，但需说明原因。

#### 2. 单 goroutine 调用
- 场景：由主线程按顺序调用，其他 goroutine 不会并发访问；
- 评估：短期风险小，但需文档化约束。

#### 3. 改造计划已立项
- 场景：计划引入 `sync.Once` 或依赖注入框架；
- 评估：可降级，但必须跟踪进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 只读配置 | 无副作用 | 低 |
| 单 goroutine | 无并发 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

