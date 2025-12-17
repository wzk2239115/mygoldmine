# C/C++ Set-Cookie 值 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `sprintf("Set-Cookie: name=%s", value)` 拼接 Cookie
- `printf("Set-Cookie: %s", cookie_string)` 直接输出
- Cookie 值拼接未过滤 CRLF

**快速定位核心操作：**
1. 搜索关键字：`Set-Cookie`、Cookie 相关的 `sprintf`/`printf`
2. 追踪 Cookie 值来源：`getenv()`、参数、网络数据
3. 检查是否存在 CRLF 过滤
4. 追踪 Cookie 构造过程

**快速定位保护机制：**
- CRLF 检查：`if (strchr(value, '') || strchr(value, '
'))`
- 循环过滤：遍历移除 CRLF 字符
- 白名单验证：正则或字符集检查
- URL 编码：`urlencode()` 函数处理

**代码示例：**
```c
// 危险：用户输入直接设置 Cookie
void set_cookie(char *token) {
    printf("Set-Cookie: session=%s
", token);  // 危险
}

// 危险：getenv 直接使用
void handle_cookie() {
    char *auth = getenv("HTTP_X_AUTH");
    printf("Set-Cookie: auth=%s
", auth);  // 危险
}

// 危险：sprintf 拼接
void create_session(char *id) {
    char cookie[256];
    sprintf(cookie, "Set-Cookie: sid=%s
", id);  // 危险
    send_response(cookie);
}
```

## Classify

**漏洞（Critical）：**
- 用户输入直接用于 Cookie 值
- 无 CRLF 过滤
- 导致响应分割

**误报：**
- Cookie 值硬编码
- 系统生成的值
- 库处理的 Cookie

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接拼接

## Low risk

**以下情况评为低风险：**
- Cookie 值硬编码
- 严格 CRLF 过滤
- 白名单验证
- 内部来源且已验证

## 审计专业技巧

### 漏洞与误报区分

**真实漏洞特征：**

1. **直接拼接 + 未验证输入**
   ```c
   // 确实是漏洞：用户输入直接写入 HTTP 头
   char buffer[256];
   sprintf(buffer, "Set-Cookie: token=%s", user_input);
   send_http_response(buffer);
   ```
   - 关键点：`sprintf/printf` 拼接 + 用户来源数据 + 无前置验证

2. **环境变量直接使用**
   ```c
   // 确实是漏洞：HTTP 头来自 CGI 环境变量
   printf("Set-Cookie: auth=%s", getenv("HTTP_X_AUTH"));
   ```
   - 审计重点：检查 `getenv()` 返回值是否经过净化

**常见误报陷阱：**

1. **硬编码 Cookie 值（误报）**
   ```c
   // 虚假警报：值完全由应用控制
   const char *session_id = "fixed_session_xyz123";
   sprintf(buffer, "Set-Cookie: sid=%s", session_id);
   ```
   - 判断标准：搜索字符串源头，是否完全由开发者定义

2. **库函数自动处理（误报）**
   ```c
   // 虚假警报：标准库已处理 CRLF
   setcookie("token", value, 0, "/", ".example.com", 1, 1);
   // 语言级别自动编码，不存在 CRLF 注入
   ```
   - 判断标准：调用的是否是框架或标准库的安全函数

3. **已编码的值（误报）**
   ```c
   // 虚假警报：输入已是 URL 编码形式
   char encoded[512];
   urlencode(user_input, encoded);
   sprintf(buffer, "Set-Cookie: data=%s", encoded);
   // 编码后不可能包含 CRLF
   ```
   - 判断标准：追踪数据流，确认是否已编码

### 审计流程细节

**第一步：追踪数据来源**
- 区分四类来源：硬编码值、用户输入、库生成、环境变量
- 硬编码 → 低风险；用户输入 → 高风险

**第二步：检查过滤点**
```c
// 完整过滤的正确做法
int is_cookie_safe(const char *value) {
    for (int i = 0; value[i]; i++) {
        if (value[i] == '\r' || value[i] == '\n' ||
            value[i] == ';' || value[i] == ',') {
            return 0;  // 拒绝不安全字符
        }
    }
    return 1;
}

// 审计时：确认过滤是否在所有入口都存在
if (is_cookie_safe(user_input)) {
    sprintf(buffer, "Set-Cookie: token=%s", user_input);
}
```

**第三步：识别迂回路径**
- 检查是否通过多个函数间接构造 Cookie
- 验证每个中间步骤是否保留了 CRLF
- 查找 memcpy/strcpy 拼接，可能绕过检查

### 常见编码错误

**错误1：不完整的黑名单**
```c
// 危险：仅检查 CR 和 LF，忽略编码绕过
value[strcspn(value, "\r")] = '\0';  // 只移除 \r
// 攻击者可用其他编码或特殊字符绕过
```

**错误2：多过程拼接**
```c
// 危险：值在两个函数间拼接，中间未验证
void process(char *input) {
    char tmp[256];
    sprintf(tmp, "auth=%s", input);  // 未检查
    set_response_header(tmp);  // 后续函数假定已安全
}
```

**错误3：条件检查不全面**
```c
// 危险：仅在特定分支检查
if (is_admin) {
    printf("Set-Cookie: role=%s", user_role);  // 可能未检查
}
```

### 审计工具检查清单

- [ ] 搜索所有 `printf`、`sprintf` 的 HTTP 头拼接
- [ ] 追踪每个拼接中的数据来源
- [ ] 验证用户输入是否通过安全函数处理
- [ ] 检查多阶段构造的 Cookie 值
- [ ] 审查过滤函数是否处理所有危险字符
- [ ] 确认没有编码或格式化绕过点
- [ ] 查看是否使用了 HTTP 库的 Cookie 管理接口
