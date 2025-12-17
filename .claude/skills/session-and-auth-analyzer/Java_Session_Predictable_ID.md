# Java_Session_Predictable_ID

**漏洞类型**: Java Servlet 或 Spring 会话管理中，会话ID由可预测的算法生成，导致会话ID可被枚举或预测，攻击者可伪造有效会话

---

## Details

### 代码示例

**易受攻击的代码模式**:
```java
// 示例1: 使用递增会话ID
private static int sessionCounter = 1000;
public static String generateSessionId() {
    sessionCounter++;
    return "SESSION_" + sessionCounter;
}

// 示例2: 使用时间戳生成会话ID
public String createSession() {
    String sessionId = Long.toString(System.currentTimeMillis());
    session.setAttribute("id", sessionId);
    return sessionId;
}

// 示例3: 使用弱随机数
import java.util.Random;
private Random rand = new Random();
public String generateSessionId() {
    return "SESSION_" + rand.nextInt(1000000);
}

// 示例4: UUID 但可预测的种子
public String createSessionId() {
    Random random = new Random(System.nanoTime() / 1000);
    UUID uuid = new UUID(random.nextLong(), random.nextLong());
    return uuid.toString();
}

// 示例5: 自定义 SessionManager 使用弱算法
public class CustomSessionManager {
    private int sessionCounter = 0;
    
    public String generateId() {
        return "USER_" + (++sessionCounter);
    }
}

// 示例6: Spring Security 会话ID未更改
@Override
protected void doFilterInternal(HttpServletRequest request, 
    HttpServletResponse response, FilterChain chain) {
    HttpSession session = request.getSession(true);
    // 登录前后 session ID 不变，存在会话固定风险
}

// 示例7: HashCode 生成会话ID
public String generateSessionId(User user) {
    return Integer.toHexString(user.hashCode());
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 会话生成: `generateSessionId()`, `createSessionId()`, `getSession()`
- 弱随机数: `java.util.Random`, `Math.random()`, `System.nanoTime()`
- 时间戳: `System.currentTimeMillis()`, `System.nanoTime()`, 用于会话ID
- 计数器: `sessionCounter++`, `++counter`, 递增变量
- 不安全函数: `hashCode()`, `toString()` 用于会话ID

**L2 跳读定位**:
- 会话创建: 登录处理函数，`HttpSession session = request.getSession()`
- 会话ID访问: `session.getId()`, 查看如何使用
- 会话验证: 检查会话ID验证逻辑
- Spring Security 配置: SessionManagementFilter, ConcurrentSessionFilter

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- SecureRandom 使用: `import java.security.SecureRandom`, `new SecureRandom()`
- 会话ID 更新: `HttpServletRequest.changeSessionId()`, `request.changeSessionId()`
- 安全配置: Spring Security 的 SessionFixationProtection

**L3 逐行分析**:
- 会话ID生成:
  - 是否使用 `java.security.SecureRandom` 而非 `java.util.Random`
  - 是否直接使用时间戳或计数器
  - 是否使用足够长的随机数 (建议 >= 128 bits)
  - 编码方式是否完全保留熵值 (hex 编码较安全)
- Servlet API:
  - 是否重写了 Servlet 的会话管理
  - 默认的会话ID生成是否被改写为弱算法
  - 是否有 `javax.servlet.http.HttpSessionIdListener`
- Spring Security:
  - `sessionFixationProtection` 是否启用
  - `sessionCreationPolicy` 是否为 `ALWAYS` 或 `STATELESS`
  - 登录前后是否调用了 `changeSessionId()`
- 自定义 SessionManager:
  - 是否重写了 Tomcat/Jetty 的会话管理
  - 会话ID 是否通过密码学安全的方式生成

**L4 跨模块追踪**:
- 追踪 Servlet 容器的会话管理实现 (Tomcat, Jetty, JBoss 等)
- 检查 Spring Security 的会话策略配置
- 验证所有登录路由是否都更新了会话ID
- 检查是否有自定义的会话监听器
- 审查容器配置文件中的会话设置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 会话ID由递增计数器生成
- 会话ID 直接由时间戳组成或通过时间戳生成
- 使用 `java.util.Random` 而非 `SecureRandom`
- 会话ID 长度过短 (< 16 字节) 或熵值不足
- 登录前后会话ID 不变 (会话固定)
- 可通过统计分析或简单的模式识别预测会话ID

**误报判定**:
- 使用 `java.security.SecureRandom` 生成会话ID
- 默认的 Servlet API 会话管理，无自定义
- Spring Security 启用了会话固定保护
- 登录后自动调用 `changeSessionId()`
- 会话ID 由密码学安全的随机数生成

**代码异味**:
- 会话ID 生成函数存在但似乎被忽视
- 有多个会话ID生成入口，部分使用安全方法，部分不使用
- 注释中提到会话ID应该随机但代码使用时间戳
- 自定义 SessionManager 但实现不当

---

## Low risk

### 低风险场景

**架构保护**:
- 即使会话ID被预测，验证时也需要检查签名或MAC
- 服务端对会话ID进行加密存储
- 会话ID与用户特征绑定 (IP, User-Agent)

**检测与监控**:
- 实时检测异常会话活动
- 记录会话创建和使用的完整历史
- 检测到并发会话时告警

**补偿措施**:
- 会话超时极短 (5-10 分钟)
- 敏感操作需重新认证
- 定期强制用户重新登录
