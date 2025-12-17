# Go_SSTI_Text_Template_User_Input

**漏洞类型**: 使用 text/template 或 html/template 时用户输入直接嵌入模板内容

---

## Details

### 代码示例

**易受攻击的代码模式**:
```go
// 用户输入直接作为模板内容
import "text/template"
userTemplate := r.URL.Query().Get("template")
tmpl, _ := template.New("user").Parse(userTemplate)
tmpl.Execute(w, data)

// 模板字符串拼接用户输入
tplStr := "Hello, {{." + r.FormValue("field") + "}}"
tmpl, _ := template.New("concat").Parse(tplStr)

// 使用 Must 解析用户可控模板
tmpl := template.Must(template.New("t").Parse(userInput))

// 从用户上传文件加载模板
content, _ := ioutil.ReadFile(uploadedPath)
tmpl.Parse(string(content))

// 传递用户可控的完整结构体
type UserData struct {
    Input interface{}  // 可能包含任意类型
}
data := UserData{Input: r.FormValue("data")}
tmpl.Execute(w, data)
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板包: `text/template`, `html/template`
- 解析函数: `.Parse()`, `.ParseFiles()`, `.ParseGlob()`, `template.Must()`
- 执行函数: `.Execute()`, `.ExecuteTemplate()`
- 用户输入: `r.URL.Query()`, `r.FormValue()`, `r.PostForm`, `r.Body`
- 模板语法: `{{.}}`, `{{.Field}}`, `{{pipeline}}`, `{{range}}`, `{{if}}`

**L2 跳读定位**:
- 从 HTTP handler 追踪用户输入到 `.Parse()` 的参数
- 检查模板字符串是否通过拼接或格式化构造
- 定位传递给 `.Execute()` 的数据对象来源
- 搜索模板文件路径是否包含用户可控部分
- 关注是否有 pipeline 操作或方法调用

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 模板预定义: 模板内容完全硬编码在代码中
- 白名单验证: 模板名称或路径经过白名单检查
- 使用 html/template: 提供自动 HTML 转义
- 数据验证: 传入 Execute 的数据经过类型检查
- 路径限制: 使用 `filepath.Clean()` 和路径前缀检查

**L3 逐行分析**:
- 模板来源:
  - 是否直接接受用户提交的模板字符串
  - 模板是否从固定的文件系统路径加载
  - ParseFiles 的文件名是否用户可控
- 模板类型:
  - text/template 无自动转义（高风险）
  - html/template 自动转义 HTML（相对安全）
  - 模板中是否调用了对象的方法
- 数据对象安全:
  - 传递给 Execute 的是否为简单类型
  - 是否包含指针、接口或嵌套结构
  - 对象是否有可被调用的导出方法
- 模板语法检查:
  - 是否使用了 `{{.}}` 直接输出整个数据
  - 是否有 pipeline 操作符组合多个操作
  - 是否使用了 range、if 等控制结构

**L4 跨模块追踪**:
- 追踪从请求解析 → 中间件 → 模板渲染的完整数据流
- 检查是否有全局模板配置或缓存机制
- 验证模板加载路径的安全策略
- 检查框架或库是否提供了模板安全包装
- 追踪数据对象的构造过程，确认字段来源

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `.Parse()` 的模板参数
- 使用 text/template 且模板结构可被用户控制
- ParseFiles/ParseGlob 的路径参数包含用户输入
- 传递给 Execute 的对象包含用户可控的方法或嵌套对象
- 模板中使用 pipeline 执行用户可控的操作链

**误报判定**:
- 模板完全硬编码，用户仅控制通过 `{{.}}` 输出的简单值
- 使用 html/template 且传递的数据仅为基本类型
- 模板文件路径虽可选但经过严格的白名单验证
- 所有用户输入在传入前经过类型转换和验证
- 模板仅用于纯文本生成，不涉及 HTML 或代码执行

**代码异味**:
- 模板路径通过拼接构造如 `"templates/" + name + ".tmpl"`
- 使用 text/template 但输出内容用于 HTTP 响应
- 传递的数据对象包含导出的方法
- 虽使用 html/template 但数据类型复杂
- 模板中使用了 range 遍历用户可控的切片
- ParseFiles 接受多个文件名且部分来自用户

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板功能仅限管理员或内部系统访问
- 需要强身份验证和授权检查
- 功能部署在隔离的内网环境
- 实施了严格的访问控制策略

**架构设计防护**:
- 强制使用 html/template 替代 text/template
- 所有模板在构建时预编译和缓存
- 模板仅从嵌入的 embed.FS 加载
- 实现了自定义的安全模板包装器

**输入与输出保护**:
- 模板名称经过严格的正则白名单验证
- 传递给 Execute 的数据仅为基本类型
- 模板文件路径使用 filepath.Clean 和前缀检查
- 输出结果经过二次验证和净化

**监控与运行环保**:
- 应用运行在受限容器环境
- 进程以最低权限运行
- 完整的审计日志记录模板执行
- 实时监控异常模板解析和错误
