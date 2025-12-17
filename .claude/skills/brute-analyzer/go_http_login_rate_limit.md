# Go HTTP登录端点速率限制缺失

**难度**：★★☆☆☆ | **审计时间**：15-20分钟 | **影响**：HIGH（无限制暴力破解） | **利用难度**：EASY

## ⚡ 审计员速查

### 30秒快速判断
搜索关键词：`login` / `auth` / `handleFunc` → 检查是否存在以下任一条件即为漏洞：
1. 无 `limiter.Allow()` / `rate.Limiter` / 第三方限流库
2. 无 `sync.Mutex` / `sync.RWMutex` / `sync.Map` 保护计数器
3. 直接使用 `X-Forwarded-For` 无验证
4. 失败计数器无过期清理机制
5. 多个登录端点但限流配置不一致

### 漏洞确认指标
- **表现**：相同IP/账户可无限次尝试登录 → 5-10分钟内可破解弱密码
- **监控**：无failed login日志或日志暴增但无限制
- **并发**：ab/wrk同时发送100+请求无任何限制

## 漏洞特征

### 成因分析
Go `net/http` 标准库无内置速率限制机制，需手动实现。常见问题链：
- 完全无限制 → 开发遗忘 / 不知道如何实现
- 仅客户端限制 → 易被绕过（HTTP工具可禁用）
- 非线程安全 map → 高并发下panic或丢失计数
- 固定窗口算法 → 存在边界绕过（同秒内切换分钟）
- 信任代理Header → 伪造X-Forwarded-For绕过限制
- 无过期机制 → 内存持续增长、OOM
- 延迟但不拒绝 → `time.Sleep()` 后仍返回200（延迟攻击）

### 典型缺陷示例

```go
// ❌ 缺陷1：完全无限制
func handleLogin(w http.ResponseWriter, r *http.Request) {
    if authenticate(r.FormValue("user"), r.FormValue("pass")) {
        http.SetCookie(w, &http.Cookie{Name: "auth", Value: token})
    } else {
        http.Error(w, "Invalid", http.StatusUnauthorized)
    }
}

// ❌ 缺陷2：非线程安全 + 信任Header + 无清理
var attempts = make(map[string]int)
ip := r.Header.Get("X-Forwarded-For") // 伪造！
if attempts[ip] >= 5 { // 数据竞争panic！
    http.Error(w, "Too many", http.StatusTooManyRequests)
}
attempts[ip]++

// ❌ 缺陷3：固定延迟无用（攻击者仍会成功）
time.Sleep(2 * time.Second)
http.Error(w, "Too many", http.StatusTooManyRequests) // 延迟后200仍返回？

// ❌ 缺陷4：客户端限制易绕过
// 前端JavaScript: if(attempts < 5) { sendLogin() }
// 攻击者：禁用JS或直接POST，检查缓存...
```

| 等级 | 场景 | 审计重点 |
|-----|------|--------|
| **L1** | 开发/演示 | 有无任何限流逻辑？ |
| **L2** | 小型生产 | 算法是否线程安全？IP验证有无？ |
| **L3** | 生产+高并发 | 内存泄漏？多端点一致？延迟是否真拒绝？ |

## 审计技巧 & 实战经验

### 🔍 代码审查要点
1. **grep定位**：`login|auth|signin` + `handler|Handler` 找所有端点
2. **检查保护**：同一处理函数中，限流检查**必须在认证前**（否则认证耗时长）
3. **内存检查**：map/slice增长是否有清理？搜索 `delete` / `time.Ticker`
4. **竞态检测**：`go test -race ./...` 运行检查数据竞争
5. **Header信任链**：追踪IP来源，nginx配置 `proxy_set_header X-Real-IP`？

### ⚠️ 常见绕过技巧
- **IP轮转**：攻击者轮换代理/VPN → 检查是否有全局限制（如账户级）
- **时间窗口边界**：固定窗口在秒/分交界刷新 → 需滑动窗口或令牌桶
- **并发突破**：100个连接同时发送 → 检查计数器是否真线程安全
- **长连接复用**：WebSocket/Server-Sent Events → 是否也限制？
- **其他端点**：`/login` 有限制但 `/api/auth` 没有？ → 需扫描所有认证点

### 🧪 验证方法
```bash
# 快速测试无限制
ab -n 100 -c 10 http://target/login -p payload.txt

# 压力测试（需wrk）
wrk -t4 -c100 -d10s http://target/login

# 检查响应时间是否均匀（没延迟=无限制）
curl -w "%{time_total}\n" http://target/login
```

### 🛡️ 安全实现方案

#### 方案A：令牌桶（推荐简单场景）
```go
var globalLimiter = rate.NewLimiter(10, 10) // 10req/s, burst=10

func handleLogin(w http.ResponseWriter, r *http.Request) {
    if !globalLimiter.Allow() {
        http.Error(w, "Rate limited", http.StatusTooManyRequests)
        return
    }
    // 认证...
}
```

#### 方案B：滑动窗口（细粒度控制）
```go
type RateLimiter struct {
    attempts map[string][]time.Time
    mu       sync.RWMutex
    window   time.Duration
    maxHits  int
}

func (rl *RateLimiter) Allow(key string) bool {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    now := time.Now()
    cutoff := now.Add(-rl.window)

    if times, ok := rl.attempts[key]; ok {
        valid := []time.Time{}
        for _, t := range times {
            if t.After(cutoff) {
                valid = append(valid, t)
            }
        }
        if len(valid) >= rl.maxHits {
            return false
        }
        valid = append(valid, now)
        rl.attempts[key] = valid
    } else {
        rl.attempts[key] = []time.Time{now}
    }
    return true
}

// 后台清理超大map
go func() {
    ticker := time.NewTicker(5 * time.Minute)
    for range ticker.C {
        rl.cleanup()
    }
}()
```

#### 方案C：双重限制（推荐生产）
```go
// IP限制：10次/分钟  账户限制：3次/30分钟
func LoginHandler(w http.ResponseWriter, r *http.Request) {
    ip := getClientIP(r)
    if !ipLimiter.Allow(ip) {
        h := w.Header()
        h.Set("Retry-After", "60")
        http.Error(w, "Too many login attempts from your IP", http.StatusTooManyRequests)
        return
    }

    username := r.FormValue("username")
    if !accountLimiter.Allow(username) {
        h := w.Header()
        h.Set("Retry-After", "900")
        http.Error(w, "Account temporarily locked", http.StatusTooManyRequests)
        return
    }
    // 认证...
}

func getClientIP(r *http.Request) string {
    // 优先级：X-Real-IP > X-Forwarded-For > RemoteAddr
    if xff := r.Header.Get("X-Forwarded-For"); xff != "" && isLocalIP(r.RemoteAddr) {
        return strings.TrimSpace(strings.Split(xff, ",")[0])
    }
    if xri := r.Header.Get("X-Real-IP"); xri != "" && isLocalIP(r.RemoteAddr) {
        return xri
    }
    ip, _, _ := net.SplitHostPort(r.RemoteAddr)
    return ip
}

func isLocalIP(ip string) bool {
    return strings.HasPrefix(ip, "127.") || strings.HasPrefix(ip, "10.") || strings.HasPrefix(ip, "172.")
}
```

### 修复优先级
1. **P0**：添加IP级限流（5min内）→ 直接阻止暴力破解
2. **P1**：添加账户级限流 → 防止枚举有效用户
3. **P2**：验证代理IP来源 → 防止Header伪造
4. **P3**：内存清理机制 → 防止OOM / DoS
5. **P4**：多端点一致性检查 → 防止漏掉其他认证点

