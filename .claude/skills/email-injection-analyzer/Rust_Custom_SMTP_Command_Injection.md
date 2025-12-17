# Rust Custom SMTP Command Injection

## Details

Rust 应用使用 Lettre 或直接操作 SMTP 连接时，若使用低级 API 手动构建 SMTP 命令且用户输入未经验证，攻击者可注入额外的 SMTP 命令。虽然 Lettre 提供了安全的高级 API，但某些场景下直接操作 SMTP 连接仍存在风险。

**代码示例与审计要点**

```rust
use std::io::Write;
use std::net::TcpStream;

// 危险：直接拼接用户输入到 SMTP 命令
let mut stream = TcpStream::connect("smtp.example.com:25").unwrap();
let mail_from = format!("MAIL FROM:<{}>\r\n", user_email);
stream.write_all(mail_from.as_bytes()).unwrap();

// 危险：自定义 SMTP 命令
let vrfy_cmd = format!("VRFY {}\r\n", user_name);
stream.write_all(vrfy_cmd.as_bytes()).unwrap();

// 危险：使用 Lettre 的 Transport 但未验证参数
use lettre::transport::smtp::client::Tls;
use lettre::transport::smtp::authentication::Credentials;

let creds = Credentials::new(user_email.to_string(), user_password.to_string());
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `TcpStream::connect()`、`.write_all()`、SMTP 端口（25、587、465）
- 查找 SMTP 命令字符串：`MAIL FROM`、`RCPT TO`、`VRFY`、`EXPN`
- 定位字符串拼接：`format!()`、`+` 拼接用户输入
- 检查低级 SMTP 操作而非使用 Lettre 的高级 API

**快速定位保护机制 (L2: 跳读)**
- 检查是否使用 Lettre 的 `SmtpTransport` 而非直接操作连接
- 搜索输入验证：邮箱格式验证、命令参数白名单
- 查找 CRLF 过滤：`.replace("\r", "").replace("\n", "")`
- 查看是否有命令注入防护

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到 SMTP 命令中
   - 使用 `TcpStream` 手动发送包含用户输入的 SMTP 命令
   - 未进行 CRLF 或空格等特殊字符过滤
   - 能通过注入 `\r\n` 执行额外的 SMTP 命令
   - 可能导致 SMTP 命令注入或邮件中继滥用

2. **确认为误报的情况**：
   - 使用 Lettre 的 `SmtpTransport` 高级 API
   - 所有 SMTP 命令参数都经过严格验证和过滤
   - 命令参数来自白名单或硬编码值
   - 不直接操作 TCP 连接

3. **代码异味判断**：
   - 验证不完整：仅检查基本格式未过滤特殊字符
   - 某些代码路径直接使用用户输入
   - 混合使用高级和低级 API

---

## Low risk

**这些情况应给予低风险评级**

1. **高级 API**：使用 Lettre 的 `SmtpTransport` 和 `Message` 构建器，避免手动构建 SMTP 命令

2. **类型安全**：利用 Rust 的类型系统，使用 `Mailbox`、`EmailAddress` 等类型确保数据格式正确

3. **严格过滤**：所有用户输入在拼接到 SMTP 命令前都经过 CRLF、空格、特殊字符过滤

4. **参数验证**：SMTP 命令参数通过白名单验证，仅允许合法的邮箱地址格式

5. **内部使用**：SMTP 客户端仅用于内部系统通信，不接受外部用户输入
