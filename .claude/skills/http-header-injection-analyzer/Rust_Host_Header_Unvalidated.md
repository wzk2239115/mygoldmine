# Rust Host头未验证

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `Host`, `req.headers()`, `uri.host()`, `x-forwarded-host`, `axum::extract::Host`, `actix_web::HttpRequest`
- **快速检查：** Host头是否用于URL构造、重定向、或业务逻辑，是否有域名白名单

## 漏洞成因

Rust Web框架（axum、actix-web等）中获取的Host头直接来自客户端请求，攻击者可完全控制。若未验证直接用于重定向URL、密码重置链接、OAuth回调等场景，可导致开放重定向、密码重置投毒、缓存中毒等攻击。

### 常见漏洞模式

```rust
// ✗ 漏洞：axum直接使用Host头重定向
use axum::{extract::Host, response::Redirect};

async fn login_redirect(Host(host): Host) -> Redirect {
    // Host头未验证
    Redirect::to(&format!("https://{}/dashboard", host))
    // 攻击: Host: evil.com -> 重定向到 https://evil.com/dashboard
}
```

```rust
// ✗ 漏洞：actix-web Host用于密码重置链接
use actix_web::{web, HttpRequest, HttpResponse};

async fn forgot_password(req: HttpRequest, form: web::Form<EmailForm>) -> HttpResponse {
    let host = req.headers()
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("localhost");

    let token = generate_token(&form.email);
    let reset_link = format!("https://{}/reset?token={}", host, token);
    send_email(&form.email, &reset_link).await;
    // 攻击者控制Host头发送钓鱼链接

    HttpResponse::Ok().body("Email sent")
}
```

```rust
// ✗ 漏洞：X-Forwarded-Host用于URL构造
async fn api_config(req: Request<Body>) -> Response<Body> {
    let host = req.headers()
        .get("x-forwarded-host")
        .or_else(|| req.headers().get("host"))
        .and_then(|v| v.to_str().ok())
        .unwrap_or("api.example.com");

    let config = serde_json::json!({
        "api_url": format!("https://{}/api", host),
        "ws_url": format!("wss://{}/ws", host)
    });
    // 响应被缓存后可能影响其他用户

    Response::new(Body::from(config.to_string()))
}
```

```rust
// ✗ 漏洞：OAuth回调地址构造
async fn oauth_start(Host(host): Host) -> Redirect {
    let callback = format!("https://{}/oauth/callback", host);
    let auth_url = format!(
        "https://auth.provider.com/authorize?redirect_uri={}",
        urlencoding::encode(&callback)
    );
    Redirect::to(&auth_url)
    // 攻击者劫持OAuth回调
}
```

```rust
// ✓ 修复：白名单验证
use std::collections::HashSet;
use once_cell::sync::Lazy;

static ALLOWED_HOSTS: Lazy<HashSet<&'static str>> = Lazy::new(|| {
    vec!["example.com", "www.example.com", "api.example.com"]
        .into_iter()
        .collect()
});

fn validate_host(host: &str) -> &str {
    // 移除端口号
    let host_without_port = host.split(':').next().unwrap_or(host);

    if ALLOWED_HOSTS.contains(host_without_port) {
        host_without_port
    } else {
        "example.com"  // 默认安全值
    }
}

async fn safe_redirect(Host(host): Host) -> Redirect {
    let safe_host = validate_host(&host);
    Redirect::to(&format!("https://{}/dashboard", safe_host))
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 密码重置/邮件链接 | 搜索 `host.*token\|host.*email\|host.*reset`，检查链接构造 |
| **P0** | 重定向URL构造 | 搜索 `Redirect.*host\|Location.*host`，检查白名单 |
| **P0** | OAuth回调地址 | 搜索 `callback\|redirect_uri.*host`，检查域名验证 |
| **P1** | API响应中的URL | 搜索 `host.*json\|host.*url`，检查是否被缓存 |
| **P1** | X-Forwarded-Host | 搜索 `x-forwarded-host`，检查代理场景 |
| **P2** | 配置或日志使用 | 搜索 `host.*log\|host.*config`，评估影响 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 使用环境变量或配置文件域名 | 快速跳过，无Host头使用 |
| **L1** | 仅日志记录使用Host头 | 关键词扫描确认无安全影响 |
| **L2** | 单函数内Host用于URL构造 | 跳读检查白名单验证 |
| **L3** | Host跨模块传递 | 逐行追踪数据流 |
| **L4** | 中间件或代理层处理 | 跨模块检查Host验证位置 |

---

## 审计专业技巧

### 真实漏洞与误报区分

#### 真实漏洞特征（高可信度）

1. **链式依赖判断**
   - Host头流入 → 字符串格式化 → URL构造 → 外部可见输出
   - 不是所有Host使用都是漏洞，关键在于是否进入**URL构造上下文**
   - 误报案例：`log!("Host: {}", host)` 仅为记录，无安全影响

2. **白名单验证的细节识别**
   - ✓ 正确：`if allowed_hosts.contains(&host_without_port) { ... }`
   - ✗ 不完整：仅移除端口但未移除IPv6中括号 `[::1]:8080`
   - ✗ 风险：使用模糊匹配如 `host.contains("example.com")` 会被 `evil.com.example.com` 绕过
   - ✗ 风险：大小写敏感的对比（DNS无视大小写）

3. **代理信任链问题**
   - 应用直接使用 `x-forwarded-host` 但无代理IP验证 = 高风险
   - 必须同时检查：是否验证请求来自可信代理（如`x-forwarded-for`）
   - 审计要点：搜索 `x-forwarded-host` 后立即查看是否有代理IP白名单

#### 常见误报场景

| 误报类型 | 示例代码 | 为何不是漏洞 | 审计建议 |
|---------|--------|-----------|---------|
| 配置日志 | `logger.info!("Client requested: {}", host)` | 仅日志记录，无URL构造 | 跟踪该日志是否用于业务逻辑 |
| 指标收集 | `metrics.gauge("host_request", &host)` | 仅统计维度，非构造URL | 检查指标是否影响流量路由 |
| 错误响应 | `format!("Invalid host: {}", host)` | Host仅在错误消息，无开放重定向 | 验证是否包含Location头 |
| 缓存键 | `format!("cache:host:{}", host)` | 仅作缓存键，无跨用户污染 | 检查缓存内容是否包含Host依赖的URL |
| 反向代理标头 | 添加`X-Original-Host: {host}`给后端 | 传给可信后端，非暴露给用户 | 确认后端也做验证 |

#### 实战审计流程

**第一步：快速定位**
```rust
// 关键搜索模式（优先级顺序）
1. grep -n "Redirect.*host"
2. grep -n "format!.*https.*host"
3. grep -n "reset.*token.*host"
4. grep -n "oauth.*callback.*host"
```

**第二步：数据流追踪**
```rust
// 发现Host使用后，反向追踪：
// a) Host来源 - 直接从Header还是经过验证？
let host = req.headers().get("host");  // 直接 = 高风险

// b) Host用途 - 用于什么业务逻辑？
format!("https://{}/reset", host)      // 邮件链接 = 严重
format!("log: {}", host)               // 仅记录 = 无关

// c) Host影响范围 - 是否跨用户或跨会话？
send_email(user.email, &reset_link)    // 用户可控Host指向钓鱼 = 漏洞
log_to_file(&host)                     // 仅自己看日志 = 无关
```

**第三步：白名单验证检查**
```rust
// 检查验证代码的安全性
❌ 不安全模式：
if host.contains("example.com") { }    // 易被"evil.com.example.com"绕过
if host.ends_with("example.com") { }   // 易被"evilexample.com"绕过
if !host.contains(":") { }             // 仅检查端口，无主机验证

✓ 安全模式：
let clean = host.split(':').next().unwrap_or("");
if WHITELIST.contains(clean) { }       // 精确匹配白名单
```

#### 上下文依赖的误报案例

**案例1：内部API**
```rust
// 内网应用，仅被内网用户和管理员访问
async fn admin_info(Host(host): Host) -> Json<AdminData> {
    Json(json!({
        "server_host": host,  // 内部调试信息
        "config": get_config()
    }))
}
// 判定：低风险（内网隔离），但审查代码执行环境
```

**案例2：受保护的后端API**
```rust
// 后端到后端通信，通过VPN/TLS验证
#[post("/webhook")]
async fn webhook(req: HttpRequest, payload: Webhook) -> HttpResponse {
    let host = req.headers().get("host").and_then(|v| v.to_str().ok());
    // 这里Host仅用于日志，数据已通过签名验证
    log!("Webhook from {}", host);
}
// 判定：低风险（已有其他安全机制），但要验证签名逻辑
```

**案例3：客户端验证**
```javascript
// Rust后端返回host给前端，由前端渲染（不是服务端漏洞）
#[get("/config")]
async fn get_config(Host(host): Host) -> Json<Config> {
    Json(json!({
        "current_host": host,  // 前端显示当前访问的Host
        "api_endpoints": get_endpoints()
    }))
}
// 判定：取决于前端如何使用这个Host值，后端暂无XSS风险
```

### 误报风险最高的代码

审计时最容易被误认为漏洞但实际无关的场景：

1. **Host在条件判断中**：`if host == "internal.local" { enable_debug() }`
   - 只要白名单验证逻辑正确，这不是漏洞

2. **Host用于功能开关**：`if host.contains("dev") { use_dev_api() }`
   - 风险：可被 `Host: dev-evil.attacker.com` 绕过
   - 需要完整的白名单，非模糊匹配

3. **Host记录但未构造URL**：`request_log.host = host`
   - 只要日志不被当作可信输入再次使用，无漏洞

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. Host头用于构造外部可见URL（重定向、邮件、回调）
2. 无白名单验证
3. 影响安全功能

### 典型漏洞特征（满足任一项即确认）
- ✗ `Redirect::to(&format!("https://{}/path", host))`
- ✗ `format!("https://{}/reset?token={}", host, token)`用于邮件
- ✗ OAuth回调URL使用未验证的Host
- ✗ API响应包含Host构造的URL且被缓存

### 安全排除（任一项充分）
- ✓ 白名单验证：`ALLOWED_HOSTS.contains(host)`
- ✓ 使用环境变量：`std::env::var("APP_URL")`
- ✓ 配置文件固定域名
- ✓ 代理层验证Host头

### 灰色判定（风险较低但需注意）
- 内网应用
- 有CDN/代理层验证
- 仅影响非安全功能

---

## 实现建议

### 核心防护方案

**方案1：白名单验证**
```rust
use std::collections::HashSet;

fn validate_host(host: &str, allowed: &HashSet<&str>) -> Option<&str> {
    let host_lower = host.to_lowercase();
    let host_without_port = host_lower.split(':').next()?;

    if allowed.contains(host_without_port) {
        Some(host_without_port)
    } else {
        None
    }
}
```

**方案2：使用环境变量**
```rust
use std::env;

fn get_base_url() -> String {
    env::var("APP_BASE_URL")
        .unwrap_or_else(|_| "https://example.com".to_string())
}

async fn forgot_password(form: web::Form<EmailForm>) -> HttpResponse {
    let base_url = get_base_url();
    let token = generate_token(&form.email);
    let reset_link = format!("{}/reset?token={}", base_url, token);
    send_email(&form.email, &reset_link).await;
    HttpResponse::Ok().body("Email sent")
}
```

**方案3：中间件验证**
```rust
use axum::{middleware::Next, response::Response};

async fn validate_host_middleware(
    Host(host): Host,
    request: Request<Body>,
    next: Next<Body>,
) -> Result<Response, StatusCode> {
    let allowed = ["example.com", "www.example.com"];

    let host_without_port = host.split(':').next().unwrap_or(&host);
    if !allowed.contains(&host_without_port) {
        return Err(StatusCode::BAD_REQUEST);
    }

    Ok(next.run(request).await)
}
```

### 检查清单
- [ ] 所有Host使用点添加白名单验证
- [ ] 密码重置链接使用配置的固定域名
- [ ] OAuth回调使用预注册的白名单URL
- [ ] API响应中的URL使用环境变量
- [ ] 测试Host头注入：`Host: evil.com`

---

## 修复优先级

1. **立即修复**：密码重置/OAuth回调使用未验证Host头
2. **本周修复**：所有重定向添加Host白名单验证
3. **可选加强**：使用环境变量替代动态Host获取
4. **长期优化**：添加Host验证中间件
