# Java Spring Security认证暴力破解防护缺失

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-30分钟
- **出现频率：** 65% (互联网应用普遍缺失)

## 🚀 30秒快速清单
- [ ] `WebSecurityConfigurerAdapter`中是否有自定义`AuthenticationFailureHandler`？
- [ ] 是否有`OncePerRequestFilter`实现速率限制（Check IP+账户维度）？
- [ ] 失败计数是否持久化到Redis/DB（非HashMap/ConcurrentHashMap）？
- [ ] 账户锁定时间≥15分钟且检查点正确（`UserDetailsService`和Filter中）？
- [ ] 3次失败后是否强制CAPTCHA验证？
- [ ] 所有认证端点（表单/API/OAuth）防护策略**一致**吗？
- [ ] 错误消息统一为`"Invalid credentials"`（防用户枚举）？
- [ ] 是否`.maximumSessions(1)`限制并发会话？
- [ ] HTTP Basic认证是否也有防护（常被遗漏）？

## 漏洞核心特征

### ⚠️ 高频缺陷模式（审计时优先检查）

| 缺陷类型 | 表现形式 | 风险等级 | 快速定位 |
|---------|--------|--------|--------|
| **无失败记录** | `failureUrl("/login?error")`无Handler实现 | 🔴 严重 | Grep`.failureUrl`和`failureHandler` |
| **内存锁定** | `HashMap<String, Integer> failureCount` | 🔴 严重 | 搜索`HashMap`/`ConcurrentHashMap`存储计数 |
| **多端点绕过** | 表单登录有防护，API端点`authenticationManager.authenticate()`裸调 | 🔴 严重 | 查找所有`/login`、`/api/auth`、`/oauth/token` |
| **信息泄露** | 异常信息区分用户是否存在：`UsernameNotFoundException` vs `BadCredentialsException` | 🟠 高 | 检查异常处理的错误消息 |
| **无会话限制** | 同账户可无限并发登录 | 🟠 高 | 找不到`.maximumSessions()` |
| **HTTP Basic无防护** | `.httpBasic()`配置无失败处理 | 🟠 高 | 检查httpBasic()块 |
| **Remember-me弱化** | `.key("hardcode")` 或 Token有效期>7天 | 🟡 中 | 搜索`.rememberMe()`和`tokenValiditySeconds` |

## Details

### 漏洞成因
Spring Security 默认无暴力破解防护，需显式实现。关键缺失：
1️⃣ **无失败追踪**：默认Handler不记录，需自定义`AuthenticationFailureHandler`
2️⃣ **无限制尝试**：无Filter限制频率（IP级、账户级）
3️⃣ **内存易失**：锁定状态存本地导致重启失效、分布式不同步
4️⃣ **多端点混乱**：表单、API、OAuth各自实现，防护不一致
5️⃣ **信息泄露**：异常映射暴露用户存在性
6️⃣ **会话滥用**：无限并发登录消耗资源

### 核心漏洞代码示例

#### 漏洞1：无失败记录 + 无速率限制
```java
// ❌ 危险：默认配置无任何防护
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http.formLogin()
            .loginPage("/login")
            .failureUrl("/login?error=true")  // 仅重定向，不记录失败
            .permitAll();
    }
}
// 攻击者可无限尝试，无任何计数记录
```

**审计技巧**：搜索`.failureUrl()`或`.failureHandler()`：
- ✗ 只有`failureUrl`无`failureHandler`实现
- ✓ 应有自定义`AuthenticationFailureHandler`实现

#### 漏洞2：内存存储失败计数（重启失效）
```java
// ❌ 严重：HashMap存储，非线程安全且重启后丢失
@Service
public class UserDetailsServiceImpl implements UserDetailsService {
    private Map<String, Integer> failureCount = new HashMap<>();  // 内存！

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        Integer failures = failureCount.getOrDefault(username, 0);
        if (failures >= 5) {
            throw new LockedException("Account locked");  // 假锁定
        }
        // ...
    }
}
// 问题：HashMap非线程安全、重启丢失、分布式环境各实例计数不同步
```

**审计技巧**：Grep搜索`HashMap<String, Integer>`或`ConcurrentHashMap`存储计数

#### 漏洞3：多端点防护不一致（API端点绕过）
```java
// ❌ 表单登录有防护，API端点无防护
@RestController
public class ApiAuthController {
    @PostMapping("/api/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest req) {
        // 直接调用authenticationManager，未经过FailureHandler和Filter！
        authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(req.getUsername(), req.getPassword())
        );
    }
}
// 攻击者在表单被锁后，直接打API端点继续破解
```

**审计技巧**：搜索所有认证端点`/login`、`/api/auth`、`/oauth/token`，验证均有防护

#### 漏洞4：信息泄露（用户枚举）
```java
// ❌ 异常映射暴露用户存在性
if (exception instanceof UsernameNotFoundException) {
    errorMessage = "User not found";  // 泄露！
} else if (exception instanceof BadCredentialsException) {
    errorMessage = "Invalid password";  // 泄露！
}
// 攻击者通过错误信息枚举有效用户
```

**审计技巧**：检查`AuthenticationFailureHandler`是否所有异常统一返回"Invalid credentials"

#### 漏洞5：无会话限制（资源耗尽）
```java
// ❌ 无.maximumSessions()导致无限并发登录
http.sessionManagement()
    .sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED)
    // 缺少：.maximumSessions(1).maxSessionsPreventsLogin(true)
```

**审计技巧**：搜索`.sessionManagement()`块，应包含`.maximumSessions(1)`

#### 漏洞6：Remember-me弱配置
```java
// ❌ 硬编码密钥+长有效期（>7天）
.rememberMe()
    .key("mySecretKey")  // 硬编码危险！
    .tokenValiditySeconds(86400 * 30)  // 30天太长！
```

**审计技巧**：搜索`.rememberMe()`，检查密钥源和有效期

---

## 快速审计清单（Field Testing Checklist）

### 📋 审计步骤（按优先级）
1. **全局搜索**：查找`WebSecurityConfigurerAdapter`、`@EnableWebSecurity`
2. **失败处理**：检查`failureHandler()`或`failureUrl()`实现
3. **多端点追踪**：找所有包含认证的`@PostMapping`（包括API、OAuth）
4. **存储检查**：Grep `HashMap`/`ConcurrentHashMap`/`failureCount`
5. **会话限制**：搜索`.maximumSessions()`
6. **HTTP Basic**：检查`.httpBasic()`块是否也有防护
7. **异常处理**：验证异常消息是否统一
8. **Remember-me**：检查密钥和有效期

### 🔴 一句话判断漏洞
```
无failureHandler实现 || 内存存储计数 || 多端点防护不一致 || 异常暴露用户存在 → 漏洞确认
```

### ✅ 正确防护的标志
```java
// 四个关键信号都需要有：
1. 自定义AuthenticationFailureHandler记录失败
2. Redis/DB持久化计数（非内存）
3. 所有认证端点统一防护策略
4. 统一错误消息"Invalid credentials" + HTTP 401
```

---

## Classify

### ✅ 确认漏洞（满足任意一条）
| # | 漏洞特征 | 确认方法 |
|---|--------|--------|
| 1 | 无自定义`AuthenticationFailureHandler` | `.failureUrl()`无对应Handler类 |
| 2 | 失败计数存内存（`HashMap`/`ConcurrentHashMap`） | Grep文件中的`Map<String, Integer>` |
| 3 | 多端点防护不一致（表单有防护，API无防护） | 找所有`/login/*`相关端点，验证防护 |
| 4 | 异常映射泄露用户存在性 | 异常处理返回`"User not found"` vs `"Invalid password"` |
| 5 | 无会话限制（可无限并发登录） | 找不到`.maximumSessions(1)` |
| 6 | HTTP Basic认证无防护 | `.httpBasic()`块无`failureHandler()` |
| 7 | Remember-me硬编码密钥+长有效期 | `.key("literal")` 或 `tokenValiditySeconds > 604800` |

### ❌ 误报排除（全部满足才为低风险）
- ✓ 有自定义`AuthenticationFailureHandler`持久化记录到Redis/DB
- ✓ 有专用Filter限制IP级频率（如10次/分钟）和账户级（如5次/分钟）
- ✓ 账户锁定≥15分钟，存储在Redis或DB（可验证：测试登录5次失败后是否立即被锁）
- ✓ 所有认证端点（表单、API、OAuth）统一返回`"Invalid credentials"` + HTTP 401
- ✓ `.maximumSessions(1).maxSessionsPreventsLogin(true)`配置存在
- ✓ Remember-me使用`PersistentTokenRepository` + 有效期≤7天 + 密钥从配置获取

### 🟡 代码异味（需进一步验证）
- △ FailureHandler仅记录日志，未限制后续尝试
- △ 失败计数存`ConcurrentHashMap`内存（改进：需持久化到Redis）
- △ 锁定时间5-10分钟（建议≥15分钟）
- △ 仅主端点有防护，JWT/API端点防护不同
- △ 没有审计日志（Spring Security Events）
- △ 分布式环境无Redis同步失败计数（各实例各自维护）

---

## 安全实现方案

### 方案1️⃣：FailureHandler + LoginAttemptService（Redis）

```java
@Component @RequiredArgsConstructor
public class CustomAuthenticationFailureHandler extends SimpleUrlAuthenticationFailureHandler {
    private final LoginAttemptService loginAttemptService;

    @Override
    public void onAuthenticationFailure(HttpServletRequest req, HttpServletResponse res,
                                       AuthenticationException e) throws IOException {
        String username = req.getParameter("username");
        loginAttemptService.loginFailed(username, getClientIP(req));

        if (loginAttemptService.getFailureCount(username) >= 3) {
            req.getSession().setAttribute("requireCaptcha", true);
        }
        setDefaultFailureUrl("/login?error=invalid");
        super.onAuthenticationFailure(req, res, e);
    }
}

@Service @RequiredArgsConstructor
public class LoginAttemptService {
    private final RedisTemplate<String, Object> redis;

    public void loginFailed(String username, String ip) {
        String userKey = "login:attempts:user:" + username;
        Long attempts = redis.opsForValue().increment(userKey);
        if (attempts == 1) redis.expire(userKey, 15, TimeUnit.MINUTES);

        if (attempts >= 5) {
            redis.opsForValue().set("login:locked:" + username, "true", 15, TimeUnit.MINUTES);
        }
    }

    public boolean isLocked(String username) {
        return redis.hasKey("login:locked:" + username);
    }
}
```

### 方案2️⃣：RateLimitFilter + Security配置

```java
@Component @RequiredArgsConstructor
public class RateLimitFilter extends OncePerRequestFilter {
    private final LoginAttemptService loginAttemptService;

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res,
                                   FilterChain chain) throws ServletException, IOException {
        if (isLoginRequest(req)) {
            String username = req.getParameter("username");
            if (username != null && loginAttemptService.isLocked(username)) {
                res.setStatus(403);
                res.getWriter().write("Account locked. Try again in 15 minutes.");
                return;
            }
        }
        chain.doFilter(req, res);
    }
}

@Configuration @EnableWebSecurity @RequiredArgsConstructor
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .addFilterBefore(rateLimitFilter, UsernamePasswordAuthenticationFilter.class)
            .formLogin()
                .failureHandler(customFailureHandler)
                .permitAll()
            .and()
            .sessionManagement()
                .maximumSessions(1)
                .maxSessionsPreventsLogin(true)
            .and().and()
            .rememberMe()
                .key("${REMEMBER_ME_KEY}")
                .tokenValiditySeconds(604800);
    }
}
```

## 修复优先级

| 级别 | 任务 | 验证方法 |
|-----|------|--------|
| P0 | FailureHandler + Redis存储 | 5次失败后第6次被拒 |
| P0 | 统一错误消息 | 同一消息给所有用户 |
| P1 | RateLimitFilter限制 | 多次请求被拒 |
| P1 | 锁定时间≥15分钟 | Redis键`login:locked:*` |
| P2 | 多端点防护一致 | 所有auth端点防护 |
| P2 | 会话限制 | 两个浏览器仅一个活跃 |
| P2 | CAPTCHA验证 | 3次失败后显示 |
