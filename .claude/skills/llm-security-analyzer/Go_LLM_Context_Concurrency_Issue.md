# **Go LLM Context Concurrency Issue**

当 Go 应用在并发处理 LLM 请求时，如果共享了可变的上下文或会话数据，多个 Goroutine 可能导致竞态条件，使数据混淆或泄露。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索全局变量：`var context`、`var sessions`、`global map`
- 查找 Goroutine：`go function()`、`goroutine`
- 搜索竞态条件标志：`go run -race`、`atomic.`、`mutex`
- 查找缓存：`map[string]interface{}`、`sync.Map`
- 定位并发模式：无 mutex 的共享变量

**核心操作保护机制（L2: 跳读）**
- 检查是否使用了 Mutex 保护共享数据
- 验证是否使用了 sync.Map 而非普通 map
- 查看是否为每个请求隔离了上下文
- 检查 channel 是否正确使用
- 查看是否有数据竞态检测

**快速定位到具体漏洞（L3: 逐行读）**
- 检查全局变量的并发访问
- 追踪 map 的读写操作
- 审查 mutex 的使用
- 查看 channel 的同步
- 检查是否有竞态条件

**数据流追踪（L4: 跨模块追踪）**
- 追踪数据在 Goroutine 间的流动
- 检查同步机制

## Classify

**确认为漏洞的特征：**
1. 多个 Goroutine 访问全局 map 无 Mutex
2. 在 Goroutine 中共享可变对象
3. Channel 使用不当
4. 缓存无同步保护
5. 竞态条件可被利用

**误报场景：**
1. 使用 Mutex 保护共享数据
2. 使用 sync.Map 或原子操作
3. 为每个请求隔离数据
4. 正确使用 channel
5. 用 -race 标志验证无竞态

**代码异味（需要深入审查）**
1. 全局 map 的并发访问
2. 无 mutex 的共享变量
3. Goroutine 中的数据竞态
4. 缓存同步问题

## Low risk

**评级为低风险的场景：**
1. 所有共享数据都使用 Mutex 保护
2. 使用 sync.Map 处理并发访问
3. 为每个请求创建独立的上下文
4. 正确使用 channel 和 context 包
5. 使用 -race 标志验证无竞态条件
