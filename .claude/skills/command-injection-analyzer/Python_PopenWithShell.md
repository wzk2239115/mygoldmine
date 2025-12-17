# Python - subprocess.Popen(shell=True) 命令注入

## Details

**代码特征：**
```python
subprocess.Popen(cmd, shell=True)
subprocess.Popen(f"command {user_input}", shell=True)
subprocess.Popen("cmd " + variable, shell=True, ...)
```

**审计等级：L3（逐行读）**

**快速定位核心操作：**
- 搜索关键词：`subprocess.Popen`、`shell=True`
- 关注第一个参数是否为字符串拼接或格式化
- 追踪 `cmd`/`command` 变量来源至用户可控输入点（request、argv、input()、文件读取）

**快速定位保护机制：**
- 检查是否使用 `shlex.quote()` 或 `pipes.quote()` 包裹变量
- 检查是否存在白名单校验（正则 `^[a-zA-Z0-9_-]+$`、in 列表）
- 检查 `shell=False` + 列表参数形式（安全实践）
- 注意：黑名单过滤（如过滤 `;|&`）通常可绕过

## Classify

**确认为漏洞：**
- 用户输入直接拼接到命令字符串 + `shell=True`
- 仅有不完整的黑名单过滤（如只过滤空格、分号）
- 路径参数未规范化（可利用 `$(command)` 或 `` `command` ``）

**误报场景：**
- `shell=False` 且参数为列表形式：`Popen(['/bin/ls', user_input])`
- 命令完全硬编码，无任何外部输入
- 使用了 `shlex.quote()` 且无二次解析场景

**代码异味：**
- 输入经过部分清洗但逻辑复杂，难以验证完整性
- 使用了白名单但允许范围过大（如允许 `.` 字符）
- 存在条件分支导致某些路径可能绕过防护

## Low risk

- 命令执行环境为低权限沙箱（容器、受限用户）
- 输入来源为管理员专用接口且有独立身份认证
- 变量仅用于命令参数位置，且已通过严格白名单（`^[a-zA-Z0-9]+$`）
- 业务场景为内部工具，无外网暴露且仅信任用户可访问
