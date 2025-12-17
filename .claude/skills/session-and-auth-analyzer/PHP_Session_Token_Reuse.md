# PHP_Session_Token_Reuse

**漏洞类型**: Laravel/PHP 会话管理中，同一会话令牌可被多次使用和复用，导致令牌长期有效且可被滥用

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// 示例1: Laravel 会话令牌未验证使用次数
class SessionController {
    public function store(Request $request) {
        Auth::login($user);
        // Session token 存储在 cookie，可被多次使用
        return redirect('/dashboard');
    }
}

// 示例2: 会话令牌无计数限制
$_SESSION['token'] = session_id();
$_SESSION['usage_count'] = 0; // 定义但未使用
// token 可无限使用，usage_count 未更新

// 示例3: 令牌验证时未检查使用次数
function validateToken($token) {
    $session = Session::where('token', $token)->first();
    return $session && $session->is_valid; // 未检查 usage_count
}

// 示例4: CSRF token 可重复使用
<form method="POST" action="/transfer">
    <input type="hidden" name="_token" value="{{ csrf_token() }}">
    <!-- 同一 token 可被多个表单使用 -->
</form>

// 示例5: API token 无使用限制
$user->createToken('api-token');
// token 可被多个请求无限使用

// 示例6: 会话固化，token 不更新
session_start();
if (!$_SESSION['initialized']) {
    $_SESSION['initialized'] = true;
    // session_regenerate_id() 未调用，token 保持不变
}

// 示例7: 令牌池实现不当
public function getSessionToken() {
    $token = $this->tokens[$sessionID];
    // 缺少计数器检查，token 可被多个用户使用
    return $token;
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Session 管理: `Session::`, `$_SESSION[]`, `session()`, `Auth::login()`
- CSRF token: `csrf_token()`, `_token`, `verifyToken()`
- 令牌验证: `validateToken()`, `checkToken()`, `verify()`
- 缺失更新: 无 `session_regenerate_id()`, 无 `usage_count++`
- 令牌重用指标: `is_valid`, `expired`, 无相关字段

**L2 跳读定位**:
- 会话初始化: Session 的创建和销毁
- 令牌生成: Laravel 的 `Session::generate()`, PHP 原生 `session_id()`
- 令牌验证: 所有检查令牌的位置
- 令牌更新: `session_regenerate_id()` 的使用

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 使用计数: `usage_count`, `used_times`, 计数器字段
- 令牌更新: `session_regenerate_id()`, `regenerateToken()`, `refresh()`
- 令牌销毁: `session_destroy()`, `delete()`, `revoke()`

**L3 逐行分析**:
- 令牌生命周期:
  - 生成时是否记录时间戳
  - 验证后是否更新 `last_used_at`
  - 使用次数是否有限制 (如仅 1 次)
  - 使用后是否销毁
- 会话更新策略:
  - 登录后是否调用 `session_regenerate_id()`
  - 登出时是否销毁会话
  - 权限变化时是否刷新令牌
  - 是否有定期令牌轮换机制
- CSRF token 特殊处理:
  - CSRF token 是否与请求绑定 (仅该请求有效)
  - 是否在表单提交后更新 token
  - token 的存储位置是否安全 (cookie vs session)
- API token 管理:
  - 是否有 API token 的撤销机制
  - 是否跟踪 token 的使用情况
  - 是否有 token 过期和轮换

**L4 跨模块追踪**:
- 追踪 Laravel 的会话驱动 (database, redis, cookie)
- 检查中间件中的令牌验证逻辑
- 验证所有 API 端点的 token 检查
- 检查是否有 token 黑名单或销毁机制
- 审查配置文件中的会话设置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 同一会话令牌可被多个不同的请求无限次使用
- 令牌验证时未检查使用次数或过期时间
- 登录后未调用 `session_regenerate_id()`, token 保持不变
- CSRF token 可被多个表单重复使用
- API token 无撤销或轮换机制
- 会话令牌存储在客户端但未签名或可被篡改

**误报判定**:
- 登录后立即调用 `session_regenerate_id()`, 旧 token 失效
- CSRF token 与请求绑定，仅该请求有效
- 每次关键操作后刷新 token
- 有 token 黑名单或销毁机制
- API token 有明确的过期时间和轮换策略
- 敏感操作前重新验证用户身份

**代码异味**:
- 存在 `usage_count` 字段但验证时未使用
- 有多个令牌生成或验证的入口，逻辑不一致
- 注释中提到令牌应该单次使用但代码未实现
- 令牌验证与销毁分离在不同函数，中间存在间隙
- 有旧的 token 更新代码但已被注释

---

## Low risk

### 低风险场景

**请求绑定令牌**:
- 令牌与请求参数 (如 nonce) 绑定，每个请求不同
- 令牌与用户特征 (IP, User-Agent) 绑定

**监控与限制**:
- 令牌使用受到速率限制，无法被滥用
- 异常使用时自动失效和告警
- 定期强制要求重新认证
