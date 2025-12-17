# Rust Rocket Framework - Unvalidated Redirect::to()

## Details

### 核心漏洞代码示例

**易受攻击的模式：**

```rust
use rocket::{State, get, Redirect};

#[get("/redirect?target=<url>")]
fn redirect_unvalidated(url: String) -> Redirect {
    // ⚠️ 直接使用用户输入构造重定向 URL
    Redirect::to(url)
}

#[post("/oauth/callback?state=<state>&redirect_uri=<uri>")]
fn oauth_callback(state: String, uri: String) -> Redirect {
    // ⚠️ OAuth 重定向开放漏洞
    Redirect::to(uri)
}

#[get("/app/return?next=<page>")]
fn app_redirect(page: String) -> Redirect {
    // ⚠️ 无谓检查的页面跳转
    Redirect::to(format!("{}", page))
}
```

**快速定位核心操作的审计技巧** `[L1: 关键词扫描]`

- 扫描 `Redirect::to()` 或 `Redirect::found()` 方法调用
- 搜索参数直接传入重定向方法的代码行
- 识别模式：`Redirect::to(<user_param>)` 或 `Redirect::to(format!("{}", <user_param>))`
- 检查路由处理器签名中的 `String` 或 `&str` 参数是否直接用于重定向
- 关键词组合：`Redirect` + `get("/")` + 路由参数

**快速定位保护机制的审计技巧** `[L2: 跳读]`

- 检查是否存在白名单验证函数（如 `is_allowed_redirect()`、`validate_url()` 等）
- 扫描 `http://` 或 `https://` 的协议验证逻辑
- 查找 URI 解析库的导入（`url` crate、`http` crate）
- 检查是否对重定向目标进行了 `allow_list` 或 `deny_list` 比对
- 验证是否限制了协议类型（`scheme` 检查）
- 查看是否使用了正则表达式或路径前缀验证

### 漏洞触发机制

Rocket 框架的 `Redirect` 类型允许开发者通过 `to()` 方法返回任意 URL。当用户输入直接作为重定向目标传入时，攻击者可以：

1. **完全控制目标 URL**：通过 `?target=https://attacker.com` 跳转到恶意网站
2. **协议注入**：使用 `javascript:`、`data:` 等协议执行脚本（在某些浏览器行为下）
3. **同源策略绕过**：利用相对路径实现类似行为
4. **信息泄露**：利用有效的重定向作为有效性检测工具

### 核心问题

- 路由参数和查询参数直接传递到 `Redirect::to()`
- 缺少对目标 URL 来源的验证（未检查是否属于应用域）
- 没有实施白名单机制
- 对重定向协议类型无限制

---

## Classify

### 漏洞研判流程

**第一阶段：代码存在性判定**

1. 确认是否使用了 `Redirect::to()` 或相关重定向方法
2. 验证重定向目标是否来自用户可控输入
3. 判断输入来源：路由参数、查询参数、POST 数据、请求头等

**第二阶段：保护机制分析**

1. **URL 验证存在性**：是否在重定向前对 URL 进行了验证
2. **验证强度评估**：
   - 仅检查协议是否为 `http://https://` ➜ **弱验证**（可被绕过）
   - 检查域名前缀（如 `starts_with("https://example.com")`）➜ **中等验证**（仍可被绕过，如 `https://example.com.attacker.com`）
   - 使用 `url` crate 完整解析 + 白名单验证 ➜ **强验证**
   - 使用相对路径 + 服务端绝对路径映射 ➜ **最强**

3. **验证机制的准确性**：
   - 检查是否存在 TOCTOU（Time-of-Check-Time-of-Use）竞态条件
   - 验证逻辑是否覆盖所有代码路径（特别是错误处理分支）
   - 检查是否正确处理了 URL 编码、双重编码、Unicode 等绕过向量

**第三阶段：上下文风险评估**

- **高风险上下文**：OAuth 回调、支付回调、会话恢复链接、敏感操作确认
- **中风险上下文**：一般页面跳转、帮助文档链接
- **低风险上下文**：已加密的一次性令牌内容、受信任输入源

**归类决策矩阵**

| 输入验证 | 保护机制 | 上下文敏感度 | 归类 |
|---------|---------|-----------|------|
| 是 | 完整白名单 | 任意 | 误报/代码异味 |
| 是 | 弱验证（仅协议检查） | 高敏感 | 漏洞 |
| 是 | 弱验证 | 低敏感 | 代码异味 |
| 否 | - | 高敏感 | 严重漏洞 |
| 否 | - | 低敏感 | 中等漏洞 |

### 误报消除准则

- ✓ 使用了 `url` crate 完整解析后的白名单验证
- ✓ 将用户输入映射到预定义的安全 URL 列表
- ✓ 使用了相对路径且确保无法逃出应用范围
- ✓ 重定向目标完全由服务器逻辑决定（用户输入仅用于索引）

### 代码异味识别

- 已实现基本的协议检查（仅 `http://https://`）但未验证域名
- 使用了 URL 白名单但机制不完整（如未考虑子域名问题）
- 对同站重定向（如 `/page` 路径）的验证不足
- 存在硬编码的"特殊处理"逻辑而非统一的验证框架

---

## Low risk

### 低风险场景评级标准

**1. 完整的白名单机制**

```rust
const ALLOWED_HOSTS: &[&str] = &["example.com", "app.example.com"];

fn validate_redirect(url: &str) -> Result<String, Error> {
    let parsed = Url::parse(url)?;
    let host = parsed.host_str().ok_or(Error::InvalidUrl)?;
    if ALLOWED_HOSTS.contains(&host) {
        Ok(url.to_string())
    } else {
        Err(Error::UnallowedHost)
    }
}
```

评级理由：通过显式的白名单验证，完全限制了重定向的目标范围。

**2. 相对路径重定向**

```rust
#[get("/page/<section>")]
fn navigate(section: String) -> Result<Redirect, Error> {
    // 限制为特定的页面列表
    let valid_sections = ["home", "about", "contact"];
    if valid_sections.contains(&section.as_str()) {
        Ok(Redirect::to(format!("/{}", section)))
    } else {
        Err(Error::InvalidSection)
    }
}
```

评级理由：使用相对路径且通过白名单限制，无法指向外部域。

**3. 索引映射方案**

```rust
let redirects: HashMap<&str, &str> = [
    ("flow1", "/checkout"),
    ("flow2", "/dashboard"),
].iter().cloned().collect();

#[get("/redirect?flow=<flow_id>")]
fn indexed_redirect(flow_id: String) -> Result<Redirect, Error> {
    let target = redirects.get(flow_id.as_str())
        .ok_or(Error::InvalidFlow)?;
    Ok(Redirect::to(target.to_string()))
}
```

评级理由：用户输入仅作为预定义映射表的键，无法注入任意 URL。

**4. 完整的 URL 验证**

```rust
use url::Url;

fn is_safe_redirect(target: &str) -> bool {
    // 解析 URL
    let url = match Url::parse(target) {
        Ok(u) => u,
        Err(_) => return false,
    };

    // 仅允许 http/https，且仅限定域名
    match url.scheme() {
        "http" | "https" => {},
        _ => return false,
    }

    match url.host_str() {
        Some(host) => ALLOWED_HOSTS.contains(&host),
        None => false,
    }
}
```

评级理由：多层验证覆盖协议、域名和完整性检查，漏洞风险极低。

**5. 安全敏感度低的场景**

- **非认证流程**：公开页面的内容导航，跳转失败无严重后果
- **调试模式专用**：仅在开发环境启用的重定向，不存在于生产代码
- **受信任输入源**：来自数据库或配置文件的预配置 URL（非用户直接输入）
- **日志/分析链接**：重定向仅用于统计分析，无涉及认证或支付流程

---

## Key Audit Checkpoints

| 检查项 | 审计等级 | 关键问题 |
|-------|--------|--------|
| `Redirect::to()` 调用位置 | L1 | 是否直接使用了用户参数？ |
| 输入来源追踪 | L2 | 参数来自哪里？是否经过任何处理？ |
| 白名单存在性 | L2 | 是否定义了允许的重定向目标？ |
| 验证逻辑完整性 | L3 | 验证是否覆盖所有代码路径和绕过向量？ |
| 跨模块依赖 | L4 | 共享的验证函数是否在所有重定向点都被使用？ |
| 错误处理 | L3 | 验证失败时的处理是否安全？是否存在默认行为？ |
