# Java | 登录接口缺乏速率限制导致暴力破解

## 基本信息

- **难度等级：** ★★☆☆☆ (初级)
- **审计时间：** 15-25分钟（单个端点）
- **先决知识：** Spring Security、ServletFilter、HTTP 状态码
- **复杂度评估：**
  - 简单场景（单个登录端点）：15-20分钟
  - 复杂场景（多个登录方式、分布式系统）：25-40分钟

## 🚀 30秒快速清单

- [ ] 登录接口是否有速率限制（Rate Limiting）？
- [ ] 是否有账户锁定机制（Account Lockout）？
- [ ] 是否有验证码防护（CAPTCHA）？
- [ ] 失败尝试是否有计数和限制？
- [ ] 是否在多次失败后返回通用错误消息？

**判断：** 如果所有问题都是否定的，需要进行 L2+ 深度分析

## Details

### 漏洞成因

Java 应用（特别是使用 Spring 的应用）在实现登录接口时，如果未配置速率限制、账户锁定或验证码防护，攻击者可以通过自动化工具进行暴力破解，尝试常见密码或通过字典攻击获得访问权限。

### 代码示例

**易受攻击的代码：**
```java
@RestController
@RequestMapping("/api/login")
public class LoginController {
    @Autowired
    private UserService userService;

    @PostMapping
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        // ❌ 问题 1：没有速率限制检查
        // ❌ 问题 2：没有失败次数计数

        User user = userService.findByUsername(request.getUsername());
        if (user != null &&
            userService.validatePassword(user, request.getPassword())) {

            String token = generateToken(user);
            return ResponseEntity.ok(new LoginResponse(token));
        }

        // ❌ 问题 3：没有账户锁定机制
        // 攻击者可以无限制地尝试
        return ResponseEntity.status(401).body("Invalid credentials");
    }

    private String generateToken(User user) {
        // token 生成逻辑
        return "token";
    }
}
```

**易受攻击的场景：**
```bash
# 攻击者可以执行自动化暴力破解
for i in {1..10000}; do
  curl -X POST http://target.com/api/login \
    -d '{"username":"admin","password":"password'$i'"}'
done
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）

**关键词扫描：** 登录端点位置、`@PostMapping("/login")`、`@RequestMapping("/auth")`、用户验证逻辑

**定位步骤：**
1. 找到所有登录相关的端点（/login, /auth, /authenticate）
2. 跳读（L2）检查是否有速率限制相关的代码
3. 检查是否有账户锁定逻辑

#### 保护机制定位（审计等级：L2-L3）

**检查是否存在：**
- Spring Security 的 `LockedException` 或自定义锁定机制
- 失败次数计数（通常存储在数据库、Redis 或内存中）
- 速率限制过滤器或拦截器
- 验证码集成（Google reCAPTCHA、Aliyun Captcha 等）

**定位技巧：**
- 逐行读（L3）查找与失败计数相关的代码
- 跨模块追踪（L4）检查 Spring Security 的配置类

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 有完整防护（速率限制 + 账户锁定 + 验证码） | **L0（快速跳过）** | 风险低 |
| 有部分防护（仅有账户锁定，无速率限制） | **L2（跳读）** | 需要验证完整性 |
| 无任何防护机制 | **L3（逐行读）** | 高风险，需深入分析 |
| 多个登录端点且防护不一致 | **L4（跨模块追踪）** | 需要审计所有端点 |

## Classify

### 研判标准

#### 确认漏洞
1. 存在登录端点，允许用户认证
2. 无速率限制或账户锁定机制
3. 可通过自动化工具进行暴力破解
4. 可通过 PoC 验证：在短时间内多次尝试登录均成功

#### 误报
1. 有完整的速率限制机制（按 IP 和账户）
2. 有可靠的账户锁定（失败 N 次后锁定 ≥15 分钟）
3. 有强验证码防护
4. 登录端点仅限内网访问

#### 代码异味
1. 失败次数计数逻辑存在，但锁定阈值过高（> 10 次）
2. 账户锁定时间过短（< 5 分钟）
3. 速率限制仅按 IP，不按账户
4. 多个登录端点，防护机制不一致

## Low risk

### 低风险评级场景

#### 1. 有多层防护机制
- 速率限制 + 账户锁定 + 验证码
- 可降级为低风险

#### 2. 登录失败后有延迟（指数退避）
- 第一次失败：无延迟
- 第二次失败：延迟 1 秒
- 第三次失败：延迟 2 秒
- ...
- 可有效防止自动化攻击

#### 3. 异常登录检测
- 检测到来自多个 IP 的登录尝试
- 检测到来自异常地理位置的登录
- 自动触发额外验证（邮件、短信）

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 完整防护 | 防护机制齐全 | 低 |
| 账户重要性低 | 攻击者收益小 | 低 |
| 内网仅限 | 攻击面受限 | 低 |
| 有定期审计 | 问题易被发现 | 中 |

## 安全实现示例

### 方案 1：使用 Spring Security + 自定义失败处理

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {

    @Autowired
    private UserDetailsService userDetailsService;

    @Bean
    public AuthenticationProvider authenticationProvider() {
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider();
        provider.setUserDetailsService(userDetailsService);
        provider.setPasswordEncoder(passwordEncoder());
        return provider;
    }

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .authorizeRequests()
                .antMatchers("/api/login").permitAll()
                .anyRequest().authenticated()
            .and()
            .formLogin()
                .failureHandler(customFailureHandler())  // ✅ 自定义失败处理
            .and()
            .csrf().disable();
    }

    @Bean
    public AuthenticationFailureHandler customFailureHandler() {
        return new CustomAuthenticationFailureHandler();
    }
}
```

### 方案 2：使用 Redis 实现速率限制

```java
@Component
public class RateLimitingService {
    @Autowired
    private RedisTemplate<String, Integer> redisTemplate;

    private static final int MAX_ATTEMPTS = 5;
    private static final long LOCK_TIME_MINUTES = 15;

    public boolean isLocked(String username) {
        String key = "brute:" + username;
        Integer attempts = redisTemplate.opsForValue().get(key);
        return attempts != null && attempts >= MAX_ATTEMPTS;
    }

    public void recordFailedAttempt(String username) {
        String key = "brute:" + username;
        redisTemplate.opsForValue().increment(key);
        redisTemplate.expire(key, LOCK_TIME_MINUTES, TimeUnit.MINUTES);
    }

    public void resetAttempts(String username) {
        String key = "brute:" + username;
        redisTemplate.delete(key);
    }
}

@RestController
@RequestMapping("/api/login")
public class SecureLoginController {
    @Autowired
    private RateLimitingService rateLimitingService;

    @PostMapping
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        // ✅ 检查是否已锁定
        if (rateLimitingService.isLocked(request.getUsername())) {
            return ResponseEntity.status(429)
                .body("Too many attempts. Try again in 15 minutes.");
        }

        // 验证用户
        boolean success = authenticateUser(request);
        if (success) {
            rateLimitingService.resetAttempts(request.getUsername());
            return ResponseEntity.ok(new LoginResponse("token"));
        } else {
            // ✅ 记录失败尝试
            rateLimitingService.recordFailedAttempt(request.getUsername());
            return ResponseEntity.status(401)
                .body("Invalid credentials");
        }
    }

    private boolean authenticateUser(LoginRequest request) {
        // 认证逻辑
        return false;
    }
}
```

### 方案 3：使用 IP 级别的速率限制（Guava）

```java
@Component
public class IPRateLimiter {
    private final Map<String, RateLimiter> limiters = new ConcurrentHashMap<>();

    public boolean allowRequest(String clientIP) {
        RateLimiter limiter = limiters.computeIfAbsent(
            clientIP,
            k -> RateLimiter.create(1.0)  // 每秒 1 个请求
        );
        return limiter.tryAcquire();
    }
}

@Component
public class RateLimitingFilter extends OncePerRequestFilter {
    @Autowired
    private IPRateLimiter ipRateLimiter;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                   HttpServletResponse response,
                                   FilterChain filterChain)
            throws ServletException, IOException {

        if (request.getRequestURI().startsWith("/api/login")) {
            String clientIP = getClientIP(request);

            if (!ipRateLimiter.allowRequest(clientIP)) {
                response.setStatus(429);
                response.getWriter().write("Rate limit exceeded");
                return;
            }
        }

        filterChain.doFilter(request, response);
    }

    private String getClientIP(HttpServletRequest request) {
        // 获取真实 IP（考虑代理）
        return request.getHeader("X-Forwarded-For") != null ?
            request.getHeader("X-Forwarded-For").split(",")[0] :
            request.getRemoteAddr();
    }
}
```

## 审计检查清单

- [ ] 是否存在登录接口的速率限制？
- [ ] 是否按 IP 和账户分别进行速率限制？
- [ ] 失败次数限制是否合理（3-5 次）？
- [ ] 账户锁定时间是否足够长（≥15 分钟）？
- [ ] 是否有验证码防护？
- [ ] 是否有异常登录检测（地理位置、设备等）？
- [ ] 错误消息是否通用（未泄露用户信息）？
- [ ] 是否有失败尝试的审计日志？

## 修复优先级

1. **立即修复：** 实施基本的账户锁定机制（2-4 小时）
2. **快速修复：** 添加 Redis 或内存式速率限制（4-8 小时）
3. **长期改善：** 集成验证码和异常检测系统（1-2 周）
