# C_ExecWithUserInput - exec系列函数用户输入注入

**审计等级：L3-L4**

## Details

### 代码特征
```c
// 危险模式：直接传递用户输入
char cmd[256];
sprintf(cmd, "/usr/bin/tool %s", user_input);
execl("/bin/sh", "sh", "-c", cmd, NULL);

// 或使用execv/execvp
char *args[] = {"/bin/sh", "-c", user_cmd, NULL};
execv("/bin/sh", args);
```

### 快速定位技巧
- **核心操作**：关键词 `execl|execle|execlp|execv|execve|execvp|execvpe` + 参数构造处
- **数据流追踪**：回溯参数来源 → 网络输入/文件读取/环境变量/命令行参数
- **shell调用识别**：检查是否调用 `/bin/sh`、`sh -c`、`bash -c` 等shell解释器
- **拼接操作**：定位 `sprintf|snprintf|strcat|strcpy` 等字符串拼接点

### 保护机制识别
- **白名单校验**：检查参数是否经过 `strcmp/strncmp` 与预定义值比对
- **字符过滤**：查找 `strchr/strpbrk` 检测特殊字符 `; | & $ \` ' "`
- **非shell调用**：使用 `execv("/bin/tool", args)` 直接执行而非通过shell
- **参数化传递**：将用户输入作为独立参数传递，避免字符串拼接

## Classify

### ✅ 确认漏洞
- 用户可控数据直接拼接到命令字符串中，无任何过滤
- 通过 `-c` 参数调用shell执行拼接后的命令
- 用户输入包含路径/命令/参数部分

### ⚠️ 代码异味
- 存在基础过滤但不完整（仅过滤部分特殊字符）
- 使用黑名单方式过滤（易绕过）
- 白名单校验逻辑存在缺陷（如大小写不敏感、通配符匹配）

### ❌ 误报
- 参数完全硬编码，无外部输入
- 严格白名单校验后调用（如枚举值映射）
- 使用 `execv` 直接执行且参数列表完全可控

## Low risk

- 命令执行位于低权限进程中，已通过 `setuid/setgid` 降权
- 执行环境已通过 `chroot` 隔离
- 用户输入仅影响命令参数而非命令本身，且参数用途受限（如文件路径但有chroot）
- 内部管理工具，仅限信任用户访问且有完整审计日志