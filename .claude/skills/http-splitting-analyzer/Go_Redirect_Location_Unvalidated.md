# Go 重定向 Location 头未验证

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `http.Redirect(w, r, url, code)` - 标准重定向
- `w.Header().Set("Location", url)` + `WriteHeader(code)`
- `http.Client` 的 CheckRedirect 回调

**快速定位核心操作：**
1. 搜索关键字：`http.Redirect`、`Location`、`WriteHeader(3`
2. 追踪 URL 来源：`Query().Get()`、`FormValue()`、`Header.Get()`
3. 检查是否存在 URL 验证
4. 查看 CheckRedirect 回调的实现

**快速定位保护机制：**
- URL 白名单：`if strings.HasPrefix(url, "https://trusted.com")`
- URL 解析验证：`url.Parse()` 检查 Host 和 Scheme
- 仅允许相对 URL：检查 `!strings.HasPrefix(url, "http")`
- 黑名单检查：禁止特定协议或域名

**代码示例：**
```go
// 危险：用户输入直接重定向
func redirect(w http.ResponseWriter, r *http.Request) {
    url := r.URL.Query().Get("url")
    http.Redirect(w, r, url, http.StatusFound)  // 危险：无验证
}

// 危险：Form 数据重定向
func submitForm(w http.ResponseWriter, r *http.Request) {
    target := r.FormValue("next")
    http.Redirect(w, r, target, http.StatusMovedPermanently)  // 危险
}

// 危险：直接设置 Location 头
func jump(w http.ResponseWriter, r *http.Request) {
    dest := r.Header.Get("X-Redirect-To")
    w.Header().Set("Location", dest)  // 危险
    w.WriteHeader(http.StatusMovedPermanently)
}
```

## Classify

**漏洞（High）：**
- 用户输入直接用于 Location 头
- 无域名验证
- 允许开放重定向

**误报：**
- 重定向目标硬编码
- 使用框架验证
- 仅允许相对 URL

**代码异味（Medium）：**
- 仅检查前缀
- 黑名单不完整
- 检查不完整

## Low risk

**以下情况评为低风险：**
- 重定向目标硬编码
- 严格白名单验证
- 仅允许相对 URL + 正则验证
- 输入由管理员配置

## 审计专业技巧

### 1. 真实漏洞的识别特征

**漏洞的必要条件（均需满足）：**

```go
// 真实漏洞必须同时满足：
// 1) 输入来自不受信任的来源
// 2) 输入直接用于重定向
// 3) 无有效的验证机制

// 真实漏洞示例
func handleRedirect(w http.ResponseWriter, r *http.Request) {
    // 1. 用户直接控制输入
    redirectURL := r.URL.Query().Get("target")

    // 2. 无验证直接使用
    http.Redirect(w, r, redirectURL, http.StatusFound)

    // 可被攻击：?target=https://evil.com
}
```

### 2. 常见误报场景

**场景A：仅检查前缀看似不完整，但有上下文保护**

```go
// 乍一看有漏洞的代码
func redirect(w http.ResponseWriter, r *http.Request) {
    path := r.URL.Query().Get("path")

    // 看起来检查不完整
    if strings.HasPrefix(path, "/") {
        url := fmt.Sprintf("https://trusted.com%s", path)
        http.Redirect(w, r, url, http.StatusFound)
    }
}

// 这里是安全的，因为：
// 1. 只接受以 / 开头的相对路径
// 2. 完整域名由代码控制，不可被修改
// 3. 攻击者无法改变 https://trusted.com
```

**场景B：黑名单虽然不完整，但配合其他机制**

```go
// 误报场景
func allowRedirect(w http.ResponseWriter, r *http.Request) {
    url := r.URL.Query().Get("url")

    // 黑名单不完整？检查上下文
    if !strings.Contains(url, "javascript:") &&
       !strings.Contains(url, "data:") {
        http.Redirect(w, r, url, http.StatusFound)
    }
}

// 判断要点：
// - 如果代码注释说「仅用于 CDN 回源」，域名可能已由基础设施限制
// - 如果有请求日志记录，可追溯
// - 如果结合速率限制、验证码等，风险降低
```

**场景C：框架级别的验证**

```go
// 使用 Gin 框架
func(c *gin.Context) {
    url := c.Query("redirect")

    // Gin 的 Redirect 本身未必进行验证，但需检查：
    // 1. 中间件是否有全局验证
    // 2. 框架配置中是否设置了白名单
    c.Redirect(http.StatusFound, url)
}

// 验证方法：
// - 查看 middleware/ 目录是否有专门的重定向验证中间件
// - 检查 config/ 中是否定义了允许的重定向域名列表
```

### 3. 区分真实漏洞 vs 误报的关键问题

| 判断维度 | 真实漏洞 | 误报 |
|---------|--------|-----|
| **输入源** | 完全由用户控制 | 来自可信来源或已预处理 |
| **验证方式** | 无验证或验证易绕过 | 有明确的白名单或格式限制 |
| **目标URL构造** | 完整URL由输入决定 | 域名/协议硬编码，仅路径变量 |
| **上下文保护** | 孤立的功能 | 结合认证、授权、日志等 |
| **协议限制** | 允许任意协议(http/https/javascript等) | 限制仅HTTPS或相对路径 |

### 4. 审计检查清单

**快速判断流程：**

1. **定位输入源**（5秒）
   ```
   □ Query().Get() / URL.Query() 参数
   □ FormValue() / PostFormValue() 表单
   □ Header.Get() 请求头
   □ Cookie.Value / Request.Header 其他来源
   ```

2. **追踪验证层**（10秒）
   ```
   □ 是否调用了 net/url.Parse()
   □ 是否检查了 u.Host / u.Scheme
   □ 是否有白名单映射 map[string]string
   □ 是否使用了 regexp 或 filepath 验证
   □ 是否在中间件中统一验证
   ```

3. **判断控制流**（10秒）
   ```
   □ 验证失败是否有错误返回
   □ 重定向前是否有多层检查
   □ 是否存在可绕过的分支
   □ Location 头是否被其他代码修改
   ```

4. **综合评分**
   ```
   完全无验证 + 直接使用 = 高风险
   单层黑名单 + 无其他保护 = 中风险
   白名单 OR 相对路径 + 路径验证 = 低风险或无风险
   ```

### 5. 高级绕过技巧识别

审计时需要识别这些绕过方式是否被考虑到：

```go
// 绕过技巧1: URL 编码
"url": "https%3a%2f%2fevil.com"

// 绕过技巧2: 双重编码
"url": "https%253a%252f%252fevil.com"

// 绕过技巧3: 混合协议
"url": "//evil.com" (Protocol-relative URL)
"url": "/\\evil.com" (某些实现可能误解)

// 绕过技巧4: 特殊字符
"url": "https://evil.com@trusted.com"  // 伪装成 trusted.com
"url": "https://trusted.com?redirect=https://evil.com"

// 真正安全的验证必须：
if u, err := url.Parse(redirectURL); err != nil {
    // URL 必须能解析
    // 必须检查 u.Scheme 和 u.Host
    // 必须白名单比对
}
```

### 6. 常见的审计陷阱

**陷阱1：仅看字符串匹配，忽视 URL 解析**
- 错误：认为 `strings.HasPrefix(url, "https")` 就安全
- 正确：必须用 `url.Parse()` 验证，防止编码绕过

**陷阱2：信任框架的 Redirect，却忽视输入来源**
- 错误：认为调用框架函数就自动安全
- 正确：检查框架版本、是否有安全补丁、中间件配置

**陷阱3：黑名单看起来完整其实不然**
- 错误：检查了 `!strings.Contains(url, "http")`，认为没问题
- 正确：`//` 可绕过，需要 `url.Parse()` + 白名单

**陷阱4：忽视隐式的重定向**
- 错误：只检查显式的 `http.Redirect()` 调用
- 正确：还要检查 `SetHeader("Location", ...)` 的所有地方
