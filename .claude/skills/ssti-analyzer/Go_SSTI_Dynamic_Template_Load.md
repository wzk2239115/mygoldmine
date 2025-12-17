# Go_SSTI_Dynamic_Template_Load

**漏洞类型**: 动态加载模板时路径参数用户可控，导致任意模板包含或路径遍历

---

## Details

### 代码示例

**易受攻击的代码模式**:
```go
// 直接使用用户输入作为模板文件名
templateName := r.URL.Query().Get("template")
tmpl, _ := template.ParseFiles("templates/" + templateName + ".tmpl")

// ParseGlob 使用用户可控模式
pattern := r.FormValue("pattern")
tmpl, _ := template.ParseGlob("templates/" + pattern)

// 从用户指定路径加载
filePath := r.PostForm.Get("file")
tmpl, _ := template.ParseFiles(filePath)

// 使用 Lookup 查找用户指定模板
tmplName := r.Header.Get("X-Template")
tmpl.Lookup(tmplName).Execute(w, data)

// 拼接多个用户可控路径
files := []string{
    "header.tmpl",
    r.URL.Query().Get("body") + ".tmpl",
    "footer.tmpl",
}
tmpl, _ := template.ParseFiles(files...)
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 文件解析: `.ParseFiles()`, `.ParseGlob()`, `.ParseFS()`
- 模板查找: `.Lookup()`, `.DefinedTemplates()`, `.Templates()`
- 路径操作: `filepath.Join()`, string concatenation with `/`
- 用户输入: `r.URL.Query()`, `r.FormValue()`, `r.PostForm`, `r.Header`
- 文件读取: `ioutil.ReadFile()`, `os.ReadFile()`, `fs.ReadFile()`

**L2 跳读定位**:
- 从 HTTP handler 追踪到 ParseFiles/ParseGlob 的参数
- 检查模板文件路径是否通过字符串拼接构造
- 定位 Lookup 的模板名称是否来自用户输入
- 搜索文件路径构造中是否有用户可控部分
- 关注是否有路径验证或清理逻辑

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 路径白名单: 检查模板名称是否在预定义列表中
- 路径清理: 使用 `filepath.Clean()`, `filepath.Base()`
- 前缀检查: 验证路径是否在允许的目录下
- embed.FS: 使用嵌入文件系统，不从磁盘动态加载
- 文件名验证: 正则表达式或字符白名单验证

**L3 逐行分析**:
- 路径构造方式:
  - 是否直接拼接用户输入如 `"dir/" + input`
  - 是否使用 filepath.Join（仍需验证）
  - 是否检查和清理 `..` 路径遍历
- 文件加载方法:
  - ParseFiles 接受的文件列表来源
  - ParseGlob 的 pattern 是否用户可控
  - ParseFS 使用的 fs.FS 是否受限
- 模板名称验证:
  - Lookup 的名称是否经过白名单检查
  - 是否允许访问所有已解析的模板
  - DefinedTemplates 返回值是否泄露模板信息
- 路径安全检查:
  - 是否使用 filepath.Clean 清理路径
  - 是否验证路径前缀在允许目录内
  - 是否检查文件是否实际存在且可读

**L4 跨模块追踪**:
- 追踪从请求 → 路由 → 模板加载的完整流程
- 检查是否有全局配置限制模板目录
- 验证文件系统访问权限和目录结构
- 检查是否使用了安全的模板管理器
- 追踪模板缓存机制，确认是否可被污染

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 模板文件路径直接或部分由用户输入构造
- ParseFiles/ParseGlob 的参数包含未验证的用户输入
- 未检查路径遍历如 `../../../etc/passwd`
- Lookup 可以访问任意已解析的模板
- 用户可以通过路径访问系统敏感文件

**误报判定**:
- 模板名称经过严格的白名单验证
- 使用 embed.FS 仅从嵌入资源加载模板
- 路径使用 filepath.Base 提取文件名并白名单验证
- 所有文件路径都有前缀检查确保在允许目录内
- 模板完全在初始化时加载，运行时不接受用户输入

**代码异味**:
- 路径使用 filepath.Join 但未做前缀验证
- 使用黑名单过滤如禁止 `..` 但可被绕过
- 模板目录虽受限但包含敏感配置文件
- Lookup 虽验证名称但模板集合过大
- ParseGlob 的 pattern 虽受限但仍可能匹配意外文件
- 文件路径验证使用字符串比较而非规范化后比较

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板选择功能仅限管理员访问
- 需要多重身份验证和授权
- 功能部署在隔离的内部网络
- 实施了严格的基于角色的访问控制

**架构设计防护**:
- 强制使用 embed.FS 从嵌入资源加载模板
- 所有模板在构建时预加载和验证
- 实现了自定义的安全模板加载器
- 模板文件与应用代码打包，不从外部加载

**输入与输出保护**:
- 模板名称经过严格的字母数字白名单验证
- 使用 filepath.Base + 白名单双重验证
- 路径规范化后检查前缀确保在允许目录
- 文件访问前验证文件类型和扩展名

**监控与运行环保**:
- 应用运行在只读文件系统的容器中
- 模板目录权限严格限制
- 完整的审计日志记录所有模板加载
- 实时监控异常路径访问和错误日志
