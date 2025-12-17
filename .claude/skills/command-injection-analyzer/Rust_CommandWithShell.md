# Rust Command with Shell 命令注入

**漏洞场景**：系统级工具开发、CLI 代理、容器编排辅助、DevOps 自动化、系统监控、进程管理工具  
**成因**：使用 `std::process::Command` 配合 `sh -c` 执行 shell 命令时，将用户输入拼接到命令字符串中

---

## Details

**典型代码示例**：
```rust
use std::process::Command;

// 危险：通过 sh -c 执行拼接命令
let user_input = args[1];
Command::new("sh")
    .arg("-c")
    .arg(format!("ls -la {}", user_input))
    .output();

// 危险：使用宏拼接
Command::new("sh")
    .arg("-c")
    .arg(&format!("cat {}", file_path))
    .status();

// 危险：字符串拼接后通过 shell 执行
let cmd = format!("ping -c 4 {}", host);
Command::new("sh").args(&["-c", &cmd]).spawn();
```

**快速定位核心操作**：
- 关键标识：`Command::new("sh")` / `Command::new("bash")` / `Command::new("/bin/sh")`
- 配合参数：`.arg("-c")` / `.args(&["-c", ...])` / `.args(["-c".to_string(), ...])`
- 危险拼接：`format!()` / `&format!()` / `String::from()` / `+` / `push_str()`
- 数据流追踪：`env::args()` / `std::io::stdin()` / HTTP 请求体 / 文件读取 / 外部 API
- 特殊字符：`;` / `|` / `&` / `&&` / `||` / `$()` / `` ` `` / `\n` / `>` / `<`

**快速定位保护机制**：
- 检查是否直接传参（安全模式）：`Command::new("ls").arg("-la").arg(user_input)` （无 `-c`）
- 白名单校验：`Regex::new(r"^[a-zA-Z0-9_-]+$")` / `matches!()` / 枚举映射
- 转义处理：`shell-escape` / `shellwords` crate / 自定义转义函数
- 路径规范化：`Path::canonicalize()` / `Path::file_name()` / `PathBuf::push()`
- 输入来源：硬编码常量 / `config.toml` / 数据库 vs 用户可控参数

**审计等级**：**L3-L4**  
- **L3**：逐行分析 `Command::new("sh")` + `.arg("-c")` 的参数构造逻辑，确认拼接方式和数据来源
- **L4**：跨模块追踪从用户输入（CLI args、HTTP 请求、文件读取）到命令执行的完整调用链，检查所有过滤点

---

## Classify

**确认为漏洞**：
- 使用 `sh -c` / `bash -c` 执行命令，且参数包含用户输入
- 通过 `format!()` / `+` / `push_str()` 拼接命令字符串
- 输入来源不可信：`env::args()` / HTTP 请求 / WebSocket / 外部文件 / 环境变量
- 无有效过滤或仅使用不完整黑名单（如只过滤 `;` 但不过滤 `|`、`&&`、换行符）
- 白名单校验存在逻辑缺陷（路径遍历 `../`、Unicode 混淆、二次编码）

**误报**：
- 直接使用 `Command::new()` 传递可执行文件和参数数组，未通过 shell（如 `Command::new("ls").arg(user_input)`）
- 命令字符串完全硬编码，无任何动态部分
- 输入通过严格正则白名单校验（如 `^[a-zA-Z0-9._-]{1,64}$`）
- 输入仅用于选择预定义命令（通过 `match` 枚举映射，键值严格校验）
- 使用 `shell-escape` crate 的 `escape()` 函数正确转义所有参数

**代码异味**：
- 使用 `sh -c` 但业务逻辑可用 Rust 标准库替代（如 `std::fs`、`std::net`、`reqwest`）
- 仅黑名单过滤部分特殊字符（`replace(';', "")` / `replace('|', "")`）
- 输入来源不明确（如从 `Option<String>` / `Result` 解包但未追溯原始来源）
- 使用 `.unwrap()` / `.expect()` 处理命令结果，缺乏错误处理
- 注释标注 "TODO" / "FIXME" / "unsafe workaround" 但长期未修复

---

## Low risk

以下情况可评为低风险，但仍建议修复：
- **受限执行环境**：容器内运行 + Seccomp/AppArmor 配置 + 禁用危险 syscall、`chroot` 沙箱、Landlock LSM
- **内网隔离接口**：仅限本地 Unix Socket / localhost 绑定，无公网暴露
- **权限控制**：进程以非特权用户运行、无 SUID 二进制文件、Capabilities 最小化
- **业务价值低**：测试工具 / 开发环境脚本 / 一次性迁移工具 / 已下线功能
- **影响范围小**：仅能执行只读命令（如 `ls`、`cat`、`grep`），且输出不回显给用户
- **输入长度限制**：`user_input.chars().count() < 16` + 类型强校验（纯数字/字母）
- **部分防护**：命令执行超时 (`timeout` 参数)、审计日志记录、异常监控告警、速率限制

**注意**：低风险≠可忽略，需结合实际部署环境（云 vs 本地）、数据敏感度（是否涉及密钥/PII）和攻击面（公网 vs 内网）综合判断。优先建议使用 `Command::new()` 的参数数组模式。