# Rust_AsyncTaskProxy

**漏洞类型：** 异步任务调度器中使用用户参数构造请求目标，缺少地址验证

---

## Details

### 代码示例

```rust
// 典型漏洞模式 - tokio + reqwest
use reqwest::Client;
use tokio::spawn;

async fn schedule_fetch(user_url: String) {
    spawn(async move {
        let client = Client::new();
        let resp = client.get(&user_url).send().await;  // 直接使用用户输入
        // 处理响应...
    });
}

// 变种：从消息队列获取任务
async fn process_task(task: Task) {
    let target = task.url;  // URL来自任务队列/数据库
    let response = reqwest::get(target).await.unwrap();  // 无验证直接请求
}

// 变种：HTTP代理服务
async fn proxy_handler(req: HttpRequest) -> HttpResponse {
    let target_url = req.headers().get("X-Target").unwrap();
    let body = reqwest::get(target_url.to_str().unwrap())
        .await.unwrap().text().await.unwrap();
    HttpResponse::Ok().body(body)
}

// 变种：拼接路径
async fn fetch_resource(path: &str) {
    let url = format!("http://backend/{}", path);  // path可控
    let data = surf::get(url).recv_string().await;
}
```

### 快速定位核心操作技巧（审计等级：L1-L2）

**L1 关键词扫描**：
- HTTP客户端库：`reqwest::`, `surf::`, `hyper::Client`, `ureq::`
- 异步运行时：`tokio::spawn`, `async_std::task::spawn`, `actix::spawn`
- 请求方法：`.get()`, `.post()`, `.send()`, `Client::new()`, `Request::builder()`
- 参数提取：`.extract()`, `.json()`, `.query()`, `req.headers()`, `Path<T>`

**L2 跳读定位**：
- 从 Web 框架入口追踪：`actix_web::web::`, `rocket::`, `warp::Filter`, `axum::`
- 定位路由处理函数：`#[get]`, `#[post]`, `.route()`, `.service()`
- 追踪用户输入流：`Path`, `Query`, `Json`, `Form` 提取器到 HTTP 请求调用点
- 关注异步上下文传递：`spawn` 闭包捕获的变量、`channel` 传递的消息结构

### 快速定位保护机制技巧（审计等级：L2-L4）

**L2 跳读检测**：
- URL 解析验证：`Url::parse()` + `.host()`, `.scheme()`, `.domain()` 检查
- 白名单匹配：`ALLOWED_HOSTS.contains()`, `matches!()`, `if let Some(host) = ...`
- IP地址过滤：`IpAddr::is_loopback()`, `is_private()`, `is_global()` 方法
- 协议限制：`.scheme() == "https"`, `starts_with("http")`

**L3 逐行分析**：
```rust
// 检查这些保护模式
- url.host_str() == Some("trusted.com")  // 精确匹配
- !url.host().unwrap().is_ipv4() || !is_private_ip()  // IP过滤逻辑
- matches!(url.scheme(), "http" | "https")  // 协议枚举限制
- ClientBuilder::new().redirect(Policy::none())  // 禁用重定向
```

**L4 跨模块追踪**：
- 验证自定义校验函数实现：`validate_url()`, `is_safe_target()` 等
- 检查 trait 实现：自定义 `FromRequest` 或中间件的验证逻辑
- 追踪配置加载：`config.toml`, `lazy_static!` 中的白名单定义
- 异步任务链：检查任务调度器是否在入队前/出队后进行验证

---

## Classify

### 漏洞判定标准

**确认为漏洞**：
- URL/Host/Path 参数完全由用户输入控制，且无白名单或仅有黑名单
- 可以指定危险协议（`file://` 虽然 `reqwest` 不支持，但需确认实际使用的 HTTP 客户端）
- 能够访问内网地址（`127.0.0.1`, `[::1]`, `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`）
- 白名单验证存在缺陷：如使用 `.contains()` 或 `.ends_with()` 可被子域绕过
- 重定向跟随未禁用，可通过外部跳转绕过白名单

**误报判定**：
- URL 来自硬编码常量或编译时配置，非运行时用户输入
- 完整且正确的域名白名单实现（使用 `host_str()` 精确匹配）
- 仅路径或查询参数可控，协议和域名部分固定
- 存在完整的 IP 地址过滤（使用标准库 `IpAddr` API 检查内网）
- 异步任务在沙箱隔离环境执行，无敏感网络访问权限

**代码异味**：
- 使用字符串操作验证 URL（如 `starts_with`, `contains`）而非 `url::Url` 解析
- 黑名单过滤特定关键词（`localhost`, `127.0.0.1`），容易被编码或其他形式绕过
- DNS 解析与请求之间存在时间窗口（TOCTOU），可能遭遇 DNS 重绑定
- 异步任务调度与验证分离，中间经过消息队列或数据库持久化
- 配置化白名单来自数据库或可被低权限用户修改的文件

---

## Low risk

### 低风险评级条件

1. **网络隔离严格** - 应用运行在网络受限容器/命名空间中，防火墙规则禁止访问内网段和元数据服务
2. **白名单外部可信域** - 虽 URL 可控但已限制为特定公开服务（需评估域名劫持风险）
3. **任务认证机制** - 异步任务需要签名验证，恶意 URL 无法通过消息队列注入
4. **只读且超时短** - 仅发起 GET 请求，设置了极短超时（<2s），且响应不返回敏感信息
5. **响应不回显** - HTTP 响应仅用于内部状态判断或日志记录，不向用户返回内容
6. **监控与限流** - 存在异常请求检测（如内网IP访问告警）、严格的速率限制和熔断机制
7. **沙箱执行** - 使用 `seccomp`/`landlock` 等机制限制网络系统调用，或在隔离的 Wasm 环境中执行

**注意：** 低风险评级依赖外部防护措施的有效性，需在审计报告中明确列出依赖项，并建议在代码层增加白名单验证作为纵深防御。Rust 的类型安全不能防御逻辑层的 SSRF 漏洞。