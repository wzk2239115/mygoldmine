# Go 多行响应头未规范化

## Details

**审计等级：L2（跳读）/ L3（逐行读）**

**危险函数特征：**
- `w.Header().Set()` 或 `Add()` 传入包含 `
` 的值
- 从外部源读取头值未规范化
- CRLF 在头值中未被过滤
- 反向代理转发头时未规范化

**快速定位核心操作：**
1. 搜索关键字：`Header().Set`、`Header().Add`、`
` 在头值
2. 追踪头值来源：外部 API、数据库、请求参数
3. 检查是否存在规范化
4. 追踪头值转发流程

**快速定位保护机制：**
- 规范化：`strings.ReplaceAll(value, "
", "")`
- 验证：`if strings.ContainsAny(value, "
")`
- RFC 合规：遵循 HTTP 标准
- 框架防护：Go net/http 某些版本自动检测

**代码示例：**
```go
// 危险：外部值直接设置为响应头
func proxyHeader(w http.ResponseWriter, r *http.Request) {
    custom := r.Header.Get("X-Custom")
    w.Header().Set("X-Forwarded", custom)  // 危险：未规范化
}

// 危险：API 响应转发
func forwardAPI(w http.ResponseWriter, r *http.Request) {
    resp, _ := http.Get("http://api")
    for k, v := range resp.Header {
        w.Header().Set(k, v[0])  // 危险：未规范化
    }
}

// 危险：数据库字段
func dbHeader(w http.ResponseWriter, r *http.Request) {
    headerVal := getFromDB(id)
    w.Header().Set("X-Custom", headerVal)  // 危险
}
```

## Classify

**漏洞（Medium）：**
- 外部值包含 `
` 未规范化
- 导致响应分割
- 框架未自动检测

**误报：**
- 头值硬编码
- 框架已规范化
- 官方库处理

**代码异味（Medium）：**
- 外部来源未验证
- 仅过滤部分字符
- 间接流程

## Low risk

**以下情况评为低风险：**
- 头值硬编码
- 明确过滤 CRLF
- 框架已验证
- 内部系统来源且已验证

## SKILL - 审计专业技巧

### 1. 真实漏洞的特征识别

**真实漏洞的五个必要条件：**

1. **外部输入源**：必须来自以下之一
   - HTTP 请求参数（`r.Header.Get()`、`r.Form.Get()`、`r.URL.Query()`）
   - HTTP 请求体（JSON/XML 解析）
   - 外部 API 响应
   - 数据库读取（考虑数据污染链）
   - 环境变量（某些情况）

2. **未规范化处理**：头值进入 `Header().Set()` 之前没有
   - ❌ 只检查有无 `\r` 或 `\n`，忘记检查 CRLF 组合
   - ✓ 使用 `strings.ReplaceAll(value, "\r\n", "")`
   - ✓ 使用 `strings.ReplaceAll(value, "\r", "")`+`strings.ReplaceAll(value, "\n", "")`

3. **框架版本确认**：Go 1.11+ 在某些情况下会自动检测，但不是所有版本都可靠
   - 审查 `go.mod` 的 Go 版本
   - 如果版本 < 1.11，几乎所有情况都是真实漏洞
   - 即使 ≥ 1.11，自定义头字段仍需手动检测

4. **响应分割可能性**：验证是否实际导致
   - 注入额外的响应头
   - 注入空行分隔符（`\r\n\r\n`）
   - 操纵响应体

5. **危害确认**：考虑实际影响
   - XSS（注入 JavaScript）
   - 会话劫持（设置 Cookie）
   - 缓存污染（CDN/代理层面）

**现场审计技巧：**
- 搜索 `Header().Set` 后，逐一回溯变量来源，画出数据流图
- 对于链式调用，每个环节都要检查（例如：数据库 → 解析 → 转发）
- 特别关注循环体内的赋值，某些场景可能漏掉规范化

### 2. 常见误报场景与规避

**误报 1：硬编码头值**
```go
// ✓ 安全：硬编码字符串
w.Header().Set("X-API-Version", "v2.1")
w.Header().Set("Cache-Control", "public, max-age=3600")
// 虽然字符串中理论上可以包含\r\n，但在源代码中明确可见
```
**审计决策**：跳过，除非看到 \r\n 字面量出现

---

**误报 2：框架自动规范化**
```go
// Go 1.11+ 某些版本会自动过滤 CRLF
w.Header().Set("X-Custom", userInput)
// 取决于 net/http 版本和配置
```
**审计决策**：检查 go.mod 版本、查看 net/http 源码注释、测试该版本行为

---

**误报 3：已明确过滤**
```go
// ✓ 安全：已过滤 CRLF
value := strings.ReplaceAll(userInput, "\r\n", "")
value = strings.ReplaceAll(value, "\r", "")
value = strings.ReplaceAll(value, "\n", "")
w.Header().Set("X-Custom", value)
```
**审计决策**：验证过滤逻辑完整性（包含 `\r`、`\n`、`\r\n`），跳过

---

**误报 4：内部数据源（但需谨慎）**
```go
// 数据库来源
headerVal := db.QueryString("SELECT header_value FROM config WHERE id=?", id)
w.Header().Set("X-Config", headerVal)

// 看似安全，但要检查：
// 1. 数据库数据来源是否受信
// 2. 是否存在数据污染链
// 3. 是否有注入点向数据库写入恶意数据
```
**审计决策**：如果能追溯数据库数据完全来自应用内部（非用户输入），评为低风险；否则评为中风险

---

**误报 5：正则验证充分**
```go
// ✓ 较安全：严格的正则验证
if !regexp.MustCompile(`^[a-zA-Z0-9\-_.]+$`).MatchString(userInput) {
    return fmt.Errorf("invalid header value")
}
w.Header().Set("X-Custom", userInput)
```
**审计决策**：验证正则表达式是否真正排除 CRLF，评为低风险

### 3. 常见陷阱场景（容易漏报的真实漏洞）

**陷阱 1：间接转发**
```go
// ❌ 真实漏洞：通过中间存储转发
redirectURL := r.Header.Get("X-Redirect")  // 外部输入
session.Set("redirect", redirectURL)        // 存储
// ... 后续处理 ...
w.Header().Set("X-Next-URL", session.Get("redirect"))  // 未规范化
```
**审计要点**：跨函数/跨请求的流向容易漏掉，必须全链路追踪

---

**陷阱 2：循环体赋值**
```go
// ❌ 真实漏洞：循环中来自外部的头
for _, header := range r.Header.Get("X-Custom-Headers") {
    parts := strings.Split(header, ",")
    for _, part := range parts {
        w.Header().Add("X-Processed", part)  // 未规范化
    }
}
```
**审计要点**：循环拆分后的子串常被遗漏验证

---

**陷阱 3：空值检查误导**
```go
// ❌ 真实漏洞：空值检查后直接使用
value := r.Header.Get("X-Custom")
if value != "" {
    w.Header().Set("X-Echo", value)  // 空值检查≠规范化检查
}
```
**审计要点**：存在值 ≠ 值安全，两者概念不同

---

**陷阱 4：反向代理头转发**
```go
// ❌ 真实漏洞：反向代理转发上游响应头
resp, _ := http.Get("http://upstream-api")
for k, vals := range resp.Header {
    for _, v := range vals {
        w.Header().Add(k, v)  // 上游响应未规范化
    }
}
```
**审计要点**：上游服务可能受攻击，不能信任其响应头

### 4. 审计检查清单

| 检查项 | 操作 | 通过条件 |
|--------|------|--------|
| 输入源 | 回溯变量到来源 | 仅硬编码或受信来源 |
| 规范化 | grep 前置过滤 | 找到 ReplaceAll/TrimSpace 等 |
| 版本 | 检查 go.mod | ≥1.11 且无特殊要求 |
| 转发链 | 追踪全链路 | 每个环节都验证 |
| 框架防护 | 查阅官方文档 | 明确说明已防护 |
| 测试覆盖 | 搜索单元测试 | 存在针对性测试 |

### 5. 现场判断决策树

```
发现 Header().Set(k, userInput)
    ├─ 输入来自外部？
    │  ├─ 否 → 检查下一个 (低风险)
    │  └─ 是 → 继续
    ├─ 存在规范化代码？
    │  ├─ 是 → 验证正则/过滤逻辑完整性
    │  │      ├─ 完整 → 低风险
    │  │      └─ 不完整 → 中风险
    │  └─ 否 → 继续
    ├─ Go 版本 < 1.11？
    │  ├─ 是 → 高风险/中风险
    │  └─ 否 → 继续
    └─ 是否框架自动防护？
       ├─ 是且文档确认 → 低风险
       └─ 否或不确定 → 中风险

最终结论：中风险（Medium）需要开发确认或补丁
```

### 6. 实战经验总结

- **漏报率最高的场景**：数据库来源 + 链式转发 + 跨函数调用
- **误报率最高的场景**：框架版本混淆 + 自动防护信息过时
- **最容易遗漏的细节**：`Add()` vs `Set()` 行为差异，前者追加，需要验证每个值
- **建议补充验证**：即使代码看起来安全，建议测试注入 `\r\n` 实际行为
