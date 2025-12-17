# C SMTP Header CRLF Injection

## Details

C 语言应用中手动构建 SMTP 命令和邮件头时，若用户输入包含 CRLF 字符（`\r\n`）未被过滤，攻击者可注入额外的邮件头或 SMTP 命令。由于 C 语言缺少高级抽象，通常直接操作字符串和网络连接，因此 CRLF 注入风险较高。

**代码示例与审计要点**

```c
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>

// 危险：直接拼接用户输入到邮件头
char header[1024];
sprintf(header, "From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n",
        user_from, user_to, user_subject);
send(sockfd, header, strlen(header), 0);

// 危险：SMTP 命令拼接用户输入
char smtp_cmd[256];
sprintf(smtp_cmd, "MAIL FROM:<%s>\r\n", user_email);
send(sockfd, smtp_cmd, strlen(smtp_cmd), 0);

// 危险：使用 strcat 拼接
strcat(header, "Cc: ");
strcat(header, user_cc);
strcat(header, "\r\n");
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `sprintf()`、`snprintf()`、`strcat()`、`strcpy()` 拼接邮件头
- 查找 SMTP 命令字符串：`"MAIL FROM"`、`"RCPT TO"`、`"DATA"`
- 定位 `send()`、`write()` 发送网络数据
- 检查 `"\r\n"` 的使用位置

**快速定位保护机制 (L2: 跳读)**
- 搜索 CRLF 过滤函数：自定义的 `remove_crlf()`、字符替换循环
- 查找输入验证：`strchr()`、`strstr()` 检查特殊字符
- 检查是否使用邮件库：libcurl、libesmtp
- 查看缓冲区大小检查：`snprintf()` 而非 `sprintf()`

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接通过 `sprintf()` 或 `strcat()` 拼接到邮件头
   - SMTP 命令字符串包含未过滤的用户输入
   - 未进行 CRLF 字符过滤
   - 能通过注入 `\r\n` 添加额外的邮件头或 SMTP 命令
   - 存在缓冲区溢出风险（使用 `sprintf()` 而非 `snprintf()`）

2. **确认为误报的情况**：
   - 使用邮件库（libcurl、libesmtp）封装 SMTP 操作
   - 所有用户输入都经过 CRLF 过滤函数处理
   - 输入来源于白名单或配置文件，不直接接受用户输入
   - 使用 `snprintf()` 并检查返回值防止缓冲区溢出

3. **代码异味判断**：
   - 使用 `sprintf()` 而非 `snprintf()`（缓冲区溢出风险）
   - 过滤不完整：仅过滤 `\n` 未过滤 `\r`
   - 某些代码路径缺少验证

---

## Low risk

**这些情况应给予低风险评级**

1. **邮件库**：使用 libcurl 的 SMTP 功能或 libesmtp 等库封装邮件发送

2. **CRLF 过滤**：所有用户输入在拼接到邮件头前都经过自定义函数过滤 `\r` 和 `\n`

3. **安全函数**：使用 `snprintf()` 替代 `sprintf()`，使用 `strncat()` 替代 `strcat()`

4. **白名单验证**：邮件头字段值仅来自配置文件或预定义数组，用户无法输入任意值

5. **内部系统**：SMTP 功能仅用于内部系统通信，不接受外部用户输入
