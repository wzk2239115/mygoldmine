# C Email Address Validation Bypass

## Details

C 语言应用中邮箱地址验证通常通过自定义函数或简单的字符串检查实现。若验证逻辑不充分，攻击者可通过特殊构造的邮箱地址绕过验证。常见问题包括：仅检查 `@` 符号、使用不完整的正则表达式、未验证域名格式、允许 CRLF 等特殊字符。

**代码示例与审计要点**

```c
#include <string.h>
#include <ctype.h>

// 危险：简单字符串检查
int validate_email(const char *email) {
    if (strchr(email, '@') != NULL && strchr(email, '.') != NULL) {
        return 1;
    }
    return 0;
}

// 危险：不完整的验证
int is_valid_email(const char *email) {
    // 仅检查一个 @
    int at_count = 0;
    for (int i = 0; email[i]; i++) {
        if (email[i] == '@') at_count++;
    }
    return at_count == 1;
}

// 危险：未过滤特殊字符
int check_email(const char *email) {
    // 未检查换行符、空格等
    return strlen(email) > 5 && strchr(email, '@') != NULL;
}
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮箱验证函数：`validate_email()`、`is_valid_email()`、`check_email()`
- 查找 `strchr()`、`strstr()`、`strpbrk()` 检查 `@` 和 `.`
- 定位正则表达式库：`regex.h`、`regcomp()`、`regexec()`
- 检查是否直接使用用户输入而无验证

**快速定位保护机制 (L2: 跳读)**
- 搜索完整的邮箱验证正则表达式
- 查找 CRLF 过滤：循环检查 `\r`、`\n`
- 检查是否使用邮件库的验证函数
- 查看是否验证域名格式和长度

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 仅检查 `@` 和 `.` 符号存在
   - 未验证本地部分和域名部分的格式
   - 允许换行符、空格、控制字符等
   - 未检查邮箱长度或允许过长输入
   - 能通过 `user@domain\r\nBcc:attacker@evil.com` 绕过验证

2. **确认为误报的情况**：
   - 使用完整的 RFC 5322 兼容正则表达式验证
   - 验证函数检查了所有特殊字符并拒绝
   - 额外进行 CRLF 和控制字符过滤
   - 邮箱地址来自配置文件，用户无法输入任意值

3. **代码异味判断**：
   - 正则验证不完整，未覆盖所有边界情况
   - 仅验证格式未过滤危险字符
   - 验证在某些代码路径中缺失

---

## Low risk

**这些情况应给予低风险评级**

1. **完整正则**：使用 POSIX 正则表达式库实现 RFC 5322 兼容的邮箱验证

2. **CRLF 过滤**：验证后额外进行循环检查，拒绝包含 `\r`、`\n` 的输入

3. **长度限制**：严格限制邮箱长度（本地部分 ≤64，域名部分 ≤255）

4. **字符白名单**：仅允许字母、数字、`@`、`.`、`-`、`_` 等安全字符

5. **配置来源**：邮箱地址仅来自配置文件或数据库查询，用户无法输入任意值
