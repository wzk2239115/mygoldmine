# C/C++ 响应头 CRLF 注入

## Details

**审计等级：L2（跳读）/ L3（逐行读）**

**危险函数特征：**
- `sprintf(header, "X-Custom: %s", user_input)` 拼接响应头
- `snprintf()` 拼接头值
- `strcat(header, user_input)` 字符串拼接
- CGI 环境变量直接用于头部：`printf("X-Custom: %s\r\n", getenv())`
- HTTP 库的头设置函数

**快速定位核心操作：**
1. 搜索关键字：`sprintf`、`snprintf`、`strcat`、`printf` 与 `
` 组合
2. 追踪头值来源：`getenv()`、命令行参数、网络数据、文件输入
3. 检查是否存在 CRLF 过滤（``、`
` 的检查）
4. 追踪从外部输入到 HTTP 头的完整链路

**快速定位保护机制：**
- 手动检查：`if (strchr(value, '') || strchr(value, '
')) return ERROR;`
- 循环过滤：遍历字符串移除 CRLF
- 白名单验证：`regex` 或手动字符检查
- HTTP 库防护：使用支持验证的 HTTP 库版本

**代码示例：**
```c
// 危险：sprintf 拼接用户输入
void handle_request(char *user_input) {
    char header[256];
    sprintf(header, "X-Custom: %s
", user_input);  // 危险
    send_response(header);
}

// 危险：getenv 直接用于头部
void send_cgi_header() {
    char *custom = getenv("HTTP_X_CUSTOM");
    printf("X-Custom: %s
", custom);  // 危险：未过滤
}

// 危险：strcat 拼接
void append_header(char *value) {
    char header[256] = "X-Data: ";
    strcat(header, value);  // 危险
    strcat(header, "
");
}
```

## Classify

**漏洞（High）：**
- `sprintf`/`snprintf`/`strcat` 等拼接了用户输入进响应头
- 无 CRLF 过滤或边界检查
- 缓冲区溢出 + CRLF 注入结合
- 多个输入来源叠加使用

**误报：**
- 头值完全硬编码
- 输入已被 HTTP 库验证
- 使用了安全的头部 API

**代码异味（Medium）：**
- 有过滤但不完整（如仅检查 `
`）
- 缓冲区大小不足引发截断
- 间接拼接：输入 → 中间变量 → 头部

## Low risk

**以下情况评为低风险：**
- 头值完全硬编码
- 使用 HTTP 库的验证 API
- 严格的输入长度限制 + CRLF 检查
- 输入来自内部可信源
- 使用现代 C++ HTTP 库（自动验证）
