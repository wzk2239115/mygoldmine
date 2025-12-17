# Go 分布式系统账号锁定状态同步缺陷

## 基本信息
- **难度等级：** ★★★★☆ (高级)
- **审计时间：** 30-45分钟

## 🚀 30秒快速清单
- [ ] 账号锁定状态存储位置（单机内存/Redis/数据库）？
- [ ] 多节点环境下是否使用分布式共享存储？
- [ ] Redis/数据库中的锁定状态是否正确同步？
- [ ] 不同节点的锁定检查是否操作同一数据源？
- [ ] 负载均衡算法是否可被攻击者利用跳过锁定检查？

## Details

### 漏洞成因
Go应用在分布式环境（多服务器、负载均衡、微服务）中实现账号锁定机制时，常见问题包括：锁定状态存储在单个节点的本地内存导致跨节点请求无法共享、Redis缓存中的锁定信息未正确同步或过期时间设置不当、数据库事务隔离级别过低导致并发修改失效、不同节点使用独立的计数器而非集中式存储、以及客户端可通过改变请求头（如修改User-Agent使会话路由到不同节点）绕过锁定。本文档重点关注Go应用在分布式架构下的锁定状态同步问题。

### 代码示例

```go
// 漏洞1：锁定状态存储在本地内存，跨节点失效
type LocalLockoutStore struct {
    mu       sync.RWMutex
    locked   map[string]time.Time  // 仅存储在当前进程内存
}

func (s *LocalLockoutStore) IsLocked(username string) bool {
    s.mu.RLock()
    defer s.mu.RUnlock()

    if lockTime, exists := s.locked[username]; exists {
        if time.Now().Before(lockTime) {
            return true
        }
    }
    return false
}

func (s *LocalLockoutStore) Lock(username string, duration time.Duration) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.locked[username] = time.Now().Add(duration)
}

func handleLogin(w http.ResponseWriter, r *http.Request) {
    username := r.PostFormValue("username")
    password := r.PostFormValue("password")

    // 仅检查当前节点的内存状态
    if lockoutStore.IsLocked(username) {
        http.Error(w, "Account locked", http.StatusForbidden)
        return
    }

    if !authenticate(username, password) {
        lockoutStore.Lock(username, 15*time.Minute)
    }
}
// 攻击场景：攻击者在节点A触发锁定，然后向节点B发送请求（轮询或指定节点）
// 节点B完全不知道账号已锁定，可继续尝试
```

```go
// 漏洞2：Redis锁定信息未同步或缺少原子性
var redisClient *redis.Client

func handleLoginWithRedis(w http.ResponseWriter, r *http.Request) {
    username := r.PostFormValue("username")
    password := r.PostFormValue("password")

    lockKey := "lockout:" + username

    // 竞态条件：检查与设置之间存在时间窗口
    val, err := redisClient.Get(r.Context(), lockKey).Result()
    if err == nil && val != "" {
        // 账户被锁定
        return
    }

    if !authenticate(username, password) {
        // 失败计数
        redisClient.Incr(r.Context(), "attempts:"+username)

        // 问题1：未在原子操作中检查计数和设置锁定
        // 问题2：未设置过期时间或设置位置不当
        attempts := getAttempts("attempts:" + username)
        if attempts >= 5 {
            // 设置锁定但未设置过期，可能导致永久锁定或依赖Redis自动淘汰
            redisClient.Set(r.Context(), lockKey, "1", 0)  // 无过期时间！
        }
    }
}
// 攻击利用：在redis命令执行前后的间隙，多个并发请求可都通过检查
```

```go
// 漏洞3：计数器和锁定分离在不同数据源
// 数据库中记录失败次数，但锁定状态在Redis
type HybridLockoutStore struct {
    db    *sql.DB
    redis *redis.Client
}

func (h *HybridLockoutStore) CheckAndUpdate(username string) error {
    // 从数据库读取失败计数
    var failureCount int
    err := h.db.QueryRow(
        "SELECT failure_count FROM users WHERE username=?",
        username,
    ).Scan(&failureCount)

    if failureCount >= 5 {
        // 检查Redis中是否已锁定
        locked, _ := h.redis.Get(context.Background(), "locked:"+username).Result()
        if locked == "" {
            // 竞态：此时另一个节点可能在更新数据库
            return fmt.Errorf("account locked")
        }
    }

    // 更新数据库计数（不是原子操作）
    _, err = h.db.Exec(
        "UPDATE users SET failure_count = failure_count + 1 WHERE username=?",
        username,
    )

    // 同步锁定状态到Redis（分开操作）
    if failureCount >= 4 {
        h.redis.Set(context.Background(), "locked:"+username, "true", 15*time.Minute)
    }

    return err
}
// 问题：两个存储间数据不一致，攻击者可从数据库查询计数，推测何时被锁定
```

```go
// 漏洞4：会话粘性失效导致负载均衡器路由到不同节点
type SessionAwareHandler struct {
    lockout map[string]time.Time
    mu      sync.RWMutex
}

func (h *SessionAwareHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    username := r.PostFormValue("username")

    // 假设负载均衡器使用Session粘性
    // 但如果用户改变User-Agent或清除Cookie，会被路由到不同节点
    if h.isLocked(username) {
        http.Error(w, "Locked", http.StatusForbidden)
        return
    }

    // 验证...
}

// 攻击场景：
// 请求1: User-Agent: Chrome -> 路由到节点A -> 锁定记录在节点A
// 请求2: User-Agent: Firefox -> 路由到节点B -> 节点B无锁定记录
```

```go
// 漏洞5：分布式计数器过期时间设置不当
func handleLoginWithDistributedCounter(w http.ResponseWriter, r *http.Request) {
    username := r.PostFormValue("username")
    attemptsKey := "attempts:" + username

    // 获取当前计数
    count, _ := redis.Incr(context.Background(), attemptsKey).Result()

    // 问题1：首次设置过期时间太晚（第一次调用时没设置TTL）
    // 只有在计数达到阈值时才设置，之前的尝试记录可能已过期
    if count == 1 {
        // 应在此时设置TTL，但有开发者会忽略
        redis.Expire(context.Background(), attemptsKey, 15*time.Minute)
    }

    // 问题2：过期时间过短
    if count >= 5 {
        redis.Set(context.Background(), "lockout:"+username, "1", 10*time.Second)  // 仅10秒
    }

    // 问题3：计数器有TTL但锁定没有，或反之
    if count >= 10 {
        redis.Set(context.Background(), "lockout:"+username, "1", 0)  // 无TTL永久锁定
    }
}
```

### 快速定位核心操作

**L1: 关键词扫描** - 快速判断是否使用分布式存储
- 存储检查：`map[string]`, `sync.Map`, `redis.Client`, `sql.DB`, `memcache`
- 本地内存：`var ... = make(map[string]...)`, `type ... struct { ... map[string]...`
- Redis操作：`redisClient.Get`, `redisClient.Set`, `Incr`, `Expire`
- 数据库操作：`QueryRow`, `Exec`, `UPDATE ... WHERE`, `SELECT ... FROM`
- 分布式工具：`sync.RWMutex`, `distributed lock`, `etcd`, `consul`

**L2: 跳读** - 5-10分钟内定位关键逻辑
- 账号锁定检查位置（发生在单个节点的本地内存还是共享存储）
- 锁定状态设置位置（设置后是否会同步到所有节点）
- 失败计数器的存储位置（是否支持分布式环境）
- 多数据源操作的顺序（先检查Redis再检查数据库或反之）
- 负载均衡配置（是否使用会话粘性/IP粘性）

**L3: 逐行读** - 15-20分钟内审查代码细节
- Redis Set/Incr/Expire是否使用事务或管道确保原子性
- 过期时间的设置时机（首次设置或每次更新时）
- 数据库UPDATE语句是否使用行锁或版本控制
- 是否有从数据库的同步延迟（主从复制lag）
- 节点间是否有定期同步机制（如消息队列）

**L4: 跨模块追踪** - 20-30分钟内验证端到端一致性
- 追踪登录请求从负载均衡器→特定节点→存储的全链路
- 追踪锁定状态从设置节点→其他节点的同步过程
- 追踪计数器在多个存储间的更新顺序
- 检查是否存在去重/幂等机制处理重复请求
- 检查监控告警是否检测节点间状态不一致

### 审计等级判定

| 等级 | 场景 | 审计策略 |
|------|------|----------|
| **L0** | 单实例应用、无负载均衡 | 跳过分布式同步检查 |
| **L1** | 多实例但使用会话粘性或IP粘性 | 验证粘性算法，检查本地内存使用 |
| **L2** | 使用Redis存储锁定状态 | 检查原子性、TTL设置、同步延迟 |
| **L3** | 混合使用数据库+Redis | 跨数据源追踪一致性、检查竞态 |
| **L4** | 微服务架构、多区域部署 | 全链路追踪、消息队列同步、最终一致性验证 |

---

## Classify

### 确认漏洞（需满足以下任一条件）

1. **完全无同步机制**：多节点环境下仅使用本地内存存储锁定状态，无任何分布式存储
   - 代码中 `map[string]time.Time` 存储在本地变量，未使用Redis/Database
   - 无中间件或全局状态共享机制

2. **跨数据源不一致**：计数器、锁定状态、过期信息分散在多个存储
   - 失败计数在数据库，锁定标志在Redis，两者更新顺序有窗口
   - 过期时间管理不一致（数据库永久存储+Redis短期存储）

3. **Redis原子性缺失**：Get-Check-Set操作非原子
   - 检查和修改之间存在时间窗口，多个并发请求可都通过检查
   - 使用separate Get和Set调用而非MULTI/WATCH或Lua脚本

4. **计数器TTL不当**：
   - 首次不设置过期时间，导致旧计数无法自动清理
   - 过期时间过短（< 5分钟）
   - 计数和锁定的TTL不同步（计数过期但锁定仍有效或反之）

5. **会话路由绕过**：负载均衡未使用会话粘性，攻击者可改变请求特征在节点间切换
   - 每个请求可能路由到不同节点
   - 本地内存中的锁定状态对新节点不可见

6. **主从复制延迟**：使用数据库主从架构但主从同步有延迟
   - 检查读自从库，更新写主库，导致检查时看不到最新的锁定状态
   - 读写分离场景下的数据一致性问题

**典型漏洞特征**：
- 应用启动时初始化本地map存储锁定状态，无Redis或数据库初始化
- handleLogin函数中检查本地变量 `if s.locked[username] != nil`
- 失败时调用 `db.Exec("UPDATE attempts")` 但锁定状态在内存
- Redis Set/Incr操作非事务，无 `WATCH` 或 `MULTI`
- 负载均衡配置为随机轮询或最少连接（无粘性）
- 不同服务实例使用不同的过期时间配置参数

### 误报排除

- ✗ 单实例应用且明确无负载均衡
- ✗ 使用专业分布式限流库（如Consul、etcd管理的分布式锁）
- ✗ Redis集群（Cluster模式）且正确实现了Lua脚本确保原子性
- ✗ 使用数据库级分布式锁（`SELECT ... FOR UPDATE`）确保一致性
- ✗ 所有节点通过消息队列（MQ）实时同步状态变更
- ✗ 已部署全局限流（CDN/WAF）在应用层之上
- ✗ 使用了专业的分布式追踪系统（如Jaeger）验证一致性

### 代码异味（需进一步验证）

- △ 使用了Redis但没有检查Incr操作后立即设置TTL的原子性
- △ 多个数据源间有同步延迟但能接受（最终一致性）
- △ 本地内存缓存了数据库状态但缓存更新机制不清晰
- △ 使用了中间件进行限流但中间件配置分散难以验证一致性
- △ 有分布式锁逻辑但未见清楚的锁的获取/释放/超时处理
- △ 负载均衡配置与应用状态管理的对应关系不明确

---

## Low Risk

### 给予低风险评级的场景

1. **完整的分布式状态管理**
   - 所有节点从同一Redis集群（Cluster或哨兵模式）读写锁定状态
   - 使用Redis Lua脚本或MULTI/WATCH确保原子操作
   - 计数器、锁定标志、过期时间统一管理
   - 设计文档清楚说明数据一致性保证（强一致性）

2. **充分的粘性保证**
   - 负载均衡配置了会话粘性且测试验证有效
   - Cookie中包含nodeID且后端验证，确保请求路由一致
   - 或采用clientIP粘性且有IP识别机制
   - 文档说明粘性失效时的降级策略

3. **数据库级别的一致性保证**
   - 使用 `SELECT ... FOR UPDATE` 或行锁确保计数原子性
   - 事务隔离级别为REPEATABLE_READ或SERIALIZABLE
   - 锁定状态存储在同一表，通过唯一索引+约束确保一致性
   - 无主从复制延迟或有读主库的配置

4. **消息队列同步**
   - 状态变更事件发送到MQ，所有节点订阅并更新本地缓存
   - 有幂等性保证（事件ID去重）
   - 有状态校验机制定期验证一致性
   - 设计能容忍短期的不一致（<1秒）

5. **监控和恢复机制**
   - 有实时监控检查节点间状态差异
   - 有自动修复机制（定期同步或人工告警）
   - 审计日志记录所有锁定操作，可追踪一致性问题
   - 有明确的分离点（circuit breaker）在同步失败时

6. **攻击成本极高**
   - 即使存在不一致，绕过所需改变请求特征过多（改IP + User-Agent + 多个Cookie）
   - 负载均衡算法难以被攻击者操纵（如基于请求内容哈希）
   - 单个节点也实现了严格的本地限流作为兜底

**评级建议**：低风险的前提是**有清晰的架构设计文档说明数据一致性**。即使存在小的不一致风险，若有完整的监控和恢复机制，也可给低风险。但若无任何文档或机制说明，应视为高风险。
