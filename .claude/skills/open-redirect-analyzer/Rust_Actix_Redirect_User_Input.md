# Rust Actix 直接重定向用户输入

## Details

### 代码示例

典型的漏洞代码：

```rust
use actix_web::{web, HttpResponse, HttpRequest};

#[post("/redirect")]
async fn redirect_handler(req: HttpRequest, query: web::Query<std::collections::HashMap<String, String>>) -> HttpResponse {
    let redirect_url = query.get("url").cloned().unwrap_or_default();
    HttpResponse::Found()
        .append_header(("Location", redirect_url))
        .finish()
}
```

或使用 `HttpResponse::Redirect`：

```rust
#[get("/go")]
async fn go_handler(query: web::Query<std::collections::HashMap<String, String>>) -> HttpResponse {
    let target = query.get("target").cloned().unwrap_or("/");
    HttpResponse::TemporaryRedirect()
        .insert_header(("Location", target))
        .finish()
}
```

### 快速定位核心操作 **[L1: 关键词扫描]**

- 搜索关键字：`HttpResponse::Found()`, `HttpResponse::Redirect()`, `HttpResponse::TemporaryRedirect()`, `HttpResponse::PermanentRedirect()`
- 搜索 `Location` 头部的赋值：`append_header(("Location", ...))`, `insert_header(("Location", ...))`
- 搜索 HTTP 状态码 302, 301, 307, 308 的响应构造
- 追踪 URL 参数的直接使用：`query.get()`, `body`, `path param`，特别是参数未经验证直接用于重定向目标

### 快速定位保护机制 **[L2-L3: 跳读与逐行读]**

- 检查是否存在域名白名单验证（通常为 `Vec<&str>` 或 `HashSet<String>`）
- 寻找 URL 解析与验证逻辑：`url::Url::parse()`, 正则表达式校验，或 `starts_with()` 检查
- 关键保护代码示例：
  ```rust
  let allowed_hosts = vec!["example.com", "trusted.domain"];
  if let Ok(parsed_url) = url::Url::parse(&redirect_url) {
      if let Some(host) = parsed_url.host() {
          if !allowed_hosts.contains(&host.to_string().as_str()) {
              return HttpResponse::BadRequest().finish();
          }
      }
  }
  ```
- 检查是否进行了相对 URL 验证（检查 `/` 开头表示相对路径）
- 检查是否使用了成熟的 URL 验证库（如 `url` crate）

## Classify

### 判断标准

1. **确认为漏洞** (Vulnerability)
   - 用户可控的 URL 参数（query, path, body）被直接用作 HTTP 重定向目标
   - 无任何域名白名单、黑名单或 URL 格式验证
   - 无论使用何种 HTTP 状态码（301/302/307/308）均构成漏洞
   - 攻击者可通过链接注入恶意域名进行钓鱼攻击

2. **误报情况** (False Positive)
   - 重定向目标为硬编码字符串常量，不涉及用户输入
   - URL 参数经过严格的白名单验证（例如仅允许特定域名集合）
   - 使用了成熟的 URL 验证库且配置正确
   - 仅允许相对路径重定向（`starts_with("/")`）且框架未再解析为绝对路径

3. **代码异味** (Code Smell)
   - 部分验证逻辑不完整（例如只检查前缀但未防护 `//evil.com` 这类双斜杠绕过）
   - 白名单过于宽泛（如允许所有子域名但未限定二级域名）
   - 使用字符串匹配而非 URL 解析库进行验证
   - 注释中存在"TODO: 验证重定向目标"之类的标记

## Low risk

### 低风险评级情景

1. **受限的使用场景**
   - 重定向仅在内部管理后台使用，且访问受严格身份认证限制
   - 虽存在用户输入，但参数来自已认证用户的个人设置（如用户自设的返回页面）

2. **有效的保护机制存在**
   - 完整的白名单验证确保只能重定向到预定义的域名列表
   - 验证逻辑基于 URL 解析库而非字符串操作
   - 日志记录所有重定向行为，便于审计和检测异常

3. **降级因素**
   - 仅允许相对路径重定向（以 `/` 开头），且充分验证不会被绕过
   - 使用短期的一次性 token（CSRF token）绑定重定向链接，防止跨域利用
   - 实现浏览器端警告或二次确认机制
