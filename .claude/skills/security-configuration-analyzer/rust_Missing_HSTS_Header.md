# Rust - Missing HSTS Header

## Details

### 代码示例

```rust
// 示例1: actix-web 未设置 HSTS
use actix_web::{web, App, HttpResponse, HttpServer};

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .route("/", web::get().to(|| async { HttpResponse::Ok().body("Hello") }))
    })
    .bind_openssl("0.0.0.0:443", builder)?  // 仅启用HTTPS但无HSTS
    .run()
    .await
}

// 示例2: warp 缺失安全响应头
use warp::Filter;

#[tokio::main]
async fn main() {
    let route = warp::path::end()
        .map(|| warp::reply::html("Hello"));
    // 直接返回响应，未添加HSTS头
    warp::serve(route).tls().run(([0,0,0,0], 443)).await;
}

// 示例3: rocket 默认配置无HSTS
#[macro_use] extern crate rocket;

#[get("/")]
fn index() -> &'static str { "Hello" }

#[launch]
fn rocket() -> _ {
    rocket::build()
        .mount("/", routes![index])
        // 配置了TLS但未设置HSTS fairing
}

// 示例4: axum 缺少安全头中间件
use axum::{Router, routing::get};

#[tokio::main]
async fn main() {
    let app = Router::new().route("/", get(|| async { "Hello" }));
    
    axum_server::bind_rustls(addr, config)
        .serve(app.into_make_service())
        .await
        .unwrap();
    // 未使用 tower-http 的 SetResponseHeaderLayer 设置HSTS
}

// 示例5: tide 自定义响应未添加HSTS
#[async_std::main]
async fn main() -> tide::Result<()> {
    let mut app = tide::new();
    app.at("/").get(|_| async { Ok("Hello") });
    app.listen("0.0.0.0:443").await?;  // 无安全头中间件
    Ok(())
}
```

### 快速定位核心操作（审计技巧）

**L1 - 关键词扫描：**
- 服务器启动：`HttpServer::new`、`warp::serve`、`rocket::build`、`axum_server::bind_rustls`、`tide::listen`
- TLS配置：`bind_openssl`、`bind_rustls`、`.tls()`、`rustls::ServerConfig`
- 响应构建：`HttpResponse::Ok()`、`warp::reply`、`Response::builder()`
- 中间件/拦截器：`wrap()`、`layer()`、`middleware()`、`Fairing`

**L2 - 跳读：**
- main函数或服务入口：重点看 `HttpServer`/`warp::serve` 的链式配置
- 中间件注册区域：查找 `.wrap()`、`.layer()` 调用链，确认是否有安全头设置
- 全局响应拦截器：检查 `Fairing::on_response`（Rocket）或 `tower::Service` 实现
- 配置文件加载：`Rocket.toml`、自定义config结构体，确认是否有HSTS配置项

**L3 - 逐行读：**
- 响应头手动设置：追踪 `response.headers_mut().insert()` 调用，检查是否有 `Strict-Transport-Security`
- 条件分支：HSTS仅在生产环境启用的条件判断（`if cfg!(production)`）
- 自定义中间件实现：逐行检查 `Service::call` 或 `Middleware::handle` 的响应修改逻辑
- Header常量定义：搜索 `const HSTS_HEADER` 或类似常量的使用位置

**L4 - 跨模块追踪：**
- 中间件模块：检查 `middleware.rs`、`security.rs` 等独立模块的导出
- 依赖库版本：确认 `tower-http`、`actix-web-lab` 等安全增强库的使用情况
- 特征实现：追踪 `ResponseHeaders` trait 的全局实现
- 编译特性门控：检查 `#[cfg(feature = "security-headers")]` 是否启用

### 快速定位保护机制（审计技巧）

**L1 - 关键词扫描：**
- 安全头库：`tower-http::set_header`、`actix-web::middleware::DefaultHeaders`
- HSTS字面量：`"Strict-Transport-Security"`、`"max-age="`、`includeSubDomains`
- 中间件名称：`SecurityHeaders`、`HstsMiddleware`、`secure_headers`
- 响应构建器：`.insert_header()`、`.append_header()`、`header::STRICT_TRANSPORT_SECURITY`

**L2 - 跳读：**
- 依赖声明：`Cargo.toml` 中是否引入 `secure-headers`、`tower-http` 等库
- 中间件调用链：从服务器启动追踪到响应返回路径，确认HSTS注入点
- 环境配置：检查生产环境配置是否显式启用HSTS（`config.hsts_enabled = true`）

**L3 - 逐行读：**
- 中间件优先级：确认HSTS中间件在响应链的位置（应在压缩/缓存之后）
- 动态HSTS配置：max-age值是否可配置，是否支持preload指令
- 条件应用：检查是否仅对HTTPS响应添加HSTS（避免HTTP误添加）
- 子域名策略：确认 `includeSubDomains` 的启用逻辑

**L0 - 快速跳过：**
- 开发环境代码：`#[cfg(debug_assertions)]` 包裹的非生产逻辑
- 示例项目：`examples/`、`benches/` 目录的演示代码
- 内部API服务：仅供后端调用且不暴露给浏览器的gRPC/内部HTTP服务

## Classify

### 确认为漏洞的判定标准：
- 生产环境中暴露给浏览器的HTTPS服务未设置HSTS响应头
- 服务配置了TLS/SSL但缺少强制浏览器使用HTTPS的机制
- 存在HTTPS端点但HTTP端点未重定向且无HSTS保护
- 手动检查响应头（curl -I）确认缺失 `Strict-Transport-Security`

### 误报的常见场景：
- 反向代理层（Nginx/Caddy）统一添加HSTS，应用层无需重复设置
- 仅用于服务间通信的内部API（无浏览器访问场景）
- 开发/测试环境使用自签名证书且明确标注非生产
- WebSocket/gRPC等非HTTP协议服务（HSTS仅适用于HTTP）

### 代码异味的判定：
- HSTS max-age设置过短（<1年，推荐31536000秒）
- 未启用 `includeSubDomains` 导致子域名仍可能受中间人攻击
- HSTS通过条件编译仅在特定feature启用，但默认feature未包含
- 存在HSTS设置代码但被注释或通过配置默认禁用

### 研判流程：
1. 确认服务类型：识别是浏览器访问的Web服务还是API服务
2. 检查架构层级：明确HSTS应由应用层还是网关层负责
3. 验证生效性：使用 `curl -I https://domain` 检查实际响应头
4. 评估配置完整性：检查 max-age、includeSubDomains、preload 指令

## Low Risk

### 低风险场景评级标准：

**场景1：代理层统一处理**
- 前置Nginx/Traefik/Caddy配置了全局HSTS策略
- 应用层无需重复设置且架构文档明确说明
- 通过网关统一管理安全头，应用层仅负责业务逻辑

**场景2：非浏览器客户端**
- gRPC/Thrift等RPC服务，客户端为后端服务而非浏览器
- 移动应用使用的API端点（通过证书锁定保护）
- 内部管理接口仅允许VPN/堡垒机访问

**场景3：临时开发环境**
- localhost绑定的开发服务器，未暴露到公网
- Docker Compose本地环境，仅用于功能测试
- 使用 `#[cfg(debug_assertions)]` 明确标记的调试构建

**场景4：协议不适用**
- 纯WebSocket服务（wss://），连接建立后不受HSTS影响
- Server-Sent Events（SSE）长连接服务
- 已通过HSTS preload list注册的域名（浏览器内置规则）

**评级降级条件（即使符合低风险也需提升等级）：**
- 应用层与代理层安全策略未文档化，存在配置漂移风险
- 混合内容场景（同时提供HTTP和HTTPS且无强制跳转）
- 曾发生SSL/TLS降级攻击的历史记录
- 子域名管理混乱，部分子域可能绕过网关直接暴露