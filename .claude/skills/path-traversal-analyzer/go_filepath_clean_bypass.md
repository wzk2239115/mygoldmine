# Go filepath.Clean 绕过导致路径遍历

**漏洞成因**：通过 `os.Open` / `os.ReadFile` / `ioutil.ReadFile` 访问用户指定路径时，仅依赖 `filepath.Clean` 做路径规范化，但未验证最终路径是否在预期根目录内，导致可遍历任意文件。

---

## Details

### 代码示例

**典型易受攻击模式**：

```go
func GetLogFile(userPath string) ([]byte, error) {
    cleanPath := filepath.Clean(userPath)
    // 危险：Clean 只规范化，不限制边界
    return os.ReadFile(filepath.Join("/var/logs", cleanPath))
}
// 输入: ../../../../etc/passwd
// 实际访问: /etc/passwd
```

```go
func LoadConfig(filename string) (*Config, error) {
    safePath := filepath.Clean(filename)
    // 危险：未检查是否包含 ..
    data, err := ioutil.ReadFile("./configs/" + safePath)
    if err != nil {
        return nil, err
    }
    return parseConfig(data), nil
}
```

```go
// 危险：Web 路由直接拼接用户输入
http.HandleFunc("/download", func(w http.ResponseWriter, r *http.Request) {
    file := r.URL.Query().Get("file")
    cleanFile := filepath.Clean(file)
    data, _ := os.ReadFile(filepath.Join(baseDir, cleanFile))
    w.Write(data)
})
```

### 快速定位核心操作技巧（L1-L2）

**关键函数调用链**（L1: 关键词扫描）：
- `os.Open` / `os.ReadFile` / `ioutil.ReadFile` / `os.OpenFile`
- `filepath.Join` + 外部输入参数
- `http.ServeFile` / `http.FileServer` 配合自定义路径处理

**核心操作识别**（L2: 跳读）：
1. 查找文件操作函数，回溯第一个参数来源
2. 检查参数是否来自 HTTP 请求（`r.URL.Query()` / `mux.Vars()` / 请求体解析）
3. 关注路径拼接逻辑：`filepath.Join(baseDir, userInput)` / 字符串拼接 `baseDir + userInput`
4. 确认是否仅有 `filepath.Clean` 而无边界检查

**特征模式**：
- `filepath.Clean(req.FormValue("path"))` 后直接文件操作
- `filepath.Join(root, filepath.Clean(user_input))` 但未验证结果是否以 `root` 为前缀
- Gin/Echo 框架：`c.Param("file")` / `c.Query("file")` 直接传入文件操作

### 快速定位保护机制技巧（L2-L3）

**有效防护特征**（L2: 跳读）：
- `strings.HasPrefix(cleanPath, baseDir)` 检查前缀
- `filepath.Rel(baseDir, finalPath)` 返回相对路径后检查是否包含 `..`
- `strings.Contains(path, "..")` 在 Clean 之后仍拒绝
- 自定义白名单：`allowedFiles = map[string]bool{"app.log": true}`

**审计要点**（L3: 逐行读）：
1. **Clean 顺序**：必须先 `Clean` 再检查，检查后再拼接则无效
2. **符号链接**：即使检查路径，符号链接仍可绕过（需 `filepath.EvalSymlinks` + 边界验证）
3. **Join 后验证**：`finalPath := filepath.Join(base, clean); if !strings.HasPrefix(finalPath, base)` 才有效
4. **空路径陷阱**：`filepath.Clean("")` 返回 `.`，拼接后可能暴露当前目录

**L4 跨模块追踪场景**：
- 中间件解析路径参数存储到 `context.Context`，业务层直接使用
- 配置文件指定 `baseDir`，需追踪配置加载逻辑确认是否可控
- 封装的文件服务模块，需检查导出函数是否做验证

---

## Classify

**漏洞判定条件**（同时满足）：
1. 用户可控的路径参数传递到文件系统操作函数
2. 仅使用 `filepath.Clean` 做处理，或 `Clean` 后未做边界验证
3. 可访问到敏感文件（`/etc/passwd` / 配置文件 / 其他用户数据）

**误报场景**：
- 路径拼接前已有硬编码白名单映射（如 `map["log1"] -> "/var/app/log1.txt"`）
- 使用 `filepath.Rel` 并检查返回值不包含 `..` 且无错误
- 文件操作前有 `filepath.HasPrefix` 或等效边界验证，且验证逻辑正确（Clean 后检查）
- 访问范围已被 chroot 或容器文件系统隔离限制

**代码异味**（潜在风险）：
- `filepath.Clean` 存在但未配合边界检查（防御意识不足）
- 路径拼接使用字符串 `+` 而非 `filepath.Join`（可能跨平台问题）
- 错误处理缺失，泄露路径信息到错误响应
- 同时存在路径过滤和文件操作，但过滤逻辑复杂且未单元测试覆盖

---

## Low risk

**降低风险评级的情况**：

1. **访问范围受限**：
   - 可遍历文件均为日志或公开资源，不包含敏感信息
   - 文件读取后仅返回统计信息（文件大小/行数），不返回内容
   - 目标目录已通过操作系统权限严格限制（仅包含非敏感文件）

2. **输入约束有效**：
   - 路径参数有严格的正则校验（如 `^[a-zA-Z0-9_-]+\.log$`）禁止 `/` 和 `.`
   - 业务逻辑限制仅支持文件名（不含路径分隔符），虽不完美但显著降低风险
   - 使用枚举值映射，虽映射后仍有 Clean 操作，但用户无法直接控制完整路径

3. **部署环境缓解**：
   - 应用运行在严格的容器/沙箱环境，文件系统访问被 AppArmor/SELinux 限制
   - 敏感文件已移除或不在同一文件系统挂载点

4. **低权限运行**：
   - 进程以低权限用户运行，无法读取关键系统文件
   - 已确认目标系统无高价值文件可被遍历（需结合实际部署验证）

**注意**：以上情况降低利用价值，但不改变漏洞存在的事实，建议仍应修复根本原因。