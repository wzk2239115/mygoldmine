# Go_Session_No_Timeout

**漏洞类型**: Gorilla Sessions 或自定义会话管理中，会话超时配置不当或完全缺失，导致会话永不过期，攻击者可长期利用被盗会话

---

## Details

### 代码示例

**易受攻击的代码模式**:
```go
// 示例1: SessionOptions 未设置 MaxAge
store := sessions.NewCookieStore([]byte("secret"))
session, _ := store.Get(r, "session_name")
session.Options = &sessions.Options{
    Path:   "/",
    MaxAge: 0, // 浏览器会话 Cookie，但无服务端超时
    HttpOnly: true,
}

// 示例2: MaxAge 设置过长
session.Options = &sessions.Options{
    MaxAge: 86400 * 365, // 365 天，过长
}

// 示例3: 自定义会话管理，无超时检查
type Session struct {
    ID    string
    UserID string
    CreatedAt time.Time
    // 缺少 ExpiresAt 或 LastActivity 字段
}

func (s *Session) IsValid() bool {
    return s.UserID != "" // 仅检查用户ID，无时间检查
}

// 示例4: 服务端会话存储无过期管理
var sessionStore = make(map[string]*Session)

func storeSession(id string, session *Session) {
    sessionStore[id] = session // 无过期时间，永久存储
}

// 示例5: 会话最后活动时间未更新
func getSession(sessionID string) (*Session, error) {
    session, ok := sessionStore[sessionID]
    if !ok {
        return nil, errors.New("not found")
    }
    // 仅返回会话，未更新 LastActivity 时间
    return session, nil
}

// 示例6: 缺少超时检查的中间件
func sessionMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        session, _ := store.Get(r, "session_name")
        if session.Values["user_id"] != nil {
            // 仅检查值存在，未检查超时
            next.ServeHTTP(w, r)
        }
    })
}

// 示例7: Redis 会话存储，无 TTL 设置
func storeInRedis(id string, data []byte) error {
    // redis.Set(id, data) 未设置过期时间
    return redisClient.Set(ctx, id, data, 0).Err() // 0 表示永不过期
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- SessionOptions 配置: `session.Options`, `&sessions.Options{}`, `MaxAge`, `Expires`
- 时间字段: `CreatedAt`, `ExpiresAt`, `LastActivity`, `LastActivityTime`
- 超时检查: `IsExpired()`, `CheckExpiry()`, `ValidateTimeout()`, `isSessionValid()`
- 会话存储: `sessionStore[id]`, `redis.Set()`, `redis.Get()`, `Set()` with TTL
- 过期清理: `expireSession()`, `cleanupExpiredSessions()`, `deleteExpired()`

**L2 跳读定位**:
- 会话初始化: 搜索 `NewCookieStore()`, `NewSessionStore()`, `store.Get()`
- 会话保存: 追踪 `session.Save()`, `store.Set()` 等操作
- 会话验证: 会话访问时是否检查超时
- 超时配置: 检查 `MaxAge` 或 TTL 设置
- 存储后端: Cookie, 内存, Redis, 数据库等不同实现

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- MaxAge 设置: `session.Options.MaxAge` 是否设置了合理值 (建议 30 分钟 - 1 小时)
- ExpiresAt 字段: Session 结构体中是否有过期时间字段
- 超时检查: 中间件或处理器中是否有 `IsExpired()` 调用

**L3 逐行分析**:
- SessionOptions 配置:
  - `MaxAge` 值是否在合理范围 (建议 1800 - 3600 秒)
  - 是否同时设置了 `Expires` 和 `MaxAge`
  - 是否设置了 `HttpOnly`, `Secure`, `SameSite`
- 会话验证逻辑:
  - `CreatedAt + MaxAge > now` 时才有效
  - 或 `ExpiresAt > now` 检查
  - 或 `LastActivity + IdleTimeout > now` 检查
  - 时间比较是否考虑了时区
- 会话获取时的操作:
  - 是否在返回前检查了超时
  - 是否更新了 `LastActivity` 时间
  - 超时后是否删除会话数据
- Redis/数据库存储:
  - `redis.Set(id, data, ttl)` 的 ttl 值
  - 是否使用 `SETEX`, `PSETEX` 等支持 TTL 的命令
  - 是否定期清理过期数据
- 并发安全:
  - 检查和删除之间是否有竞态
  - 是否需要锁保护

**L4 跨模块追踪**:
- 追踪所有会话访问点，确认都进行了超时检查
- 检查是否有后台任务定期清理过期会话
- 验证所有会话存储后端是否都配置了 TTL
- 检查中间件栈中会话验证的位置
- 审查配置文件中关于会话超时的设置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- SessionOptions.MaxAge 为 0 或未设置，会话永不过期
- 会话模型中完全缺少 ExpiresAt 或过期相关字段
- 会话验证时未检查创建时间或活动时间
- Redis/数据库存储会话时未设置 TTL
- 会话可无限期使用，无操作超时或绝对超时
- 即使客户端 Cookie 过期，服务端仍保留会话数据

**误报判定**:
- SessionOptions.MaxAge 设置了合理值 (30 分钟 - 1 小时)
- 会话有 CreatedAt 和 ExpiresAt 字段，且验证逻辑正确
- Redis/数据库使用 TTL，数据自动过期
- 有定期清理过期会话的后台任务
- 敏感操作前重新验证用户身份
- 有活动时间跟踪，操作超时独立管理

**代码异味**:
- MaxAge 设置为 24 小时或更长
- 存在 ExpiresAt 字段但验证时未使用
- 会话删除代码被注释或有条件执行
- LastActivity 时间记录但未用于超时判断
- 日志中显示会话永久存储

---

## Low risk

### 低风险场景

**架构保护**:
- 虽然会话不过期，但包含签名或加密，无法被篡改
- 即使得到会话，还需定期验证用户身份或权限
- 会话与特定 IP 或 User-Agent 绑定，环境变化时失效

**补偿控制**:
- 每个敏感操作都需要重新认证或 MFA
- 用户可以随时登出，主动清除会话
- 有详细的登录历史，用户可审计会话使用
- 异常登录时自动登出并通知用户

**检测与监控**:
- 实时监控会话活动，检测异常长会话
- 记录会话创建、使用、删除的完整历史
- 检测跨地域或跨设备的会话活动
- 定期要求用户重新登录
