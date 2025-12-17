# PHP｜HTTP Security Headers 缺失配置

## Details

### 漏洞成因
HTTP安全响应头是Web应用防护的重要组成部分，用于防止XSS、点击劫持、信息泄露等多种攻击。PHP应用中，当缺少关键的安全响应头或配置不当时，会显著降低应用的安全性。常见的缺失包括：X-Frame-Options（点击劫持防护）、X-Content-Type-Options（MIME嗅探防护）、Strict-Transport-Security（HTTPS强制）、X-XSS-Protection（XSS过滤）、Referrer-Policy（引用信息控制）等。

### 代码示例

**易受攻击的代码 - 完全缺少安全头：**
```php
// 没有任何安全响应头设置
header('Content-Type: text/html; charset=utf-8');
// 缺少所有关键的安全防护头
```

**易受攻击的代码 - 配置不当：**
```php
// 设置但配置错误的安全头
header('X-Frame-Options: ALLOWALL'); // 错误：允许所有框架嵌入
header('X-XSS-Protection: 0'); // 错误：禁用XSS过滤
header('Referrer-Policy: unsafe-url'); // 错误：暴露完整引用信息
```

**易受攻击的代码 - SameSite Cookie配置缺失：**
```php
// 会话Cookie缺少SameSite属性
setcookie('session_id', $session_id, time() + 3600, '/');
// 缺少HttpOnly、Secure、SameSite属性
```

**安全示例 - 完整的安全头配置：**
```php
// 严格的安全响应头配置
$security_headers = [
    'X-Frame-Options' => 'DENY', // 或 'SAMEORIGIN'
    'X-Content-Type-Options' => 'nosniff',
    'X-XSS-Protection' => '1; mode=block',
    'Strict-Transport-Security' => 'max-age=31536000; includeSubDomains; preload',
    'Referrer-Policy' => 'strict-origin-when-cross-origin',
    'Permissions-Policy' => 'geolocation=(), microphone=(), camera=()',
    'Content-Security-Policy' => "default-src 'self'", // 结合CSP使用
];

foreach ($security_headers as $header => $value) {
    header("$header: $value");
}

// 安全的Cookie设置
setcookie('session_id', $session_id, [
    'expires' => time() + 3600,
    'path' => '/',
    'domain' => $_SERVER['HTTP_HOST'],
    'secure' => true,
    'httponly' => true,
    'samesite' => 'Strict'
]);
```

**安全示例 - 框架级别的安全头配置：**
```php
// Laravel中间件示例
namespace App\Http\Middleware;

class SecurityHeaders
{
    public function handle($request, Closure $next)
    {
        $response = $next($request);
        
        $response->headers->set('X-Frame-Options', 'DENY');
        $response->headers->set('X-Content-Type-Options', 'nosniff');
        $response->headers->set('X-XSS-Protection', '1; mode=block');
        $response->headers->set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
        $response->headers->set('Referrer-Policy', 'strict-origin-when-cross-origin');
        $response->headers->set('Permissions-Policy', 'geolocation=(), microphone=(), camera=()');
        
        return $response;
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 响应头：`header(`, `headers->set`
- 安全头：`X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`
- Cookie设置：`setcookie(`, `session_set_cookie_params`

**定位步骤：**
1. 搜索项目中所有header设置相关的代码
2. 检查是否存在安全响应头的设置
3. 验证Cookie参数设置是否安全

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **点击劫持防护：** `X-Frame-Options` 设置为 `DENY` 或 `SAMEORIGIN`
- **MIME嗅探防护：** `X-Content-Type-Options` 设置为 `nosniff`
- **HTTPS强制：** `Strict-Transport-Security` 包含适当max-age
- **引用信息控制：** `Referrer-Policy` 设置为安全值
- **Cookie安全：** HttpOnly、Secure、SameSite属性

**定位技巧：**
- 检查是否所有响应都包含基本的安全头
- 验证HTTPS站点是否设置HSTS
- 确认Cookie是否设置SameSite属性
- 检查是否存在全局的安全头中间件

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 完整安全头+安全Cookie | **L0（快速跳过）** | 配置完善 |
| 有安全头但个别缺失 | **L2（跳读）** | 需验证具体缺失 |
| 完全缺少安全头 | **L3（逐行读）** | 高风险配置 |
| HTTPS站点缺少HSTS | **L4（跨模块追踪）** | 严重缺失 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 缺少关键安全响应头（X-Frame-Options/X-Content-Type-Options/HSTS）
2. Cookie未设置HttpOnly、Secure或SameSite属性
3. 安全头设置值不安全（如X-Frame-Options: ALLOWALL）
4. HTTPS应用未设置Strict-Transport-Security

#### 误报
以下情景可判定为误报：
1. 完整设置所有关键安全头
2. Cookie安全属性配置正确
3. 使用框架级别的全局安全头中间件
4. 分阶段部署安全头策略

#### 代码异味
需记录的风险：
1. 仅在部分页面设置安全头
2. 安全头值设置不一致
3. 动态生成的安全头存在注入风险
4. 移动端和桌面端安全策略差异

## Low risk

### 低风险评级场景

#### 1. 渐进式安全增强
- **场景：** 逐步添加安全头，先解决高风险问题
- **风险评估：** 合理的实施策略，风险可控

#### 2. 兼容性考虑
- **场景：** 为兼容旧系统暂时放宽某些安全设置
- **风险评估：** 业务需求驱动，已评估风险

#### 3. 框架内置安全机制
- **场景：** 使用现代框架的安全特性
- **风险评估：** 框架通常提供合理的默认配置

### HTTP安全头检查表

| 响应头 | 安全设置 | 作用 | 检测要点 |
|--------|----------|------|----------|
| X-Frame-Options | DENY/SAMEORIGIN | 点击劫持防护 | 是否设置 |
| X-Content-Type-Options | nosniff | MIME嗅探防护 | 是否设置 |
| X-XSS-Protection | 1; mode=block | XSS过滤 | 是否启用 |
| Strict-Transport-Security | max-age=31536000 | HTTPS强制 | HTTPS站点必设 |
| Referrer-Policy | strict-origin-when-cross-origin | 引用信息控制 | 信息泄露防护 |
| Permissions-Policy | geolocation=() | 权限控制 | 功能权限限制 |

### Cookie安全属性检查表

| 属性 | 作用 | 设置要求 | 检测要点 |
|------|------|----------|----------|
| HttpOnly | XSS防护 | 必须设置 | 防止JS访问 |
| Secure | 传输安全 | HTTPS必设 | 仅HTTPS传输 |
| SameSite | CSRF防护 | 推荐Strict | CSRF防护 |
| Domain/Path | 作用域控制 | 最小化 | 限制作用域 |

### 常见配置错误

| 错误类型 | 示例 | 风险等级 | 修复建议 |
|----------|------|----------|----------|
| 完全缺失 | 无安全头 | 高 | 立即添加基础安全头 |
| 设置错误 | X-Frame-Options: ALLOWALL | 高 | 改为DENY或SAMEORIGIN |
| Cookie不安全 | 缺少HttpOnly/Secure | 高 | 添加安全属性 |
| HTTPS无HSTS | 缺少HSTS头 | 高 | 添加HSTS配置 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 基础安全头完备 | 核心防护到位 | 高 |
| Cookie安全属性 | 会话安全 | 高 |
| 框架安全中间件 | 统一安全策略 | 中 |
| 分阶段部署计划 | 风险控制 | 中 |