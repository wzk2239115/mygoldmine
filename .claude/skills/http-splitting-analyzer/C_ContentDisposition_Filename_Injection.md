# C/C++ Content-Disposition 文件名注入

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `sprintf(header, "Content-Disposition: attachment; filename=%s", name)` 拼接
- `printf("Content-Disposition: attachment; filename=%s", name)` 直接输出
- 文件名直接拼接未转义

**快速定位核心操作：**
1. 搜索关键字：`Content-Disposition`、`filename=`、`sprintf`/`printf`
2. 追踪文件名来源：用户输入、文件系统、数据库
3. 检查是否使用双引号包装
4. 查看是否过滤特殊字符（`;`、`,`、`
`）

**快速定位保护机制：**
- 特殊字符过滤：手动 `strchr()` 检查并移除
- 双引号转义：`replace '"' with '"'`
- 白名单验证：正则或字符集检查
- RFC 编码：使用 RFC 5987 编码

**代码示例：**
```c
// 危险：用户文件名直接拼接
void download_file(char *filename) {
    char header[256];
    sprintf(header, "Content-Disposition: attachment; filename=%s
",
            filename);  // 危险
    send_response(header);
}

// 危险：printf 直接输出
void serve_file(char *name) {
    printf("Content-Disposition: attachment; filename=%s
", name);  // 危险
}

// 危险：strcat 拼接
void build_header(char *user_name) {
    char header[512] = "Content-Disposition: attachment; filename=";
    strcat(header, user_name);  // 危险
    strcat(header, "
");
}
```

## Classify

**漏洞（High）：**
- 用户文件名未验证
- 文件名包含特殊字符导致头分割
- 允许目录遍历

**误报：**
- 文件名硬编码
- 经过白名单验证
- 使用安全库

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 缓冲区大小问题

## Low risk

**以下情况评为低风险：**
- 文件名硬编码
- 严格白名单验证
- RFC 合规编码
- 内部来源且已验证

## 审计专业技巧

### 1. 精准识别漏洞的5个特征

**特征1：头注入触发点识别**
```c
// 真实漏洞：换行符未过滤，导致HTTP头分割
sprintf(header, "Content-Disposition: attachment; filename=%s", user_input);
// 攻击：filename=file.txt\r\nContent-Type: text/html\r\n\r\n<script>alert(1)</script>
// 结果：浏览器执行HTML/JS，而非下载文件
```

**特征2：编码转换陷阱**
```c
// 误报案例：多字节字符处理
wchar_t *filename = L"文件.txt";  // 合法中文
// 审计误区：假设任何非ASCII都是攻击
// 正确做法：检查编码后是否包含\r\n\x00等控制字符
```

**特征3：保护机制绕过**
```c
// 不安全的过滤
char safe[256];
strcpy(safe, filename);
safe[strcspn(safe, "\n")] = '\0';  // 仅过滤\n，漏掉\r
// 漏洞：\r仍可导致头分割

// 安全的过滤
char safe[256];
for(int i=0; i<strlen(filename) && i<255; i++) {
    if(filename[i] < 32 || filename[i] > 126) {
        return ERROR;  // 拒绝所有控制字符
    }
    safe[i] = filename[i];
}
safe[i] = '\0';
```

**特征4：上下文分析**
```c
// 漏洞：Content-Disposition 在错误位置
printf("HTTP/1.1 200 OK\n");
printf("Content-Disposition: attachment; filename=%s\n", user_file);
// 如果user_file包含\r\n，可注入新的HTTP头

// 安全：使用RFC 5987编码
printf("HTTP/1.1 200 OK\r\n");
printf("Content-Disposition: attachment; filename*=UTF-8''");
// RFC编码会将特殊字符转为%%HH格式
```

**特征5：调用链追踪**
```c
// 真实场景：多层包装
void handle_request(char *req_filename) {
    char local_name[512];
    decode_url(req_filename, local_name);      // 第1层处理
    validate_filename(local_name);              // 第2层检查
    send_file_header(local_name);              // 第3层输出
}

// 审计关键：检查 validate_filename 是否实际阻挡了\r\n
// 误报原因：假设所有中间函数都已处理
```

### 2. 真实漏洞与误报的区分经验

**真实漏洞的必要条件（三层检查）**

| 条件 | 漏洞 | 误报 | 审计要点 |
|-----|------|------|--------|
| 用户输入来源 | 直接来自HTTP请求/表单 | 内部变量/配置文件 | 追踪taint source |
| 控制字符处理 | 未过滤\r\n\x00 | 完整过滤所有控制字符 | 检查过滤函数 |
| 上下文位置 | 在HTTP头中 | 在响应body中 | 确认sprintf位置 |
| 输出函数 | send()、fwrite() | printf()到日志 | 检查调用栈 |

**案例1：真实漏洞**
```c
// Java中的Content-Disposition漏洞（常见）
response.setHeader("Content-Disposition", "attachment; filename=" + userInput);
// 攻击：userInput = "file.zip\r\nContent-Length: 0\r\n\r\n<html>"
// 后果：HTTP响应被分割，注入恶意HTML
```

**案例2：误报案例**
```c
// 误报：虽然有sprintf拼接，但已有保护
char buffer[256];
// 验证步骤
if(strlen(filename) > 100) return ERROR;          // 长度限制
if(strcspn(filename, ";\r\n\"") != strlen(filename)) {
    return ERROR;                                  // 黑名单过滤
}
sprintf(header, "Content-Disposition: attachment; filename=%s", filename);
// 判定：低风险或不易利用，标记为code smell而非漏洞
```

**案例3：易漏掉的漏洞**
```c
// 危险：仅过滤\n，遗漏\r
char *filtered = filename;
filtered[strcspn(filtered, "\n")] = '\0';  // 残留\r
// 攻击成功：\r单独可导致某些服务器解析混乱
```

### 3. 审计检查清单

- [ ] **第1步**：定位所有sprintf/printf/fprintf拼接Content-Disposition的位置
- [ ] **第2步**：追踪filename参数的来源（用户输入或内部？）
- [ ] **第3步**：检查是否存在以下过滤：
  - `\r` 和 `\n` 双重过滤（不是仅过滤\n）
  - `\x00` （NULL字节）
  - 双引号转义或白名单验证
- [ ] **第4步**：确认输出是否真的发送到HTTP响应头（非日志）
- [ ] **第5步**：测试绕过：尝试URL编码(无效)、Unicode(需编码)、百分比编码后是否保留\r\n
- [ ] **第6步**：检查服务器配置是否额外保护（如某些WAF规则）

### 4. 常见误判错误

**误判1：假设框架自动处理**
```java
// 错误判定：假设Spring框架已处理
response.setHeader("Content-Disposition", userFilename);  // Spring会自动转义吗？不会！
// 正确做法：查证框架文档，通常需要手动处理
```

**误判2：只看过滤代码，不看调用顺序**
```c
char buffer[256];
strcpy(buffer, user_input);        // 未过滤
filter_special_chars(buffer);      // 过滤
send_header(buffer);               // 使用过滤后的
// 判定：安全（但需确认filter_special_chars真的过滤了\r\n）
```

**误判3：混淆RFC编码与安全性**
```c
// RFC 5987编码并非完全安全
char *encoded = rfc5987_encode(filename);  // %HH编码
printf("Content-Disposition: attachment; filename*=UTF-8''%s", encoded);
// 陷阱：如果编码实现有bug，仍可能注入
```

### 5. 快速漏洞/误报判定表

| 代码特征 | 判定 | 理由 | 置信度 |
|--------|------|------|--------|
| `sprintf(h, "...filename=%s", user)` + 无过滤 | 漏洞 | 直接拼接 | 95% |
| `sprintf + 黑名单过滤"; \r\n` | 低风险 | 不易利用但有缺陷 | 85% |
| `sprintf + 白名单[a-zA-Z0-9._-]` | 低风险 | 严格限制 | 98% |
| `sprintf + strlen()<50 + no_control_chars()` | 低风险 | 多重保护 | 90% |
| 硬编码文件名 | 安全 | 无用户输入 | 99% |
| `Content-Disposition` 在printf到日志中 | 低风险 | 非HTTP响应 | 88% |
