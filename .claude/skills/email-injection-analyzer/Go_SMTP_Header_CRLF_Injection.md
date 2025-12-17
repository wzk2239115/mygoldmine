# Go SMTP Header CRLF Injection

## Details

Go 标准库 `net/smtp` 和 `net/mail` 包在构建 SMTP 命令和邮件头时，若用户输入包含 CRLF 字符（`\r\n`）未被过滤，攻击者可注入额外的邮件头或 SMTP 命令。虽然 Go 的 `net/smtp` 对部分命令有验证，但自定义邮件头构建时仍存在风险。

**代码示例与审计要点**

```go
import (
    "net/smtp"
    "net/mail"
)

// 危险：直接使用用户输入构建邮件头
from := mail.Address{Name: userName, Address: userEmail}
to := mail.Address{Name: "", Address: recipientEmail}
headers := make(map[string]string)
headers["From"] = from.String()
headers["To"] = to.String()
headers["Subject"] = userSubject  // 用户输入
headers["X-Custom"] = userHeader  // 用户输入

// 构建邮件
message := ""
for k, v := range headers {
    message += fmt.Sprintf("%s: %s\r\n", k, v)
}
message += "\r\n" + body

// 发送
smtp.SendMail("smtp.example.com:25", nil, from.Address, []string{to.Address}, []byte(message))
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `net/smtp`、`smtp.SendMail`、`smtp.Client`
- 查找邮件头构建：`headers := make(map[string]string)`、`fmt.Sprintf("%s: %s\r\n"`
- 定位用户输入来源：`r.FormValue()`、`r.URL.Query().Get()`、请求体解析
- 检查自定义头部拼接

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`strings.ReplaceAll(s, "\r", "")`、`strings.ReplaceAll(s, "\n", "")`
- 查找邮箱验证：`mail.ParseAddress()`、正则验证
- 检查头部值的白名单验证
- 查看是否使用邮件库：`gomail`、`email` 包

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到邮件头字符串中
   - 自定义头部值包含未过滤的用户数据
   - 未进行 CRLF 字符过滤
   - 能通过注入 `\r\n` 添加额外的邮件头或修改邮件结构
   - 直接使用 `smtp.SendMail` 而非安全的邮件库

2. **确认为误报的情况**：
   - 使用 `mail.ParseAddress()` 解析并验证邮箱地址
   - 所有头部值都经过 CRLF 过滤
   - 使用 `gomail` 或 `email` 等库自动处理头部
   - 用户输入仅用于邮件正文，不涉及头部字段

3. **代码异味判断**：
   - 验证不完整：仅检查是否包含 `@`
   - 过滤不彻底：仅过滤 `\n` 未过滤 `\r`
   - 某些代码路径缺少验证

---

## Low risk

**这些情况应给予低风险评级**

1. **邮件库**：使用 `gomail` 或 `github.com/jordan-wright/email` 等库自动处理头部验证

2. **CRLF 过滤**：所有用户输入在拼接到头部前都经过 `strings.ReplaceAll()` 过滤 `\r` 和 `\n`

3. **地址解析**：使用 `mail.ParseAddress()` 解析并验证所有邮箱地址

4. **白名单验证**：头部值仅来自预定义列表或数据库查询，用户无法输入任意内容

5. **仅正文输入**：用户输入仅用于邮件正文内容，不影响任何头部字段
