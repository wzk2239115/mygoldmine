# Rust Location 头重定向未验证

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `HttpResponse::Found().insert_header(("Location", url))` 重定向
- `web::HttpResponse::SeeOther()` 等
- 使用 `actix_web::http::StatusCode::MOVED_PERMANENTLY` 等重定向状态码

**快速定位核心操作：**
1. 搜索关键字：`Location`、`Found`、`Redirect`、重定向状态码
2. 追踪 URL 来源：`web::Query`、`web::Form`、参数
3. 检查是否存在 URL 验证
4. 检查是否限制域名和协议

**快速定位保护机制：**
- URL 解析验证：`url::Url::parse()` 检查
- 域名限制：比较 `host()` 部分
- 协议限制：仅允许 `http` 和 `https`
- 相对 URL：检查 `!url.starts_with("http")`

**代码示例：**
```rust
// 危险：用户 URL 直接重定向
async fn redirect(Query(params): Query<HashMap<String, String>>) -> impl Responder {
    let url = params.get("url").unwrap_or(&"/".to_string());
    HttpResponse::Found()
        .insert_header(("Location", url.as_str()))  // 危险
        .finish()
}

// 危险：Form 数据
async fn login(Form(data): Form<LoginData>) -> impl Responder {
    HttpResponse::Found()
        .insert_header(("Location", data.next.as_str()))  // 危险
        .finish()
}

// 危险：直接返回 URL
async fn jump(web::Path(dest): web::Path<String>) -> impl Responder {
    HttpResponse::MovedPermanently()
        .insert_header(("Location", dest.as_str()))  // 危险
        .finish()
}
```

## Classify

**漏洞（High）：**
- 用户输入直接重定向
- 无域名验证
- 允许开放重定向

**误报：**
- 重定向目标硬编码
- 框架验证已启用

**代码异味（Medium）：**
- 仅检查前缀
- 黑名单不完整
- 检查不完整

## Low risk

**以下情况评为低风险：**
- 重定向目标硬编码
- 严格白名单验证
- 仅允许相对 URL + 验证
- 管理员配置的 URL

## 审计专业技巧

### 1. 真实漏洞的特征识别

**典型真实漏洞场景：**
- `Location` 头完全由用户参数控制，无任何验证
- 参数来自 `Query`、`Form`、`Path`、`Json` 等外部输入
- 代码路径短，直接在处理器中设置 Header，无中间验证层
- 使用 `unwrap()` 或 `unwrap_or_default()` 处理用户输入

**高危红点：**
- `params.get("url").unwrap()` + `insert_header(("Location", ...))`
- `Form` 数据中存在 URL 字段直接用于重定向
- `Path` 参数直接作为重定向 URL
- 无 `url::Url::parse()` 验证或验证存在绕过

### 2. 真实漏洞与误报的区分经验

**真实漏洞的确认步骤：**
1. **输入来源检查**：确认数据确实来自用户可控输入
   - 本地配置文件 = 低风险
   - 环境变量 = 通常低风险（除非环境本身可控）
   - HTTP 请求参数 = 高风险

2. **验证完整性评估**：
   - 检查是否存在 `url::Url::parse()` 且确实检查了 host
   - 检查是否有硬编码白名单或动态白名单
   - 检查黑名单时，验证是否遗漏了 `//`、`///`、协议混淆等

3. **常见误报场景**：
   - Location 来自 User-Agent 或其他 HTTP 请求头 = 误报（Location 必须是 URL）
   - Location 值被 encode/decode = 需要追踪处理方式
   - Location 前面添加了 `/` = 可能是相对 URL 保护
   - Status code 是 `200` 而非 3xx = 误报（非重定向）

### 3. 常见绕过手法的识别

**黑名单绕过示例：**
```rust
// 误：仅检查前缀
if !url.starts_with("http://attacker.com") {
    // 绕过：http://attacker.com.legitimate.com
}

// 误：不完整的协议检查
if !url.starts_with("javascript:") && !url.starts_with("data:") {
    // 绕过：JaVaScript:, JAVASCRIPT:
}

// 误：使用 contains
if url.contains("attacker.com") {
    // 绕过：http://example.com/attacker.com/../real-attacker.com
}
```

**正确的验证方式：**
```rust
// 正确：使用 URL 解析
if let Ok(parsed) = url::Url::parse(&url) {
    if let Some(host) = parsed.host() {
        let allowed = ["example.com", "sub.example.com"];
        if allowed.contains(&host.to_string().as_str()) {
            // 允许
        }
    }
}

// 正确：仅允许相对 URL
if !url.starts_with("http://") && !url.starts_with("https://") && !url.starts_with("//") {
    // 相对 URL 安全
}
```

### 4. 审计步骤

**第一步 - 快速定位：**
- 搜索 `insert_header(("Location"` 或 `header("Location"`
- 搜索重定向相关关键词：`Found`, `Redirect`, `MovedPermanently`

**第二步 - 追踪输入源：**
- 确认 Location 值是否来自 Query、Form、Path、Json 等用户输入
- 查看参数的默认值（`unwrap_or` 的参数）

**第三步 - 检查验证：**
- 查看 Location 值设置前是否存在验证逻辑
- 在中间件或守卫中查找验证代码
- 检查是否使用了 URL 解析库的检查

**第四步 - 确认漏洞级别：**
- 无验证 = High（确认）
- 有验证但存在绕过 = Medium（需要验证绕过方式）
- 验证完整 = 低风险或误报

### 5. 审计清单

- [ ] 确认 Location 值完全来自用户输入
- [ ] 确认没有 URL 解析和白名单验证
- [ ] 确认没有协议限制（仅允许 http/https）
- [ ] 确认没有域名白名单检查
- [ ] 尝试用 Burp Suite 手动测试是否能重定向到外部域名
- [ ] 检查是否存在 URL 编码绕过（%2F、双编码）
- [ ] 检查 CRLF 注入可能性（`\r\n` 注入）
