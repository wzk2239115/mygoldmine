# Go_Session_ID_Predictable

**漏洞类型**: Gorilla Sessions 或自定义会话管理中，会话ID生成使用时间戳或可预测的随机算法，导致会话ID可枚举或预测

---

## Details

### 代码示例

**易受攻击的代码模式**:
```go
// 示例1: 使用时间戳生成会话ID
func createSession(w http.ResponseWriter, r *http.Request) {
    sessionID := fmt.Sprintf("%d", time.Now().Unix()) // 可预测的时间戳
    http.SetCookie(w, &http.Cookie{
        Name:  "session_id",
        Value: sessionID,
        Path:  "/",
    })
}

// 示例2: 弱随机数生成器
import "math/rand"
func generateSessionID() string {
    rand.Seed(time.Now().UnixNano())
    id := rand.Intn(1000000)
    return fmt.Sprintf("%06d", id) // 熵值极低
}

// 示例3: Gorilla Sessions 配置不当
store := sessions.NewCookieStore([]byte("weak_secret"))
session, _ := store.Get(r, "session_key")
// SessionOptions 未设置或使用默认配置，可导致ID生成不安全

// 示例4: 自定义会话ID算法
func unsafeSessionID() string {
    seed := time.Now().Unix() / 1000 // 时间戳精度低
    h := sha1.New()
    h.Write([]byte(fmt.Sprintf("%d", seed)))
    return hex.EncodeToString(h.Sum(nil))[:16]
}

// 示例5: 递增会话ID
var sessionCounter int = 1000
func nextSessionID() string {
    sessionCounter++
    return fmt.Sprintf("SESSION_%d", sessionCounter)
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 会话ID生成: `sessions.NewCookieStore()`, `Store.Get()`, `Store.Set()`, 自定义 `generateSessionID()`, `createSession()`, `sessionID()`
- 弱随机数来源: `math/rand.Rand`, `math/rand.Intn()`, `math/rand.Int63()`, `time.Now().Unix()`, `time.Now().UnixNano()`
- 时间戳相关: `time.Now()`, `time.Unix()`, `UnixNano()` 直接用于ID生成
- 会话存储: `http.SetCookie()`, `session.Values[]`, `Cookie{Value:}` 赋值
- 弱哈希算法: `sha1.New()`, `md5.New()` 用于ID生成

**L2 跳读定位**:
- 会话创建路由/处理函数: 搜索 `/login`, `/auth`, `/session` 相关端点
- 追踪会话ID从生成到存储的数据流
- 关键判断点: 是否使用 `crypto/rand` 还是 `math/rand`
- 检查 `NewCookieStore()` 或 `NewSessionStore()` 初始化参数
- 查看是否有自定义的ID生成逻辑，而非使用框架内置机制

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 安全随机数导入: `import "crypto/rand"`, `gobwas/glob`, `gorilla/sessions` 的使用
- 会话存储初始化: `session.Options` 配置检查，如 `HttpOnly: true`, `Secure: true`
- ID生成调用: 是否使用 `rand.Read()` 或 `generateSessionID()` 等安全函数

**L3 逐行分析**:
- `math/rand` vs `crypto/rand`: 确认是否使用了密码学安全的随机数生成器
- 随机数熵值: `rand.Read()` 读取足够字节数 (建议 >= 32 字节)
- 时间戳使用: 是否直接将时间戳用于ID生成或仅作为种子
- 编码方式: `hex.EncodeToString()`, `base64.StdEncoding.EncodeToString()` 确保完整熵值
- Gorilla Sessions 配置:
  - 检查 `session.Options.Path`, `Domain`, `HttpOnly`, `Secure`, `SameSite` 设置
  - 确认 `MaxAge` 和过期时间设置是否合理
- Cookie Store 密钥长度: 检查 `NewCookieStore()` 的密钥是否足够强 (>= 32 字节)

**L4 跨模块追踪**:
- 追踪 Gorilla Sessions 框架的会话存储实现 (Cookie Store vs Database Store)
- 检查是否有自定义的 `SessionStore` 接口实现
- 验证会话ID是否在持久化到数据库时也保持安全生成
- 检查会话中间件是否对所有会话操作统一处理
- 审查配置管理或环境变量中关于会话安全的设置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 会话ID使用 `math/rand` 而非 `crypto/rand` 生成
- ID由时间戳直接构成或使用可预测的时间戳作为种子
- ID为递增序列或遵循明显的数学规律
- 会话ID长度过短 (< 16 字节) 或熵值明显不足
- 两个会话的ID间隔固定且易于预测 (如仅相差常数)
- 即使使用 `crypto/rand`，生成过程中有信息泄露 (如会话时间戳可见)
- 无法通过统计分析或暴力枚举区分有效和无效会话ID

**误报判定**:
- 使用 Gorilla Sessions 框架且未自定义ID生成逻辑，框架内置使用安全随机数
- 会话ID由密码学安全的随机数生成器产生，熵值充分 (>= 128 bits)
- 会话存储在服务端数据库中，ID作为令牌存储，不依赖可预测的ID本身
- 应用有额外的会话验证机制 (如签名、加密、服务端映射)，即使ID被预测也无法伪造有效会话
- ID虽含时间戳但有大量随机组件，时间戳部分不可单独利用

**代码异味**:
- 混合使用 `math/rand` 和 `crypto/rand`，但主要逻辑基于 `math/rand`
- 会话ID包含用户可预测的信息 (如用户ID、时间戳) 作为组成部分
- ID生成调用时未初始化或seed初始化方式不安全
- 会话ID长度在16-31字节之间，处于临界值
- 框架级会话管理配置不完整，缺少HttpOnly或Secure等保护标志

---

## Low risk

### 低风险场景

**架构层面保护**:
- 会话ID虽可预测，但存储在服务端数据库中，通过ID查询时还需验证签名或MAC
- 服务端对每个会话ID维护强绑定的用户身份，ID仅作为索引，无法伪造
- 即使会话ID被预测，后续请求需进行CSRF令牌验证或其他状态检查

**访问限制**:
- 会话功能仅限内网或VPN用户访问，公网环境不可直接进行会话枚举
- 应用有严格的速率限制，无法进行批量会话ID枚举 (如每秒最多10次尝试)
- 单个用户并发会话数严格限制，无法保持多个预测的会话同时活跃

**检测与监控**:
- 有详细的会话审计日志，可记录所有会话创建、使用、销毁事件
- 实时监控异常会话活动 (如频繁的ID枚举请求、跨地域登陆、并发会话)
- 会话异常时主动通知用户，并要求重新认证

**补偿控制**:
- 会话超时设置极短 (如 5-10 分钟)，即使被预测的会话也难以长期利用
- 每次敏感操作前重新验证用户身份 (如支付、修改密码、权限变更)
- 会话与IP、User-Agent 等客户端特征绑定，跨环境使用无效
- 应用中敏感数据操作均需二次认证 (MFA、邮箱确认等)
