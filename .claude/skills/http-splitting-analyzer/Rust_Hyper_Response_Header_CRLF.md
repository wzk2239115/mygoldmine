# Rust Hyper 响应头 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `response.headers_mut().insert()` 设置响应头
- `HeaderValue::from_str()` 包含用户输入
- `HeaderMap` 直接赋值用户数据
- Actix-web `HttpResponse.insert_header()` 等

**快速定位核心操作：**
1. 搜索关键字：`headers_mut()`、`insert_header`、`HeaderValue`
2. 追踪头值来源：`web::Query`、`web::Form`、请求头
3. 检查是否存在 CRLF 过滤或验证
4. 追踪从请求到响应头的链路

**快速定位保护机制：**
- 值检查：`if value.contains('') || value.contains('
')`
- HeaderValue 验证：`HeaderValue::from_str()` 会自动检测某些问题
- 白名单验证：`regex` 或手动检查
- 框架级防护：某些框架版本自动验证

**代码示例：**
```rust
// 危险：用户输入直接设置为响应头（如果框架不验证）
async fn handle(Query(params): Query<HashMap<String, String>>) -> impl Responder {
    let custom = params.get("name").unwrap_or(&String::new());
    HttpResponse::Ok()
        .insert_header(("X-Custom", custom.as_str()))  // 危险：如果未过滤
        .finish()
}

// 危险：Request 头直接转发
async fn proxy(req: HttpRequest) -> impl Responder {
    if let Some(header) = req.headers().get("X-Custom") {
        let val = header.to_str().unwrap_or("");
        HttpResponse::Ok()
            .insert_header(("X-Forwarded", val))  // 危险
            .finish()
    } else {
        HttpResponse::BadRequest().finish()
    }
}

// 危险：直接拼接
async fn create_header(Form(data): Form<HashMap<String, String>>) -> impl Responder {
    let value = &data["value"];
    let mut response = HttpResponse::Ok();
    response.insert_header(("X-Data", value.as_str()));  // 危险
    response.finish()
}
```

## Classify

**漏洞（High）：**
- 用户输入直接用于响应头
- 无 CRLF 过滤（如 HeaderValue 验证被绕过）
- 允许响应分割

**误报：**
- 响应头值硬编码
- Hyper/框架已自动验证
- `HeaderValue::from_str()` 成功（已验证）

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 使用 `unwrap()` 跳过验证

## Low risk

**以下情况评为低风险：**
- 响应头值硬编码
- 使用框架的类型安全 API（如 `HeaderValue::from_static()`）
- 严格的 CRLF 过滤
- 白名单验证
- 内部来源且已验证
