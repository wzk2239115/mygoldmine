# C/C++ libcurl请求头用户输入注入

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `curl_easy_setopt`, `CURLOPT_HTTPHEADER`, `curl_slist_append`, `sprintf`, `snprintf`, `CURLOPT_URL`, `CURLOPT_USERAGENT`
- **快速检查：** curl_slist_append的参数是否包含用户输入，是否有CRLF过滤

## 漏洞成因

使用libcurl发送HTTP请求时，若用户输入直接拼接到请求头（通过`curl_slist_append`添加到`CURLOPT_HTTPHEADER`），攻击者可注入CRLF字符创建任意HTTP头，导致请求走私、认证绕过、SSRF增强等攻击。

### 常见漏洞模式

```c
// ✗ 漏洞：用户输入直接拼接到请求头
void send_request(const char *user_value) {
    CURL *curl = curl_easy_init();
    struct curl_slist *headers = NULL;
    char header[256];

    snprintf(header, sizeof(header), "X-Custom: %s", user_value);
    headers = curl_slist_append(headers, header);  // 未过滤CRLF

    curl_easy_setopt(curl, CURLOPT_URL, "https://api.example.com");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_perform(curl);
    // 攻击: user_value = "value\r\nX-Admin: true"
}
```

```c
// ✗ 漏洞：User-Agent使用用户输入
void fetch_with_ua(const char *user_agent) {
    CURL *curl = curl_easy_init();

    curl_easy_setopt(curl, CURLOPT_URL, "https://api.example.com");
    curl_easy_setopt(curl, CURLOPT_USERAGENT, user_agent);  // 未验证
    curl_easy_perform(curl);
    // 攻击: user_agent = "Mozilla\r\nX-Injected: header"
}
```

```c
// ✗ 漏洞：Authorization头使用用户输入
void api_call(const char *token) {
    CURL *curl = curl_easy_init();
    struct curl_slist *headers = NULL;
    char auth_header[512];

    snprintf(auth_header, sizeof(auth_header), "Authorization: Bearer %s", token);
    headers = curl_slist_append(headers, auth_header);

    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_perform(curl);
    // 攻击: token = "valid_token\r\nHost: evil.com"
}
```

```c
// ✗ 漏洞：Cookie值用户可控
void send_with_cookie(const char *session_id) {
    CURL *curl = curl_easy_init();
    char cookie[256];

    snprintf(cookie, sizeof(cookie), "session=%s", session_id);
    curl_easy_setopt(curl, CURLOPT_COOKIE, cookie);  // Cookie值可控
    curl_easy_perform(curl);
}
```

```c
// ✓ 修复：CRLF过滤
char* sanitize_header_value(const char *input) {
    static char output[1024];
    size_t j = 0;

    for (size_t i = 0; input[i] && j < sizeof(output) - 1; i++) {
        if (input[i] != '\r' && input[i] != '\n') {
            output[j++] = input[i];
        }
    }
    output[j] = '\0';
    return output;
}

void safe_request(const char *user_value) {
    CURL *curl = curl_easy_init();
    struct curl_slist *headers = NULL;
    char header[256];

    const char *safe_value = sanitize_header_value(user_value);
    snprintf(header, sizeof(header), "X-Custom: %s", safe_value);
    headers = curl_slist_append(headers, header);

    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_perform(curl);
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | curl_slist_append用户输入 | 搜索 `curl_slist_append.*%s\|sprintf.*curl_slist`，追踪变量来源 |
| **P0** | CURLOPT_HTTPHEADER | 搜索 `CURLOPT_HTTPHEADER`，检查headers构造过程 |
| **P1** | CURLOPT_USERAGENT | 搜索 `CURLOPT_USERAGENT`，检查参数是否用户可控 |
| **P1** | CURLOPT_COOKIE | 搜索 `CURLOPT_COOKIE`，检查Cookie值来源 |
| **P2** | Authorization头 | 搜索 `Authorization.*%s`，检查token来源 |
| **P2** | 自定义头拼接 | 搜索 `snprintf.*:.*%s.*curl_slist`，评估注入风险 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 请求头全部硬编码 | 快速跳过，无用户输入 |
| **L1** | 头值来自配置文件 | 关键词扫描确认来源可信 |
| **L2** | 单文件内拼接用户输入到头 | 跳读检查CRLF过滤 |
| **L3** | 头值由外部函数返回 | 逐行追踪函数返回值 |
| **L4** | 封装的HTTP客户端库 | 跨模块审计头设置接口 |

---

## 审计专业技巧与经验

### 真实漏洞vs误报区分指南

**真实漏洞特征（High Confidence）：**
1. **直接拼接模式** - 用户输入通过sprintf/snprintf直接拼接到字符串，然后传入curl_slist_append
   - 查证方法：从curl_slist_append向前逆向追踪变量构造，检查是否有格式化字符串且参数来自输入源
   - 案例：`snprintf(buf, size, "X-Token: %s", user_token); curl_slist_append(headers, buf)`

2. **函数返回值直接使用** - 从用户输入相关函数的返回值未经过滤就传给curl_slist_append
   - 追踪技巧：检查函数名含义（如get_user_header、extract_value等）和调用链
   - 红旗：函数在同文件内定义但没有CRLF过滤逻辑

3. **CURLOPT_*选项的直接赋值** - CURLOPT_USERAGENT、CURLOPT_COOKIE等直接赋值用户变量
   - 识别：grep搜索`curl_easy_setopt.*CURLOPT_(USERAGENT|COOKIE|REFERER).*[a-z_]`，排除硬编码字符串

**误报常见原因：**
1. **错误的数据流追踪** - 变量名相似但实际来源不同
   - 排查：分析变量初始化位置，区分用户输入vs系统变量vs配置值
   - 示例：`const char *user_agent = "Mozilla/5.0"` 看起来像用户输入但实际是常量

2. **已经过滤的输入** - 存在CRLF过滤但代码审计时遗漏
   - 核查：向前向后搜索sanitize、filter、validate等关键词
   - 技巧：检查变量作用域，确认过滤函数的调用顺序（过滤必须在curl_slist_append之前）

3. **库函数自动防护** - 某些libcurl版本或特定参数的内置保护
   - 局限：不同版本行为不同，建议信任工作假设（假设无内置防护）

### 审计高效技巧

**关键代码模式识别：**
```c
// 🔴 极高风险：循环中动态构造头
for (int i = 0; i < count; i++) {
    snprintf(header, sizeof(header), "X-Custom-%d: %s", i, user_array[i]);
    headers = curl_slist_append(headers, header);  // 多次注入机会
}

// 🔴 高风险：字符串拼接后传入
char temp[512];
strcpy(temp, user_prefix);
strcat(temp, ": ");
strcat(temp, user_value);
curl_slist_append(headers, temp);  // 双点注入

// 🟡 中风险：条件分支导致覆盖
if (user_header) {
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, user_header);  // 用户可控分支
}

// 🟢 低风险：有基础验证
if (strlen(user_input) < 100 && !strchr(user_input, '\n')) {  // 虽然不完美但有防护意图
    curl_easy_setopt(curl, CURLOPT_USERAGENT, user_input);
}
```

**快速定位技巧：**
1. **反向搜索法**：先找所有curl_slist_append调用点，再追踪参数来源
2. **变量流向法**：跟踪user/input前缀的变量在何处被使用，特别关注curl_相关函数
3. **函数签名法**：搜索函数参数是否包含const char*或char*，推测可能的输入点
4. **宏展开法**：对于CURLOPT_HTTPHEADER等宏，查看实际传递的结构体内容

### 误报排查检查单

- [ ] 该变量的初始化是否来自真实的用户输入（GET/POST参数、文件内容、网络数据）
- [ ] CRLF过滤函数是否在curl_slist_append调用之前执行
- [ ] 过滤函数是否覆盖所有危险字符（至少\r\n，建议加上\0）
- [ ] 是否存在多个赋值路径，其中某些路径未经过滤
- [ ] 函数返回值是否直接用于curl操作，还是还有后续处理

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. curl_slist_append或CURLOPT_*的参数包含用户输入
2. 未进行CRLF字符过滤
3. 请求发送到外部服务器

### 典型漏洞特征（满足任一项即确认）
- ✗ `snprintf(header, size, "X-Custom: %s", user_input); curl_slist_append(headers, header)`
- ✗ `curl_easy_setopt(curl, CURLOPT_USERAGENT, user_input)`
- ✗ `curl_easy_setopt(curl, CURLOPT_COOKIE, user_cookie)`
- ✗ Authorization头使用未过滤的用户token

### 安全排除（任一项充分）
- ✓ 存在CRLF过滤（检查`\r`和`\n`）
- ✓ 头值来自可信来源（配置、硬编码）
- ✓ 使用URL编码处理头值
- ✓ libcurl版本有内置CRLF检查（需验证）

### 灰色判定（风险较低但需注意）
- 请求仅发送到内部服务
- 用户输入经过长度限制但无字符过滤
- 有基础验证但可能被绕过

---

## 实现建议

### 核心防护方案

**方案1：CRLF过滤函数**
```c
int sanitize_header_value(const char *input, char *output, size_t outsize) {
    size_t j = 0;
    for (size_t i = 0; input[i] && j < outsize - 1; i++) {
        char c = input[i];
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
int is_valid_header_value(const char *value) {
    // 仅允许可打印ASCII字符，排除控制字符
    for (size_t i = 0; value[i]; i++) {
        if (value[i] < 0x20 || value[i] > 0x7E) {
            return 0;
        }
    }
    return 1;
}
```

**方案3：使用Base64编码**
```c
void set_encoded_header(CURL *curl, const char *name, const char *value) {
    struct curl_slist *headers = NULL;
    char header[1024];
    char encoded[512];

    // Base64编码可确保无CRLF
    base64_encode(value, encoded, sizeof(encoded));
    snprintf(header, sizeof(header), "%s: %s", name, encoded);
    headers = curl_slist_append(headers, header);

    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
}
```

### 检查清单
- [ ] 所有curl_slist_append的参数经过CRLF过滤
- [ ] CURLOPT_USERAGENT使用固定值或过滤后的值
- [ ] CURLOPT_COOKIE值进行字符验证
- [ ] Authorization头的token进行格式验证
- [ ] 测试CRLF注入：`value\r\nX-Injected: header`

---

## 修复优先级

1. **立即修复**：Authorization或认证头使用未过滤的用户输入
2. **本周修复**：所有自定义头添加CRLF过滤
3. **可选加强**：实现统一的头设置函数
4. **长期优化**：封装安全的HTTP客户端API
