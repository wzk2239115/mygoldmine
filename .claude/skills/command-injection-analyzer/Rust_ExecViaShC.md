# Rust 通过 sh -c 执行动态命令注入

**漏洞成因**：使用 `Command::new("sh")` + `.arg("-c")` 方式执行动态拼接的命令字符串，而非使用 `Command::new(program)` + `.args([...])` 的参数化方式，常见于系统级工具开发、CLI 代理、容器编排辅助、日志收集、运维自动化等场景。

---

## Details

**典型代码示例**：
```rust
use std::process::Command;

// 危险：通过 sh -c 执行拼接的命令
let user_input = get_user_input();
Command::new("sh")
    .arg("-c")
    .arg(format!("ls -la {}", user_input))  // 字符串拼接
    .output();

// 危险：使用 /bin/bash -c
Command::new("/bin/bash")
    .arg("-c")
    .arg(&format!("grep {} /etc/hosts", pattern))
    .spawn();

// 危险：宏拼接
let cmd = format!("cat {} | wc -l", file_path);
Command::new("sh").args(&["-c", &cmd]).status();
```

**快速定位核心操作**：
- 关键模式：`Command::new("sh")` / `Command::new("/bin/sh")` / `Command::new("bash")`
- 危险组合：`.arg("-c")` 或 `.args(&["-c", ...])` + 包含 `format!()` / `&format!()` 的参数
- 字符串拼接：`format!("{} {}", cmd, var)`、`&format!(...)`、字符串插值
- 数据流追踪：参数来源为 `env::args()`、`std::io::stdin()`、HTTP 请求体、配置文件外部输入
- Shell 元字符：`;`、`|`、`&`、`&&`、`||`、`$(...)`、`` `...` ``、`\n`、`>`

**快速定位保护机制**：
- 安全模式：直接使用 `Command::new("ls").args(&["-la", user_input])` 而不通过 shell
- 白名单校验：`Regex::new(r"^[a-zA-Z0-9_-]+$").unwrap().is_match()` 或枚举 `match`
- 转义处理：使用 `shell-escape` crate 的 `escape()` 或 `shlex::quote()`
- 参数化：将命令和参数分离，避免字符串拼接
- 命令白名单：通过 `match` 或 `HashMap` 映射预定义命令

**审计等级**：**L3-L4**  
- **L3**：逐行读取 `Command::new("sh")` + `.arg("-c")` 调用上下文，确认参数构造方式
- **L4**：跨模块追踪用户输入从入口（CLI args、HTTP、文件）到命令执行的完整数据流，检查所有校验点

---

## Classify

**确认为漏洞**：
- 外部输入直接或间接参与 `sh -c` 命令字符串的拼接（`format!()` / `&format!()` / `String::push_str()`）
- 未对 shell 元字符进行转义或白名单校验
- 黑名单过滤不完整（仅过滤 `;` 或 `|`，可通过 `\n`、`$(...)` 等绕过）
- 间接拼接：输入先存入 `String` / `Vec<String>` 再传入 `-c` 参数

**误报**：
- 命令字符串完全硬编码，无任何变量参与：`Command::new("sh").arg("-c").arg("ls /tmp")`
- 外部输入仅用作枚举选择器，通过 `match` 映射到预定义命令字符串
- 使用严格正则白名单校验（如 `^[0-9]+$`）或 `shell-escape::escape()` 正确转义
- 直接使用参数数组模式：`Command::new("ls").args(&["-la", user_input])`（无 shell 介入）

**代码异味**：
- 使用黑名单过滤部分特殊字符：`.replace(';', "").replace('|', "")`（可绕过）
- 输入经过简单校验但仍允许路径遍历：`../`、`~`、环境变量 `$HOME`
- 使用 `sh -c` 但业务逻辑可用 Rust 标准库替代（`std::fs`、`std::path`、`walkdir` crate）
- 注释标注 "TODO: 改用参数化" 但未实际修复
- 命令来自配置文件但缺乏格式校验和字段类型约束

---

## Low Risk

以下情况可评为低风险，但仍建议修复：

- **受限执行环境**：Docker 容器无特权模式 + seccomp 策略、SELinux 强制访问控制、Landlock 沙箱
- **最小权限运行**：进程以非 root 用户运行、`capabilities` 受限（无 `CAP_SYS_ADMIN`）、文件系统只读挂载
- **内网隔离接口**：仅限本地 Unix socket、localhost 绑定、VPN 内网访问 + mTLS 认证
- **输入严格限制**：参数长度 `< 16` 字符 + 字符集白名单 `[a-z0-9]` + 枚举值硬编码
- **业务价值低**：开发/测试环境工具、POC 验证代码、已弃用功能、日志分析脚本（只读操作）
- **影响范围小**：仅能执行只读命令（如 `cat`、`grep`、`find`），无网络访问和文件写入权限
- **存在部分防护**：命令执行超时设置（`.timeout()`）、审计日志记录、异常监控告警

**注意**：低风险≠可忽略，Rust 的安全保证主要在内存安全层面，命令注入属于逻辑漏洞范畴。优先建议使用 `Command::new(program).args([...])` 的参数化方式，彻底避免 shell 解析。