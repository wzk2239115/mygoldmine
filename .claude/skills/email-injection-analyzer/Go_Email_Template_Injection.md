# Go Email Template Injection

## Details

Go 应用使用 `text/template` 或 `html/template` 包渲染邮件内容时，若用户输入直接嵌入模板字符串未经转义，攻击者可注入模板指令。虽然 `html/template` 有自动转义，但 `text/template` 不转义，且即使使用 `html/template`，某些场景下仍可能导致模板注入。

**代码示例与审计要点**

```go
import (
    "text/template"
    "html/template"
)

// 危险：用户输入拼接到模板字符串（text/template）
templateStr := fmt.Sprintf("Hello %s, your code is: {{.Code}}", userName)
tmpl, _ := template.New("email").Parse(templateStr)
tmpl.Execute(buf, data)

// 危险：允许用户提供模板内容
userTemplate := r.FormValue("emailTemplate")
tmpl, _ := template.New("email").Parse(userTemplate)
tmpl.Execute(buf, data)

// 危险：使用 text/template 处理 HTML 邮件
tmpl := template.Must(template.New("email").Parse(userInput))
tmpl.Execute(buf, data)
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `text/template`、`html/template`、`template.New()`、`.Parse()`
- 查找字符串拼接到模板：`fmt.Sprintf()`、`+` 拼接
- 定位用户输入来源：`r.FormValue()`、`r.URL.Query()`、请求体
- 检查 `.Execute()`、`.ExecuteTemplate()` 调用

**快速定位保护机制 (L2: 跳读)**
- 检查是否使用 `html/template` 而非 `text/template`
- 查找模板文件加载：`template.ParseFiles()`、`template.ParseGlob()`
- 搜索转义函数：`html.EscapeString()`、`template.HTMLEscapeString()`
- 查看模板是否定义在代码中为常量

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到模板字符串中
   - 允许用户提供完整的模板内容
   - 使用 `text/template` 处理包含用户输入的 HTML 邮件
   - 可通过输入 `{{.}}` 或 `{{printf "%s" .}}` 测试注入
   - 能访问模板上下文中的敏感数据

2. **确认为误报的情况**：
   - 模板完全从文件系统加载（`ParseFiles`、`ParseGlob`）
   - 使用 `html/template` 并且用户输入仅作为数据变量
   - 模板字符串在代码中定义为常量
   - 用户输入经过 HTML 转义后才传入模板

3. **代码异味判断**：
   - 使用 `text/template` 处理 HTML 内容
   - 模板上下文暴露了敏感对象或函数
   - 使用自定义函数映射（`Funcs()`）但未限制功能

---

## Low risk

**这些情况应给予低风险评级**

1. **html/template**：使用 `html/template` 包并确保用户输入仅作为数据变量，利用自动转义

2. **静态模板**：所有邮件模板从文件系统加载（`ParseFiles`），用户输入仅作为执行数据

3. **常量模板**：模板字符串在代码中定义为 `const` 或字符串字面量，不可修改

4. **输入转义**：所有用户输入在传入模板前都经过 `html.EscapeString()` 转义

5. **纯文本邮件**：使用 `text/template` 但仅发送纯文本邮件，不包含 HTML，注入影响有限
