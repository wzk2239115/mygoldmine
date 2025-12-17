# Go Gomail Header Injection

## Details

Go 的 Gomail 库通过 `SetHeader()` 和 `SetAddressHeader()` 方法设置邮件头字段。当直接拼接用户输入至这些方法，未进行 CRLF 过滤，攻击者可通过注入 `\r\n` 改变邮件头结构，实现邮件欺骗、插入恶意头部或重定向邮件。

**代码示例与审计要点**

```go
m := gomail.NewMessage()
m.SetHeader("From", userEmail)
m.SetHeader("To", userEmail)
m.SetHeader("Subject", userSubject)
m.SetBody("text/html", body)
dialer := gomail.NewDialer("smtp.gmail.com", 587, user, password)
dialer.DialAndSend(m)
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `gomail.NewMessage()`、`SetHeader()`、`SetAddressHeader()`、`SetBody()`
- 定位参数来源：`r.URL.Query()`、`r.FormValue()`、JSON 请求体解析
- 查找 `dialer.DialAndSend()` 和 `m.WriteTo()` 调用
- 检查 HTTP 处理函数中邮件对象的构建过程

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤：`strings.ReplaceAll(value, "\r", "")`、`strings.ReplaceAll(value, "\n", "")`
- 查找邮箱验证：`net.ParseEmail()`、`regexp` 正则验证邮箱格式
- 检查是否使用第三方验证库：`go-playground/validator`、`asaskevich/govalidate`
- 查看邮箱来源是否有数据库查询和白名单限制

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - `SetHeader()` 或 `SetAddressHeader()` 直接接收用户输入
   - 邮箱地址未通过 `net.ParseEmail()` 或 `mail.ParseAddress()` 验证
   - 邮件头字段拼接用户数据且未过滤 CRLF
   - 能成功注入 `\r\n` 改变邮件头结构
   - 用户输入来自外部请求（GET/POST/JSON）

2. **确认为误报的情况**：
   - 所有邮件地址通过 `net.ParseEmail()` 或 RFC 5322 兼容正则验证
   - 邮件头值通过严格的白名单过滤或仅限字母数字
   - 邮箱来自数据库查询结果，用户仅能选择
   - 第三方验证库（validator/v10）在结构体标签中强制验证

3. **代码异味判断**：
   - 验证不完整：仅检查 `len(email) > 0` 而非完整格式验证
   - 验证后仍使用原始值，未保存验证结果
   - 条件分支中验证不一致：某些代码路径缺失验证

---

## Low risk

**这些情况应给予低风险评级**

1. **标准库验证**：使用 `net.SplitHostPort()` 和 `mail.ParseAddress()` 验证所有邮箱地址，正确解析格式

2. **正则验证**：通过 RFC 5322 兼容的正则表达式 `regexp.MustCompile("...")` 验证邮件地址和头部值

3. **白名单机制**：邮箱地址和头部值仅来自数据库预设数据或配置常量，不允许用户输入

4. **验证器库**：使用 `go-playground/validator` 的 `email` 标签在结构体中声明，所有数据必须通过验证

5. **SMTP 隔离**：SMTP 服务器为内部部署，不转发至外部邮件系统，邮件欺骗影响范围有限
