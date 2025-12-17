# Go 模板表达式注入

**漏洞成因**：Go 的 `text/template` 和 `html/template` 包提供模板渲染功能，支持在模板中使用变量、函数调用、管道操作等表达式。当应用将用户输入作为模板内容进行解析时，攻击者可构造恶意模板访问对象字段、调用方法、执行函数等，导致信息泄露或服务器端模板注入（SSTI）。虽然 Go 模板相比其他语言受限较多，但仍可能导致敏感信息泄露。常见于动态页面生成、邮件模板、报表生成等场景。

---

## Details

**代码示例**：
```go
// 危险：使用 template.New().Parse() 解析用户输入的模板
package main
import (
    "text/template"
    "net/http"
)

func handler(w http.ResponseWriter, r *http.Request) {
    userTemplate := r.URL.Query().Get("template")
    tmpl, _ := template.New("user").Parse(userTemplate) // 危险：用户提供的模板内容
    data := map[string]interface{}{"User": "admin"}
    tmpl.Execute(w, data)
}

// 攻击载荷示例（Go 模板相对受限）
// {{.Config}}  // 访问配置对象
// {{.Request.Header}}  // 访问请求头
// {{index .SensitiveData "password"}}  // 访问敏感字段
// {{call .Method "arg"}}  // 调用方法

// 危险：使用 html/template 但模板内容来自用户
import "html/template"
tmpl, _ := template.New("user").Parse(userInput) // 仍存在信息泄露风险

// 较安全：使用预定义模板文件，用户仅能提供数据
tmpl, _ := template.ParseFiles("user_profile.html") // 模板文件由开发者控制
tmpl.Execute(w, userData) // 用户仅能提供数据值

// 较安全：使用 html/template 并限制上下文对象
import "html/template"
tmpl := template.Must(template.ParseFiles("page.html"))
// 仅传递必要的数据，不包含敏感对象
tmpl.Execute(w, struct{ Name string }{Name: userName})

// 较安全：验证模板语法，拒绝用户输入的模板
if strings.Contains(userInput, "{{") || strings.Contains(userInput, "}}") {
    http.Error(w, "Invalid input", http.StatusBadRequest)
    return
}
```

**快速定位核心操作**：
- 关键词：`template.New()`、`Parse()`、`ParseFiles()`、`Execute()`、`{{`、`}}`
- 查找模板的创建和解析位置：`template.New().Parse(userInput)`
- 追踪模板字符串的来源，判断是否包含用户输入
- 检查模板执行时传递的数据对象，是否包含敏感信息
- 区分 `text/template` 和 `html/template`（后者有一定转义保护）
- 搜索动态模板生成的场景

**快速定位保护机制**：
- 模板字符串是否来自可信的文件系统而非用户输入
- 是否使用 `html/template` 而非 `text/template`（提供 XSS 防护）
- 是否使用 `ParseFiles()` 加载预定义模板文件
- 模板数据对象是否限制了敏感字段的暴露
- 是否对用户输入进行验证，拒绝包含模板语法的输入
- 是否使用了自定义函数映射（`template.FuncMap`）限制可调用函数
- Go 版本是否为最新稳定版

**审计等级**：**L2-L3**
- **L2**：跳读模板解析代码，识别动态模板的使用
- **L3**：逐行验证模板字符串来源和数据对象，确认安全措施

---

## Classify

**确认为漏洞**：
- 使用 `template.New().Parse()` 解析用户输入的模板字符串
- 模板数据对象包含敏感信息（如配置、请求对象、数据库连接）
- 可通过模板语法访问未导出的字段或调用方法
- 使用 `text/template` 处理 HTML 内容，未进行 XSS 防护

**误报**：
- 模板字符串来自可信的文件系统，用户仅能提供数据值
- 使用 `html/template` 且模板数据对象仅包含必要的、非敏感的字段
- 用户输入经过严格验证，拒绝包含模板语法的内容
- 模板中使用的函数均为安全的内置函数或自定义函数

**代码异味**：
- 大量使用动态模板生成，增加 SSTI 风险
- 通过字符串拼接构造模板内容
- 模板数据对象包含过多字段，增加信息泄露风险
- 使用 `text/template` 而非 `html/template` 处理 Web 内容

---

## Low Risk

以下情况可评为低风险：
- **预定义模板**：仅使用 `ParseFiles()` 加载文件系统中的模板，用户仅能提供数据值
- **html/template 保护**：使用 `html/template` 提供自动转义和上下文感知的安全保护
- **受限数据对象**：模板数据对象仅包含必要的、非敏感的字段，使用结构体而非 `map[string]interface{}`
- **输入验证**：对用户输入进行严格验证，拒绝包含 `{{` 和 `}}` 的内容
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **最小暴露**：模板执行时仅传递最小必要的数据，避免暴露配置和系统对象
- **日志监控**：所有动态模板解析操作均记录日志并监控异常模式

**注意**：Go 模板虽然相对安全，但仍可能导致信息泄露，应避免将用户输入作为模板内容，始终使用预定义模板文件。
