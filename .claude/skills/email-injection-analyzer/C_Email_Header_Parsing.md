# C Email Header Parsing

## Details

C 语言邮件客户端或服务端在解析邮件头时，若未正确处理边界情况、特殊字符、长度限制或格式异常，可能导致缓冲区溢出、格式字符串漏洞、头部注入或拒绝服务。常见问题包括：使用不安全的字符串函数、未验证头部长度、未处理折叠头部（folded headers）、未清理 CRLF 等。

**代码示例与审计要点**

```c
#include <stdio.h>
#include <string.h>

// 危险：使用 sscanf 解析头部，未检查长度
char subject[256];
sscanf(header_line, "Subject: %s", subject);  // 缓冲区溢出

// 危险：使用 strcpy 提取头部值
char *colon = strchr(line, ':');
if (colon) {
    strcpy(header_value, colon + 2);  // 未检查长度
}

// 危险：未处理折叠头部（多行头部）
if (line[0] == ' ' || line[0] == '\t') {
    strcat(prev_header, line);  // 可能溢出
}

// 危险：使用 sprintf 格式化头部
sprintf(buffer, "From: %s", header_from);  // 格式字符串漏洞
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索邮件头解析函数：`sscanf()`、`strchr()`、`strstr()`、`strtok()`
- 查找不安全的字符串函数：`strcpy()`、`strcat()`、`sprintf()`、`gets()`
- 定位头部提取逻辑：查找 `"From:"`、`"Subject:"`、`"To:"` 等字符串
- 检查循环读取头部的代码

**快速定位保护机制 (L2: 跳读)**
- 搜索安全函数：`strncpy()`、`strncat()`、`snprintf()`、`fgets()`
- 查找长度检查：`strlen()` 与缓冲区大小比较
- 检查折叠头部处理：连续的空格或制表符开头的行
- 查看是否使用邮件解析库：libcurl、GMime

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 使用 `strcpy()`、`strcat()`、`sprintf()` 处理邮件头部
   - 使用 `sscanf()` 读取头部值但未限制长度（`%s` 而非 `%255s`）
   - 未检查邮件头长度就复制到固定大小缓冲区
   - 折叠头部处理时使用 `strcat()` 拼接多行
   - 存在缓冲区溢出、格式字符串漏洞风险

2. **确认为误报的情况**：
   - 使用 `strncpy()`、`strncat()`、`snprintf()` 等安全函数
   - 在字符串操作前检查长度：`if (strlen(src) < sizeof(dst))`
   - 使用成熟的邮件解析库（GMime、libcurl）
   - 所有缓冲区操作都有明确的边界检查

3. **代码异味判断**：
   - 使用 `strncpy()` 但未确保字符串终止符
   - 长度检查不完整：仅检查部分缓冲区操作
   - 手动解析邮件头而非使用标准库

---

## Low risk

**这些情况应给予低风险评级**

1. **安全函数**：所有字符串操作都使用 `strncpy()`、`strncat()`、`snprintf()` 并正确检查返回值

2. **邮件库**：使用 GMime、libcurl 等成熟库解析邮件头，避免手动解析

3. **长度限制**：在所有缓冲区操作前都进行严格的长度检查和边界验证

4. **输入验证**：解析前验证邮件头格式，拒绝超长、格式错误的头部

5. **静态分析**：代码通过静态分析工具（Coverity、Clang Static Analyzer）检查，无缓冲区溢出警告