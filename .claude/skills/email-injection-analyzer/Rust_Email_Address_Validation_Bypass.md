# Rust Email Address Validation Bypass

## Details

Rust 应用中邮箱地址验证不充分时，攻击者可通过特殊构造的邮箱地址绕过验证逻辑。常见问题包括：使用不完整的正则表达式、仅检查 `@` 符号、未使用验证库、允许 CRLF 等特殊字符。虽然 Rust 的类型系统提供了一定保护，但仍需正确验证输入。

**代码示例与审计要点**

```rust
use regex::Regex;

// 危险：简单字符串检查
if email.contains('@') && email.contains('.') {
    send_email(email);
}

// 危险：不完整的正则
let re = Regex::new(r"^[\w\.-]+@[\w\.-]+$").unwrap();
if re.is_match(email) {
    send_email(email);
}

// 危险：未过滤特殊字符
if email.matches('@').count() == 1 {
    send_email(email);
}

// 危险：允许换行符
let re = Regex::new(r".+@.+\..+").unwrap();
if re.is_match(email) {
    send_email(email);
}
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮箱验证：`.contains('@')`、`Regex::new()`、`.is_match()`
- 查找邮件发送：`send()`、`SmtpTransport::relay()`
- 定位输入来源：请求参数、表单数据、环境变量
- 检查是否直接使用输入而无验证

**快速定位保护机制 (L2: 跳读)**
- 搜索验证库：`email_address` crate、`validator` crate
- 查找 CRLF 过滤：`.replace("\r", "").replace("\n", "")`
- 检查 `Mailbox::new()` 或 `EmailAddress::from_str()` 的使用
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
   - 使用 `email_address` crate 的 `EmailAddress::from_str()` 验证
   - 使用 `validator` crate 的 `#[validate(email)]` 属性
   - 使用 Lettre 的 `Mailbox::new()` 并处理 `Result`
   - 正则表达式符合 RFC 5322 标准

3. **代码异味判断**：
   - 正则验证不完整，未覆盖所有边界情况
   - 使用 `.unwrap()` 处理验证结果而未检查错误
   - 验证在某些代码路径中缺失

---

## Low risk

**这些情况应给予低风险评级**

1. **验证库**：使用 `email_address` crate 的 `EmailAddress::from_str()` 进行标准验证

2. **Validator Derive**：使用 `validator` crate 的 `#[validate(email)]` 属性自动验证

3. **Lettre 类型**：使用 `Mailbox::new()` 构建邮箱地址，使用 `?` 操作符处理错误

4. **组合验证**：结合验证库和 CRLF 过滤：`.replace()` 方法

5. **白名单验证**：邮箱地址仅来自配置文件或数据库查询，用户无法输入任意值
