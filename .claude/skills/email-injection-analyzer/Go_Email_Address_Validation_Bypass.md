# Go Email Address Validation Bypass

## Details

Go 应用中邮箱地址验证不充分时，攻击者可通过特殊构造的邮箱地址绕过验证逻辑。常见问题包括：使用不完整的正则表达式、仅检查 `@` 符号、未使用 `net/mail.ParseAddress()`、允许 CRLF 等特殊字符。这可能导致邮件头注入、垃圾邮件发送或系统滥用。

**代码示例与审计要点**

```go
import (
    "strings"
    "regexp"
)

// 危险：简单字符串检查
if strings.Contains(email, "@") && strings.Contains(email, ".") {
    sendEmail(email)
}

// 危险：不完整的正则
if matched, _ := regexp.MatchString(`^[\w\.-]+@[\w\.-]+$`, email); matched {
    sendEmail(email)
}

// 危险：未过滤特殊字符
if strings.Count(email, "@") == 1 {
    sendEmail(email)
}

// 危险：允许换行符
if matched, _ := regexp.MatchString(`.+@.+\..+`, email); matched {
    sendEmail(email)
}
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮箱验证：`strings.Contains(email, "@")`、`regexp.MatchString()`
- 查找邮件发送：`smtp.SendMail`、`gomail.Send()`
- 定位输入来源：`r.FormValue()`、`r.URL.Query().Get()`、请求体解析
- 检查是否直接使用输入而无验证

**快速定位保护机制 (L2: 跳读)**
- 搜索标准解析：`mail.ParseAddress()`、`mail.ParseAddressList()`
- 查找 CRLF 过滤：`strings.ReplaceAll(email, "\r", "")`
- 检查验证库：`github.com/badoux/checkmail`、`gopkg.in/mail.v2`
- 查看正则表达式是否符合 RFC 5322

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 仅检查 `@` 和 `.` 符号存在
   - 正则表达式不完整，允许换行符、空格等特殊字符
   - 未验证本地部分和域名部分的合法性
   - 允许连续点号、多个 `@` 符号
   - 能通过 `user@domain\r\nBcc:attacker@evil.com` 绕过验证

2. **确认为误报的情况**：
   - 使用 `mail.ParseAddress()` 解析并验证邮箱格式
   - 使用 `checkmail.ValidateFormat()` 或类似库验证
   - 正则表达式符合 RFC 5322 标准
   - 额外进行 CRLF 过滤

3. **代码异味判断**：
   - 正则验证不完整，未覆盖所有边界情况
   - 使用 `ParseAddress()` 但未检查返回的错误
   - 验证在某些代码路径中缺失

---

## Low risk

**这些情况应给予低风险评级**

1. **标准库解析**：使用 `mail.ParseAddress()` 解析并验证邮箱格式，检查返回的错误

2. **验证库**：使用 `github.com/badoux/checkmail` 的 `ValidateFormat()` 进行格式验证

3. **组合验证**：结合 `ParseAddress()` 和 CRLF 过滤：`strings.ReplaceAll()`

4. **白名单验证**：邮箱地址仅来自数据库查询或预定义列表，用户无法输入任意值

5. **DNS 验证**：使用 `net.LookupMX()` 验证域名 MX 记录是否存在
