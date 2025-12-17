# Go net/http响应头CRLF注入

## Details

### 漏洞成因与常见模式

Go的`net/http`包在Go 1.5+对响应头有一定CRLF保护，但直接拼接响应字符串、使用`http.ResponseWriter.Write`绕过标准API、或低版本Go仍可能存在CRLF注入风险。

#### 模式1：Header.Set直接使用用户输入

```go
// ✗ 漏洞：Go 1.4及更早版本，Header.Set未验证CRLF
func handler(w http.ResponseWriter, r *http.Request) {
    lang := r.URL.Query().Get("lang")
    w.Header().Set("Content-Language", lang)  // Go 1.5+会拒绝CRLF
    w.Write([]byte("data"))
    // 攻击: ?lang=en%0d%0aSet-Cookie:admin=true
}
```

#### 模式2：直接写入响应绕过Header API

```go
// ✗ 漏洞：绕过Header API直接写入HTTP响应
func rawHandler(w http.ResponseWriter, r *http.Request) {
    customHeader := r.URL.Query().Get("header")

    // 直接写入响应，绕过Go的CRLF检查
    conn := w.(http.Hijacker).Hijack()
    conn.Write([]byte("HTTP/1.1 200 OK\r\n"))
    conn.Write([]byte("X-Custom: " + customHeader + "\r\n\r\n"))
    // 攻击: ?header=value%0d%0aSet-Cookie:hacked=1
    conn.Write([]byte("body"))
}
```

#### 模式3：Redirect Location头注入

```go
// ✗ 漏洞：未验证重定向URL
func redirectHandler(w http.ResponseWriter, r *http.Request) {
    next := r.URL.Query().Get("next")
    http.Redirect(w, r, next, http.StatusFound)
    // Go http.Redirect会调用Header().Set，但URL解析可能有差异
    // 攻击: ?next=http://example.com%0d%0aX-Injected:header
}
```

#### 模式4：第三方路由框架头注入

```go
// ✗ 漏洞：Gin/Echo等框架自定义头处理
import "github.com/gin-gonic/gin"

func ginHandler(c *gin.Context) {
    customValue := c.Query("value")
    c.Header("X-Custom", customValue)  // 依赖框架的CRLF过滤
    c.String(200, "data")
}
```

#### 模式5：Content-Disposition文件名注入

```go
// ✗ 漏洞：文件名未转义
func downloadHandler(w http.ResponseWriter, r *http.Request) {
    filename := r.URL.Query().Get("filename")
    w.Header().Set("Content-Disposition", "attachment; filename="+filename)
    // 攻击: ?filename=file.txt%0d%0aX-XSS-Protection:0
    http.ServeFile(w, r, "/path/to/file")
}
```

#### 安全实现参考

```go
// ✓ 安全：CRLF过滤 + 白名单验证
import (
    "net/http"
    "regexp"
    "strings"
)

var crlfPattern = regexp.MustCompile(`[\r\n]`)

func sanitizeHeader(value string) string {
    return crlfPattern.ReplaceAllString(value, "")
}

func secureHandler(w http.ResponseWriter, r *http.Request) {
    lang := r.URL.Query().Get("lang")
    safeLang := sanitizeHeader(lang)

    // ✓ 额外白名单验证
    validLangs := map[string]bool{"en": true, "zh": true, "ja": true}
    if validLangs[safeLang] {
        w.Header().Set("Content-Language", safeLang)
    }

    w.Write([]byte("data"))
}
```

### 审计检查清单

| 优先级 | 检查项 | 审计方法 | 审计等级 |
|--------|--------|---------|----------|
| **P0** | Hijacker直接写入 | 搜索 `Hijacker\|Hijack()` + 手动拼接响应头 | **L3-L4** |
| **P0** | Header.Set用户输入 | 搜索 `Header().Set\|Add` + `Query\|FormValue\|Header`来源 | **L2** |
| **P0** | Redirect未验证 | 搜索 `http.Redirect` + URL参数拼接 | **L2** |
| **P1** | 第三方框架头设置 | 搜索 `c.Header\|ctx.Response().Header` + 用户输入 | **L2-L3** |
| **P1** | Content-Disposition | 搜索 `Content-Disposition` + 文件名参数 | **L2** |
| **P2** | 低版本Go | 检查 `go.mod` 中Go版本是否 < 1.5 | **L1** |
| **P3** | Cookie值设置 | 搜索 `http.SetCookie` + 用户输入Value字段 | **L2** |

### 审计等级判定

| 等级 | 代码特征 | 审计策略 |
|------|---------|---------|
| **L0** | 响应头全部硬编码，Go 1.5+ | 快速跳过，确认Go版本和无用户输入 |
| **L1** | 仅使用标准库Header API，无Hijacker | 关键词扫描：确认Go版本 >= 1.5 |
| **L2** | 单文件内Header.Set使用用户输入 | 跳读：检查是否有CRLF过滤或白名单 |
| **L3** | 自定义ResponseWriter或中间件 | 逐行读：追踪自定义实现的头处理逻辑 |
| **L4** | 使用Hijacker绕过标准API | 跨模块追踪：检查所有手动拼接响应的地方 |

---

## Classify

### 确认漏洞的标准

1. **Go版本风险**：使用Go < 1.5（无内置CRLF检查）或使用Hijacker绕过标准API
2. **用户输入可达**：响应头值直接或间接来自URL参数、表单、请求头
3. **无过滤机制**：代码未调用 `strings.ReplaceAll(value, "\r", "")` 等过滤函数

### 判定为误报的情况

1. **Go版本保护**：Go 1.5+ 且仅使用 `Header().Set/Add` 标准API（内置CRLF检查）
2. **框架自动保护**：Gin/Echo等框架在最新版本自动过滤CRLF
3. **白名单验证**：响应头值仅允许预定义的枚举值
4. **仅内部使用**：头值来自配置文件或内部服务响应（需确认来源安全）

### 代码异味识别

1. **版本假设**：注释"Go自动过滤"，但未验证Go版本或使用了Hijacker
2. **不完整过滤**：仅过滤 `\n` 未过滤 `\r`
3. **混合使用**：部分代码使用 `Header().Set`，部分使用手动拼接
4. **框架版本未知**：使用第三方框架但未明确版本依赖

---

## Low risk

### 低风险场景判定标准

满足以下任一条件时，可评估为低风险（仍需标注并建议修复）：

1. **Go版本保护**
   - Go 1.5+ 且所有响应头使用 `Header().Set/Add` API
   - 未使用 `http.Hijacker` 或 `net.Conn` 直接写入
   - `go.mod` 明确指定 `go 1.17+`

2. **受限输入**
   - 响应头值来自有限字符集（仅字母数字）
   - 使用正则验证输入格式（严格模式）
   - 输入长度严格限制（<20字符）

3. **框架防护**
   - Gin 1.8+、Echo 4.9+（包含CRLF修复）
   - 使用框架的 `Context.Header()` 方法（非直接操作 `http.ResponseWriter`）
   - 中间件统一过滤所有响应头

4. **业务影响有限**
   - 响应头仅用于客户端展示（如 `X-Request-ID`）
   - 不涉及认证Cookie或安全相关头
   - 应用无缓存机制，无中毒风险

### 评级建议

- **低风险 + Go 1.5+**：确认无Hijacker使用，建议代码添加防御性CRLF检查
- **低风险 + 框架保护**：确认框架版本，代码层仍应过滤
- **低风险 + 字符集限制**：评估正则严格程度（避免 `.` 匹配换行符）

---

## Audit Skills 审计专业技巧

### 真实漏洞与误报的区分经验

#### 1. **Hijacker使用的精确判定**

**真实漏洞特征**：
```go
// ✓ 这是真实漏洞（即使Go 1.5+）
conn, bufrw, _ := w.(http.Hijacker).Hijack()
userInput := r.URL.Query().Get("value")
bufrw.WriteString("X-Header: " + userInput + "\r\n\r\n")
// CRLF注入可行，标记为P0
```

**误报排查**：
- 检查Hijack()的上下文是否实际写入了响应头
- 如果只用于WebSocket升级或流式传输，不涉及头注入则为误报
- 确认 `WriteString` 或 `Write` 是在 `http.ResponseWriter` 的头部写入阶段

**审计技巧**：
- 搜索 `Hijack()` 后逐行跟踪用户输入流向
- 看是否有 `\r\n\r\n` 的分界线写入（标志头部结束）
- 如果Hijack用于代理或隧道，检查上游是否转发了用户头

#### 2. **Header.Set/Add的版本与框架验证**

**真实漏洞条件链**：
```go
// 需要同时满足：
// 1. 使用了Header().Set/Add
// 2. 值来自用户输入
// 3. Go版本 < 1.5 OR 框架有bug

// 真实漏洞示例（Go 1.4）
func handler(w http.ResponseWriter, r *http.Request) {
    redirect := r.URL.Query().Get("goto")
    // Go 1.4: 不检查CRLF
    w.Header().Set("Location", redirect)
}
```

**误报排查步骤**：
1. **必须验证Go版本**：不是注释或假设，要看 `go.mod` 的 `go` 指令
   ```
   ✓ go.mod明确指定: go 1.16
   ✗ 注释说"使用Go 1.5+"但无版本文件
   ```
2. **确认Header实际值来源**：
   - `r.URL.Query()` / `r.FormValue()` → 需防护
   - `r.Header.Get()` → 代理转发，需防护
   - 配置文件 / 常量 → 一般安全，除非配置热更新
3. **框架版本核验**：
   - Gin: 搜索 `go.mod` 看 `github.com/gin-gonic/gin` 版本
   - Echo: 需要 `v4.9.0+` 才有CRLF防护
   - 自定义框架：需逐行审计

**审计命令技巧**：
```bash
# 快速检查Go版本
grep "^go " go.mod

# 检查框架版本
grep "github.com/gin-gonic/gin\|github.com/labstack/echo" go.mod

# 定位Header.Set的所有用户输入
grep -n "Header().Set\|Header().Add" *.go | \
  grep -E "Query|FormValue|Header.Get"
```

#### 3. **Redirect/Location头的特殊性**

**容易误判的场景**：
```go
// 场景A：GET参数重定向（高风险）
func handleRedirect(w http.ResponseWriter, r *http.Request) {
    next := r.URL.Query().Get("next")
    http.Redirect(w, r, next, http.StatusFound)
    // 虽然http.Redirect内部用Header().Set，但Go 1.5+有保护
    // 但URL本身可能被污染，需要额外URL验证！
}

// 场景B：业务逻辑生成的重定向（低风险）
func handleAfterLogin(w http.ResponseWriter, r *http.Request) {
    redirectURL := "/dashboard"  // 硬编码
    http.Redirect(w, r, redirectURL, http.StatusFound)
}
```

**判断标准**：
- Go 1.5+ 的 `http.Redirect` **不会产生CRLF注入**，但要评估**打开重定向**风险
- 真实漏洞：Go < 1.5 + Location来自用户输入
- 误报：Go 1.5+ + Location来自用户输入（需改为打开重定向评估）

#### 4. **Content-Disposition陷阱**

**真实漏洞**：
```go
// ✗ 真实漏洞：文件名注入Header
func download(w http.ResponseWriter, r *http.Request) {
    file := r.URL.Query().Get("f")
    // Go 1.5+会过滤CRLF，但RFC 5987允许带参数的值
    // 如果文件名本身通过中文编码可能逃逸过滤
    w.Header().Set("Content-Disposition",
        fmt.Sprintf("attachment; filename*=UTF-8''%s", file))

    // 攻击: ?f=file.txt%0d%0aX-Header:value
    // Header.Set会过滤，但如果框架自定义处理则可能漏洞
}
```

**误报场景**：
```go
// ✓ 安全：文件名来自文件系统（已验证）
import "path/filepath"

func download(w http.ResponseWriter, r *http.Request) {
    fileID := r.URL.Query().Get("id")
    // ID已通过数据库验证，映射到安全的文件名
    file := getFileNameByID(fileID)  // 返回"report_2024.pdf"
    w.Header().Set("Content-Disposition",
        fmt.Sprintf("attachment; filename=%s", file))
}
```

**审计窍门**：
- 跟踪文件名的来源是否经过 `filepath.Base()` 处理（去除路径）
- 检查是否用了正确的RFC 5987编码或引号包裹
- 如果使用了 `filepath.Clean()` 或 `path.Base()` 则风险降低

#### 5. **Cookie注入的隐蔽性**

**容易遗漏的漏洞**：
```go
// ✗ 漏洞：虽然Set-Cookie看起来独立，但值可能被注入
func setCookie(w http.ResponseWriter, r *http.Request) {
    token := r.URL.Query().Get("session_id")
    // http.SetCookie 内部也调用Header().Add
    // Go 1.5+检查值中的\r\n，但可能绕过
    http.SetCookie(w, &http.Cookie{
        Name:  "sid",
        Value: token,  // 用户输入
        Path:  "/",
    })
}

// 攻击: ?session_id=abc%0d%0aSet-Cookie:admin=true
// Go会在Value中检查，但旧版本或框架可能失败
```

**安全检查**：
- 查看Cookie值是否经过base64编码或加密
- 验证Value字段是否有长度限制和字符白名单
- 搜索 `http.SetCookie` 然后逐个检查参数来源

---

### 高效审计工作流

#### 第一步：快速筛查
```bash
# 1. 检查Go版本和框架版本
grep "^go " go.mod
grep "gin-gonic\|labstack/echo\|chi" go.mod

# 2. 查找高危API调用
grep -r "Hijack()\|WriteString\|Write(" . --include="*.go" | \
  grep -v "test\|vendor" | head -20

# 3. 初步判断是否需要深入审计
# 如果: Go 1.17+ 且仅用Gin/Echo && 无Hijack => L0
```

#### 第二步：精准定位
```bash
# 查找所有Header().Set + 用户输入的组合
grep -n "Header().Set\|Header().Add" main.go | while read line; do
    # 检查后续5行是否有Query/FormValue
    sed -n "${line%:*},$((${line%:*}+5))p" main.go
done
```

#### 第三步：验证上下文
- 是否有CRLF过滤：搜索 `strings.ReplaceAll` / `regexp`
- 输入来源确认：跟踪 `Query()` 到 `Header().Set` 的完整链路
- 框架防护确认：检查框架版本和使用的API（`c.Header()` vs 直接 `http.ResponseWriter`）

#### 第四步：漏洞等级判定
| 代码模式 | Go版本 | 框架 | 过滤 | 输入来源 | 判定 |
|---------|-------|------|------|---------|------|
| Header.Set | 1.5+ | 无 | 无 | Query | **L2-低风险** |
| Header.Set | 1.5+ | Gin1.8+ | 无 | Query | **L1-低风险** |
| Hijacker | 1.5+ | 无 | 无 | Query | **L3-中风险** |
| Header.Set | <1.5 | 无 | 无 | Query | **L4-高风险** |
| SetCookie | 1.5+ | 无 | base64 | Query | **L1-低风险** |

---

### 常见的错误判定与纠正

1. **误判1**：看到 `Header().Set` + 用户输入就标记P0
   - **纠正**：必须检查Go版本和是否有过滤
   - **正确判定**：Go 1.5+ 无过滤 = L2（低风险，仍需修复）

2. **误判2**：认为框架自动保护，代码不需要防护
   - **纠正**：框架保护 + 代码防护 = 深度防御
   - **建议**：框架有保护仍要建议代码层加防护

3. **误判3**：看到Hijack()就判定为真实漏洞
   - **纠正**：需要检查是否真的在头部写入，还是仅用于流传输
   - **验证**：查看Hijack()后是否有 `\r\n\r\n` 的头尾分界
