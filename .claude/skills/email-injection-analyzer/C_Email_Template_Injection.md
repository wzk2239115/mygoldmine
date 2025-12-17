# C Email Template Injection

## Details

C 语言应用中使用字符串拼接或简单的占位符替换生成邮件内容时，若用户输入直接嵌入模板字符串未经转义，攻击者可注入恶意内容。虽然 C 语言较少使用复杂的模板引擎，但简单的字符串替换仍可能导致邮件内容篡改或 HTML 注入（如果发送 HTML 邮件）。

**代码示例与审计要点**

```c
#include <stdio.h>
#include <string.h>

// 危险：直接 sprintf 拼接用户输入到邮件内容
char email_body[2048];
sprintf(email_body, "Hello %s,\n\nYour verification code is: %s\n\n",
        user_name, verification_code);

// 危险：HTML 邮件未转义
sprintf(email_body, "<html><body>Hello %s, <a href='%s'>Click here</a></body></html>",
        user_name, user_link);

// 危险：使用 strstr/strrep 简单替换
char *template = read_template_file("email.txt");
str_replace(template, "{{USERNAME}}", user_input);
str_replace(template, "{{MESSAGE}}", user_message);
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `sprintf()`、`snprintf()` 拼接邮件内容
- 查找字符串替换函数：`str_replace()`、`strstr()`、自定义替换函数
- 定位 HTML 标签：`<html>`、`<body>`、`<a href=`
- 检查模板文件读取：`fopen()`、`read_template()`

**快速定位保护机制 (L2: 跳读)**
- 搜索 HTML 转义函数：自定义的 `html_escape()`、`escape_string()`
- 查找输入验证：长度检查、特殊字符过滤
- 检查是否使用纯文本邮件而非 HTML
- 查看缓冲区大小检查：`snprintf()` 返回值验证

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接通过 `sprintf()` 拼接到邮件内容中
   - HTML 邮件中未对用户输入进行 HTML 转义
   - 使用简单的字符串替换将用户输入嵌入模板
   - 能注入 HTML 标签或邮件格式控制符
   - 存在缓冲区溢出风险（使用 `sprintf()` 而非 `snprintf()`）

2. **确认为误报的情况**：
   - 仅发送纯文本邮件，不包含 HTML
   - 所有用户输入都经过 HTML 转义函数处理
   - 模板内容完全静态，用户输入仅作为纯文本数据
   - 使用 `snprintf()` 并检查返回值防止缓冲区溢出

3. **代码异味判断**：
   - 使用 `sprintf()` 而非 `snprintf()`（缓冲区溢出风险）
   - HTML 转义不完整：仅转义部分特殊字符
   - 转义仅在部分代码路径中执行

---

## Low risk

**这些情况应给予低风险评级**

1. **纯文本邮件**：仅发送纯文本邮件（Content-Type: text/plain），不包含 HTML

2. **HTML 转义**：所有用户输入在嵌入 HTML 邮件前都经过自定义 HTML 转义函数处理

3. **安全函数**：使用 `snprintf()` 替代 `sprintf()`，检查返回值防止缓冲区溢出

4. **静态模板**：邮件模板完全静态，用户输入仅作为纯文本数据追加而不修改模板结构

5. **白名单验证**：模板变量值仅来自配置文件或预定义数组，用户无法输入任意内容
