# Go 登录重定向未验证漏洞

登录认证成功后，应用将用户重定向到 `return_url` 参数指定的地址，但未对目标域名进行有效校验。攻击者可利用此漏洞将已认证用户重定向至恶意网站，用于窃取敏感信息、注入恶意内容或进行钓鱼攻击。此类漏洞特别危险，因为用户已完成身份验证，信任度高。

## Details

### 代码示例

```go
// 漏洞代码：登录成功后直接使用参数进行重定向
func LoginHandler(w http.ResponseWriter, r *http.Request) {
    username := r.FormValue("username")
    password := r.FormValue("password")

    // 验证用户凭证
    if validateCredentials(username, password) {
        returnURL := r.FormValue("return_url")
        // 直接使用未校验的用户输入
        http.Redirect(w, r, returnURL, http.StatusFound)
        return
    }

    http.Redirect(w, r, "/login", http.StatusFound)
}

// 调用示例
// POST /login with return_url=https://evil.com/steal_session
```

**快速定位到核心操作的技巧** `(L1:关键词扫描)`
- 搜索关键词：`http.Redirect()`、`w.Header().Set("Location")`、`r.FormValue()`、`r.URL.Query()`
- 重点关注：认证成功分支中的重定向调用
- 识别模式：登录验证成功后立即重定向至用户可控参数（`return_url`、`redirect_to`、`next`、`callback`）
- 追踪输入源：从表单、查询参数、Cookie中获取重定向URL的代码路径

**快速定位到保护机制的技巧** `(L2:跳读)`
- 在 `http.Redirect()` 调用前搜索URL验证函数的存在性
- 识别验证模式：
  - URL解析步骤：`url.Parse(returnURL)` 的结果是否被检查
  - 协议白名单：是否显式限制 `https://` 或 `http://`
  - 域名白名单：是否与配置的允许域名列表进行对比（使用 `parsedURL.Host`）
  - 路径检查：是否禁止 `//`、`///` 等特殊序列
  - 编码检查：是否处理URL编码绕过（如 `%2f%2f` 代表 `//`）
- 检查验证结果使用情况：验证通过后是否使用了验证结果而非原始输入
- 查阅中间件或辅助函数：是否存在统一的 URL 验证库函数
- 跳读逻辑边界：验证函数中的条件判断是否完整覆盖所有规避手段

## Classify

从漏洞成因分类标准：

**真实漏洞的判断依据**
- 登录认证后，重定向URL完全来自 `FormValue()`、`URL.Query()`、`Header()` 等用户可控源，无任何验证
- 验证存在但可被绕过：
  - 仅检查前缀（如 `strings.HasPrefix(url, "/")`），未防止 `//evil.com` 的双斜杠绕过
  - 协议检查不严格，允许 `javascript:`、`data:` 等特殊协议
  - 白名单检查使用 `strings.Contains()` 而非完整的 URL 解析与 `Host` 字段比对
  - 相对路径验证中未考虑 `//` 前缀（被解析为协议相对URL）
  - URL验证函数存在但验证后仍使用原始输入变量
- 认证逻辑与重定向逻辑之间无依赖关系验证

**误报的特征**
- 重定向URL来自服务端配置文件或数据库，不受用户输入影响
- 仅允许相对路径重定向（如 `/dashboard`、`/profile`），绝对无法指定外部域名
- `return_url` 参数虽存在但被完整的白名单机制保护（如查表操作）
- 登录失败时不进行任何重定向，参数仅在非认证路径使用

**代码异味的表现**
- URL验证函数存在但逻辑不完整或未考虑全部绕过方式
- 存在多个重定向点，部分受保护，部分不受保护
- 有过时的验证方式（如简单的前缀检查），虽未成为严重漏洞但不符合最佳实践
- 使用了自定义验证函数且实现方式存在明显缺陷（如未处理编码）

## Low risk

低风险情况的评级标准：

**协议和域名的严格限制**
- 代码明确限制仅允许 `https://` 协议，例如：`if !strings.HasPrefix(returnURL, "https://")` 或 `parsedURL.Scheme != "https"`
- 已实现完整的域名白名单验证，使用 `url.Parse()` 解析后，通过 `parsedURL.Host` 与白名单进行精确对比
- 子域名处理正确（如 `.example.com` 匹配 `sub.example.com` 但不匹配 `evilexample.com`）

**防御性输入处理**
- 用户输入为空值时默认重定向至安全页面（如首页 `/` 或个人中心），存在显式的空值检查逻辑
- 使用 `url.Parse()` 进行强制解析，解析失败时拒绝重定向

**相对路径的强制使用**
- 代码强制要求 `return_url` 为相对路径，通过前缀检查 `!strings.HasPrefix(returnURL, "/")` 来验证
- 使用正则表达式进行路径格式限制，如 `^/[a-zA-Z0-9/_-]+$`，禁止 `://`、`//` 等特殊序列
- 若允许查询参数，确保参数值本身也经过了编码验证

**会话与令牌绑定**
- 使用签名的重定向令牌机制，例如服务端生成一次性令牌存储在 Session 中，而非直接使用用户输入
- 重定向前验证令牌有效性，确保 URL 来自服务端生成

**框架级安全措施**
- 使用成熟的 Go URL 验证库（如 Go 标准库 `url.Parse()` + 自定义约束）
- 在统一的中间件或通用函数中实现验证逻辑，所有登录成功重定向均通过此函数处理
- 有明确的代码注释说明验证策略，便于维护和审计
