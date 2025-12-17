# Rust Rocket 框架响应头配置未包含安全的 CSP 策略

## Details

### 漏洞本质
Rocket 框架应用在处理 HTML 响应时，若未通过响应头（`Content-Security-Policy`）设置严格的内容安全策略，浏览器将无法有效限制脚本、样式表、图片、iframe 等资源的加载来源与执行权限，导致 XSS 攻击成功概率大幅提升。该漏洞通常源于 CSP 配置缺失或策略过于宽松（如包含通配符、unsafe-inline、unsafe-eval 等）。

### 核心代码示例
```rust
// 模式1：响应头完全缺失 CSP
#[get("/")]
fn index() -> String {
    "<html><body><h1>Welcome</h1></body></html>".to_string()
    // HttpResponse中未添加Content-Security-Policy头
}

// 模式2：Rocket 的 Responder 实现未设置 CSP
#[get("/page")]
fn render_page() -> impl Responder {
    (
        Status::Ok,
        ("Content-Type".parse::<Header>().unwrap(), "text/html"),
        "<html><script>alert('xss')</script></html>"
    )
    // 仅设置Content-Type，缺失CSP响应头
}

// 模式3：全局 fairing 未设置 CSP
pub fn main() {
    rocket::build()
        .mount("/", routes![index, page])
        .launch();
    // 未通过Fairing或其他中间件机制全局设置CSP
}

// 模式4：CSP 策略过于宽松
#[get("/")]
fn index() -> Response<'static> {
    let mut response = Response::build()
        .status(Status::Ok)
        .header(ContentType::HTML)
        .sized_body(None, Cursor::new("<html>..."))
        .finalize()
        .unwrap();

    response.set_header(Header::new("Content-Security-Policy",
        "default-src *; script-src 'unsafe-inline'"));
    response
}

// 模式5：条件化 CSP 配置导致覆盖不完整
#[get("/?<mode>")]
fn page(mode: Option<String>) -> Response<'static> {
    let mut response = Response::build()
        .status(Status::Ok)
        .header(ContentType::HTML)
        .finalize()
        .unwrap();

    if mode == Some("dev".to_string()) {
        // 仅开发环境设置CSP，生产环境缺失
        response.set_header(Header::new("Content-Security-Policy", "default-src 'self'"));
    }
    response
}
```

### 快速定位到核心操作的技巧 **【L1: 关键词扫描】**
Rocket 框架中 CSP 响应头设置通常涉及两种机制：
1. **Response Builder 链式配置**
   - 搜索关键词：`Response::build()`、`.header()`、`set_header()`、`Content-Security-Policy`
   - 关注所有返回 HTML 内容的路由处理函数（routes）
   - 检查 HTML template 或直接返回 HTML string 的 handler

2. **全局 Fairing 中间件注入**
   - 搜索关键词：`impl Fairing`、`on_response()`、`attach()`、`AdHoc::on_response()`
   - 识别通过 `rocket::build().attach(fairing)` 或 `rocket.attach()` 注册的 fairing
   - 检查 fairing 的 `on_response()` 实现是否设置 CSP 响应头

3. **路由级别装饰器或 Guard**
   - 搜索关键词：`#[get]`、`#[post]`、`impl<'r> FromRequest<'r>`、`Request::local_cache()`
   - 关注涉及 HTML 渲染的所有路由

### 快速定位到保护机制的技巧 **【L2: 跳读】**
按以下顺序跳读代码检查保护机制：

1. **全局 CSP 设置点**
   - 查看 `main()` 函数中 `rocket::build()` 的链式调用
   - 检查是否有 `.attach(some_fairing)` 调用且该 fairing 实现了 CSP
   - 搜索 `impl Fairing` 的所有实现，特别是 `Response` 相关的处理

2. **Response 生成链路**
   - 定位所有返回 HTML 内容的 handler（通过 `Content-Type: text/html` 或 Rocket 的 `impl Responder`）
   - 检查每个 handler 是否在 Response 中设置 CSP 头
   - 统计覆盖率：如有 N 个 HTML handler，检查其中有多少设置了 CSP

3. **CSP 策略强度审查**
   - 跳读 CSP 策略字符串，检查是否包含：
     - `default-src *`（最高风险）
     - `script-src 'unsafe-inline'` 或 `'unsafe-eval'`（高风险）
     - `http:` 或 `https:` 作为独立源值（允许所有 HTTP/HTTPS 域名）
     - 多级通配符如 `*.com`（中风险）
   - 理想配置应为 `default-src 'self'; script-src 'nonce-...' 或 'sha256-...'; style-src 'self'` 等严格策略

4. **关键文件位置检查**
   - **应用入口** - `src/main.rs` 中的 fairing 配置
   - **中间件/Fairing 定义** - `src/fairing/`、`src/middleware/` 目录
   - **路由处理器** - `src/routes/`、`src/handlers/` 目录
   - **配置管理** - `Rocket.toml`、环境变量读取部分

### 代码审计跟踪流程
```
1. 查看src/main.rs中的rocket::build()调用
   ↓
2. 识别所有.attach()的fairing列表
   ↓
3. 对每个fairing，检查是否有impl Fairing且on_response()中设置CSP
   ↓
4. 扫描所有#[get]、#[post]等路由，统计返回HTML的handler数量
   ↓
5. 对每个HTML handler，检查是否手动设置了CSP响应头
   ↓
6. 收集所有CSP策略字符串，评估策略强度
```

## Classify

### 研判标准

**确认为真实漏洞的条件（需同时满足）：**
1. 应用存在返回 HTML 内容的路由处理函数（可通过 Content-Type 或 HTML string/template 识别）
2. 这些 HTML 路由处理函数中未显式设置 `Content-Security-Policy` 响应头
3. 应用级别的全局 fairing 中也未通过 `on_response()` 方法统一注入 CSP 响应头
4. 应用包含可能被攻击者利用的内容注入点（如模板变量、用户生成内容、来自 API 的数据）

**升级为高危的额外条件：**
- CSP 策略包含 `default-src *` 或 `script-src *`（完全无限制）
- CSP 同时包含 `'unsafe-inline'` 和 `'unsafe-eval'`（等同于无防护）
- 应用处理敏感数据（认证信息、个人数据）且无 CSP 保护

### 研判为误报的条件：

1. **纯 API 应用**
   - 所有响应均为 `Content-Type: application/json`
   - 不包含 HTML 路由处理函数
   - CSP 对 JSON API 无意义

2. **静态文件服务**
   - HTML 由 Rocket 前置的 Web 服务器（nginx、Apache）或 CDN 直接提供
   - Rocket 应用仅处理 API 请求
   - 可通过网络拓扑确认

3. **CSP 在上游层设置**
   - 反向代理（nginx、HAProxy）或 WAF 层统一设置 CSP
   - Rocket 应用无需重复设置
   - 审计者应检查代理配置确认覆盖

4. **受保护的执行环境**
   - 应用运行在隔离的内部网络，无外部用户访问
   - 所有 HTML 内容完全由后端生成且无用户可控数据
   - 应有组织文档确认此应用场景

### 代码异味（需进一步审查）：

1. **CSP 硬编码但策略不当** - 虽然设置了 CSP，但策略过于宽松（`*`、`unsafe-inline` 等）
2. **条件化 CSP 配置** - 仅在某些环境（如开发）中设置 CSP，生产环境缺失
3. **不完整的 fairing 覆盖** - 虽有全局 fairing，但某些特殊路由手动返回响应，绕过 fairing
4. **冗余配置点** - 既在 handler 中设置 CSP，又在 fairing 中设置，可能存在冲突或覆盖

## Low risk

### 允许低风险评级的情况

1. **使用 nonce 或 hash 机制的严格 CSP**
   - CSP 策略包含 `script-src 'nonce-xyz'` 或 `'sha256-xxx'`，严格限制脚本来源
   - 虽然可能包含 `'unsafe-inline'`，但通过 nonce/hash 实际约束脚本执行
   - 示例：`script-src 'nonce-random-value' https://trusted-cdn.com`

2. **仅限资源加载、不涉及脚本执行的宽松策略**
   - `img-src *`、`media-src *`、`font-src *`（图片、音视频、字体来源宽松但不涉及代码执行）
   - `style-src 'self' 'unsafe-inline'`（样式表未包含 unsafe-eval）
   - 此时需结合 XSS 漏洞才能造成实质伤害

3. **多层防护机制完整**
   - 虽然 CSP 本身宽松（如 `script-src *`），但：
     - 应用实现了严格的输入验证与 HTML 转义（Content-Type 为 UTF-8，所有用户输入都经过 encode）
     - 设置了 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY` 等补充防护
     - 使用 HTTPOnly 和 Secure Cookie 标志
   - 此时安全边界由应用级防护而非 CSP 承载，CSP 为纵深防护

4. **已部署监控和日志记录机制**
   - CSP 策略中配置了 `report-uri` 或 `report-to` 指令
   - 应用能有效记录 CSP violation 事件
   - 组织已建立响应流程，可快速发现和应对 XSS 尝试
   - 此情景下风险可通过监控层面部分抵消

5. **应用明确的业务场景限制**
   - 应用为内部管理后台，仅限信任网络访问（如 VPN、堡垒机后）
   - 所有 HTML 内容由可信后端完全生成，不包含任何用户生成内容
   - 应有明确的文档和访问控制策略支撑

6. **Rocket 框架级别的防护机制**
   - 应用使用了 Rocket 官方推荐的安全 middleware 或 contrib（如 `rocket::shield` 相关库）
   - 这些库在框架层面提供了等效的防护
   - 需审查库的实现代码确认防护强度
