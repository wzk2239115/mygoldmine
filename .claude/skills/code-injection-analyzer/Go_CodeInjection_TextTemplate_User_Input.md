# Go 代码执行注入：text/template 用户输入

## 漏洞成因

Go 的 `text/template` 包（及 `html/template`）提供模板引擎功能。当模板内容或动态字段由用户可控的输入构成时，攻击者可注入模板语法（如 `{{.}}`、`{{range}}`、`{{call}}`）来执行任意代码。虽然 `text/template` 的函数调用能力受限，但与反射、环境变量、或全局状态结合时仍可实现代码执行。此外，误用 `Execute()` 时易导致代码逻辑被篡改。

---

## Details

### 代码示例

```go
package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"text/template"
)

// 危险模式1：直接使用用户输入作为模板内容
func handleDirectTemplate(w http.ResponseWriter, r *http.Request) {
	userTemplate := r.URL.Query().Get("template")
	// 危险：userTemplate 完全可控，可注入模板语法
	tmpl, err := template.New("user").Parse(userTemplate)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	tmpl.Execute(w, nil)
}

// 危险模式2：模板中使用用户输入访问字段
func handleFieldInjection(w http.ResponseWriter, r *http.Request) {
	fieldName := r.PostFormValue("field")
	// 危险：fieldName 注入到模板表达式中
	tmpl, err := template.New("user").Parse(fmt.Sprintf("{{.%s}}", fieldName))
	if err != nil {
		return
	}
	data := map[string]interface{}{
		"Name": "Alice",
		"Cmd":  "secret_value", // 敏感字段
	}
	tmpl.Execute(w, data)
}

// 危险模式3：反射调用与模板结合
func handleReflectCall(w http.ResponseWriter, r *http.Request) {
	methodName := r.FormValue("method")
	// 危险：methodName 未验证，可通过模板语法调用任意方法
	tmplStr := fmt.Sprintf("{{call .%s}}", methodName)
	tmpl, err := template.New("user").Parse(tmplStr)
	if err != nil {
		return
	}
	handler := &Handler{}
	tmpl.Execute(w, handler)
}

// 危险模式4：环境变量和 range 组合
func handleEnvInjection(w http.ResponseWriter, r *http.Request) {
	pattern := r.URL.Query().Get("pattern")
	// 危险：pattern 可用于构造遍历环境变量或系统对象的模板
	tmplStr := fmt.Sprintf("{{range .Funcs}}{{if contains .Name \"%s\"}}{{.Name}}{{end}}{{end}}", pattern)
	tmpl, err := template.New("user").Parse(tmplStr)
	if err != nil {
		return
	}

	// 如果 Funcs 包含系统对象或敏感函数指针
	data := map[string]interface{}{
		"Funcs": os.Environ(), // 危险暴露
	}
	tmpl.Execute(w, data)
}

// 危险模式5：FuncMap 中函数名由用户控制
func handleFuncMapInjection(w http.ResponseWriter, r *http.Request) {
	allowedFunc := r.FormValue("func")
	// 危险：allowedFunc 未严格验证，可能调用意外的函数
	funcMap := template.FuncMap{
		"print":  fmt.Sprintf,
		"cmd":    os.Getenv,     // 敏感函数
		"syscall": executeCommand, // 危险函数
	}

	tmplStr := fmt.Sprintf("{{%s \"arg\"}}", allowedFunc)
	tmpl, err := template.New("user").Funcs(funcMap).Parse(tmplStr)
	if err != nil {
		return
	}
	tmpl.Execute(w, nil)
}

// 危险模式6：嵌套模板注入
func handleNestedTemplate(w http.ResponseWriter, r *http.Request) {
	baseTmpl := `<div>{{template "user" .}}</div>`
	userContent := r.FormValue("content")

	// 危险：userContent 作为嵌套模板被解析和执行
	tmpl, err := template.New("base").Parse(baseTmpl)
	if err != nil {
		return
	}

	// 动态添加用户提供的模板
	tmpl.New("user").Parse(userContent) // 危险：userContent 可注入恶意模板
	tmpl.Execute(w, nil)
}

// 危险模式7：管道链注入
func handlePipelineInjection(w http.ResponseWriter, r *http.Request) {
	funcName := r.URL.Query().Get("filter")
	value := r.FormValue("data")

	// 危险：funcName 未验证，通过管道实现任意函数调用
	tmplStr := fmt.Sprintf("{{.Data | %s}}", funcName)
	funcMap := template.FuncMap{
		"unsafe": unsafeOperation,
		"exec":   executeShell, // 危险
	}

	tmpl, err := template.New("user").Funcs(funcMap).Parse(tmplStr)
	if err != nil {
		return
	}

	data := map[string]interface{}{"Data": value}
	tmpl.Execute(w, data)
}

// 危险模式8：with 指令绕过
func handleWithBypass(w http.ResponseWriter, r *http.Request) {
	accessor := r.FormValue("accessor")

	// 危险：{{with}} 可改变上下文，accessor 在新上下文中执行
	tmplStr := fmt.Sprintf("{{with .Secret}}{{%s}}{{end}}", accessor)
	tmpl, err := template.New("user").Parse(tmplStr)
	if err != nil {
		return
	}

	data := map[string]interface{}{
		"Secret": map[string]interface{}{
			"key":  "value",
			"exec": executeCommand, // 通过 with 上下文访问
		},
	}
	tmpl.Execute(w, data)
}

// 辅助函数示意
type Handler struct {
	AdminPanel func() string
	Debug      func() string
}

func executeCommand(cmd string) string {
	// 示意：在实际代码中这会执行命令
	return "executed: " + cmd
}

func executeShell(cmd string) string {
	// 示意：shell 执行
	return cmd
}

func unsafeOperation(data interface{}) interface{} {
	// 示意：不安全操作
	return data
}
```

### 快速定位核心操作 **[L1:关键词扫描]**

重点扫描以下 patterns：
- `template.New()` + `.Parse()` - 模板创建和解析
- `template.ParseFiles()` / `ParseGlob()` - 从文件加载模板
- 用户输入直接作为参数传入 `Parse()` 或出现在 `fmt.Sprintf(template_string)` 中
- `.Execute()` / `.ExecuteTemplate()` - 模板执行
- `.Funcs(funcMap)` 配合 FuncMap 中的函数名由用户控制
- `{{.Field}}`、`{{call .Method}}`、`{{range}}`、`{{with}}` 等模板指令
- `html/template` 包（同样风险）

关键搜索词：`template.Parse`, `template.New`, `Execute`, `Funcs`, `ParseFiles`, `ParseGlob`, `fmt.Sprintf` 配合模板字符串

### 快速定位保护机制 **[L3:逐行读]**

审计重点：

1. **模板源白名单** - 是否限制模板来源于预定义的可信文件
   - 检查 `ParseFiles()` / `ParseGlob()` 是否仅限于特定目录
   - 确认模板路径是否经过路径遍历防护（黑名单 `../`）
   - 验证文件权限是否防止修改（文件所有者、权限位）

2. **模板语法限制** - 是否禁用或隔离危险的模板指令
   - 查看是否通过预编译模板避免运行时解析用户输入
   - 检查是否使用沙箱或模板审计库限制可用指令
   - 确认是否禁用了 `call`、`range`、`with` 等高危指令

3. **数据上下文隔离** - 传入 `Execute()` 的数据是否包含敏感函数或对象
   - 检查 `Execute()` 第二参数是否为用户可控数据
   - 验证数据结构是否包含可执行的方法指针、系统函数、环境变量等
   - 确认是否使用了受限的数据类型（如只允许基本类型、struct 字段）

4. **FuncMap 白名单** - 注册的模板函数是否存在不被允许的函数
   - 列举所有通过 `.Funcs()` 注册的函数
   - 核实每个函数是否必要，是否存在逃逸、执行、反射操作
   - 检查函数名是否由用户输入控制
   - 确认是否有 `call` / `invoke` 等动态调用机制

5. **输入校验** - 模板相关的用户输入是否经过校验
   - 查找模板内容出现前是否有白名单验证
   - 检查模板中字段/函数名是否在预定义列表中
   - 验证是否使用了正则或黑名单过滤（通常不安全）

6. **错误处理与日志** - 模板执行是否被监控
   - 检查 `Parse()` 和 `Execute()` 错误是否被捕获和记录
   - 确认异常模板是否被审计（如包含禁用指令的检测）
   - 查看是否记录了执行上下文和执行者身份

---

## Classify

### 漏洞研判标准

**确认为漏洞的条件：**

1. **用户输入可直接影响模板内容** - 无论是 GET/POST 参数、HTTP header、文件上传还是数据库字段，只要被用于 `template.Parse()` 或被拼接进模板字符串

2. **模板语法未被限制** - 模板允许使用 `{{call}}`、`{{range}}`、`{{with}}` 等可访问对象属性和方法的指令

3. **执行上下文包含敏感数据** - 传入 `Execute()` 的数据包含：
   - 函数指针、方法集或 FuncMap
   - 可执行的对象（如 `*os.File`、网络连接等）
   - 环境变量、密钥、配置信息
   - 反射对象或通用接口

4. **FuncMap 中存在危险函数** - 注册了可能导致代码执行的函数（如 `exec.Command`、`os.Getenv`、反射操作等）

5. **跨模板污染** - 通过模板名称或嵌套模板机制，用户控制的模板内容被嵌入到正常模板中

**区分误报的关键点：**

- 模板内容完全由应用硬编码定义，用户输入仅用于填充数据（如 `Execute()` 的第二参数）
- 虽然 `Parse()` 接收动态字符串，但源限制在预编译的、不可修改的文件中
- 模板仅包含简单的条件和数据显示，无 `call`、`range` 等复杂指令
- FuncMap 仅包含无害的格式化、字符串操作函数，无系统调用
- 使用了专门的模板沙箱库（如 Pongo2 的受限模式、Go template lint）来静态检查和限制指令

**代码异味指标：**

- 存在 `template.New().Parse()` 但参数来自用户输入或网络
- 模板字符串通过 `fmt.Sprintf()` / 字符串拼接动态构造
- `.Funcs()` 注册的函数集合中存在 `os.*`、`exec.*`、`reflect.*` 等危险函数
- 执行模板前未对用户输入的模板字符串做任何验证（仅依赖 `template.Parse()` 的语法检查）
- 同时使用了 `{{call}}`、反射和权限操作的模板
- 模板嵌套中使用了用户可控的模板名称

---

## Low risk

以下场景应评为低风险：

1. **预定义模板文件** - 所有模板均来自应用打包的不可修改文件（通过 `ParseFiles()` / `ParseGlob()` 加载固定路径），用户输入仅用于 `Execute()` 的数据参数

2. **数据上下文隔离** - `Execute()` 传入的数据为简单结构体或 map，仅包含基本类型（string、int、bool）或不包含可执行操作的嵌套对象，且无函数指针

3. **受限的 FuncMap** - 注册的模板函数白名单明确且均为无害操作：
   - 字符串处理（`strings.ToLower`、`strings.Replace` 等）
   - 数学计算（`math.Abs`、`math.Max` 等）
   - 格式化（`time.Format`、`strconv.Itoa` 等）
   - 无系统调用、网络操作、反射、文件操作

4. **模板语法受限** - 虽允许用户输入，但通过静态分析工具（如自定义的 AST 检查器）确保模板中不存在 `{{call}}`、`{{range}}`、`{{with}}` 等指令

5. **完全的模板白名单** - 预先编译或缓存所有可能的模板变体（如基于配置或数据库预生成的模板集合），运行时仅从白名单中选择，无新增模板解析

6. **html/template 的 XSS 防护** - 使用 `html/template` 而非 `text/template`，且仅用于生成 HTML 内容，自动转义处理已启用，用户输入与模板逻辑分离
