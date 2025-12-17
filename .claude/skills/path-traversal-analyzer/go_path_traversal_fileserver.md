# Go 路径遍历与文件包含漏洞

## Details

### 漏洞成因
Go 后端常使用 `http.FileServer`, `http.ServeFile`, `os.Open`, `ioutil.ReadFile`, `template.ParseFiles` 等 API 提供静态文件、日志下载或模板渲染。如果直接拼接来自 URL 的路径（如 `r.URL.Query().Get("file")`）并传递给文件系统调用，而未进行 `filepath.Clean` 和根目录校验，攻击者可利用 `../`、`..\\`, `%2e%2e/`, 甚至 Windows 驱动器前缀实现目录穿越，读取敏感文件或覆盖目标。若自定义模板加载器支持远程 URL，还可能造成 RFI。`archive/zip`、`tar` 解压时若不检查 `Clean` 后路径，同样会被符号链接或绝对路径绕过。

### 代码示例

**易受攻击的代码（ServeFile）：**
```go
func downloadLog(w http.ResponseWriter, r *http.Request) {
    name := r.URL.Query().Get("name")
    // name=../../../../etc/passwd
    path := "/var/app/logs/" + name
    http.ServeFile(w, r, path) // 未 Clean + 前缀校验
}
```

**自定义文件读取：**
```go
func readConfig(w http.ResponseWriter, r *http.Request) {
    filename := r.FormValue("config")
    data, err := os.ReadFile("/etc/app/" + filename)
    if err != nil {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    w.Write(data)
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件访问：`os.Open`, `os.ReadFile`, `os.WriteFile`, `ioutil.ReadFile`, `http.ServeFile`
- 路径处理：`filepath.Join`, `filepath.Clean`, `path.Join`, `path.Clean`
- 静态服务：`http.FileServer`, `http.StripPrefix`, `fs.Sub`
- 模板加载：`template.ParseFiles`, `template.ParseGlob`
- 解压：`zip.NewReader`, `tar.NewReader`, `io.Copy` + 创建文件

**定位步骤：**
1. 搜索上述函数，查看是否直接使用 `r.URL`, `r.FormValue`, `mux.Vars` 等输入。
2. 关注 `FileServer` 包装逻辑、API 返回文件、管理后台导入导出。
3. 跳读（L2）检查是否调用 `filepath.Clean` 并对结果做根目录比较。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径规范化：** `filepath.Clean`, `filepath.Abs`
- **根目录校验：** 比较 `strings.HasPrefix(cleaned, base)` 或使用 `filepath.Rel`
- **文件系统封装：** 使用 `embed.FS`, `fs.Sub` 限制访问范围
- **符号链接检查：** `os.Lstat` 避免跟随不可信 symlink
- **上传解压保护：** 对 `zip.File.Name`、`header.Name` 做 Clean + 前缀校验

**定位技巧：**
- 确认使用的是 `filepath.Clean` 而非 `path.Clean`（后者不处理 Windows 分隔符）。
- 检查 `filepath.Rel` 返回错误时是否中止。
- 对 `FileServer` 自定义处理，确认是否存在路径穿透（如错误 `StripPrefix`）。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 `fs.Sub` 或 embedStrict | **L0（快速跳过）** | 目录范围受限 |
| `Clean` + `Rel` 校验 | **L2（跳读）** | 检查异常处理是否完整 |
| 直接拼接请求参数 | **L3（逐行读）** | 高风险，需要跟踪 |
| 涉及解压/模板远程加载 | **L4（跨模块追踪）** | 需跨函数分析 |

## Classify

### 研判标准

#### 确认漏洞
判定为漏洞需要满足：
1. **用户输入控制路径。**
2. **缺乏 `Clean` + 根目录校验或白名单。**
3. **可访问敏感文件或写入未授权位置。**

#### 误报
可视为误报的情况：
1. **输入通过白名单枚举映射。**
2. **`filepath.Clean` 并结合 `Rel` 验证，异常即拒绝。**
3. **访问目录仅包含公开内容且部署隔离。**

#### 代码异味
需记录的隐患：
1. **仅依赖字符串替换 `../`。**
2. **Clean 后未使用返回值。**
3. **未考虑 Windows/Unix 分隔符差异。**
4. **`FileServer` 直接暴露绝对目录，无额外限制。**

## Low risk

### 低风险评级场景

#### 1. 内部运维接口
- **场景：** API 仅供内部认证用户使用。
- **风险评估：** 攻击面小，但需防凭证泄露。

#### 2. 只读公开资源
- **场景：** 提供公共文档/图片访问。
- **风险评估：** 影响有限，但可能泄露结构。

#### 3. 容器化部署隔离
- **场景：** 服务运行在只包含少量文件的容器。
- **风险评估：** 越权影响有限，仍需修复。

#### 4. 文件系统访问控制
- **场景：** 使用 AppArmor/SELinux 限制进程访问。
- **风险评估：** 降低危害但不是最终方案。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 高可信内部接口 | 攻击面小 | 中 |
| `Clean` + `Rel` 校验 | 技术封堵遍历 | 低 |
| 容器隔离/最小根文件系统 | 限制影响面 | 中 |
| 强制访问控制 (MAC) | 外部防护 | 高（继续推进修复）|

