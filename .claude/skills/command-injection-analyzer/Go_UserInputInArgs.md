## Go - 用户输入直接作为 exec.Command 参数

**漏洞成因**：将未过滤的用户输入直接作为 `exec.Command` 的参数传递，可能导致命令注入。常见于基础设施管理、CLI 工具封装、容器操作等场景。

### Details

**代码示例**：
```go
import "os/exec"

// 危险：用户输入直接作为参数
cmd := exec.Command("git", "clone", userInput)
cmd.Run()

// 危险：从 HTTP 请求参数构造命令
filename := r.URL.Query().Get("file")
exec.Command("cat", filename).Output()
```

**审计等级**：**L2 - 跳读**

**快速定位核心操作**：
- 搜索关键词：`exec.Command(`、`exec.CommandContext(`
- 重点关注第二个参数及之后的参数来源
- 追踪参数是否来自：HTTP 请求参数(`r.FormValue`、`r.URL.Query`)、用户配置文件、外部 API 响应

**快速定位保护机制**：
- 检查是否存在白名单校验（如 `switch`、`map` 查表）
- 检查是否使用 `filepath.Clean`、`path.Base` 等路径清理
- 检查是否有参数格式校验（正则匹配、类型断言）
- 注意：`strings.Replace` 黑名单过滤不可靠

### Classify

**确认为漏洞**：
- 用户可控参数直接传入 `exec.Command` 且无任何校验
- 参数来自 HTTP/gRPC 请求、WebSocket、数据库查询结果（如用户配置表）
- 保护机制可被绕过（如仅过滤 `;` 但未过滤 `&&`、`|`、换行符）

**误报**：
- 参数经过严格的白名单校验（枚举有限值）
- 参数类型为整数、布尔等非字符串类型且未经字符串拼接
- 硬编码常量或受信任的内部配置

**代码异味**：
- 参数来源不明确，需跨模块追踪（升级为 L4）
- 存在部分校验但不够完善（如长度限制、前缀匹配）
- 使用黑名单过滤但可能存在绕过风险

### Low risk

- 命令执行结果不返回给用户，且执行环境为沙箱/容器
- 参数仅用于文件路径，且已使用 `filepath.Base` 限制在单层目录
- 执行用户为低权限账户，且操作对象为临时文件
- 用户输入经过业务逻辑严格校验（如 UUID、数字 ID）且与实际文件/资源做二次验证