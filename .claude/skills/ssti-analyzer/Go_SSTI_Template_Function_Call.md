# Go_SSTI_Template_Function_Call

**漏洞类型**: Go 模板执行时未限制函数调用，允许执行危险函数

---

## Details

### 代码示例

**易受攻击的代码模式**:
```go
// 注册危险函数到模板
tmpl := template.New("test").Funcs(template.FuncMap{
    "exec": func(cmd string) string {
        out, _ := exec.Command("sh", "-c", cmd).Output()
        return string(out)
    },
})

// 用户可控函数名称
funcName := r.URL.Query().Get("func")
tmpl.Funcs(template.FuncMap{funcName: dangerousFunc})

// 模板中调用系统命令
tpl := `{{exec .UserInput}}`
tmpl.Parse(tpl)
tmpl.Execute(w, data)

// 传递整个 os/exec 包到模板
tmpl.Funcs(template.FuncMap{
    "command": exec.Command,
})

// 用户输入作为函数参数
data := map[string]interface{}{
    "cmd": r.FormValue("command"),
}
tmpl.Execute(w, data)  // 模板中: {{exec .cmd}}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 函数注册: `.Funcs()`, `template.FuncMap{}`
- 危险函数: `exec.Command`, `os.OpenFile`, `ioutil.ReadFile`, `eval`
- 模板包: `text/template`, `html/template`
- 执行方法: `.Execute()`, `.ExecuteTemplate()`
- 用户输入: `r.URL.Query()`, `r.FormValue()`, `r.PostForm`

**L2 跳读定位**:
- 从 `FuncMap` 定义追踪注册的函数实现
- 检查函数是否涉及文件操作、命令执行、网络请求
- 定位模板字符串中 `{{函数名 参数}}` 的调用模式
- 追踪传递给 `.Execute()` 的数据对象来源
- 搜索是否有用户可控的函数名或参数

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 函数白名单: 仅注册安全的格式化、字符串处理函数
- 参数验证: 函数实现中对参数进行严格校验
- 使用 html/template: 自动转义，比 text/template 更安全
- 禁用危险函数: 不注册任何系统调用相关函数
- 输入过滤: 检查传入数据是否经过验证

**L3 逐行分析**:
- FuncMap 安全性:
  - 注册的函数是否仅限于纯计算和格式化
  - 是否包含文件读写、命令执行、网络请求功能
  - 函数参数是否有类型检查和范围限制
- 模板定义检查:
  - 模板是否完全静态定义在代码中
  - 是否允许用户控制模板内容或结构
  - 函数调用的参数是否来自可信数据
- 数据对象验证:
  - 传递给 Execute 的对象是否仅包含基本类型
  - 是否传递了指针、接口或复杂对象
  - 数据来源是否经过验证和类型断言
- html/template vs text/template:
  - html/template 提供自动转义（更安全）
  - text/template 不转义，更易受攻击

**L4 跨模块追踪**:
- 追踪从 HTTP handler → 数据处理 → 模板执行的完整流程
- 检查全局 FuncMap 配置是否在初始化时限定
- 验证是否有中间件层面的输入验证
- 检查模板加载和缓存机制的安全性
- 追踪自定义类型的方法，确认是否可被模板调用

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- FuncMap 中注册了 `exec.Command`、`os.OpenFile` 等危险函数
- 模板函数的参数直接来自用户输入且无验证
- 用户可以控制调用哪个函数或函数名称
- 函数实现中存在命令注入、路径遍历等漏洞
- 使用 text/template 且输出用户可控内容

**误报判定**:
- FuncMap 仅包含纯计算函数如字符串格式化、数学运算
- 所有函数参数都经过严格的白名单验证和类型检查
- 使用 html/template 且函数仅处理安全数据
- 模板完全静态，函数调用的参数都是常量
- 危险函数虽注册但模板中未被使用

**代码异味**:
- FuncMap 中包含文件操作函数但有路径限制
- 使用黑名单过滤函数参数如禁止 `..` 路径
- 虽使用 html/template 但注册了复杂对象方法
- 函数参数虽经验证但验证逻辑不完善
- 在模板中使用 pipeline 组合多个函数调用
- 传递给 Execute 的数据对象包含方法和嵌套结构

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染功能仅限管理员或内部系统使用
- 需要多重身份验证才能访问模板功能
- 功能部署在隔离的内网环境
- 使用严格的基于角色的访问控制

**架构设计防护**:
- 仅注册经过安全审计的纯函数
- 使用 html/template 替代 text/template
- 模板在构建时预编译和验证
- 实现了完整的沙箱环境限制函数能力

**输入与输出保护**:
- 所有函数参数都经过严格的白名单验证
- 数据对象仅包含基本类型，不传递复杂结构
- 函数实现中有完整的错误处理和边界检查
- 输出结果经过二次验证和净化

**监控与运行环保**:
- 应用运行在受限容器中，限制系统调用
- 进程以最低权限用户运行
- 部署了完整的审计日志记录所有模板执行
- 实时监控异常函数调用和错误日志
