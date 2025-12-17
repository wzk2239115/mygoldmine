# Actix-web 速率限制缺失审计指南

## Details

### 核心操作定位

Actix-web 框架中速率限制漏洞主要表现为在处理用户请求的路由层缺少限流 middleware 配置。易受攻击的模式包括：

- **直接暴露端点**：未通过任何限流 middleware 的 route handlers
- **代码示例**：
  ```rust
  HttpServer::new(|| {
    App::new()
      .route("/api/login", web::post().to(login_handler))  // 无限流防护
      .route("/api/register", web::post().to(register_handler))
  })
  ```

### 快速定位核心操作 **(审计等级 L1: 关键词扫描)**

搜索以下关键词定位未保护的端点：
- `.route()` 或 `.service()` 直接注册路由
- `web::post()`, `web::get()`, `web::put()`, `web::delete()` 等 HTTP 方法
- 敏感操作：`login`, `register`, `reset_password`, `verify_otp`, `api/v1` 等
- 缺少 middleware 的特征：未见 `.wrap()` 调用或无限流相关的 guard/middleware 组合

搜索建议：
```
grep -n "\.route\|\.service" src/main.rs src/routes.rs
grep -n "web::post\|web::get" src/handlers.rs
grep -rn "\.wrap" src/ | grep -i "rate\|limit\|throttle"
```

### 快速定位保护机制 **(审计等级 L2: 跳读)**

识别现有的限流防护机制：

1. **Middleware 层限流**
   - `actix-web-guard`, `actix-ratelimit`, `async-ratelimit` 等第三方库
   - 代码特征：`.wrap(RateLimiter::...)`

2. **自定义 middleware**
   - 自定义的 `struct` 实现 `Service` trait
   - 时间戳或计数器管理（Redis, HashMap, DashMap 等）

3. **Guard 级别防护**
   - 使用 `.guard()` 方法的自定义防护逻辑
   - 请求级别的限流判断

4. **数据库级限流**
   - 数据库中的尝试次数计数和冷却期
   - 常见字段：`failed_attempts`, `locked_until`, `last_attempt_time`

关键搜索：
```
grep -rn "RateLimiter\|ratelimit" src/
grep -rn "impl.*Service" src/
grep -rn "Redis\|Cache" src/
grep -n "failed_attempts\|locked_until" src/models.rs
```

---

## Classify

### 漏洞研判标准

**判定为漏洞的依据：**
- 验证端点（登录、注册、密码重置、OTP 验证）完全无限流防护
- 无任何计数器或冷却机制管理请求频率
- 攻击者可无限制地发起请求而无惩罚机制
- 业务功能允许自动化批量操作（无 CAPTCHA、无异步验证）

**判定为误报的依据：**
- 端点本身并非敏感操作（非身份验证相关）
- 具有其他强力保护机制（CAPTCHA、异步 OTP、设备指纹）
- 数据库已实现账户锁定或冷却期机制
- 已配置 WAF 或反向代理级别的全局限流（需验证配置）

**代码异味（降低风险）：**
- 有限流逻辑但配置不当（窗口过大、阈值过高）
- 限流仅应用于部分端点，留下漏洞
- 限流机制依赖客户端提供的标识符（IP 可伪造）
- 限流规则硬编码，难以调整

---

## Low risk

### 低风险评级场景

以下情况应评级为低风险或可接受：

1. **公开 API 端点**
   - 非身份验证相关操作
   - 如公开信息查询、搜索功能
   - 该类端点的请求成本较低，不涉及资源消耗

2. **已有强力替代防护**
   - CAPTCHA 或其他人机验证
   - 基于设备指纹的异常检测
   - 多因素认证（MFA）强制要求
   - 完整的账户锁定机制与告警

3. **内部系统或受限访问**
   - 仅限特定 IP 段访问
   - 需要特殊令牌或密钥的端点
   - VPN 或堡垒机保护的后台系统

4. **低成本操作**
   - 查询类请求（GET）且无计算消耗
   - 返回缓存内容的端点
   - 已有全局 WAF 限流配置（需确认有效）

5. **业务容错设计**
   - 短期内限流不影响业务连续性
   - 用户可通过其他渠道完成操作
   - 已实现请求去重或幂等性保证
