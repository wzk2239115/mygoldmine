# PHP_MFA_State_Not_Verified

**漏洞类型**: Laravel/PHP 多因素认证实现中，MFA 验证状态未正确检查，导致 MFA 验证可被跳过，攻击者可绕过二次认证

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 示例1: 登录后直接设置认证状态，未检查MFA
function login(Request $request) {
    if (Auth::attempt(['email' => $email, 'password' => $password])) {
        Auth::login($user); // 直接认证用户，未要求MFA
        return redirect('/dashboard');
    }
}

// 示例2: MFA状态检查缺失
public function dashboard() {
    if (Auth::check()) {
        return view('dashboard'); // 仅检查是否登录，未检查MFA状态
    }
    return redirect('/login');
}

// 示例3: MFA验证后未正确设置状态
function verifyMFA(Request $request) {
    $mfaCode = $request->input('mfa_code');
    $user = Auth::user();
    // 未验证 $user->mfa_enabled 或 $user->mfa_verified
    Auth::login($user);
    return redirect('/dashboard');
}

// 示例4: 会话中MFA状态可被篡改
public function verifyTwoFactor(Request $request) {
    $code = $request->input('code');
    if ($this->validateCode($code)) {
        session()->put('2fa_verified', true); // 可被前端改篡
        return response()->json(['success' => true]);
    }
}

// 示例5: MFA绕过 - 直接访问需要MFA的页面
Route::get('/sensitive-data', function() {
    // 缺少 MFA 验证中间件
    return Auth::user()->sensitiveData();
})->middleware('auth');

// 示例6: 前端检查MFA状态而非后端
function isMFAEnabled() {
    return localStorage.getItem('mfa_verified') === 'true'; // 后端未检查
}

// 示例7: MFA验证步骤可被跳过
public function loginFlow(Request $request) {
    $step = $request->input('step'); // 用户可控的步骤参数
    if ($step == 2) { // 步骤2应该是MFA验证
        // 但用户可能跳过，直接访问step=3
        return $this->step3();
    }
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- MFA验证函数: `verifyMFA()`, `verifyTwoFactor()`, `validate2FA()`, `checkMFA()`, `verifyOTP()`
- MFA检查缺失: 路由或控制器方法中仅有 `Auth::check()` 而无MFA检查
- MFA状态字段: `mfa_enabled`, `mfa_verified`, `two_factor_enabled`, `2fa_verified`, `totp_enabled`
- 会话操作: `session()->put()`, `session()->get()`, `$_SESSION[]` 中与MFA相关的状态
- 中间件缺失: 搜索 `middleware('auth')` 但未看到 `middleware('mfa')` 或 `middleware('2fa')`

**L2 跳读定位**:
- 登录相关路由: `/login`, `/authenticate`, `/auth/login`
- MFA验证路由: `/verify-mfa`, `/verify-2fa`, `/two-factor`, `/totp`
- 敏感操作路由: `/dashboard`, `/settings`, `/profile`, `/admin` 等需要MFA的页面
- 追踪用户登录到验证MFA的完整流程
- 检查是否存在跳过MFA的快速路径或后门

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- MFA中间件存在: `middleware('mfa')`, `middleware('2fa')`, `middleware('totp')`
- MFA状态检查: `Auth::user()->mfa_verified`, `session()->get('mfa_verified')`, `$user->hasMFAEnabled()`
- 重定向逻辑: 未验证MFA时是否重定向到 `/verify-mfa` 等验证页面

**L3 逐行分析**:
- MFA状态检查逻辑:
  - 是否同时检查了 `Auth::check()` 和 MFA 验证状态
  - 检查状态来源：后端 session vs 数据库字段，后端更可靠
  - 时间有效性：MFA验证后是否设置了过期时间 (如15分钟)
- 会话安全性:
  - MFA状态是否存储在服务端 session 中而非客户端
  - 是否有 `HttpOnly`, `Secure`, `SameSite` 保护
  - MFA验证后是否更新 session ID 防止固定
- 多步骤认证流程:
  - 是否检查了步骤顺序 (不能跳过MFA步骤)
  - 是否在MFA验证前临时认证 (临时权限有限)
- 数据库状态:
  - `mfa_verified_at` 时间戳是否与登录时间合理
  - 是否有 `mfa_device_id` 等标识绑定特定设备

**L4 跨模块追踪**:
- 追踪 Laravel Guardian 或自定义认证驱动的完整流程
- 检查所有 `Auth::login()` 的调用位置，确认都进行了MFA检查
- 验证所有需要MFA的路由是否都应用了保护中间件
- 检查API端点是否也需要MFA验证
- 审查第三方认证包 (OAuth2, SAML) 是否与MFA集成

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 登录后未检查MFA状态，直接允许访问受保护资源
- MFA验证与后续资源访问之间无状态检查或状态可被篡改
- 仅在前端检查MFA状态，后端无验证
- 会话中MFA状态来自客户端输入或可被用户修改
- MFA验证步骤可被跳过或乱序执行
- 特定用户禁用MFA时未正确处理，仍要求MFA
- 没有中间件或装饰器强制MFA要求，仅在控制器中有选择地检查

**误报判定**:
- 仅部分用户需要MFA (如管理员)，其他用户本就无MFA要求，架构明确
- MFA状态存储在服务端 session，有完整的后端验证
- 所有需要MFA的操作都有专门的中间件保护，无例外
- MFA验证后 session ID 会重新生成，防止会话固定
- MFA验证有合理的过期时间，且验证成功后立即更新状态
- 应用有详细的审计日志，记录每次MFA验证

**代码异味**:
- MFA字段存在但仅在某些控制器中检查，不一致
- 存在 `if ($user->mfa_enabled)` 检查但后续无 `&&` 条件检查验证状态
- 会话中存在 `mfa_verified` 但其他地方使用 `mfa_checked` 等不一致命名
- 前端代码中存在 MFA 验证逻辑，后端也独立实现但可能不同步
- 找到多个登录入口，部分检查MFA，部分不检查

---

## Low risk

### 低风险场景

**架构保护**:
- MFA 为可选功能，用户未启用时无需验证，架构明确
- 应用有分层的权限系统，MFA 仅用于最敏感操作 (如资金转账)
- MFA 与特定角色绑定 (如只有管理员需要)，其他角色无此要求

**检测与监控**:
- 实时监控登录-MFA验证间隔，异常时告警 (如过长延迟)
- 记录每次MFA验证的时间、设备、位置，用户可查询
- 检测到相同用户同时从多地登录时强制重新验证
- 登录失败过多时自动锁定账户，防止暴力攻击

**强制措施**:
- MFA验证失败超过 N 次后锁定账户
- 某时段内所有登录都必须通过MFA，无例外
- MFA验证过期后自动登出，需重新验证

**备用方案**:
- 虽然可能存在绕过MFA的备用认证 (如备用码)，但备用码也有强保护
- 一次性备用码使用后立即销毁，不可重用
