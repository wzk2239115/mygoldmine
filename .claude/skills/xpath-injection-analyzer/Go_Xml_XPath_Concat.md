# Go - encoding/xml 和 XPath 字符串拼接

## Details

### 漏洞成因
Go 的 `encoding/xml` 包用于 XML 解析，通常配合第三方 XPath 库（如 `github.com/antchfx/xmlquery` 或 `github.com/ChrisTrenkamp/goxpath`）进行节点查询。当用户输入通过字符串拼接（`+`, `fmt.Sprintf()`, 字符串模板）直接嵌入 XPath 表达式时，攻击者可注入 XPath 语法字符来改变查询逻辑。Go 的强类型特性虽然提供一定保护，但字符串拼接仍是主要风险点。常见于 XML 配置解析、SOAP 客户端和数据查询服务。

代码示例：
```go
package main

import (
    "fmt"
    "github.com/antchfx/xmlquery"
    "net/http"
)

func searchHandler(w http.ResponseWriter, r *http.Request) {
    username := r.URL.Query().Get("username")

    doc, _ := xmlquery.LoadURL("users.xml")
    query := fmt.Sprintf("//user[username='%s']", username)
    nodes := xmlquery.Find(doc, query)

    fmt.Fprintf(w, "Found: %v", nodes)
}
```

### 快速定位核心操作 (L1: 关键词扫描)
- `import "encoding/xml"`, `xml.Unmarshal()`, `xml.Decoder`
- `import "github.com/antchfx/xmlquery"`, `xmlquery.Find()`, `xmlquery.FindOne()`
- `import "github.com/ChrisTrenkamp/goxpath"`, `goxpath.Parse()`
- 字符串拼接：`+`, `fmt.Sprintf()`, `fmt.Sprintf("%s%s")`
- XPath 特征：`//`, `@`, `[`, `]`, `'`, `"`, `and`, `or`
- 数据源：`r.URL.Query().Get()`, `r.FormValue()`, `r.PostFormValue()`

### 快速定位保护机制 (L2-L4)
- **输入验证** (L2 跳读) - 查找 `regexp.MatchString()`, `strings.ContainsAny()`, 自定义验证函数
- **白名单检查** (L2 跳读) - 检查 map 或 slice 的枚举值验证（`allowedFields[input]`）
- **类型转换** (L2 跳读) - 查找 `strconv.Atoi()`, `strconv.ParseInt()` 强制数值转换
- **转义函数** (L3 逐行读) - 检查自定义 `escapeXPath()` 或 `sanitize()` 函数实现
- **跨包追踪** (L4) - 从 HTTP handler 到 XPath 查询的数据流，检查中间处理函数

## Classify

### 漏洞判定标准

**确认为漏洞**：
1. 用户可控数据（HTTP 请求参数）通过字符串拼接嵌入 XPath 表达式
2. 未实施有效的输入验证、转义或参数化机制
3. 表达式通过 XPath 库执行查询（如 `xmlquery.Find()`）
4. 查询的 XML 数据包含敏感信息（用户凭证、权限、配置）

**误报情况**：
- 拼接的数据来自常量或配置文件
- 用户输入经过严格白名单验证（如正则 `^[a-zA-Z0-9]+$`）
- 输入经过 `strconv.Atoi()` 等强制类型转换为整数
- XML 数据为公开的静态资源

**代码异味**：
- 存在自定义转义函数但未覆盖所有 XPath 特殊字符
- 使用 `strings.Replace()` 进行黑名单过滤，可能被绕过
- 输入验证逻辑分散在多个函数或包中
- 依赖前端验证而非后端强制验证

## Low risk

### 低风险评级场景

1. **强类型转换** - 输入经过 `strconv.Atoi()` 或 `strconv.ParseInt()` 转换为整数
   - 例：`id, err := strconv.Atoi(r.URL.Query().Get("id")); if err != nil { return }`

2. **枚举值验证** - 输入限制为预定义的 map 或 slice
   - 例：`allowedFields := map[string]bool{"name": true}; if !allowedFields[field] { return }`

3. **正则白名单** - 使用 `regexp.MatchString()` 进行严格验证
   - 例：`matched, _ := regexp.MatchString("^[a-zA-Z0-9]+$", input)`

4. **非敏感数据** - XML 数据为公开的产品目录或配置文件

5. **只读查询** - XPath 仅用于数据检索，不涉及身份验证或授权

6. **内部服务** - HTTP handler 仅在内部网络或通过认证中间件访问

7. **结果过滤** - 查询结果经过额外的权限检查或数据脱敏

8. **长度限制** - 输入长度严格限制（如 `input[:10]`），降低攻击面
