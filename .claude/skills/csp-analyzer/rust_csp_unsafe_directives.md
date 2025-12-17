# Rust CSP 不安全指令审计指南

## 漏洞描述

在 Rust Web 框架中，当 Content Security Policy (CSP) 头部配置使用 `unsafe-inline` 或通配符（`*`）等不安全指令时，会严重削弱 CSP 的防护能力，使浏览器无法有效阻止内联脚本或样式的注入攻击，导致 XSS 漏洞风险大幅增加。

## Details

### 核心操作示例

**Actix-web 框架中的 CSP 头部配置：**

```rust
use actix_web::{web, App, HttpResponse, HttpServer, middleware};
use actix_cors::Cors;

async fn index() -> HttpResponse {
    HttpResponse::Ok()
        .insert_header(("Content-Security-Policy", "script-src 'unsafe-inline' *"))
        .body("vulnerable content")
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .route("/", web::get().to(index))
            // 或在中间件中全局设置
            .wrap_fn(|req, srv| {
                let mut res = srv.call(req);
                res.add_header(("Content-Security-Policy", "default-src *; script-src 'unsafe-inline'"));
                futures::future::ok(res)
            })
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}
```

**Rocket 框架中的 CSP 配置：**

```rust
use rocket::response::{Responder, Response};
use rocket::http::Header;

pub struct CspResponse;

impl<'r> Responder<'r, 'static> for CspResponse {
    fn respond_to(self, _: &'r rocket::Request<'_>) -> rocket::response::Result<'static> {
        Response::build()
            .header(Header::new("Content-Security-Policy", "script-src 'unsafe-eval' *"))
            .ok()
    }
}
```

**Axum 框架中的不安全配置：**

```rust
use axum::{
    routing::get,
    http::header::{HeaderMap, HeaderValue},
    response::IntoResponse,
    Router,
};

async fn handler() -> impl IntoResponse {
    let mut headers = HeaderMap::new();
    headers.insert(
        "Content-Security-Policy",
        HeaderValue::from_static("default-src * 'unsafe-inline' 'unsafe-eval'")
    );
    (headers, "response body")
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/", get(handler));

    let listener = tokio::net::TcpListener::bind("127.0.0.1:3000")
        .await
        .unwrap();
    axum::serve(listener, app).await.unwrap();
}
```

### 快速定位核心操作

**【L1: 关键词扫描】**

- 直接搜索 CSP 相关关键字：`"Content-Security-Policy"`、`"CSP"`、`"script-src"`、`"style-src"`
- 查找不安全指令：`"'unsafe-inline'"`、`"'unsafe-eval'"`、`"*"`（作为源指令时）
- 定位头部设置：`insert_header`、`header`、`Header::new`、`HeaderValue`、`.wrap_fn`
- 搜索 CSP 中间件框架：`csp`、`SecurityHeaders`、`ResponseHeader` 相关的 crate 使用

### 快速定位保护机制

**【L2: 跳读】**

- 检查是否存在 CSP 头部设置的配置文件或常量定义（如 `config.rs`、`constants.rs`）
- 查找是否有 CSP 白名单配置模块，是否采用了 crate 如 `rocket-security`、`actix-cors` 的安全中间件
- 跳读路由定义和响应构建部分，查看是否对所有 HTTP 响应一致地添加了 CSP 头部
- 检查是否存在环境变量控制的 CSP 策略，或通过配置文件动态加载的安全策略
- 寻找是否有针对特定内容类型（如 HTML、JSON）的差异化 CSP 设置

## Classify

### 研判为真实漏洞的条件

1. **完全不安全的 CSP 配置**：设置 `default-src *` 或 `script-src 'unsafe-inline' 'unsafe-eval'` 而无任何白名单约束，直接导致 XSS 防护完全失效
2. **内联脚本与样式注入风险**：存在 `'unsafe-inline'` 且应用接收并输出用户输入到 HTML 属性或 `<script>` 标签，形成可实际利用的 XSS 链路
3. **动态内容绕过**：使用 `'unsafe-eval'` 或 nonce/hash 机制配置不当，导致攻击者能执行任意代码
4. **全局性漏洞**：不安全 CSP 通过中间件应用于所有响应路由，覆盖范围广，影响面大

### 研判为误报的条件

1. **应用场景受限**：CSP 仅用于非关键内容（如错误页面、日志视图）的静态资源加载，即使 `unsafe-inline` 也因内容固定而风险可控
2. **存在补充防护**：虽然 CSP 不安全但应用实现了严格的输入验证、HTML 转义、模板自动转义等强有力的一级防护
3. **沙箱隔离**：应用运行在完全隔离的沙箱环境，且输入严格受限于预定义格式

### 研判为代码异味的条件

1. **开发环境特例**：CSP 宽松仅在 `debug` 模式或特定开发配置中启用，生产环境严格安全
2. **遗留代码标记**：存在代码注释明确指出 CSP 配置待改进，或存在 TODO/FIXME 标记
3. **过度保护的白名单**：CSP 虽使用通配符，但结合其他层级防护或实际应用限制，其风险实际可控

## Low risk

### 低风险评级场景

1. **仅针对特定资源类型**：CSP 配置在个别指令（如 `font-src *`）上使用通配符，但关键指令（`script-src`、`style-src`）仍保持严格的白名单限制
2. **API 响应而非页面**：应用主要返回 JSON/XML 等数据，不涉及页面级 CSP 配置；即使配置也因内容格式无法执行脚本
3. **内容完全由应用生成**：HTML 内容完全由应用代码生成，不包含任何用户输入部分，即使 `unsafe-inline` 也无实际被利用的入口点
4. **受众群体受限**：应用仅供内部信任用户使用，或运行在受控的企业网络环境，外部攻击面受限
5. **特定浏览器/环境**：CSP 配置虽不安全但仅影响特定老旧浏览器版本，或目标用户主要使用支持更新安全机制的浏览器
