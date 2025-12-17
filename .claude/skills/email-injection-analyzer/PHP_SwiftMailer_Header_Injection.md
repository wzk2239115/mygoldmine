# PHP SwiftMailer Header Injection

## Details

Swift Mailer 库处理邮件头时，若用户输入直接拼接至邮件地址或头部字段，未过滤 CRLF 字符，攻击者可注入换行符改变邮件头结构。该库允许通过 `addTo()`、`setSubject()`、`addCc()` 等方法拼接用户数据，特别在自定义头部时风险更大。

**代码示例与审计要点**

```php
$message = (new Swift_Message())
    ->setTo($userEmail)
    ->setSubject($userSubject)
    ->addCc($userCc);
$mailer->send($message);
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `Swift_Message`、`setTo()`、`setFrom()`、`setSubject()`、`addTo()`、`addCc()`、`addBcc()`
- 定位这些方法调用的参数，检查是否来自 `$_GET`、`$_POST`、`$_REQUEST` 或外部输入
- 查找 `Swift_Message::newInstance()` 或 `new Swift_Message()`
- 检查 `addHeader()` 或 `getHeaders()` 的自定义头部设置

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤函数：`str_replace("\r\n", "")`、`preg_replace()` 过滤换行符
- 查找邮箱验证：`filter_var($email, FILTER_VALIDATE_EMAIL)`、`preg_match()` 正则验证
- 检查是否有白名单验证或数据库查询限制邮箱来源
- 查看是否使用 Symfony Validator 等框架级验证组件

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入未经验证直接传入 `setTo()`、`setSubject()` 等方法
   - 自定义头部拼接用户数据：`addHeader('X-Custom', $userInput)`
   - 邮箱地址未通过 `filter_var(..., FILTER_VALIDATE_EMAIL)` 验证
   - 成功注入 `\r\n` 可改变邮件结构，实现邮件头注入

2. **确认为误报的情况**：
   - 所有邮件地址和头部字段都通过 `filter_var(FILTER_VALIDATE_EMAIL)` 或完整的 RFC 5321 正则验证
   - 头部值通过严格的白名单过滤或仅限字母数字
   - 邮箱来自数据库中的预设值，用户仅能选择不能输入
   - Swift Mailer 版本已自动进行 CRLF 转义处理

3. **代码异味判断**：
   - 验证不完整：仅检查 `is_string()` 或 `strlen()` 而未真正验证邮箱格式
   - 验证后仍使用原始值：验证通过但仍使用未清理的输入
   - 验证在条件分支中：某些代码路径缺少验证

---

## Low risk

**这些情况应给予低风险评级**

1. **严格邮箱验证**：使用 `filter_var($email, FILTER_VALIDATE_EMAIL)` 或 RFC 5321 兼容的正则表达式完整验证所有邮件地址字段

2. **白名单验证**：所有邮件地址和自定义头部值来自数据库预设数据或有限的可控列表，用户无法输入任意值

3. **自动化过滤**：Swift Mailer 的新版本（6.x+）已自动对头部值进行 CRLF 转义，或中间件已正确实现

4. **受限输入场景**：邮件操作不直接依赖用户输入，仅在系统内部批量发送或通知场景中使用

5. **环境隔离**：SMTP 服务器仅内部可达，不对外部邮件系统转发，邮件欺骗影响范围有限
