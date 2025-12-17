# Rust 多行响应头未规范化

## Details

**审计等级：L2（跳读）/ L3（逐行读）**

**危险函数特征：**
- `response.insert_header()` 传入包含 `
` 的值
- 从外部源读取头值未规范化
- 反向代理转发头时未规范化

**快速定位核心操作：**
1. 搜索关键字：`insert_header`、`
` 在值中
2. 追踪头值来源：外部 API、数据库、请求参数
3. 检查是否存在规范化
4. 追踪头值转发流程

**快速定位保护机制：**
- 规范化：`value.replace("
", "").replace("", "").replace("
", "")`
- 验证：`if value.contains('') || value.contains('
')`
- 框架防护：某些版本自动检测
- RFC 合规：遵循 HTTP 标准

**代码示例：**
```rust
// 危险：外部值直接设置为响应头
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

// 危险：API 响应转发
async fn forward_api() -> impl Responder {
    let api_response = /* API call */;
    for (key, value) in api_response.headers() {
        let val = value.to_str().unwrap_or("");
        // 直接使用，危险
    }
    HttpResponse::Ok().finish()
}

// 危险：数据库字段
async fn db_header() -> impl Responder {
    let header_val = /* from db */;
    HttpResponse::Ok()
        .insert_header(("X-Custom", header_val.as_str()))  // 危险
        .finish()
}
```

## Classify

**漏洞（Medium）：**
- 外部值包含 `
` 未规范化
- 导致响应分割
- 框架未自动检测

**误报：**
- 头值硬编码
- 框架已规范化

**代码异味（Medium）：**
- 外部来源未验证
- 仅过滤部分字符
- 间接流程

## Low risk

**以下情况评为低风险：**
- 头值硬编码
- 明确过滤 CRLF
- 框架已验证
- 内部来源且已验证
