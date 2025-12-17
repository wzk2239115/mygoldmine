# Rust OAuth 回调处理中 redirect_uri 验证不足

## Details

### 漏洞成因

Rust OAuth2 流程中，客户端应用在接收授权服务器的回调时，应验证 `redirect_uri` 参数与预注册值的严格匹配。常见不足包括：

1. **缺少回调 URI 白名单验证** - 未验证回调地址是否在预注册列表中
2. **URL 解析差异** - 利用 URL 标准化差异（端口、编码、路径遍历等）绕过验证
3. **协议验证缺失** - 允许 HTTP 代替 HTTPS，或对协议转换的处理不当
4. **主机名验证不当** - 子域名、IP 地址、通配符处理的逻辑漏洞

### 核心操作定位

```rust
// 典型的 OAuth 回调处理
#[get("/oauth/callback?code=<code>&state=<state>")]
fn oauth_callback(code: String, state: String, req: Request) -> Result<Redirect, Status> {
    // ❌ 风险位置：redirect_uri 的验证逻辑
    let redirect_uri = req.uri().to_string();  // 或从请求头获取

    // ⚠️ 审计焦点：这里是否进行了严格的白名单验证？
    validate_redirect_uri(&redirect_uri)?;

    // 后续的令牌交换
    let token = exchange_code(&code, &redirect_uri).await?;
    Ok(Redirect::to(token.user_info))
}
```

**关键审计技巧** **(L1 - 关键词扫描)**
- 搜索关键词：`redirect_uri`, `callback`, `location`, `Redirect`, `validate_uri`
- 跟踪处理回调的路由定义和中间件逻辑
- 查找是否存在预注册的 URI 白名单（常见位置：配置文件、数据库、环境变量）

### 保护机制定位

```rust
// ✅ 正确的验证示例（审计时应查找类似逻辑）
lazy_static::lazy_static! {
    static ref ALLOWED_REDIRECTS: Vec<&'static str> = vec![
        "https://app.example.com/oauth/callback",
        "https://app.example.com/auth/callback",
    ];
}

fn validate_redirect_uri(uri: &str) -> Result<(), OAuthError> {
    // 1. 解析 URL 确保格式正确
    let parsed = url::Url::parse(uri)
        .map_err(|_| OAuthError::InvalidUri)?;

    // 2. 强制 HTTPS（开发环境可放宽）
    if parsed.scheme() != "https" && !cfg!(debug_assertions) {
        return Err(OAuthError::InsecureScheme);
    }

    // 3. 精确白名单匹配
    let canonical = format!("{}://{}{}", parsed.scheme(), parsed.host_str().unwrap_or(""), parsed.path());
    if !ALLOWED_REDIRECTS.contains(&canonical.as_str()) {
        return Err(OAuthError::UnauthorizedRedirect);
    }

    // 4. 禁止查询参数篡改（重要）
    if !parsed.query().is_none() {
        return Err(OAuthError::QueryParamsNotAllowed);
    }

    Ok(())
}
```

**保护机制审计技巧** **(L3 - 逐行读)**
- 确认白名单存储位置和加载机制的安全性
- 验证 URL 解析库的使用（推荐 `url` crate 而非字符串处理）
- 检查是否对 `scheme`, `host`, `path` 进行了分离验证
- 确认是否禁止了查询参数、URL 片段的动态追加
- 追踪是否有 DNS rebinding 防护（对动态生成的 URI）

## Classify

### 漏洞 vs 误报 vs 代码异味

**判定为漏洞的依据：**
- 回调 URI 参数**完全未经验证**（接收任意值）
- 白名单存在但使用了前缀匹配、后缀匹配、正则表达式，导致可绕过
- 允许将 HTTP 用于生产环境的回调地址
- 使用了字符串拼接而非 URL 库进行 URI 解析和比对
- 允许在重定向 URI 中追加查询参数（如 `registered_uri?user=attacker`）
- 支持通配符或主机名范围验证（如 `*.example.com`），但未防止子域接管

**判定为代码异味的情况：**
- 验证逻辑存在但不够严格（如仅检查前缀）
- 白名单存储方式不当但已通过其他安全控制弥补
- 允许 localhost 或 127.0.0.1 的回调，但仅在开发环境

**判定为误报的情况：**
- 使用了成熟的 OAuth2 库（如 `openidconnect` crate），且库本身进行了验证
- 回调地址由认证服务器（而非客户端）决定并验证
- 系统架构中通过反向代理、WAF 等防护层进行了 URI 验证

## Low risk

### 低风险评级的情况

1. **完全受信的部署环境**
   - 所有回调 URI 均为内部服务地址（如专网、VPC 内部）
   - 网络已通过防火墙、ACL 等措施隔离，外部无法访问到这些地址

2. **使用官方 OAuth2 库且配置正确**
   - 依赖权威库实现（`openidconnect`, `actix-web` 官方 OAuth 中间件等）
   - 库的版本无已知 CVE，且配置中显式启用了 URI 验证

3. **状态参数防护充分**
   - 虽然 URI 验证不够严格，但通过加密/签名状态参数防止 CSRF
   - 状态参数验证逻辑正确，攻击者无法伪造有效状态（此时重定向 URI 宽松的危害降低）

4. **受害面受限**
   - 仅允许回调到 localhost 或预留的本地端口
   - 即使攻击者可以接收回调，也因网络隔离而无法获取授权码

5. **授权码短生命周期 + 其他防护**
   - 授权码极短生命周期（< 1 分钟）
   - 且实现了 PKCE 验证，attacker 无法单独利用授权码换取令牌
