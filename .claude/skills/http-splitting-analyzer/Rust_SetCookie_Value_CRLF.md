# Rust Set-Cookie 值 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `response.insert_header(("Set-Cookie", value))` 直接设置
- Cookie 中间件使用的值包含用户输入
- `HttpResponse.cookie()` 等方法

**快速定位核心操作：**
1. 搜索关键字：`Set-Cookie`、`insert_header`、`cookie()`
2. 追踪 Cookie 值来源：`web::Query`、`web::Form`、会话数据
3. 检查是否存在 CRLF 过滤
4. 追踪 Cookie 构造过程

**快速定位保护机制：**
- 值检查：`if value.contains('
') || value.contains('
')`
- 白名单验证：`regex` 或字符集检查
- URL 编码：使用标准编码库
- 框架防护：某些框架自动处理

**代码示例：**
```rust
// 危险：用户输入直接设置 Cookie
async fn set_cookie(Query(params): Query<HashMap<String, String>>) -> impl Responder {
    let token = params.get("token").unwrap_or(&String::new());
    HttpResponse::Ok()
        .insert_header(("Set-Cookie", token.as_str()))  // 危险
        .finish()
}

// 危险：Form 数据
async fn auth(Form(data): Form<AuthData>) -> impl Responder {
    HttpResponse::Ok()
        .insert_header(("Set-Cookie", data.auth.as_str()))  // 危险
        .finish()
}

// 危险：请求头转发
async fn forward(req: HttpRequest) -> impl Responder {
    if let Some(header) = req.headers().get("X-Token") {
        let val = header.to_str().unwrap_or("");
        HttpResponse::Ok()
            .insert_header(("Set-Cookie", val))  // 危险
            .finish()
    } else {
        HttpResponse::BadRequest().finish()
    }
}
```

## Classify

**漏洞（Critical）：**
- 用户输入直接用于 Cookie 值
- 无 CRLF 过滤
- 导致响应分割

**误报：**
- Cookie 值硬编码
- 系统生成的值
- 框架管理

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接拼接

## Skill

### 审计专业技巧

#### 1. 数据流追踪技巧
**关键问题：识别边界数据源**
- 追踪用户输入的全路径：从 HTTP 请求 → 中间件 → 业务逻辑 → 响应
- 注意隐蔽的用户输入来源：
  - 请求头转发（X-Forwarded-* 等）
  - Cookie 读取后再写入
  - 从数据库读取后直接用于响应（需检查数据库中的数据来源）
  - URL 路径参数、查询参数、JSON 请求体

**实战例子：**
```rust
// 隐蔽漏洞：从数据库读取后直接设置
async fn login(req: LoginReq) -> impl Responder {
    let user = db.find_user(&req.username).await;
    HttpResponse::Ok()
        .insert_header(("Set-Cookie", user.session_id.as_str()))  // 看起来安全，但session_id可能来自用户输入
        .finish()
}
```

#### 2. CRLF 过滤检查清单
**完整性验证（容易遗漏的情况）：**
- `\r\n` 被过滤，但 `\n` 没有（可能仍可分割响应）
- `\r\n` 被转义，但原始字符被编码（`%0d%0a` 需要提前解码）
- 过滤发生在编码后（晚于用户输入）
- 仅过滤特定位置（如 Cookie 名称被过滤，但值没有）

**代码检查要点：**
```rust
// 不完整过滤：仅过滤 \r\n，未考虑 \r 或 \n
if value.contains("\r\n") {
    return Err("Invalid");  // 弱点：可用 \n 或 \r 分割
}

// 正确做法：验证白名单或完整过滤
if value.contains('\r') || value.contains('\n') || value.contains('\0') {
    return Err("Invalid");
}

// 最佳实践：使用标准库或已验证的 cookie 库
use http::HeaderValue;
HeaderValue::from_str(value)?;  // 会验证字符有效性
```

#### 3. 真实漏洞 vs 误报的区分经验

**真实漏洞的特征（High Confidence）：**
1. **直接拼接且无验证**
   - 用户输入直接进入 Set-Cookie 的值部分
   - 代码路径中没有任何过滤或验证
   - 可以通过 Payload 如 `\r\nSet-Cookie: admin=true` 来验证

2. **框架漏洞而非应用漏洞**
   - Actix-web 早期版本 (< 3.x) 中 `insert_header` 不验证
   - 检查项目的 Cargo.toml 中框架版本
   - 即使代码安全，框架本身有漏洞也需要报告

3. **双重编码场景**
   - 用户输入 → 数据库（已编码）→  读取后直接使用（未解码）
   - 虽然是编码状态，但可能被中间件或浏览器解码后产生漏洞

**误报的特征（Low Risk/False Positive）：**
1. **受信任源的数据**
   ```rust
   // 误报：从配置文件读取
   let cookie_val = config.get("session_cookie").unwrap();
   response.insert_header(("Set-Cookie", cookie_val));

   // 误报：系统生成的随机值（假设 random() 实现正确）
   let session_id = format!("sess_{}", random_uuid());
   response.insert_header(("Set-Cookie", session_id));
   ```

2. **框架自动处理**
   ```rust
   // 安全：使用框架提供的 cookie builder
   response.cookie(
       cookie::Cookie::new("session", session_id)
           .http_only(true)
           .secure(true)
   );

   // 安全：框架的 insert_header 在某些版本会自动验证
   response.insert_header(("Set-Cookie", secure_value));  // 需确认版本
   ```

3. **明确的白名单验证**
   ```rust
   // 低风险：明确的白名单
   if !value.chars().all(|c| c.is_alphanumeric() || c == '-' || c == '_') {
       return Err("Invalid");
   }
   response.insert_header(("Set-Cookie", value));
   ```

#### 4. 高级审计检查点

**多层次防御评估：**
- 一层防御存在但不完整：标记为 Medium
- 多层防御的第一层被绕过：标记为 Medium（后续层可能拦截）
- 所有防御层都失效才能到达最终响应：标记为 Critical

**实际案例分析：**
```rust
// Case 1: 多层防御，但第一层有绕过
fn set_cookie_case1(input: String) -> Result<HttpResponse, Error> {
    // 防御1：前端验证（客户端可绕过）
    let sanitized = input.replace("\r\n", "");  // 不完整

    // 防御2：数据库存储
    db.save(&sanitized).await?;

    // 防御3：读取时再过滤
    let value = db.load(id).await?;
    if !value.contains('\n') {
        response.insert_header(("Set-Cookie", &value));  // 仍可通过 \r 注入
    }
    Ok(response)
}
// 评级：Medium - 多层防御但有绕过

// Case 2: 完整验证的白名单
fn set_cookie_case2(input: String) -> Result<HttpResponse, Error> {
    if !input.chars().all(|c| matches!(c, 'a'..='z' | 'A'..='Z' | '0'..='9' | '-' | '_' | '.')) {
        return Err(Error::InvalidInput);
    }
    response.insert_header(("Set-Cookie", &input));
    Ok(response)
}
// 评级：Low - 严格白名单，且白名单集合安全
```

#### 5. 常见审计误区

**误区1：编码≠保护**
- Base64 编码后的值仍可能被 URL 解码或其他方式利用
- 需要验证编码方案是否能阻止 CRLF 字节的存在

**误区2：过滤位置检查**
- Cookie 值被过滤，但名称没有：`\r\nSet-Cookie: attacker=123`
- 需要检查整个 `Set-Cookie: name=value` 字符串

**误区3：框架版本盲区**
- 同一框架不同版本防护差异大
- 必须交叉检查：代码逻辑 + Cargo.lock 版本 + 框架 changelog

**误区4：间接用户输入的忽视**
- 从 Redis/缓存读取的值也是用户输入
- HTTP 请求头转发（如从客户端转发到另一个请求）也是用户输入

## Low risk

**以下情况评为低风险：**
- Cookie 值硬编码
- 严格 CRLF 过滤（包括 `\r`、`\n`、`\0`）
- 完整的字符集白名单验证
- 内部来源且已在入口验证
- 框架库提供的安全 cookie 接口
