# Go text/html template 模板文件本地文件包含

## Details

### 漏洞成因

Go 标准库的 `html/template` 和 `text/template` 包提供了强大的模板功能。当应用使用 `template.ParseFiles()` 或 `template.ParseGlob()` 时，若文件路径由用户输入控制且未做白名单或路径规范化，攻击者可加载并渲染任意模板文件。结合模板注入（SSTI），可能导致信息泄露或远程代码执行。此漏洞常见于多用户系统、SaaS 应用、模板自定义系统。

### 代码示例

**易受攻击的代码（ParseFiles）：**
```go
package main

import (
	"html/template"
	"net/http"
)

func renderTemplate(w http.ResponseWriter, r *http.Request) {
	templateName := r.URL.Query().Get("tpl")  // tpl=../../etc/passwd
	templatePath := "templates/" + templateName + ".html"

	tmpl, err := template.ParseFiles(templatePath)
	if err != nil {
		http.Error(w, "Template not found", 404)
		return
	}

	tmpl.Execute(w, nil)
}
```

**ParseGlob 风险版本：**
```go
func renderWithGlob(w http.ResponseWriter, r *http.Request) {
	templateDir := r.URL.Query().Get("dir")  // dir=../../
	pattern := templateDir + "*.html"

	tmpl, err := template.ParseGlob(pattern)  // 可加载任意目录的模板
	if err != nil {
		http.Error(w, "Error", 500)
		return
	}

	tmpl.ExecuteTemplate(w, "index.html", nil)
}
```

**嵌套模板包含：**
```go
func loadTemplate(w http.ResponseWriter, r *http.Request) {
	basePath := "templates/"
	templateName := r.FormValue("template")  // template=../../config.html

	// ParseFiles 可能包含 {{define}} 中的文件路径
	tmpl, _ := template.ParseFiles(basePath + templateName)
	tmpl.Execute(w, nil)
}
```

**管理后台模板编辑：**
```go
func editTemplate(w http.ResponseWriter, r *http.Request) {
	// 用户可编辑任意模板文件
	templatePath := r.FormValue("path")  // path=../../app_config.html
	content := r.FormValue("content")

	// 直接写入用户指定路径
	ioutil.WriteFile(templatePath, []byte(content), 0644)
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）

**关键词扫描：**
- 模板加载：`template.ParseFiles()`, `template.ParseGlob()`, `template.Parse()`
- 目录访问：`filepath.Join()`, `filepath.Glob()`, `os.DirFS()`
- 执行模板：`Execute()`, `ExecuteTemplate()`
- 文件操作：`ioutil.WriteFile()`, `os.Create()`
- 输入源：`r.URL.Query()`, `r.FormValue()`, `r.Header.Get()`

**定位步骤：**
1. 搜索 `ParseFiles`、`ParseGlob` 等函数，检查参数中是否有变量。
2. 追踪变量来源：HTTP 请求、配置文件。
3. 检查是否有路径过滤或白名单。
4. 关注嵌套模板的 `{{define}}` 和 `{{include}}` 指令。

#### 保护机制定位（审计等级：L2-L3）

**检查是否存在：**
- **白名单验证：** 允许加载的模板列表
- **路径规范化：** `filepath.Clean()`, `filepath.Abs()` 规范化路径
- **前缀校验：** 规范化后检查 `strings.HasPrefix()` 固定目录
- **禁用不安全指令：** 模板是否禁用了 `define`, `include` 等
- **符号链接检查：** `os.Lstat()` 检测符号链接

**定位技巧：**
- 确认 `ParseFiles()` 的路径是否来自用户输入。
- 检查是否使用了 `filepath.Join()` 的绝对路径绕过。
- 验证 `ExecuteTemplate()` 时的模板名称是否检查。
- 查看模板内容是否包含用户输入且未转义。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单模板列表 | **L0（快速跳过）** | 用户输入仅为键值 |
| 路径规范化 + 前缀校验 | **L2（跳读）** | 确认校验逻辑完备 |
| 直接拼接用户输入 | **L3（逐行读）** | 极高风险 |
| 模板可编辑 + 执行 | **L4（跨模块追踪）** | SSTI + RCE |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **模板路径由用户输入控制**。
2. **缺乏路径规范化或白名单验证**。
3. **能够加载敏感文件或模板内容可控**。

#### 误报

可视为误报的情况：
1. **模板名称仅用于索引白名单字典**，返回固定模板。
2. **路径经过规范化并检查前缀**。
3. **模板目录由框架固定控制，不受用户输入影响**。

#### 代码异味

需记录的潜在问题：
1. **使用 `ParseGlob()` 与用户可控的目录**。
2. **模板内容包含用户输入且未转义**（SSTI）。
3. **允许用户编辑模板文件**。
4. **符号链接未检查**，可指向任意文件。
5. **错误处理泄露路径信息**。

## Low risk

### 低风险评级场景

#### 1. 白名单模板列表 + 固定扩展名

- **场景：** 只允许加载预定义模板，强制 `.html` 扩展名。
- **风险评估：** 防护有效，但需定期审查白名单。

#### 2. 受限模板目录 + 路径规范化

- **场景：** 模板只能从固定目录加载，使用 `filepath.Clean()` + 前缀检查。
- **风险评估：** 防护层次清晰，但需验证规范化逻辑。

#### 3. 只读模板 + 完整转义

- **场景：** 模板文件只读，模板内容不包含用户输入或完全转义。
- **风险评估：** 危害有限，但仍可能泄露文件内容。

#### 4. 受控后台操作

- **场景：** 模板编辑功能仅对管理员开放，需要多重认证。
- **风险评估：** 攻击面小，但管理员账号泄露仍会导致问题。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 白名单模板 | 限制加载范围 | 低 |
| 路径规范化 + 前缀检查 | 有效防护 | 低 |
| 符号链接检查 | 深度防御 | 低 |
| 管理员限定 | 攻击面小 | 中 |
