# Rust hyper响应头CRLF注入

## 基本信息
- **难度等级：** ★★☆☆☆ | **审计时间：** 15-25分钟
- **关键词搜索：** `Response::builder`, `headers_mut`, `HeaderValue`, `hyper::Response`, `axum::response`, `actix_web::HttpResponse`
- **快速检查：** 响应头值是否来自用户输入，HeaderValue构造是否正确处理错误

## 漏洞成因

Rust的`http`/`hyper`crate在构造`HeaderValue`时会验证并拒绝包含CRLF的值。然而，若使用`unsafe`方法、错误处理不当导致panic、或通过底层API绕过检查，用户输入可能污染响应头。此外，即使CRLF被阻止，头值的业务语义仍可能被利用。

### 常见漏洞模式

```rust
// ✗ 漏洞：unwrap()可能导致panic
use hyper::{Response, Body, header::HeaderValue};

fn set_response_header(user_input: &str) -> Response<Body> {
    Response::builder()
        .header("X-Custom", HeaderValue::from_str(user_input).unwrap())
        // 如果user_input包含非法字符，程序panic
        .body(Body::empty())
        .unwrap()
}
```

```rust
// ✗ 漏洞：axum响应头使用用户输入
use axum::{response::{IntoResponse, Response}, http::header};

async fn handler(query: Query<Params>) -> impl IntoResponse {
    let custom_value = &query.custom;

    // 直接使用用户输入，虽然http crate会拒绝CRLF，
    // 但unwrap可能导致panic或DoS
    Response::builder()
        .header("X-Custom", custom_value.as_str())
        .body(Body::empty())
        .unwrap()
}
```

```rust
// ✗ 漏洞：Content-Disposition文件名注入
use hyper::header::{CONTENT_DISPOSITION, HeaderValue};

fn download_response(filename: &str) -> Response<Body> {
    let disposition = format!("attachment; filename=\"{}\"", filename);

    Response::builder()
        .header(CONTENT_DISPOSITION, HeaderValue::try_from(disposition).unwrap())
        // 文件名可能包含引号或其他特殊字符
        .body(Body::from(file_content))
        .unwrap()
}
```

```rust
// ✗ 漏洞：Location重定向头
use hyper::{Response, Body, StatusCode};

fn redirect(url: &str) -> Response<Body> {
    Response::builder()
        .status(StatusCode::FOUND)
        .header("Location", url)  // URL未验证
        .body(Body::empty())
        .unwrap()
}
```

```rust
// ✓ 修复：正确错误处理
use hyper::{Response, Body, StatusCode};
use http::header::HeaderValue;

fn safe_set_header(user_input: &str) -> Response<Body> {
    match HeaderValue::try_from(user_input) {
        Ok(value) => {
            Response::builder()
                .header("X-Custom", value)
                .body(Body::empty())
                .unwrap()
        }
        Err(_) => {
            // 返回错误响应而非panic
            Response::builder()
                .status(StatusCode::BAD_REQUEST)
                .body(Body::from("Invalid header value"))
                .unwrap()
        }
    }
}

fn safe_download(filename: &str) -> Response<Body> {
    // 过滤文件名特殊字符
    let safe_filename: String = filename
        .chars()
        .filter(|c| c.is_alphanumeric() || *c == '.' || *c == '-' || *c == '_')
        .collect();

    let disposition = format!("attachment; filename=\"{}\"", safe_filename);

    Response::builder()
        .header(CONTENT_DISPOSITION, disposition)
        .body(Body::from(file_content))
        .unwrap()
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | Location/重定向头 | 搜索 `Location\|Redirect`，检查URL来源和验证 |
| **P0** | HeaderValue::*unwrap | 搜索 `HeaderValue.*unwrap\|expect`，检查panic风险 |
| **P1** | Content-Disposition | 搜索 `CONTENT_DISPOSITION\|filename=`，检查文件名过滤 |
| **P1** | Response::builder().header | 搜索 `.header\(`，追踪值来源 |
| **P2** | Set-Cookie | 搜索 `Set-Cookie\|SET_COOKIE`，检查Cookie值来源 |
| **P2** | 自定义响应头 | 搜索 `X-Custom\|headers_mut`，评估用户输入影响 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 头值全部硬编码 | 快速跳过 |
| **L1** | 头值来自配置或环境变量 | 关键词扫描确认来源可信 |
| **L2** | 单函数内设置用户输入头值 | 跳读检查错误处理 |
| **L3** | 头值由Service层返回 | 逐行追踪返回值来源 |
| **L4** | 自定义响应中间件 | 跨模块审计头设置逻辑 |

---

## 审计专业技巧

### 真实漏洞与误报区分

#### 场景1：Location重定向头

**误报案例**
```rust
// 看似漏洞，但实际安全
fn redirect_safe(target: &str) -> Response<Body> {
    let allowed = ["https://example.com", "https://admin.example.com"];

    // 已在前置代码中验证
    if !allowed.contains(&target) {
        return Response::builder()
            .status(StatusCode::BAD_REQUEST)
            .body(Body::from("Invalid redirect"))
            .unwrap();
    }

    Response::builder()
        .status(StatusCode::FOUND)
        .header("Location", target)  // 看似用户输入，实际已白名单验证
        .body(Body::empty())
        .unwrap()
}
```

**审计技巧**：不要只看`Location`头的赋值行，需要**向上追踪至少20行代码**，查看是否有白名单/正则验证。常见的误报来自于：
- 已验证的变量再次赋值
- 通过中间函数已经过滤（需追踪调用链）
- URL解析库已拒绝恶意URL

**真实漏洞特征**
```rust
// 真正的漏洞：直接使用用户输入
async fn download_redirect(Query(params): Query<DlParams>) -> Response<Body> {
    Response::builder()
        .status(StatusCode::FOUND)
        .header("Location", &params.download_url)  // ✗ 直接使用，未验证
        .body(Body::empty())
        .unwrap()
}
```

#### 场景2：Content-Disposition文件名

**误报案例**
```rust
// 虽然使用了用户输入文件名，但已通过系统API验证
fn serve_file(file_id: u32) -> Response<Body> {
    let file_path = format!("/secure/files/{}", file_id);

    // 使用PathBuf::new()验证路径合法性
    let path = PathBuf::from(&file_path);
    if !path.starts_with("/secure/files") {
        return Response::builder().status(StatusCode::NOT_FOUND).body(Body::empty()).unwrap();
    }

    let filename = path.file_name().unwrap().to_string_lossy();
    let disposition = format!("attachment; filename=\"{}\"", filename);

    Response::builder()
        .header(CONTENT_DISPOSITION, &disposition)
        .body(Body::from(content))
        .unwrap()
}
```

**审计技巧**：关键在于文件名来源：
- 从数据库查询 + DB字段受系统控制 = 低风险
- 从文件系统读取 + 已通过path validation = 低风险
- 直接来自URL参数 = 高风险

**红旗信号**：
```rust
// ✗ 来自URL参数，无过滤
let filename = params.name;

// ✓ 来自数据库
let filename = db_query(file_id).unwrap().filename;

// ✗ 轻量级过滤不足
let filename = params.name.replace("\"", "");  // 可绕过
```

#### 场景3：Set-Cookie头

**误报vs真实漏洞**
```rust
// 误报：Cookie值虽然来自外部，但已严格验证
fn set_session(user_id: u32) -> Response<Body> {
    // Cookie值是系统生成的，不是用户提供
    let session_id = generate_secure_session_id(user_id);  // 系统生成

    Response::builder()
        .header(SET_COOKIE, format!("session={}", session_id))
        .body(Body::empty())
        .unwrap()
}

// 真实漏洞：直接使用用户输入
fn set_preference(Query(q): Query<PrefParams>) -> Response<Body> {
    Response::builder()
        .header(SET_COOKIE, format!("pref={}", q.preference))  // ✗ 未验证
        .body(Body::empty())
        .unwrap()
}
```

### 高级审计技巧

**技巧1：调用链追踪**
- 不要停留在当前函数，追踪参数来源
- 查看是否经过中间件、过滤器、validator
- 搜索参数的所有使用点，而不仅是当前行

**技巧2：编译时vs运行时**
```rust
// 安全：编译时常量
Response::builder().header("X-Version", "1.0.0").body(Body::empty())

// 需要检查：运行时变量
let version = config.version;
Response::builder().header("X-Version", &version).body(Body::empty())
```

**技巧3：错误处理的隐藏漏洞**
```rust
// 问题：错误分支虽然返回400，但可用于DoS
HeaderValue::from_str(user_input)
    .map_err(|_| Response::status(StatusCode::BAD_REQUEST))  // 可大量触发错误

// 进阶问题：判断是否有速率限制、日志记录
```

**技巧4：框架特定的防护**
```rust
// axum框架使用TypedHeader会自动拒绝非法值
use axum::TypedHeader;
use http::header::User_Agent;

async fn handler(TypedHeader(user_agent): TypedHeader<User_Agent>) {
    // user_agent已由框架验证，安全
}

// 相比之下，手动解析更易出错
let ua = headers.get("User-Agent").map(|h| h.to_str());
```

### 常见误报陷阱

| 陷阱 | 特征 | 如何判断 |
|------|------|---------|
| 配置来源误判 | 认为.env/.yaml文件的值是用户输入 | 检查部署流程，配置通常由运维管理 |
| 类型系统保护 | HeaderValue::try_from已验证 | 检查是否确实使用了try_from而非unsafe |
| 中间件过滤 | 假设中间件一定执行 | 验证中间件加载顺序和条件分支 |
| 数据库洁净性 | 假设数据库数据总是安全 | 检查INSERT权限，是否有SQL注入风险 |
| 长度限制假设 | 认为字符串长度有保障 | 搜索.len()、.take()等限制操作 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 响应头值来自用户输入
2. 使用unwrap/expect可能导致panic
3. 或头值语义可被利用（如Location重定向）

### 典型漏洞特征（满足任一项即确认）
- ✗ `HeaderValue::from_str(user_input).unwrap()` panic风险
- ✗ `Response::builder().header("Location", user_url)` 未验证
- ✗ Content-Disposition文件名包含用户输入，未过滤特殊字符
- ✗ Set-Cookie值使用未验证的用户输入

### 安全排除（任一项充分）
- ✓ http crate自动拒绝CRLF（且正确处理Result）
- ✓ 使用`from_static`仅用于编译时常量
- ✓ 白名单验证头值
- ✓ 正确处理错误，返回安全响应

### 灰色判定（风险较低但需注意）
- 错误导致400响应但可能泄露信息
- 头值有长度限制
- 内部服务间通信

---

## 实现建议

### 核心防护方案

**方案1：正确错误处理**
```rust
use http::header::HeaderValue;
use hyper::{Response, Body, StatusCode};

fn set_header_safe(user_input: &str) -> Response<Body> {
    let header_result = HeaderValue::try_from(user_input);

    match header_result {
        Ok(value) => {
            Response::builder()
                .header("X-Custom", value)
                .body(Body::empty())
                .unwrap()
        }
        Err(e) => {
            log::warn!("Invalid header value: {}", e);
            Response::builder()
                .status(StatusCode::BAD_REQUEST)
                .body(Body::from("Invalid input"))
                .unwrap()
        }
    }
}
```

**方案2：安全的重定向**
```rust
use std::collections::HashSet;

fn safe_redirect(url: &str, allowed_domains: &HashSet<&str>) -> Response<Body> {
    // 解析URL并验证域名
    if let Ok(parsed) = url::Url::parse(url) {
        if let Some(host) = parsed.host_str() {
            if allowed_domains.contains(host) {
                return Response::builder()
                    .status(StatusCode::FOUND)
                    .header("Location", url)
                    .body(Body::empty())
                    .unwrap();
            }
        }
    }

    // 默认重定向到首页
    Response::builder()
        .status(StatusCode::FOUND)
        .header("Location", "/")
        .body(Body::empty())
        .unwrap()
}
```

**方案3：安全的Content-Disposition**
```rust
fn safe_content_disposition(filename: &str) -> String {
    // 仅保留安全字符
    let safe_name: String = filename
        .chars()
        .filter(|c| c.is_alphanumeric() || *c == '.' || *c == '-' || *c == '_')
        .take(100)  // 限制长度
        .collect();

    // 使用RFC 5987编码
    format!("attachment; filename=\"{}\"; filename*=UTF-8''{}",
            safe_name,
            urlencoding::encode(&safe_name))
}
```

### 检查清单
- [ ] 所有HeaderValue构造使用try_from并处理错误
- [ ] Location重定向使用URL白名单
- [ ] Content-Disposition文件名过滤特殊字符
- [ ] Set-Cookie值进行验证
- [ ] 测试非法输入：`\r`, `\n`, `\0`

---

## 修复优先级

1. **立即修复**：Location重定向使用未验证的用户输入
2. **本周修复**：所有unwrap改为正确错误处理
3. **可选加强**：实现白名单验证头值
4. **长期优化**：封装安全的响应构建API
