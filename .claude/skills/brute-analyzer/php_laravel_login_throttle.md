# Laravel 登录节流防护缺失

## Details

### 代码示例
```php
// 易受攻击的登录控制器
class LoginController extends Controller
{
    public function login(Request $request)
    {
        $credentials = $request->validate([
            'email' => 'required|email',
            'password' => 'required'
        ]);

        if (Auth::attempt($credentials)) {
            return redirect()->route('dashboard');
        }

        return back()->withErrors(['email' => 'Invalid credentials']);
    }
}

// 路由定义（未应用节流）
Route::post('/login', [LoginController::class, 'login']);
```

### 核心操作定位 **[L1: 关键词扫描]**
- **搜索关键词**：`login`, `authenticate`, `post /login`, `password_verify`, `Auth::attempt`
- **扫描位置**：登录相关的控制器方法、路由定义、表单处理
- **快速识别技巧**：查找处理用户身份验证的方法，确认是否在路由或控制器中明确应用了速率限制

### 保护机制定位 **[L2: 跳读]**
- **中间件检查**：查看路由中是否应用了 `throttle:` 中间件
  - 完整模式：`Route::post('/login', [...]);->middleware('throttle:5,1')`
  - 检查位置：路由文件（`routes/web.php`, `routes/api.php`）、控制器方法上的属性、中间件组配置
- **配置检查**：验证 `config/hashing.php` 和认证相关配置
- **防护层级**：
  - **L3: 逐行读**：审查中间件参数含义（请求上限数、时间窗口），确认阈值是否合理（通常登录应为 5-10次/分钟）
  - **L4: 跨模块追踪**：追踪速率限制是否在负载均衡器、网关、WAF 层面实现，检查分布式环境下的一致性

---

## Classify

### 漏洞识别标准
- **完全缺失**：未在任何层面应用节流防护，登录端点允许无限制请求
- **配置过宽松**：应用了节流但阈值过高（如 100次/分钟），无法有效防御
- **实现不完整**：仅在部分认证路由上应用，忽略了其他可达成认证的端点（如 API 登录、社交登录、密码重置接口）

### 误报判断
- 应用了合理阈值的 `throttle` 中间件且覆盖所有认证入口
- 在网络层（负载均衡器、WAF）实现了等效的速率限制
- 实现了基于 IP + 用户标识的自适应限流（如 fail2ban）

### 代码异味
- 硬编码的延迟机制（如 `sleep()` 或 `usleep()`）而非中间件
- 手动实现的限流逻辑而未使用 Laravel 内置机制
- 日志记录失败次数但无相应的限制操作

---

## Low risk

### 低风险评级情形
- **受保护的认证**：登录端点已通过 `throttle` 中间件或等效机制限制频率
- **合理阈值**：速率限制设置为 5-10 次请求/分钟，符合行业标准
- **全面覆盖**：所有可能的认证入口（含 API、密码重置、验证码校验）均有相应保护
- **环境隔离**：开发/测试环境中虽未限流，但生产环境已配置防护
- **附加防御**：同时实施了验证码验证、账户临时锁定、登录日志告警等多层防护

---

## 审计专业技巧 **[审计人员必读]**

### 1. 真实漏洞与误报的区分经验

#### **真实漏洞的典型特征**
```php
// 漏洞特征1：完全缺失节流配置
Route::post('/login', [LoginController::class, 'login']);
Route::post('/auth/check', [AuthController::class, 'check']);
// 无任何 ->middleware('throttle') 声明

// 漏洞特征2：使用自定义认证库，绕过 Laravel 框架保护
class CustomAuthController extends Controller {
    public function login(Request $request) {
        // 直接查询数据库，未通过 Laravel Auth 系统
        $user = DB::table('users')->where('email', $request->email)->first();
        if (password_verify($request->password, $user->password)) {
            // 无任何速率限制检查
            session(['user_id' => $user->id]);
        }
    }
}

// 漏洞特征3：节流中间件被错误配置
->middleware('throttle:1000,1')  // 阈值过高（1000次/分钟是误配）

// 漏洞特征4：仅在特定环境限流
if (app()->isProduction()) {
    Route::middleware('throttle:5,1')->post('/login', [LoginController::class, 'login']);
} else {
    Route::post('/login', [LoginController::class, 'login']);  // 测试环境无保护
}
```

#### **常见误报场景**
1. **认证缓存导致的假正常**
   - 现象：登录成功后，相同用户多次请求未被限流
   - 原因：已认证用户的请求被缓存或豁免
   - 验证方法：使用不同用户账号或失败凭证重复测试

2. **WAF 层面的保护被误认为应用层保护**
   - 现象：HTTP 429 响应来自 nginx/cloudflare，而非 Laravel
   - 识别方法：查看响应头 `X-RateLimit-*` 或特定的 WAF 标识
   - 审计建议：需同时确认应用层配置

3. **Rate Limit 重置后的虚假通过**
   - 现象：时间窗口结束后请求成功
   - 正常行为：这是节流的设计特性
   - 漏洞判断：如果窗口过长（>5分钟）则可考虑配置不当

### 2. 进阶审计检查清单

#### **Step 1: 静态代码扫描**
```bash
# 在 routes 目录中查找所有登录相关路由
grep -r "login\|auth\|password.*reset" routes/

# 检查是否使用了 throttle 中间件
grep -r "throttle" routes/ | grep -E "login|auth"

# 查找自定义认证处理（可能绕过框架保护）
grep -r "password_verify\|Auth::attempt\|bcrypt" app/

# 定位认证相关的 API 路由
grep -r "api.*login\|login.*api" routes/api.php
```

#### **Step 2: 配置文件验证**
- 检查 `config/auth.php` 的认证驱动配置
- 验证 `app/Http/Middleware/ThrottleRequests.php` 是否被自定义修改
- 查看 `config/hashing.php` 确认密码算法（与性能限制相关）

#### **Step 3: 中间件链路追踪**
```php
// 不要只看路由定义，还要追踪中间件的应用
// 中间件可能在以下位置应用：

// 1. 路由级别
Route::post('/login', [LoginController::class, 'login'])->middleware('throttle:5,1');

// 2. 路由组级别
Route::middleware(['throttle:5,1'])->group(function () {
    Route::post('/login', [LoginController::class, 'login']);
});

// 3. 控制器级别
class LoginController {
    public function __construct() {
        $this->middleware('throttle:5,1')->only('login');
    }
}

// 4. 中间件组（app/Http/Kernel.php）
protected $middlewareGroups = [
    'web' => [
        // throttle 可能在这里
    ]
];
```

#### **Step 4: 实际测试验证**
```bash
# 快速爆破测试（超过限流阈值）
for i in {1..10}; do
  curl -X POST http://target/login \
    -d "email=test@example.com&password=wrong" \
    -w "\nStatus: %{http_code}\n"
done

# 观察第几个请求开始返回 429 或 430（取决于配置）
# 如果超过 15 次还未被限制，则为漏洞

# 改变 IP（使用代理）重新测试
# 验证是否基于 IP 地址限流
```

### 3. 分层防御评估

| 防御层级 | 检查方式 | 重要性 |
|---------|--------|------|
| 应用层 | 检查路由/中间件配置 | **必需** |
| 框架层 | 验证 Laravel Auth 机制 | 推荐 |
| 网络层 | WAF/负载均衡器配置 | 推荐 |
| 业务层 | 验证码、账户锁定、日志告警 | 加分项 |

### 4. 真实案例对比

**案例A：真实漏洞（高风险）**
- 登录端点无任何速率限制
- 自定义认证绕过框架保护
- 测试可在 1 秒内发送 100+ 个请求均返回 200/401
- **评级**：Critical

**案例B：误报（实际安全）**
- 应用层未配置，但 Cloudflare 层面配置了速率限制
- 人工测试时看到 429 响应
- 需验证：生产环境 WAF 配置、回源策略
- **评级**：需二次确认，可能为 Low（取决于 WAF 覆盖范围）

**案例C：配置不当（中等风险）**
- 配置了 `throttle:100,1`（100次/分钟）
- 从安全角度仍存在风险，但比无保护好
- **评级**：Medium（建议优化到 5-10 次/分钟）

### 5. 常见逃逸技巧与对策

| 攻击者策略 | 检查方式 | 对应防御 |
|-----------|--------|--------|
| 轮流切换账号爆破 | 检查是否限制失败次数而非请求数 | 需账户级限流 |
| 分布式爆破（多 IP）| 基于 IP 的限流失效 | 需基于用户名/邮箱的限流 |
| 代理池绕过 | 轮换代理突破 IP 限流 | 结合 fail2ban + 验证码 |
| 慢速爆破（每分钟 2 次）| 绕过时间窗口限制 | 长期账户锁定机制 |
