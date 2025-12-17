# Go HTTP Header用户输入直接赋值

## 基本信息
- **难度等级：** ★★☆☆☆ | **审计时间：** 15-25分钟
- **关键词搜索：** `Header().Set`, `Header().Add`, `w.Header()`, `ResponseWriter`, `Query`, `FormValue`, `r.Header.Get`
- **快速检查：** 用户输入是否直接传入Header().Set/Add方法，是否有CRLF过滤

## 漏洞成因

Go net/http包在1.5+版本对Header.Set/Add方法有CRLF检查，但直接拼接头值、使用低版本Go、或通过第三方库绕过标准API仍可能导致头注入。攻击者可注入任意HTTP头，实现响应拆分、会话劫持、缓存中毒。

### 常见漏洞模式

```go
// ✗ 漏洞：用户输入直接设置响应头值
func handler(w http.ResponseWriter, r *http.Request) {
    lang := r.URL.Query().Get("lang")
    w.Header().Set("Content-Language", lang)  // 未过滤CRLF
    // 攻击: ?lang=en%0d%0aSet-Cookie:admin=true
}
```

```go
// ✗ 漏洞：用户输入作为头名称
func customHeader(w http.ResponseWriter, r *http.Request) {
    name := r.URL.Query().Get("header_name")
    value := r.URL.Query().Get("header_value")
    w.Header().Set(name, value)  // 头名和值都可控
}
```

```go
// ✗ 漏洞：请求头透传到响应头
func proxyHeader(w http.ResponseWriter, r *http.Request) {
    customID := r.Header.Get("X-Custom-ID")
    w.Header().Set("X-Response-ID", customID)  // 未验证来源头
}
```

```go
// ✗ 漏洞：Content-Disposition文件名注入
func download(w http.ResponseWriter, r *http.Request) {
    filename := r.FormValue("filename")
    w.Header().Set("Content-Disposition", "attachment; filename="+filename)
    // 攻击: ?filename=file.txt%0d%0aX-Injected:header
}
```

```go
// ✓ 修复：CRLF过滤 + 白名单验证
var crlfPattern = regexp.MustCompile(`[\r\n]`)

func safeHandler(w http.ResponseWriter, r *http.Request) {
    lang := r.URL.Query().Get("lang")
    safeLang := crlfPattern.ReplaceAllString(lang, "")
    validLangs := map[string]bool{"en": true, "zh": true}
    if validLangs[safeLang] {
        w.Header().Set("Content-Language", safeLang)
    }
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | Header().Set/Add用户输入 | 搜索 `Header().Set\|Add` + `Query\|FormValue`，检查参数来源 |
| **P0** | 头名称可控 | 搜索 `Header().Set(变量`，检查第一个参数是否用户可控 |
| **P1** | 请求头透传响应 | 搜索 `r.Header.Get` + `w.Header().Set`，追踪数据流 |
| **P1** | Content-Disposition | 搜索 `Content-Disposition` + 字符串拼接，检查filename参数 |
| **P2** | 第三方框架头设置 | 搜索 `c.Header\|ctx.SetHeader`（Gin/Echo），检查参数来源 |
| **P2** | Go版本检查 | 查看go.mod，Go < 1.5存在更大风险 |
| **P3** | 中间件统一处理 | 搜索自定义ResponseWriter，检查Header方法重写 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 头值全部硬编码，Go 1.5+ | 快速跳过，无用户输入 |
| **L1** | 使用标准库，头值来自配置 | 关键词扫描，确认数据来源 |
| **L2** | 单文件内Header.Set使用用户参数 | 跳读检查CRLF过滤和白名单 |
| **L3** | 头值由Service层方法返回 | 逐行追踪方法返回值来源 |
| **L4** | 自定义ResponseWriter/中间件 | 跨模块检查Header方法实现 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. Header.Set/Add的值直接或间接来自用户输入（Query/FormValue/Header）
2. 未进行CRLF字符过滤（无`strings.ReplaceAll`或正则替换`[\r\n]`）
3. Go版本 < 1.5 或使用非标准方式设置头（如Hijacker）

### 典型漏洞特征（满足任一项即确认）
- ✗ `w.Header().Set("X-Custom", r.URL.Query().Get("value"))`
- ✗ `w.Header().Set(userControlledName, userControlledValue)`
- ✗ `w.Header().Set("Content-Disposition", "attachment; filename="+userInput)`
- ✗ 使用Hijacker绕过标准Header API直接写入响应

### 安全排除（任一项充分）
- ✓ Go 1.5+ 且仅使用标准Header API（内置CRLF拒绝）
- ✓ 存在CRLF过滤：`regexp.MustCompile("[\r\n]").ReplaceAllString()`
- ✓ 白名单验证头值：`map[string]bool{"en": true}`
- ✓ 头值来自代码常量或可信配置文件

### 灰色判定（风险较低但需注意）
- 框架版本未明确，可能存在旧版本CRLF绕过
- 部分头有验证，部分头无验证
- 依赖前端验证但后端未二次检查

---

## 审计专业技巧

### 真实漏洞vs误报的区分

**真实漏洞的关键标志：**

1. **数据流完整性** - 用户输入必须真正到达Header设置
   - 真漏洞：`lang := r.URL.Query().Get("lang")` → `w.Header().Set("Content-Language", lang)`
   - 误报：`lang := r.URL.Query().Get("lang")` → 存在`if lang == "en" { w.Header().Set(...) }`（白名单隐含过滤）

2. **Header方法调用方式** - 标准库vs绕过方式
   - 可能真漏洞：直接调用`w.Header().Set()`、使用`http.Hijacker`、或自定义ResponseWriter
   - 需确认Go版本 - 1.5+版本标准Header.Set内置CRLF检查（Ctrl+R/Ctrl+N被拒）
   - 低版本风险：Go < 1.5、net包绕过（如直接写入底层conn）

3. **框架层面的隐藏防护**
   - Gin/Echo等框架在1.0+版本已内置Header.Set的CRLF检查（类似Go标准库）
   - 看到`c.Header("X-Custom", userInput)`不一定是漏洞，需检查框架版本
   - 验证框架源码：框架内部是否调用了`net/http.Header.Set`（安全）还是直接字符串拼接（危险）

4. **隐式过滤vs显式过滤**
   - 误报案例：`headerValue = strings.TrimSpace(userInput)` + `Header().Set()`
     - TrimSpace只移除头尾空白，不过滤CRLF，但在某些场景可能不可利用
   - 真漏洞：完全无过滤或仅过滤部分特殊字符（如过滤`%`但不过滤`\r\n`字符码）

### 常见误报场景

| 场景 | 代码示例 | 判定 | 原因 |
|------|--------|------|------|
| 硬编码头名+用户值 | `w.Header().Set("X-ID", userInput)` | 需检查Go版本 | Go 1.5+ 标准库会拒绝CRLF |
| 白名单验证 | `if allowed[userInput] { Header().Set(...) }` | 安全 | 用户输入被白名单隔离 |
| 头值来自数据库 | `value := db.QueryValue()` | 看数据源 | 数据库是否也验证了输入 |
| 只移除空白 | `TrimSpace(userInput)` + `Header().Set()` | 风险 | CRLF未被过滤 |
| 自定义ResponseWriter | 重写`Header()`方法 | 高风险 | 可能绕过标准库CRLF检查 |
| 第三方库直接写响应 | `conn.Write([]byte("Header: " + userInput))` | 真漏洞 | 完全绕过标准库 |

### 审计实战经验

**技巧1：追踪完整数据流**
- 不要看到`Header().Set`就直接标记，需要追踪参数来源
- 从最后一行`Header().Set`往前追：该参数从哪个函数返回？
- 该函数的参数从哪来？是否存在中间转换（验证/过滤）
- 示例：`handler` → `getHeaderValue(userInput)` → `Header().Set(result)`
  - 需进入`getHeaderValue`检查是否有白名单/过滤逻辑

**技巧2：识别安全的隐式防护**
```go
// 这是安全的，虽然没有显式过滤
headerValue := userInput
if !isValidLang(headerValue) {  // 白名单检查
    headerValue = "en"           // 默认值
}
w.Header().Set("Content-Language", headerValue)  // 最终设置的是白名单验证过的值
```

**技巧3：注意头部特殊字符处理**
- `Content-Disposition`：检查filename参数是否经过RFC 5987编码
- `Set-Cookie`：检查是否使用http.SetCookie()而非手动Header().Set()
- `Location`：检查重定向URL是否经过URL编码
- 这些头部的非标准用法更容易出现漏洞

**技巧4：框架特定的风险**
- **标准库**：go.mod中无net/http版本（内置），检查Go版本
- **Gin/Echo/Fiber**：检查框架版本后再判定，新版本已修复
- **自定义框架**：最危险，需要检查源码实现
- **HTTP客户端库**：如httpclient设置出站请求头，风险较低（响应头注入风险高）

**技巧5：CRLF编码变体检测**
- 标准CRLF：`%0d%0a`（十进制：`\r\n`）
- 双重编码：`%250d%250a`（%被编码为%25）
- URL编码变体：`%0D%0A`（大写）
- 若代码仅过滤小写`\r\n`字符而不过滤`%0d%0a`十六进制，可能误报

**技巧6：判断是否为有效漏洞的黄金法则**
```
✓ 真漏洞条件（三个都满足）：
  1. 用户可控的数据流到Header.Set/Add
  2. 无CRLF过滤（标准库1.5+除外，需确认版本）
  3. 能实际注入换行符（非标准库可能被http客户端库再次检查）

✗ 排除为漏洞的条件（任一满足）：
  1. 标准库Header.Set + Go >= 1.5（自带检查）
  2. 用户输入被白名单验证隔离
  3. 数据流中存在硬过滤（regexp[\r\n]、sanitize函数）
  4. 虽然用户可控但不涉及HTTP协议层（如业务数据）
```

---

## 实现建议

### 核心防护方案

**方案1：CRLF过滤**
```go
import "regexp"

var crlfPattern = regexp.MustCompile(`[\r\n]`)

func sanitizeHeaderValue(value string) string {
    return crlfPattern.ReplaceAllString(value, "")
}
```

**方案2：白名单验证**
```go
var allowedLanguages = map[string]bool{
    "en": true, "zh": true, "ja": true, "ko": true,
}

func setLanguageHeader(w http.ResponseWriter, lang string) {
    if allowedLanguages[lang] {
        w.Header().Set("Content-Language", lang)
    }
}
```

**方案3：安全的Content-Disposition**
```go
import "mime"

func safeContentDisposition(filename string) string {
    // 使用mime包进行RFC 5987编码
    return mime.FormatMediaType("attachment", map[string]string{
        "filename": filename,
    })
}
```

### 检查清单
- [ ] 所有用户输入的头值经过CRLF过滤
- [ ] 头名称使用白名单，禁止用户控制
- [ ] Content-Disposition使用mime包编码
- [ ] 确认Go版本 >= 1.5
- [ ] 测试CRLF注入：`?value=test%0d%0aSet-Cookie:admin=1`

---

## 修复优先级

1. **立即修复**：用户输入直接作为头值且无任何过滤
2. **本周修复**：添加CRLF过滤函数，统一所有头值处理
3. **可选加强**：实现白名单验证，限制可接受的头值范围
4. **长期优化**：升级Go版本，使用框架内置安全机制
