# C Custom Email Command Injection

## Details

C 语言自定义邮件发送库或 SMTP 客户端在构建邮件命令时，若用户输入直接拼接到命令字符串未经转义和验证，攻击者可注入额外的 SMTP 命令或邮件头。由于 C 语言通常直接操作字符串和网络连接，缺少高级抽象，因此命令注入风险较高。

**代码示例与审计要点**

```c
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>

// 危险：直接拼接用户输入到 SMTP 命令
char cmd[512];
sprintf(cmd, "MAIL FROM:<%s>\r\n", user_email);
send(sockfd, cmd, strlen(cmd), 0);

// 危险：RCPT TO 命令拼接用户输入
sprintf(cmd, "RCPT TO:<%s>\r\n", recipient);
send(sockfd, cmd, strlen(cmd), 0);

// 危险：自定义命令拼接
sprintf(cmd, "VRFY %s\r\n", user_name);
send(sockfd, cmd, strlen(cmd), 0);

// 危险：使用 strcat 构建多个命令
strcpy(cmd, "MAIL FROM:<");
strcat(cmd, user_from);
strcat(cmd, ">\r\n");
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 SMTP 命令字符串：`"MAIL FROM"`、`"RCPT TO"`、`"DATA"`、`"VRFY"`、`"EXPN"`
- 查找字符串拼接函数：`sprintf()`、`snprintf()`、`strcat()`、`strcpy()`
- 定位网络发送函数：`send()`、`write()`、`sendto()`
- 检查 `"\r\n"` 的使用和用户输入的拼接位置

**快速定位保护机制 (L2: 跳读)**
- 搜索输入验证函数：邮箱格式验证、命令参数白名单
- 查找 CRLF 过滤：自定义过滤函数、字符替换循环
- 检查是否使用邮件库：libcurl、libesmtp 封装 SMTP 操作
- 查看缓冲区大小检查：`snprintf()` 返回值验证

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接通过 `sprintf()` 或 `strcat()` 拼接到 SMTP 命令中
   - SMTP 命令字符串包含未过滤的用户输入
   - 未进行 CRLF、空格或特殊字符过滤
   - 能通过注入 `\r\n` 执行额外的 SMTP 命令
   - 存在缓冲区溢出风险（使用 `sprintf()` 而非 `snprintf()`）

2. **确认为误报的情况**：
   - 使用邮件库（libcurl、libesmtp）封装 SMTP 操作
   - 所有 SMTP 命令参数都经过严格验证和过滤
   - 使用 `snprintf()` 并检查返回值防止溢出
   - 命令参数来自白名单或配置文件，不直接接受用户输入

3. **代码异味判断**：
   - 使用 `sprintf()` 而非 `snprintf()`（缓冲区溢出风险）
   - 验证不完整：仅检查基本格式未过滤特殊字符
   - 某些代码路径直接使用用户输入

---

## Low risk

**这些情况应给予低风险评级**

1. **邮件库**：使用 libcurl 的 SMTP 功能或 libesmtp 等库封装所有 SMTP 命令

2. **严格过滤**：所有用户输入在拼接到 SMTP 命令前都经过自定义函数过滤 CRLF、空格、特殊字符

3. **安全函数**：使用 `snprintf()` 替代 `sprintf()`，检查返回值防止缓冲区溢出

4. **参数验证**：SMTP 命令参数通过白名单验证，仅允许合法的邮箱地址格式

5. **内部使用**：SMTP 客户端仅用于内部系统通信，不接受外部用户输入