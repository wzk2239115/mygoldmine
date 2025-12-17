# Go｜并发写 map 竞态

## Details

### 漏洞成因
Go 内建 `map` 在并发写入时是不安全的。多个 goroutine 对同一 map 进行 `map[key] = value` 或删除操作，会触发 `fatal error: concurrent map writes` 或导致数据错乱。常见于缓存、上下文状态表、定时任务共享 map，开发者为追求性能省略了锁或 `sync.Map`。

### 代码示例

**易受攻击示例：**
```go
var cache = map[string]string{}

func write(key, value string) {
    cache[key] = value // 无锁写入
}

func main() {
    for i := 0; i < 10; i++ {
        go write(strconv.Itoa(i), "value")
    }
    time.Sleep(time.Second)
}
```

**安全示例：**
```go
var (
    cache = make(map[string]string)
    mu    sync.RWMutex
)

func write(key, value string) {
    mu.Lock()
    cache[key] = value
    mu.Unlock()
}

// 或使用 sync.Map
var cache sync.Map
cache.Store(key, value)
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `map[`, `make(map`, `go func`, `sync.WaitGroup`, `cache`, `state`。

**定位步骤：**
1. 搜索 map 声明，关注是否为包级变量或在 struct 中嵌入；
2. 跳读（L2）定位写操作 `map[key] =`、`delete(map, key)` 是否处于 goroutine；
3. 判断是否使用 `sync.Mutex`、`sync.RWMutex`、`sync.Map` 或 channel 串行化。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `sync.Mutex` / `sync.RWMutex` 包裹访问；
- `sync.Map` 用于读多写多场景；
- 通过 channel 统一序列化写操作；
- map 仅在 goroutine 内部作用域使用，不共享。

**定位技巧：**
- 逐行读（L3）确保 `defer mu.Unlock()` 未遗漏；
- 检查是否在 `for range` 中遍历时同时进行写操作；
- 跨模块追踪（L4）当 map 嵌入 struct 并被多个组件共享时，确认所有访问路径都加锁。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 `sync.Map` 或统一锁封装 | **L0（快速跳过）** | 可直接通过 |
| 部分路径加锁 | **L2（跳读）** | 快速确认遗漏 |
| 无锁写入共享 map | **L3（逐行读）** | 高风险 |
| 多包共享 map 且封装不统一 | **L4（跨模块追踪）** | 全链路分析 |

## Classify

### 研判标准

#### 确认漏洞
1. map 被多个 goroutine 写入且缺乏同步；
2. 压测可触发 panic 或脏数据；
3. map 保存关键状态（配置、会话、任务表）。

#### 误报
1. map 仅在单 goroutine 中使用或在函数内创建；
2. 所有访问均受锁保护或通过 channel 串行；
3. 使用 `sync.Map`/第三方并发容器。

#### 代码异味
1. 部分调用者加锁、部分不加锁；
2. map 被导出供外部访问，缺少接口封装；
3. 依赖 `-race` 未报错的侥幸心理。

## Low risk

### 低风险评级场景

#### 1. 缓存仅用于非关键指标
- 场景：map 保存可丢失的统计数据；
- 评估：可标记低风险，但仍建议修复。

#### 2. 实际部署单 goroutine
- 场景：通过配置确保只有一个 worker；
- 评估：短期可降级，但需文档化约束。

#### 3. 正在迁移到锁封装
- 场景：已有计划封装访问层或引入 `sync.Map`；
- 评估：可列低风险，同时跟踪进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键数据 | 影响可控 | 低 |
| 单 goroutine | 攻击面小 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

