# Go - antchfx/xpath 库 XPath 注入

## Details

### 漏洞成因
`github.com/antchfx/xmlquery` 和 `github.com/antchfx/htmlquery` 是 Go 生态中流行的 XPath 查询库，提供高性能的节点查询功能。其 `Find()`, `FindOne()`, `QueryAll()` 等方法接收 XPath 表达式字符串。当用户输入通过字符串拼接（`+`, `fmt.Sprintf()`）直接嵌入表达式时，攻击者可注入 XPath 语法元素操纵查询逻辑。该库不支持参数化查询，使得字符串拼接成为主要风险。常见于 web 爬虫、XML API 集成和配置管理。

代码示例：
```go
import (
    "github.com/antchfx/xmlquery"
    "net/http"
)

func handler(w http.ResponseWriter, r *http.Request) {
    category := r.FormValue("category")

    doc, _ := xmlquery.LoadURL("products.xml")
    expr := "//product[@category='" + category + "']"
    nodes := xmlquery.Find(doc, expr)

    for _, n := range nodes {
        w.Write([]byte(n.InnerText()))
    }
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `import "github.com/antchfx/xmlquery"`, `import "github.com/antchfx/htmlquery"`
- `xmlquery.Find()`, `xmlquery.FindOne()`, `xmlquery.QueryAll()`
- `htmlquery.Find()`, `htmlquery.FindOne()`
- 字符串拼接：`+`, `fmt.Sprintf()`, `strings.Join()`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`, `not()`
- 数据源：`r.URL.Query().Get()`, `r.FormValue()`, `r.PostFormValue()`, `c.Query()` (Gin)

### 快速定位保护机制 (L2-L4)
- **输入验证函数** (L2 跳读) - 查找 `regexp.MatchString()`, 自定义 `validate()` 函数
- **白名单 map** (L2 跳读) - 检查 `map[string]bool` 或 `[]string` 的枚举值验证
- **类型断言** (L2 跳读) - 查找 `strconv` 包的类型转换函数
- **转义实现** (L3 逐行读) - 检查自定义 `escapeXPath()` 函数，验证特殊字符处理
- **中间件追踪** (L4) - 从 HTTP handler 到 XPath 查询的完整链路，检查中间处理层

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据通过字符串拼接嵌入 antchfx XPath 表达式
2. 未实施有效的输入验证或转义机制
3. 表达式通过 `Find()` 或 `QueryAll()` 等方法执行
4. 查询的 XML/HTML 数据包含敏感信息

**误报情况**：
- 拼接的数据来自常量、配置或已验证的数据源
- 用户输入经过严格白名单验证（正则 `^[a-zA-Z0-9_-]+$`）
- 输入通过 `strconv.Atoi()` 强制转换为整数
- XML 数据为公开的网页或产品列表

**代码异味**：
- 自定义转义函数但未处理所有 XPath 特殊字符（遗漏 `[`, `]`, `//`）
- 使用 `strings.ReplaceAll()` 进行黑名单过滤
- 输入验证逻辑分散在多个 handler 或 service 中
- 仅在某些路由中进行验证，其他路由缺失

## Low risk

### 低风险评级场景

1. **整数转换** - 输入经过 `strconv.Atoi()` 或 `strconv.ParseInt()` 转换
   - 例：`id, err := strconv.Atoi(idStr); if err != nil { return }`

2. **枚举值验证** - 输入限制为预定义的 map 或 slice
   - 例：`validFields := []string{"name", "price"}; if !contains(validFields, field) { return }`

3. **正则白名单** - 使用严格的正则表达式验证
   - 例：`if !regexp.MustCompile("^[a-zA-Z0-9]+$").MatchString(input) { return }`

4. **公开数据** - XPath 查询的目标为公开的 HTML 页面或 XML 文档

5. **只读操作** - 仅用于数据抓取或展示，不涉及身份验证

6. **认证中间件** - HTTP 路由通过认证中间件保护，仅授权用户可访问

7. **结果过滤** - 查询结果经过权限检查或数据清理

8. **输入长度限制** - 输入长度严格限制（如 `input[:10]`），降低注入风险
