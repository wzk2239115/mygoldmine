# C/C++ 响应头CRLF注入

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 25-35分钟
- **关键词搜索：** `sprintf`, `snprintf`, `strcat`, `strcpy`, `write`, `send`, `Content-Type`, `Location`, `Set-Cookie`, `\r\n`
- **快速检查：** HTTP响应头是否使用字符串拼接构造，用户输入是否直接进入响应头

## 漏洞成因

C/C++中构造HTTP响应头通常使用字符串拼接函数（sprintf/strcat等），若用户输入直接拼接到响应头而未过滤CRLF（`\r\n`）字符，攻击者可注入任意HTTP头或响应体，导致HTTP响应拆分、XSS、会话劫持、缓存中毒等攻击。

### 常见漏洞模式

```c
// ✗ 漏洞：sprintf直接拼接用户输入到响应头
void send_response(int sock, const char *user_input) {
    char response[4096];
    sprintf(response, "HTTP/1.1 200 OK\r\n"
                      "Content-Type: text/html\r\n"
                      "X-Custom: %s\r\n"  // 用户输入直接拼接
                      "\r\n"
                      "<html>...</html>", user_input);
    send(sock, response, strlen(response), 0);
    // 攻击: user_input = "value\r\nSet-Cookie: admin=true"
}
```

```c
// ✗ 漏洞：Location重定向头注入
void handle_redirect(int sock, const char *url) {
    char response[1024];
    snprintf(response, sizeof(response),
             "HTTP/1.1 302 Found\r\n"
             "Location: %s\r\n"  // URL未验证
             "\r\n", url);
    write(sock, response, strlen(response));
    // 攻击: url = "http://evil.com\r\nSet-Cookie: session=hijacked"
}
```

```c
// ✗ 漏洞：Content-Disposition文件名注入
void serve_file(int sock, const char *filename) {
    char header[512];
    sprintf(header, "HTTP/1.1 200 OK\r\n"
                    "Content-Disposition: attachment; filename=%s\r\n"
                    "\r\n", filename);
    send(sock, header, strlen(header), 0);
    // 攻击: filename = "file.txt\r\nX-Injected: header"
}
```

```c
// ✗ 漏洞：Set-Cookie值注入
void set_cookie(int sock, const char *value) {
    char response[1024];
    snprintf(response, sizeof(response),
             "HTTP/1.1 200 OK\r\n"
             "Set-Cookie: session=%s\r\n"  // Cookie值未过滤
             "\r\n", value);
    write(sock, response, strlen(response));
}
```

```c
// ✓ 修复：CRLF过滤函数
char* sanitize_header_value(const char *input, char *output, size_t outsize) {
    size_t j = 0;
    for (size_t i = 0; input[i] && j < outsize - 1; i++) {
        if (input[i] != '\r' && input[i] != '\n') {
            output[j++] = input[i];
        }
    }
    output[j] = '\0';
    return output;
}

void safe_response(int sock, const char *user_input) {
    char safe_value[256];
    char response[4096];
    sanitize_header_value(user_input, safe_value, sizeof(safe_value));
    snprintf(response, sizeof(response),
             "HTTP/1.1 200 OK\r\n"
             "X-Custom: %s\r\n\r\n", safe_value);
    send(sock, response, strlen(response), 0);
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | sprintf/snprintf构造响应头 | 搜索 `sprintf.*\\r\\n\|snprintf.*HTTP`，检查变量来源 |
| **P0** | Location头拼接 | 搜索 `Location:.*%s\|Location.*sprintf`，追踪URL来源 |
| **P1** | Content-Disposition | 搜索 `Content-Disposition.*%s`，检查filename参数 |
| **P1** | Set-Cookie值 | 搜索 `Set-Cookie.*%s`，检查Cookie值来源 |
| **P2** | 自定义HTTP库 | 搜索 `write\|send.*HTTP/1`，检查响应构造逻辑 |
| **P2** | CGI程序输出 | 搜索 `printf.*Content-Type`，检查CGI头部处理 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 使用成熟HTTP库（nginx模块、Apache模块） | 快速跳过，框架处理CRLF |
| **L1** | 响应头全部硬编码 | 关键词扫描确认无变量 |
| **L2** | 单文件内sprintf构造响应 | 跳读检查变量来源和过滤 |
| **L3** | 响应头值来自外部函数 | 逐行追踪函数调用链 |
| **L4** | 自定义HTTP服务器实现 | 跨模块审计所有响应构造点 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. HTTP响应头使用字符串拼接函数构造
2. 拼接内容包含用户可控输入
3. 未进行CRLF字符过滤

### 典型漏洞特征（满足任一项即确认）
- ✗ `sprintf(buf, "Location: %s\r\n", user_url)`
- ✗ `snprintf(header, size, "X-Custom: %s\r\n", user_input)`
- ✗ `strcat(response, user_header_value)`
- ✗ CGI程序直接printf用户输入到响应头

### 安全排除（任一项充分）
- ✓ 使用nginx/Apache等服务器的API设置响应头
- ✓ 存在CRLF过滤函数（检查`\r`和`\n`）
- ✓ 白名单验证头值（枚举值、固定格式）
- ✓ 头值来自可信来源（配置文件、硬编码）

### 灰色判定（风险较低但需注意）
- 用户输入经过长度截断但无字符过滤
- 内部服务间通信，攻击面有限
- 有输入验证但不完整（仅检查部分字符）

---

## 审计专业技巧

### 真实漏洞 vs 误报区分

#### 1. **误报常见场景**

**场景A：响应头值完全硬编码**
```c
// ✓ 无漏洞：虽然使用sprintf，但值来自硬编码常量
const char *RESPONSE_TEMPLATE = "HTTP/1.1 200 OK\r\n"
                                "Content-Type: text/html\r\n"
                                "X-App-Version: 1.0.0\r\n\r\n";
sprintf(response, RESPONSE_TEMPLATE);
```
**判定依据：** 编译时常量，攻击者无法注入CRLF

**场景B：严格的整数/枚举参数**
```c
// ✓ 无漏洞：status_code是枚举值，仅包含固定数字
void send_status(int sock, int status_code) {
    const char *status_text[] = {"OK", "NotFound", "BadRequest"};
    if (status_code < 0 || status_code > 2) return;
    char response[256];
    snprintf(response, sizeof(response),
             "HTTP/1.1 %d %s\r\n\r\n",
             status_codes[status_code], status_text[status_code]);
}
```
**判定依据：** 参数范围受限，即使注入也无法突破边界检查

**场景C：隐式过滤（虽然代码不显眼）**
```c
// ✓ 无漏洞：虽然sprintf看起来危险，但前置过滤了CRLF
int validate_and_set_cookie(const char *name) {
    // 检查name是否仅包含字母数字
    if (!regex_match(name, "^[a-zA-Z0-9]+$")) {
        return -1;  // 拒绝
    }
    char response[512];
    sprintf(response, "Set-Cookie: session_id=%s\r\n\r\n", name);
}
```
**判定依据：** 正则表达式白名单包含隐式过滤

---

#### 2. **真实漏洞的隐蔽形式**

**漏洞形式A：多步函数调用链的过滤缺失**
```c
// ✗ 漏洞：过滤在A函数，但B函数直接使用原始输入
void process_input(const char *user_input) {
    char *filtered = sanitize(user_input);  // 在这里过滤了
    set_response_header(filtered);  // 安全的
}

void process_header_directly(const char *user_input) {
    // 攻击者调用这个函数绕过sanitize
    char response[512];
    sprintf(response, "X-User: %s\r\n\r\n", user_input);
}
```
**审计要点：**
- 搜索所有sprintf/snprintf的调用点，不能只看一个函数
- 检查是否存在多个入口都能到达同一个响应头构造函数

**漏洞形式B：条件判断不当的过滤**
```c
// ✗ 漏洞：过滤逻辑有缺陷
void send_redirect(const char *url) {
    // 检查是否包含\r\n，但URL编码的%0d%0a绕过了此检查
    if (strstr(url, "\r\n")) {
        return;  // 拒绝
    }
    // 攻击: url = "http://evil.com%0d%0aSet-Cookie:..."
    char response[1024];
    sprintf(response, "Location: %s\r\n\r\n", url);
}
```
**审计要点：**
- 检查是否有URL解码、HTML实体解码等后续处理
- 漏洞可能发生在解码后而非原始输入

**漏洞形式C：缓冲区溢出导致的CRLF注入**
```c
// ✗ 漏洞：虽然有过滤，但缓冲区不足导致截断
void handle_header(const char *value) {
    char filtered[16];
    // 简单移除CRLF，但没有检查边界
    strcpy(filtered, value);  // 缓冲区溢出！
    char response[256];
    sprintf(response, "X-Data: %s\r\n\r\n", filtered);
}
```
**审计要点：**
- 过滤函数本身可能存在缓冲区问题
- 需要审计完整的数据流

---

### 3. **实战审计技巧**

**技巧1：追踪数据流的完整路径**

在发现疑似漏洞时：
1. 向上追踪：用户输入从哪里开始（HTTP参数、文件、网络）
2. 横向检查：中间经过哪些函数处理
3. 向下追踪：最终如何进入响应头

```c
// 追踪示例
const char *user_lang = get_param("lang");  // 入口
set_content_language(user_lang);  // 中间处理
// 在set_content_language内部:
char response[512];
sprintf(response, "Content-Language: %s\r\n", lang);  // 风险点
```

**技巧2：区分系统调用层级**

| 调用层级 | 风险等级 | 审计方法 |
|---------|--------|---------|
| 应用层sprintf → send | **P0高危** | 必须人工审计 |
| 应用层sprintf → strcat → send | **P0高危** | 追踪完整链路 |
| 应用层 → 库函数 → 系统send | **P1中** | 检查库函数是否过滤 |
| 应用层 → Web框架API | **P2低** | 框架通常内置过滤 |

**技巧3：识别"聪明的过滤"陷阱**

过滤代码看起来很安全，但实际有绕过方式：

```c
// 陷阱1：只检查\n，漏掉\r
if (strchr(input, '\n')) reject();
// 绕过: input = "value\rSet-Cookie:..."
// HTTP/1.1接受单独的\r作为换行符

// 陷阱2：使用isprint()检查
if (!isprint(c)) reject();
// 但这在某些locale下可能将某些控制字符判定为可打印

// 陷阱3：替换而非删除
char *p = input;
while ((p = strchr(p, '\n'))) *p = ' ';  // 替换为空格
// 同样可能绕过：\r仍然存在
```

---

### 4. **代码审计检查表（高效版）**

按以下顺序快速判定：

```
[ ] 步骤1：检查是否使用成熟框架
    ✓ nginx/Apache/IIS/Tomcat → 跳过
    ✗ 自定义HTTP → 继续

[ ] 步骤2：定位所有sprintf/snprintf
    搜索: sprintf\|snprintf\|strcat\|strcpy
    定位: 含有\r\n或HTTP头关键词的调用

[ ] 步骤3：验证参数来源
    参数是常量 → 无漏洞
    参数是函数参数 → 检查步骤4
    参数是外部输入 → 检查步骤5

[ ] 步骤4：验证过滤机制
    存在明确的CRLF过滤 → 检查步骤6
    存在白名单验证 → 检查步骤6
    无过滤 → 确认漏洞！

[ ] 步骤5：验证过滤的有效性
    检查是否过滤了\r\n两者
    检查是否有URL解码/HTML实体解码后的绕过
    检查过滤函数的缓冲区安全性

[ ] 步骤6：验证所有入口
    该响应头是否在其他地方也被设置？
    是否存在绕过过滤的其他代码路径？
```

---

### 5. **真实案例区分**

**案例1：Nginx模块中的CRLF注入**
- 表现：自定义Nginx模块使用sprintf构造响应
- 判定：95%是真漏洞（Nginx开发者通常不会自己处理HTTP细节）
- 修复：使用ngx_table_elt_t API替代手动字符串构造

**案例2：CGI程序的头注入**
- 表现：CGI脚本用printf输出HTTP头
- 判定：需要检查是否有HTTP头标准库函数
  - 直接printf → 通常有漏洞
  - 使用CGI库 → 库通常过滤
- 修复：使用CGI库的安全API

**案例3：WebSocket握手响应的CRLF**
- 表现：WebSocket服务器手动构造升级响应
- 判定：难度大，通常需要看RFC 6455实现细节
- 风险：WebSocket Sec-WebSocket-Key字段必须是base64编码（不含CRLF），但其他字段可能有注入风险

---



## 实现建议

### 核心防护方案

**方案1：CRLF过滤函数**
```c
int sanitize_header_value(const char *input, char *output, size_t outsize) {
    size_t j = 0;
    for (size_t i = 0; input[i] && j < outsize - 1; i++) {
        char c = input[i];
        // 移除CRLF和NULL
        if (c != '\r' && c != '\n' && c != '\0') {
            output[j++] = c;
        }
    }
    output[j] = '\0';
    return j;
}
```

**方案2：白名单验证**
```c
const char *VALID_LANGUAGES[] = {"en", "zh", "ja", "ko", NULL};

int is_valid_language(const char *lang) {
    for (int i = 0; VALID_LANGUAGES[i]; i++) {
        if (strcmp(lang, VALID_LANGUAGES[i]) == 0) {
            return 1;
        }
    }
    return 0;
}
```

**方案3：使用HTTP库API**
```c
// 使用libmicrohttpd等库
MHD_add_response_header(response, "X-Custom", sanitized_value);

// 使用nginx模块API
ngx_table_elt_t *h = ngx_list_push(&r->headers_out.headers);
h->value.data = sanitized_value;
```

### 检查清单
- [ ] 所有sprintf/snprintf构造的响应头检查CRLF过滤
- [ ] Location重定向使用URL验证
- [ ] Content-Disposition文件名进行字符过滤
- [ ] Set-Cookie值使用安全编码
- [ ] 测试CRLF注入：`value\r\nSet-Cookie: admin=1`

---

## 修复优先级

1. **立即修复**：Location重定向直接使用用户输入
2. **本周修复**：所有响应头构造添加CRLF过滤
3. **可选加强**：实现统一的响应头构造函数
4. **长期优化**：使用成熟HTTP库替代手动构造
