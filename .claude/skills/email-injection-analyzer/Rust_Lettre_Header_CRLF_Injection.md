# Rust Lettre Header CRLF Injection

## Details

Lettre 是 Rust 最流行的邮件发送库。虽然 Lettre 对邮件头有一定的验证，但在使用 `Message::builder()` 构建邮件时，若用户输入直接传入邮件头字段或使用 `header()` 方法添加自定义头部未经验证，仍可能存在 CRLF 注入风险。

**代码示例与审计要点**

```rust
use lettre::{Message, Transport, SmtpTransport};
use lettre::message::header;

// 危险：直接使用用户输入
let email = Message::builder()
    .from(user_from.parse().unwrap())
    .to(user_to.parse().unwrap())
    .subject(user_subject)  // 用户输入
    .header(header::ContentType::TEXT_PLAIN)
    .body(body)
    .unwrap();

// 危险：自定义头部
let email = Message::builder()
    .to("user@example.com".parse().unwrap())
    .subject("Test")
    .header(("X-Custom-Header", user_header))  // 用户输入
    .body(body)
    .unwrap();
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `lettre::Message::builder()`、`.from()`、`.to()`、`.subject()`
- 查找 `.header()` 方法的自定义头部设置
- 定位用户输入来源：请求参数、表单数据、环境变量
- 检查 `.parse()` 调用是否验证了输入格式

**快速定位保护机制 (L2: 跳读)**
- 搜索输入验证：`validate_email()`、自定义验证函数
- 查找 CRLF 过滤：`.replace("\r", "").replace("\n", "")`
- 检查 Lettre 版本（较新版本有改进的验证）
- 查看是否使用 `Mailbox::new()` 验证邮箱格式

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接传给 `.from()`、`.to()`、`.subject()` 等方法
   - 使用 `.header()` 添加包含用户输入的自定义头部
   - `.parse()` 失败时使用 `.unwrap()` 导致 panic 而非验证
   - 未进行 CRLF 字符过滤
   - 能通过注入 `\r\n` 添加额外的邮件头

2. **确认为误报的情况**：
   - 使用 Lettre 0.10+ 版本（改进的头部验证）
   - 所有邮箱地址通过 `Mailbox::new()` 构建并处理错误
   - 头部值经过 CRLF 过滤
   - 用户输入仅用于邮件正文，不涉及头部字段

3. **代码异味判断**：
   - 使用 `.unwrap()` 处理 `.parse()` 结果而未验证
   - 验证不完整：仅检查字符串非空
   - 某些代码路径缺少验证

---

## Low risk

**这些情况应给予低风险评级**

1. **新版本 Lettre**：使用 Lettre 0.10 或更高版本，具有改进的头部验证和类型安全

2. **类型安全构建**：使用 `Mailbox::new()` 构建邮箱地址，使用 `?` 操作符处理错误而非 `.unwrap()`

3. **CRLF 过滤**：所有用户输入在传入 Lettre 前都经过 `.replace()` 过滤 `\r` 和 `\n`

4. **白名单验证**：邮箱地址来自配置文件或数据库查询，用户无法输入任意值

5. **仅正文输入**：用户输入仅影响邮件正文（`.body()`），不影响任何头部字段
