# Go - exec.Command 字符串拼接命令注入

**场景：** 基础设施管理、CLI 工具封装、容器操作、运维脚本  
**成因：** 将用户输入作为完整命令字符串传递，而非使用参数列表隔离

---

## Details

**典型代码示例：**
```go
// 危险模式：通过 sh -c 执行拼接字符串
cmd := exec.Command("sh", "-c", "ls " + userInput)

// 或使用 bash -c
cmd := exec.Command("bash", "-c", fmt.Sprintf("curl %s", url))
```

**审计等级：L2 (跳读)**

**快速定位核心操作：**
- 搜索关键词：`exec.Command("sh"`, `exec.Command("bash"`, `"/bin/sh"`, `"-c"`
- 关注第三个参数是否为字符串拼接：`+`、`fmt.Sprintf`、`strings.Join`
- 追踪拼接字符串中的变量来源（参数、HTTP请求、文件读取等）

**快速定位保护机制：**
- 检查是否使用白名单验证：`regexp.MatchString`、`switch/case` 枚举
- 检查是否使用 `shellescape.Quote()` 或 `strconv.Quote()` 转义
- 检查是否限制字符集：`strings.ContainsAny(input, ";|&$")`

---

## Classify

**✓ 确认漏洞：**
- 用户输入直接拼接到 shell 命令字符串中，且无任何过滤
- 通过 `-c` 参数执行拼接的字符串命令
- 输入来源不可信（HTTP参数、WebSocket、外部文件等）

**△ 代码异味：**
- 输入经过部分过滤（如仅过滤空格），但未覆盖所有特殊字符
- 使用黑名单过滤（易绕过）
- 仅验证输入长度或格式，未验证内容

**✗ 误报：**
- 使用正确的参数数组模式：`exec.Command("ls", "-l", userInput)` （无 `-c`）
- 输入经过严格白名单验证（如仅允许 `[a-zA-Z0-9_-]`）
- 输入为硬编码常量或来自可信配置文件

---

## Low risk

**以下情况评为低风险：**
- 命令执行在受限容器/沙箱环境中（Docker、gVisor）
- 程序以低权限用户运行且已禁用提权路径
- 输入长度被严格限制（如 < 10 字符），且已过滤部分特殊字符
- 仅影响当前用户数据，无横向移动风险
- 业务场景为内网工具，仅管理员可访问且有操作日志
- 输入来源虽不可信，但后续通过 `filepath.Clean()` + 路径前缀检查限制为文件名
