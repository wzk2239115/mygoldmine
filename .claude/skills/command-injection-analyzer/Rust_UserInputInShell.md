# Rust Command::new() 用户输入直接嵌入 Shell 命令

**漏洞成因**：在构造 `std::process::Command` 时，将未过滤的用户输入直接拼接到 shell 命令字符串或通过 `sh -c` 执行，常见于系统级工具开发、CLI 代理、容器编排辅助、自动化运维脚本等业务场景。

---

## Details

**典型代码模式**：
```rust
use std::process::Command;

// 危险：通过 sh -c 执行拼接命令
let user_input = req.param("file").unwrap();
Command::new("sh")
    .arg("-c")
    .arg(format!("cat {}", user_input))
    .output();

// 危险：直接拼接到命令参数
Command::new("bash")
    .arg("-c")
    .arg(&format!("ls -la {}", path))
    .spawn();

// 危险：动态命令字符串
let cmd = format!("ping -c 4 {}", host);
Command::new("sh").arg("-c").arg(cmd).status();
```

**快速定位核心操作**：
- 关键词：`Command::new(`、`use std::process::Command`、`.arg("-c")`、`sh`、`bash`、`cmd.exe`
- 重点模式：`Command::new("sh")` + `.arg("-c")` + `format!()` / `&format!()` 宏拼接
- 查看参数拼接方式：`format!()`、`&format!()`、字符串 `+` 连接、`concat!()`
- 追踪数据流：用户输入 → 字符串处理（`trim()`、`replace()`） → `Command` 构造
- 特殊字符关注：`;`、`|`、`&`、`&&`、`||`、`$(...)`、`` `...` ``、`\n`、`$()`

**快速定位保护机制**：
- 是否直接使用参数化调用：`Command::new("ls").arg("-la").arg(user_path)`（无 shell 中介）
- 是否存在白名单校验：`match`、`if let`、`regex::Regex`、`lazy_static!` 定义允许值
- 是否使用转义库：`shell-escape` crate 的 `escape()` 函数
- 是否限制可执行命令：`Path::canonicalize()` 规范化路径、`starts_with()` 限定目录
- 是否使用 `OsStr` / `OsString` 而非 `String`（降低注入风险）

**审计等级**：**L3-L4**  
- **L3**：逐行读取 `Command::new()` 调用及其 `.arg()` 链，确认是否经过 shell 中介和参数来源
- **L4**：跨模块追踪用户输入到 `Command` 构造的完整数据流，检查所有转换函数和校验逻辑

---

## Classify

**确认为漏洞**：
- 用户输入通过 `format!()`、`&format!()` 或字符串拼接嵌入命令字符串
- 使用 `sh -c`、`bash -c`、`cmd /c` 模式且命令参数包含外部输入
- 未对特殊字符进行转义或白名单校验
- 白名单校验存在逻辑缺陷（路径遍历 `../`、通配符 `*`、空字符注入）
- 过滤不完整（仅黑名单部分特殊字符，可通过其他字符绕过）

**误报**：
- 命令字符串完全硬编码，无任何动态部分
- 直接参数化调用：`Command::new("executable").arg(user_input)`（无 shell 层）
- 用户输入仅用于选择预定义命令（通过 `match` 或 `HashMap` 映射，键值严格校验）
- 存在严格的正则白名单：`Regex::new(r"^[a-zA-Z0-9_-]+$")` 且校验失败时拒绝执行
- 使用 `shell-escape::escape()` 或等价转义机制包装所有外部输入

**代码异味**：
- 使用 shell 中介但业务逻辑可直接调用可执行文件
- 黑名单过滤不完整（如 `.replace(";", "")` 但未处理 `|`、`&`、换行符）
- 输入来源注释不明确（无法判断是配置常量还是用户可控）
- 存在 `TODO` / `FIXME` 注释提及需要修复但未实施
- 权限控制依赖外部系统但代码中无明确校验

---

## Low Risk

以下情况可评为低风险，但仍建议修复：
- **受限执行环境**：容器内无特权运行、seccomp 限制 `execve` 族系统调用、SELinux 强制访问控制
- **内网隔离接口**：仅限内网/管理员访问，有二次认证（TOTP、证书认证、堡垒机跳转）
- **业务价值低**：开发/测试环境、demo 代码、已下线功能、本地工具脚本
- **影响范围小**：仅能执行只读命令（如 `ls`、`cat`、`grep`），进程以低权限用户运行
- **存在部分防护**：输入长度限制（如 `&input[..20]`）、命令执行超时 `timeout(Duration)`、审计日志记录
- **编译时约束**：使用 `const` 泛型参数限定命令类型，或 `typed-builder` 强制分离命令与参数

**注意**：低风险≠可忽略，需结合实际部署环境（特权容器、共享主机）、数据敏感度和攻击面综合判断。优先建议改用直接参数化调用或白名单映射。