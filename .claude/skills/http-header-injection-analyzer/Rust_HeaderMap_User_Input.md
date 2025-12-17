# Rust HeaderMap用户输入注入

## 基本信息
- **难度等级：** ★★☆☆☆ | **审计时间：** 15-25分钟
- **关键词搜索：** `HeaderMap`, `HeaderName`, `HeaderValue`, `insert`, `append`, `from_bytes`, `try_from`, `headers_mut()`
- **快速检查：** HeaderMap insert/append的值是否来自用户输入，HeaderValue构造是否有错误处理

## 漏洞成因

Rust的`http`crate中`HeaderValue::from_bytes()`和`HeaderValue::try_from()`会拒绝包含CRLF等非法字符的输入。然而若使用`unsafe`方法或错误处理不当，用户输入可能绕过检查。此外，头名称用户可控或头值业务语义被利用也存在风险。

### 常见漏洞模式

```rust
// ✗ 漏洞：使用from_static绕过验证（编译时检查，运行时可能有问题）
use http::header::{HeaderMap, HeaderName, HeaderValue};

fn set_custom_header(headers: &mut HeaderMap, user_input: &str) {
    // 如果user_input包含非法字符，from_static会panic或UB
    // 应使用try_from并处理错误
    let value = HeaderValue::from_str(user_input).unwrap();  // panic风险
    headers.insert("X-Custom", value);
}
```

```rust
// ✗ 漏洞：头名称用户可控
async fn set_dynamic_header(
    headers: &mut HeaderMap,
    name: String,
    value: String,
) {
    // 用户可控制头名称，可能设置敏感头
    if let Ok(header_name) = HeaderName::try_from(name) {
        if let Ok(header_value) = HeaderValue::try_from(value) {
            headers.insert(header_name, header_value);
        }
    }
    // 攻击: name="Set-Cookie", value="admin=true"
}
```

```rust
// ✗ 漏洞：from_maybe_shared使用未验证输入
use bytes::Bytes;

fn set_header_from_bytes(headers: &mut HeaderMap, user_bytes: Bytes) {
    // from_maybe_shared可能接受非法值
    let value = HeaderValue::from_maybe_shared(user_bytes).unwrap();
    headers.insert("X-Custom", value);
}
```

```rust
// ✗ 漏洞：忽略HeaderValue构造错误
fn set_header_ignore_error(headers: &mut HeaderMap, user_input: &str) {
    // 错误被静默忽略，但攻击者可能利用其他头
    if let Ok(value) = HeaderValue::try_from(user_input) {
        headers.insert("X-Custom", value);
    }
    // 未处理错误可能导致逻辑漏洞
}
```

```rust
// ✓ 修复：正确验证和错误处理
use http::header::{HeaderMap, HeaderName, HeaderValue};
use std::collections::HashSet;

static ALLOWED_CUSTOM_HEADERS: &[&str] = &["x-request-id", "x-correlation-id"];

fn safe_set_header(
    headers: &mut HeaderMap,
    name: &str,
    value: &str,
) -> Result<(), HeaderError> {
    // 1. 白名单验证头名称
    if !ALLOWED_CUSTOM_HEADERS.contains(&name.to_lowercase().as_str()) {
        return Err(HeaderError::HeaderNotAllowed);
    }

    // 2. 构造HeaderName和HeaderValue，处理错误
    let header_name = HeaderName::try_from(name)
        .map_err(|_| HeaderError::InvalidHeaderName)?;
    let header_value = HeaderValue::try_from(value)
        .map_err(|_| HeaderError::InvalidHeaderValue)?;

    // 3. 安全插入
    headers.insert(header_name, header_value);
    Ok(())
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 头名称用户可控 | 搜索 `HeaderName::try_from\|from_bytes`，检查参数来源 |
| **P0** | unwrap()用于HeaderValue | 搜索 `HeaderValue.*unwrap\|expect`，检查panic风险 |
| **P1** | from_maybe_shared | 搜索 `from_maybe_shared`，检查输入验证 |
| **P1** | headers_mut().insert | 搜索 `headers_mut\(\).*insert`，追踪值来源 |
| **P2** | 错误处理不当 | 搜索 `if let Ok.*HeaderValue`，评估错误处理逻辑 |
| **P2** | 批量头设置 | 搜索循环中的header设置，检查用户输入 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 头名和值全部硬编码 | 快速跳过 |
| **L1** | 头值来自配置或环境变量 | 关键词扫描确认来源可信 |
| **L2** | 单函数内设置用户输入头值 | 跳读检查错误处理和白名单 |
| **L3** | 头值由外部函数返回 | 逐行追踪返回值来源 |
| **L4** | 自定义响应构建器 | 跨模块审计头设置接口 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. HeaderMap操作涉及用户输入
2. 头名称可控或错误处理不当（unwrap/expect）
3. 可能影响响应安全性

### 典型漏洞特征（满足任一项即确认）
- ✗ `HeaderName::try_from(user_input)` 头名称用户可控
- ✗ `HeaderValue::from_str(user_input).unwrap()` panic风险
- ✗ `from_maybe_shared(user_bytes)` 使用未验证字节
- ✗ 忽略HeaderValue构造错误但继续处理

### 安全排除（任一项充分）
- ✓ http crate自动拒绝CRLF（正确处理Result）
- ✓ 头名称使用白名单
- ✓ 使用`from_static`仅用于编译时常量
- ✓ 正确处理try_from错误并返回安全响应

### 灰色判定（风险较低但需注意）
- 错误被记录但未返回给用户
- 内部服务间通信
- 头值有长度限制但无字符验证

---

## 实现建议

### 核心防护方案

**方案1：头名称白名单**
```rust
use std::collections::HashSet;
use once_cell::sync::Lazy;

static ALLOWED_HEADERS: Lazy<HashSet<&'static str>> = Lazy::new(|| {
    vec!["x-request-id", "x-correlation-id", "x-custom-data"]
        .into_iter()
        .collect()
});

fn is_allowed_header(name: &str) -> bool {
    ALLOWED_HEADERS.contains(name.to_lowercase().as_str())
}
```

**方案2：安全的头值设置**
```rust
use http::header::{HeaderMap, HeaderName, HeaderValue};

fn safe_insert_header(
    headers: &mut HeaderMap,
    name: &'static str,  // 静态字符串，编译时检查
    value: &str,
) -> Result<(), &'static str> {
    let header_value = HeaderValue::try_from(value)
        .map_err(|_| "Invalid header value")?;

    headers.insert(
        HeaderName::from_static(name),
        header_value,
    );
    Ok(())
}
```

**方案3：框架级头设置**
```rust
// axum示例
use axum::response::{IntoResponse, Response};
use http::StatusCode;

async fn handler(value: String) -> impl IntoResponse {
    // 使用框架方法，自动处理错误
    match HeaderValue::try_from(&value) {
        Ok(header_value) => {
            let mut response = Response::new("OK".into());
            response.headers_mut().insert("X-Custom", header_value);
            response
        }
        Err(_) => {
            Response::builder()
                .status(StatusCode::BAD_REQUEST)
                .body("Invalid header value".into())
                .unwrap()
        }
    }
}
```

### 检查清单
- [ ] 禁止用户控制头名称
- [ ] HeaderValue::try_from错误正确处理
- [ ] 不使用unwrap/expect于用户输入
- [ ] 使用白名单限制可设置的自定义头
- [ ] 测试非法字符：`\r`, `\n`, `\0`

---

## 审计专业技巧与漏洞判别

### 1. 真实漏洞特征识别

#### 漏洞模式A：头名称动态可控（HIGH RISK）
```rust
// ✗ 真实漏洞：完全用户可控的头名称
async fn proxy_custom_headers(req: &HttpRequest, mut resp_headers: HeaderMap) {
    // 攻击者可注入Set-Cookie、Content-Type等敏感头
    for (key, value) in req.headers().iter() {
        if key.as_str().starts_with("x-forward-") {
            let new_key = key.as_str().strip_prefix("x-forward-").unwrap();
            // 🔴 直接用用户输入作为头名称
            if let Ok(header_name) = HeaderName::try_from(new_key) {
                if let Ok(header_value) = HeaderValue::try_from(value.to_str().unwrap()) {
                    resp_headers.insert(header_name, header_value);
                }
            }
        }
    }
}

// 攻击示例：
// GET / HTTP/1.1
// X-Forward-Set-Cookie: admin=true; Path=/
// X-Forward-Content-Type: text/html; charset=utf-8
```

**识别要点：**
- 头名称通过用户输入、URL参数、请求头传入
- 未做白名单过滤，只验证格式合法性
- 即使try_from正确处理，也能注入任意标准HTTP头

#### 漏洞模式B：错误处理导致的逻辑绕过（MEDIUM RISK）
```rust
// ✗ 真实漏洞：错误静默忽略，导致部分逻辑失效
fn add_security_headers(headers: &mut HeaderMap, user_data: String) {
    // 试图添加CSP头
    if let Ok(csp_value) = HeaderValue::try_from(format!("default-src 'self'; script-src {}", user_data)) {
        headers.insert("Content-Security-Policy", csp_value);
    } else {
        // 错误被忽略，但其他地方假设CSP已设置！
        log::warn!("CSP header setting failed");
    }
    // 🔴 如果user_data包含\r\n，try_from失败，CSP未设置
    // 而响应处理逻辑可能认为已有CSP保护
}
```

**识别要点：**
- 错误处理后仅log，未返回错误或使用默认值
- 调用方假设头设置成功（安全关键头）
- 用户输入导致头设置失败时的业务逻辑是否安全

### 2. 常见误报与排除标准

#### 误报案例1：from_static仅用于编译时常量
```rust
// ✓ 安全（虽然看起来像使用from_static）
fn respond_with_cache(body: String) -> impl Response {
    // from_static保证值在编译时已知，无运行时风险
    let mut headers = HeaderMap::new();
    headers.insert("Cache-Control", HeaderValue::from_static("max-age=3600, public"));
    headers.insert("X-Cached", HeaderValue::from_static("true"));
    // ✓ 完全安全，用户输入只在body中
}

// ✗ 审计误报示例：
// "发现使用了from_static（可能不安全）"
// 错误原因：from_static只能用编译时常量，用户无法注入
```

**排除规则：**
- `HeaderValue::from_static()` 或 `HeaderName::from_static()` 传入的必须是编译时字面量
- 无法传入变量或用户输入（编译器会强制报错）
- 审计中可快速跳过此类

#### 误报案例2：正确的try_from错误处理
```rust
// ✓ 安全：正确处理try_from的Result
async fn handle_custom_header(req: HttpRequest) -> HttpResponse {
    let user_input = req.query().get("custom_header").map(|s| s.to_string());

    match user_input {
        Some(value) => {
            // 关键：尝试转换，失败返回错误
            match HeaderValue::try_from(value) {
                Ok(hv) => {
                    let mut resp = HttpResponse::Ok();
                    resp.headers_mut().insert("X-Echo", hv);
                    resp.finish()
                }
                Err(_) => {
                    // ✓ 错误被正确处理，返回4xx而非设置头
                    HttpResponse::BadRequest().body("Invalid header value")
                }
            }
        }
        None => HttpResponse::Ok().finish(),
    }
}

// 误报诱因：看起来在处理用户输入
// 实际安全原因：
// 1. try_from失败时不设置头
// 2. 返回4xx给客户端，响应安全
// 3. 没有CRLF注入风险（http crate验证）
```

**排除规则：**
- try_from返回Err时，代码路径中不设置任何头
- 错误导致返回error response（4xx/5xx），而非继续执行
- HeaderValue::try_from已验证非法字符（http crate内置）

#### 误报案例3：内部系统间通信（低风险）
```rust
// ⚠️ 低风险（上下游都可信）
async fn call_backend_service(req: HttpRequest) -> Result<HttpResponse> {
    let mut backend_req = http::Request::builder();

    // 从请求头复制部分头到后端服务
    for (name, value) in req.headers() {
        if name.as_str().starts_with("x-internal-") {
            // 虽然用户可控，但：
            // 1. 只转发给内部后端服务（非响应）
            // 2. 后端也信任这些头
            // 3. 不存在向客户端回显的风险
            backend_req = backend_req.header(name, value);
        }
    }

    let backend_resp = backend_req.send().await?;
    Ok(HttpResponse::from(backend_resp))
}

// 审计判定：
// 虽然有用户输入，但不涉及Response.headers()修改
// 仅涉及内部Request.headers()设置
// 风险等级从HIGH降低到LOW
```

**排除规则：**
- 用户输入头仅用于向内部服务发起请求（Request）
- 不被设置到HTTP响应头中（Response.headers()）
- 下游服务已验证这些头格式

### 3. 审计决策树

```
发现HeaderMap操作
    ↓
[1] 涉及用户输入？
    ├─ No  → ✓ 安全（跳过）
    └─ Yes → [2]

[2] 操作类型？
    ├─ Request头设置（向内部服务）→ [3]
    ├─ Response头设置（返回给客户端）→ [4]
    └─ 其他 → 检查具体风险

[3] 下游是否可信？
    ├─ 可信内部服务 + 头格式已验证 → ✓ 低风险
    └─ 不可信或未验证 → [4]

[4] 头名称来源？
    ├─ 硬编码或白名单 → [5]
    ├─ 完全用户可控 → ✗ 高风险漏洞
    └─ 部分可控 → [5]

[5] 头值处理？
    ├─ from_static(字面量) → ✓ 安全
    ├─ try_from() + 正确错误处理 → [6]
    ├─ unwrap/expect/panic → ✗ 中危漏洞
    └─ from_maybe_shared + 验证 → [6]

[6] 业务逻辑是否依赖头设置成功？
    ├─ 否（错误处理返回错误响应） → ✓ 较安全
    └─ 是（假设头已设置） → ✗ 逻辑漏洞
```

### 4. 高危特征速查表

| 特征 | 等级 | 说明 | 误报可能 |
|------|------|------|---------|
| `HeaderName::try_from(user_var)` | 🔴高 | 头名称用户可控 | 极低 |
| `HeaderValue::from_str(user).unwrap()` | 🔴高 | panic风险 + 用户输入 | 极低 |
| `headers.insert(x, y).ignore_err()` | 🟠中 | 错误忽略，需检查业务逻辑 | 低 |
| 循环遍历请求头后转发到响应 | 🟠中 | 需判断头名称是否过滤 | 中 |
| `from_static()` 传编译时常量 | 🟢低 | 完全安全 | 高（常见误报） |
| Request头设置 + 内部服务 | 🟢低 | 需确认下游可信 | 中 |

---

## 修复优先级

1. **立即修复**：头名称用户可控的场景
2. **本周修复**：所有unwrap改为正确错误处理
3. **可选加强**：实现头名称白名单
4. **长期优化**：封装安全的头设置API
