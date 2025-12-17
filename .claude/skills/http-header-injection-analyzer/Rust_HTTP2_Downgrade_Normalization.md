# Rust HTTP/2降级规范化不一致

## 基本信息
- **难度等级：** ★★★★★ | **审计时间：** 40-60分钟
- **关键词搜索：** `http2`, `h2`, `:authority`, `:method`, `HeaderName`, `to_lowercase`, `hyper`, `tower`, `axum::extract`
- **快速检查：** 是否处理HTTP/2请求，头字段大小写处理是否一致

## 漏洞成因

HTTP/2协议强制所有头字段小写（如`content-type`），而HTTP/1.1传统使用多种大小写形式。Rust的`http`crate中`HeaderName`自动规范化为小写，但若手动处理字符串形式的头或进行协议转换时处理不当，可能导致安全检查绕过、请求走私等攻击。

### 常见漏洞模式

```rust
// ✗ 漏洞：手动字符串比较，大小写敏感
fn check_content_type(headers: &str) -> bool {
    // HTTP/2头是小写，此检查可能被绕过
    headers.contains("Content-Type: application/json")
}
```

```rust
// ✗ 漏洞：从原始字符串解析头，大小写敏感过滤
fn filter_headers(raw_headers: &str) -> Vec<(&str, &str)> {
    let blocked = vec!["X-Forwarded-For", "X-Real-IP"];
    let mut result = vec![];

    for line in raw_headers.lines() {
        let parts: Vec<&str> = line.splitn(2, ':').collect();
        if parts.len() == 2 {
            let name = parts[0].trim();
            // 大小写敏感比较，HTTP/2小写头可绕过
            if !blocked.contains(&name) {
                result.push((name, parts[1].trim()));
            }
        }
    }
    result
}
```

```rust
// ✗ 漏洞：HTTP/2伪头处理不当
async fn h2_proxy(req: Request<Body>) -> Result<Response<Body>, Error> {
    // 从HTTP/2请求获取头
    let authority = req.headers()
        .get(":authority")  // 伪头可能不在headers中
        .map(|v| v.to_str().unwrap_or(""));

    // 同时检查Host头，可能导致不一致
    let host = req.headers()
        .get("host")
        .map(|v| v.to_str().unwrap_or(""));

    // 攻击者可能发送冲突的:authority和Host
}
```

```rust
// ✗ 漏洞：自定义头规范化逻辑
fn normalize_header_name(name: &str) -> String {
    // 简单的首字母大写，与http crate行为不一致
    name.split('-')
        .map(|s| {
            let mut c = s.chars();
            match c.next() {
                None => String::new(),
                Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
            }
        })
        .collect::<Vec<_>>()
        .join("-")
}
```

```rust
// ✓ 修复：使用http crate的HeaderName（自动小写化）
use http::header::HeaderName;

fn check_header_safe(headers: &http::HeaderMap, name: &str) -> Option<&str> {
    // HeaderName自动规范化为小写
    let header_name = HeaderName::from_bytes(name.as_bytes()).ok()?;
    headers.get(&header_name)?.to_str().ok()
}

fn filter_blocked_headers(headers: &mut http::HeaderMap) {
    let blocked: Vec<HeaderName> = vec![
        HeaderName::from_static("x-forwarded-for"),
        HeaderName::from_static("x-real-ip"),
    ];

    for name in blocked {
        headers.remove(&name);
    }
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 手动字符串头比较 | 搜索 `contains\|==.*"Content-Type\|"Host"`，检查大小写敏感性 |
| **P0** | HTTP/2伪头处理 | 搜索 `:authority\|:method\|:path`，验证与Host的一致性处理 |
| **P1** | 头黑名单过滤 | 搜索 `blocked\|filter.*header`，检查是否使用HeaderName类型 |
| **P1** | 自定义头规范化 | 搜索 `to_uppercase\|to_lowercase.*header`，检查一致性 |
| **P2** | hyper/h2协议转换 | 搜索 `h2::.*h1\|http2.*http1`，检查转换逻辑 |
| **P2** | 原始请求解析 | 搜索 `lines\|split.*":".*header`，评估解析安全性 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 仅使用http crate的HeaderMap | 快速跳过，自动规范化 |
| **L1** | 使用axum/actix-web框架默认处理 | 关键词扫描确认无手动处理 |
| **L2** | 存在字符串形式头操作 | 跳读检查大小写处理 |
| **L3** | 自定义头解析或规范化 | 逐行审计处理逻辑 |
| **L4** | HTTP/2代理或协议转换 | 跨模块追踪转换全流程 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 存在手动字符串形式的头处理
2. 使用大小写敏感比较或自定义规范化
3. 安全功能依赖该头检查

### 典型漏洞特征（满足任一项即确认）
- ✗ `headers.contains("Content-Type")` 字符串匹配
- ✗ `if name == "X-Forwarded-For"` 大小写敏感比较
- ✗ 自定义`to_uppercase()`规范化而非使用HeaderName
- ✗ HTTP/2伪头与Host头处理不一致

### 安全排除（任一项充分）
- ✓ 使用`http::HeaderMap`和`HeaderName`（自动小写化）
- ✓ 使用框架提供的头访问方法（axum/actix-web）
- ✓ 所有字符串比较使用`eq_ignore_ascii_case()`
- ✓ 仅HTTP/1.1环境，无HTTP/2支持

### 灰色判定（风险较低但需注意）
- 仅内部服务通信
- 大小写差异仅影响非安全功能
- 使用第三方库但版本不确定

---

## 审计专业技巧

### 真实漏洞vs误报区分指南

#### 常见误报案例1：业务字段非HTTP头
```rust
// ✓ 误报风险：这不是真正的HTTP头处理
struct UserProfile {
    content_type: String,  // 业务数据字段，非HTTP头
}

fn validate_user(profile: &UserProfile) -> bool {
    // 即使大小写敏感也无安全风险
    profile.content_type == "application/json"
}
```
**区分要点**：检查数据来源是否真实来自HTTP请求头。若是JSON/配置数据，则无漏洞。

#### 常见误报案例2：框架自动规范化
```rust
// ✓ 误报风险：actix-web已自动处理
use actix_web::HttpRequest;

async fn handler(req: HttpRequest) -> String {
    // 获取头后，actix已自动小写化为"content-type"
    let ct = req.headers().get("Content-Type");
    format!("{:?}", ct)
}
```
**区分要点**：验证是否使用了框架提供的自动提取器。查看`HttpRequest::headers()`的实现版本。

#### 常见误报案例3：调试或日志代码
```rust
// ✓ 误报风险：仅用于输出展示，不影响安全决策
fn log_headers(headers: &HeaderMap) {
    for (name, value) in headers.iter() {
        // 原始头信息打印，大小写不一致仅影响日志格式
        println!("{}: {}", name, value);
    }
}
```
**区分要点**：确认代码是否用于安全决策还是仅用于输出。搜索该数据是否在条件判断中使用。

### 真实漏洞的深层特征

#### 特征1：跨协议转换的规范化不一致
```rust
// ✗ 真实漏洞：HTTP/1.1到HTTP/2转换
fn convert_h1_to_h2(h1_headers: &str) -> Vec<(String, String)> {
    let mut h2_headers = Vec::new();

    for line in h1_headers.lines() {
        let (name, value) = parse_header_line(line)?;
        // 致命错误：未转换为小写
        h2_headers.push((name.to_string(), value));
    }

    h2_headers
}

fn validate_sensitive_header(headers: &[(String, String)]) {
    // 安全检查依赖小写头名称
    for (name, _) in headers {
        if name == "x-api-key" {  // HTTP/2必须小写
            // 但上面的转换没有小写化，导致检查失效
        }
    }
}
```
**识别方法**：跟踪HTTP/2请求的完整链路，查看转换点是否遗漏了规范化。

#### 特征2：黑名单绕过的确切场景
```rust
// ✗ 真实漏洞：反向代理身份验证绕过
async fn reverse_proxy(req: Request<Body>) -> Result<Response<Body>, Error> {
    let blocked_headers = vec!["X-Forwarded-For", "X-Real-IP"];

    for header in blocked_headers {
        req.headers_mut().remove(header);  // 大小写敏感remove
    }

    // 发送到内部服务 - 但"x-forwarded-for"（小写）仍存在!
    forward_request(req).await
}
```
**识别方法**：测试用小写头名称是否绕过移除逻辑。通过HTTP/2客户端发送`x-forwarded-for`。

### 审计现场技巧

#### 技巧1：快速定位关键代码
```bash
# 1. 查找HTTP/2相关导入
grep -r "use h2\|use hyper.*h2\|http2" .

# 2. 查找疑似手动头处理
grep -r "headers\.get\|contains.*:\|split.*:" . | grep -v "HeaderMap\|HeaderName"

# 3. 查找大小写操作
grep -r "to_uppercase\|to_lowercase" . | grep -i header

# 4. 查找黑名单白名单
grep -r "blocked\|allowed.*header\|filter.*header" .
```

#### 技巧2：判断黑名单风险等级
- **P0**（立即报告）：黑名单用于安全隔离（如移除代理头）且大小写敏感
- **P1**（风险）：黑名单用于协议转换点
- **P2**（信息）：黑名单仅用于日志过滤

#### 技巧3：验证HTTP/2支持
```bash
# 查找h2使用
grep -r "\"h2\"\|h2::" Cargo.toml

# 查找hyper HTTP/2支持
grep -r "hyper.*features.*http2" Cargo.toml
```

#### 技巧4：确认框架版本的安全性
```bash
# 验证axum是否已修复已知问题
grep "axum =" Cargo.lock | head -1

# 查询框架changelog中的HTTP/2相关修复
```

### 常见审计陷阱

| 陷阱 | 表现 | 应对方法 |
|------|------|---------|
| **误报过度** | 任何头处理都标记为漏洞 | 验证是否真实来自HTTP请求 |
| **忽视业务逻辑** | 不考虑头用途直接报告 | 追踪数据流到安全决策点 |
| **版本遗漏** | 使用旧版本已知漏洞库 | 检查Cargo.lock中的确切版本 |
| **跨文件遗漏** | 仅检查单个文件 | 追踪请求处理的完整链路 |
| **协议假设错误** | 假设仅支持HTTP/1.1 | 检查Cargo.toml和特性标志 |

---

## 实现建议

### 核心防护方案

**方案1：使用http crate类型**
```rust
use http::header::{HeaderMap, HeaderName, HeaderValue};

fn get_header(headers: &HeaderMap, name: &str) -> Option<&str> {
    // HeaderName自动小写化
    let key = HeaderName::from_bytes(name.as_bytes()).ok()?;
    headers.get(&key)?.to_str().ok()
}
```

**方案2：大小写不敏感比较**
```rust
fn is_blocked_header(name: &str) -> bool {
    let blocked = ["x-forwarded-for", "x-real-ip", "x-forwarded-host"];
    blocked.iter().any(|b| name.eq_ignore_ascii_case(b))
}
```

**方案3：安全的HTTP/2处理**
```rust
use axum::extract::Host;

async fn handler(Host(host): Host) -> impl IntoResponse {
    // axum自动从:authority或Host提取，处理优先级正确
    format!("Host: {}", host)
}
```

### 检查清单
- [ ] 使用`HeaderMap`和`HeaderName`而非手动字符串处理
- [ ] 黑名单/白名单使用小写形式或`eq_ignore_ascii_case`
- [ ] HTTP/2伪头优先于Host头
- [ ] 框架提取器正确处理协议差异
- [ ] 测试HTTP/2请求的小写头绕过

---

## 修复优先级

1. **立即修复**：安全检查使用大小写敏感字符串比较
2. **本周修复**：统一使用http crate类型处理头
3. **可选加强**：添加HTTP/2协议转换测试
4. **长期优化**：使用框架提供的安全抽象
