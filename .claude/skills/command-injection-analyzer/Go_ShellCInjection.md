# Go Shell 命令注入 (sh -c / bash -c)

**漏洞场景**：基础设施管理、CLI工具封装、容器操作、日志分析脚本、批处理任务等

---

## Details

**典型代码模式**：
```go
// 危险：字符串拼接
cmd := exec.Command("sh", "-c", "ls " + userInput)
cmd := exec.Command("bash", "-c", fmt.Sprintf("cat %s", filename))
cmd := exec.Command("/bin/sh", "-c", cmdStr) // cmdStr包含外部输入
```

**核心定位技巧**：
- 关键API：`exec.Command()` / `exec.CommandContext()`
- shell标识：第一参数为 `sh` / `bash` / `/bin/sh` / `/bin/bash`，第二参数为 `-c`
- 危险操作：第三参数使用 `+`、`fmt.Sprintf`、字符串模板拼接外部数据

**保护机制定位**：
- 检查是否使用 `shellescape.Quote()` / `shlex.Quote()` 包装输入
- 查找白名单校验：`regexp.MatchString()`、`strings.Contains()`、硬编码允许值
- 确认输入来源：内部配置/文件内容 vs HTTP参数/环境变量/用户输入

**审计等级**：**L3-L4**（逐行读/跨模块追踪）  
理由：需追溯参数来源、确认是否经过净化、评估业务上下文

---

## Classify

| 分类 | 判定条件 |
|------|---------|
| **真实漏洞** | ① 输入来自外部（HTTP参数、WebSocket消息、文件上传路径、环境变量）<br>② 直接拼接到命令字符串<br>③ 无有效过滤或白名单限制 |
| **误报** | ① 参数为硬编码常量<br>② 输入已通过严格正则校验（如`^[a-zA-Z0-9_-]+$`）<br>③ 命令字符串完全可控（如内部配置文件） |
| **代码异味** | ① 输入虽来自内部但缺乏文档说明<br>② 使用弱校验（仅过滤 `;` `\|` `&`）<br>③ 可用 `exec.Command(cmd, arg1, arg2)` 替代但用了shell |

---

## Low risk

**降级评估条件**：
1. **受限运行环境**：容器内无敏感文件、SELinux强制模式、沙箱执行
2. **输入长度限制**：参数长度<20字符且校验字符类型
3. **最小权限**：进程以nobody用户运行、chroot隔离
4. **业务特性**：开发/测试环境专用工具、需要管理员权限才能触发
5. **部分防护**：虽可绕过但需要复杂前置条件（如需先通过认证+CAPTCHA）

**注意**：低风险≠无风险，仍应在审计报告中标注，建议修改为参数数组模式。