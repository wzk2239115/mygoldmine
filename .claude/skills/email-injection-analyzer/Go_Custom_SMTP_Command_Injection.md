# Go Custom SMTP Command Injection

## Details

Go 应用使用 `net/smtp.Client` 的低级 API 直接发送 SMTP 命令时，若用户输入未经验证直接拼接到 SMTP 命令中，攻击者可注入额外的 SMTP 命令。虽然 `net/smtp` 对部分命令有验证，但使用 `Text.PrintfLine()` 或直接操作连接时仍存在风险。

**代码示例与审计要点**

```go
import (
    "net/smtp"
    "net/textproto"
)

// 危险：直接拼接用户输入到 SMTP 命令
client, _ := smtp.Dial("smtp.example.com:25")
text := textproto.NewConn(client.Text.Conn)
text.PrintfLine("MAIL FROM:<%s>", userEmail)  // 用户输入
text.PrintfLine("RCPT TO:<%s>", recipientEmail)  // 用户输入

// 危险：自定义 SMTP 命令
cmd := fmt.Sprintf("VRFY %s", userName)  // 用户输入
client.Text.PrintfLine(cmd)

// 危险：使用 Client.Extension 但未验证参数
if ok, _ := client.Extension("AUTH"); ok {
    client.Auth(smtp.PlainAuth("", userEmail, userPassword, "smtp.example.com"))
}
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `smtp.Client`、`smtp.Dial()`、`textproto.NewConn()`
- 查找低级 SMTP 操作：`Text.PrintfLine()`、`Text.Cmd()`
- 定位字符串拼接：`fmt.Sprintf()`、`+` 拼接用户输入
- 检查自定义 SMTP 命令：`VRFY`、`EXPN`、`MAIL FROM`、`RCPT TO`

**快速定位保护机制 (L2: 跳读)**
- 搜索输入验证：邮箱格式验证、命令参数白名单
- 查找 CRLF 过滤：`strings.ReplaceAll()`
- 检查是否使用高级 API：`smtp.SendMail()` 而非低级 Client
- 查看是否有命令注入防护

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到 SMTP 命令中
   - 使用 `Text.PrintfLine()` 或 `Text.Cmd()` 发送包含用户输入的命令
   - 未进行 CRLF 或空格等特殊字符过滤
   - 能通过注入 `\r\n` 执行额外的 SMTP 命令
   - 可能导致 SMTP 命令注入或邮件中继滥用

2. **确认为误报的情况**：
   - 使用高级 API `smtp.SendMail()` 而非直接操作 Client
   - 所有 SMTP 命令参数都经过严格验证和过滤
   - 使用邮件库（`gomail`）封装 SMTP 操作
   - 命令参数来自白名单或硬编码值

3. **代码异味判断**：
   - 验证不完整：仅检查基本格式未过滤特殊字符
   - 某些代码路径直接使用用户输入
   - 混合使用高级和低级 API

---

## Low risk

**这些情况应给予低风险评级**

1. **高级 API**：使用 `smtp.SendMail()` 而非直接操作 `smtp.Client`，避免手动构建 SMTP 命令

2. **邮件库**：使用 `gomail` 或 `github.com/jordan-wright/email` 等库封装 SMTP 操作

3. **严格过滤**：所有用户输入在拼接到 SMTP 命令前都经过 CRLF、空格、特殊字符过滤

4. **参数验证**：SMTP 命令参数通过白名单验证，仅允许合法的邮箱地址格式

5. **内部使用**：SMTP 客户端仅用于内部系统通信，不接受外部用户输入
