# C/C++ 多行响应头解析未规范化

## Details

**审计等级：L2（跳读）/ L3（逐行读）**

**危险函数特征：**
- `sprintf(header, "%s", external_value)` 中值包含 `
`
- `strcat()` 拼接包含换行的值
- 从外部源读取头值未过滤

**快速定位核心操作：**
1. 搜索关键字：`
` 在 `sprintf`/`printf`/`strcat` 中
2. 追踪头值来源：`getenv()`、网络数据、文件、数据库
3. 检查是否存在规范化处理
4. 追踪头值的完整处理流程

**快速定位保护机制：**
- 规范化过滤：遍历字符串移除 `` 和 `
`
- 检查函数：`strchr(value, '') || strchr(value, '
')`
- RFC 合规：验证响应头格式
- 库防护：使用验证头部的 HTTP 库

**代码示例：**
```c
// 危险：外部值直接用于响应头
void forward_header(char *external_header) {
    printf("%s
", external_header);  // 危险：未规范化
}

// 危险：API 响应直接转发
void proxy_response(char *api_response) {
    char header[512];
    sprintf(header, "X-Custom: %s
", api_response);  // 危险
    send_response(header);
}

// 危险：数据库字段直接用于头
void db_to_header(char *db_value) {
    printf("X-Data: %s
", db_value);  // 危险
}
```

## Classify

**漏洞（Medium）：**
- 外部值包含 `
` 未规范化
- 导致响应分割
- 框架/库未自动检测

**误报：**
- 头值硬编码
- 库已规范化

**代码异味（Medium）：**
- 外部来源未验证
- 仅过滤部分字符
- 间接流程

## Low risk

**以下情况评为低风险：**
- 头值硬编码
- 明确过滤 CRLF
- 库已验证
- 内部来源且已验证

## Audit Tips

### 专业审计技巧

#### 1. 精准定位注入点
**容易误判的场景：**
- `sprintf()` 中的 `%s` 格式符不等于危险：仅当值来自外部时才危险
- `printf("Host: %s\n", hostname)` 在已验证 hostname 时安全
- **核心判断**：追踪值的来源，不要看函数名

**正确的追踪方法：**
```c
// 步骤1：识别可能点
char header[256];
sprintf(header, "X-Forward: %s", user_input);  // 标记为可疑

// 步骤2：回溯数据来源
// user_input 来自：request->header vs request->body vs config_file？

// 步骤3：检查中间处理
// 是否被 validate_header() 清理过？
// 是否经过 URL decode（可能包含 %0D%0A）？
```

#### 2. 隐蔽的注入向量
**常见但易忽视的来源：**
- `getenv()` 返回值：环境变量可被攻击者控制（容器/CI/CD 场景）
- `getpwnam()->pw_gecos` 注释字段：从 /etc/passwd 读取，可能包含换行
- `readlink()` 结果：符号链接可被伪造
- 正则表达式捕获组：如果 regex 允许任意字符
- 二进制协议解析：长度字段可能包含 `\r\n`

**审计案例：**
```c
// 危险：环境变量直接用于头部
char *user_agent = getenv("HTTP_USER_AGENT");
sprintf(header, "X-UA: %s\n", user_agent);  // 攻击者可控环境

// 危险：数据库 BLOB 字段
sqlite3_stmt *stmt = prepare("SELECT data FROM users");
char *db_blob = (char*)sqlite3_column_blob(stmt, 0);
sprintf(header, "X-Data: %s\n", db_blob);  // BLOB 可能包含字节 0x0D0A
```

#### 3. 真实漏洞 vs 误报的鉴别

**真实漏洞的 4 个必要条件：**

| 条件 | 判断标准 | 例外情况 |
|------|---------|---------|
| **外部输入** | 来自网络/API/文件/ENV | 硬编码常量 = 误报 |
| **包含 CRLF** | 值本身或解码后含 `\r\n` | 仅规范化不包含字符 = 误报 |
| **未规范化** | 代码无 `strchr(v, '\r')` 检查 | 调用了安全库（如 libcurl）= 误报 |
| **可达响应** | 攻击者控制的值送入 HTTP 响应头 | 值只用于日志/数据库 = 低风险 |

**常见误报模式：**
```c
// 误报1：硬编码值
sprintf(header, "Server: Apache/2.4\r\n");  // 虽有 \r\n 但不可控

// 误报2：库已防护
curl_slist_append(headers, user_value);  // libcurl 内部规范化

// 误报3：仅规范化不注入
char sanitized[256];
strcpy(sanitized, user_value);
for(int i=0; i<strlen(sanitized); i++) {
    if(sanitized[i]=='\r' || sanitized[i]=='\n')
        sanitized[i]='_';  // 虽未检查但规范化了
}

// 误报4：值不可达响应
char *data = get_user_input();
if(strchr(data, '\r') || strchr(data, '\n')) {
    log_suspicious(data);  // 只记录日志，未进入响应
    return ERROR;
}
```

#### 4. 高级漏洞场景

**常见的真实漏洞组合：**

1. **反向代理/网关模式** - 最高风险
   - 从上游 API 读取响应头，直接转发给客户端
   - 上游响应可能经过多个过滤层，客户端却绕过限制
   - 审计重点：查找 `strcpy/sprintf` 用于头部转发的地方

2. **自定义 HTTP 库** - 高风险
   - 团队自己写的 HTTP 响应生成函数
   - 通常缺少 RFC 7230 CRLF 验证
   - 审计重点：搜索 `\r\n` 硬编码，再检查前面的 `%s`

3. **编码/解码混淆** - 中风险
   - 输入 URL decode → 包含字面 `\r\n`
   - 或输入含 `%0D%0A` 字符串 → 若代码检查字面 `\r\n` 会绕过
   - 审计重点：检查 decode 顺序和检查顺序

#### 5. 审计检查清单

**L2 快速审查（5 分钟）：**
- [ ] 搜索 `sprintf.*header` + `%s`
- [ ] 搜索 `send_response`/`printf` 上下文
- [ ] 值是否来自 `getenv/argv/request`？
- [ ] 是否有 `strchr(*, '\r')` 或 `filter` 调用？

**L3 深度审查（15 分钟）：**
- [ ] 完整追踪数据流从网络到响应
- [ ] 检查是否使用了验证库（libcurl/nghttp2）
- [ ] 查看是否有 URL decode/encode 操作
- [ ] 验证过滤函数的完整性（是否遗漏 `\n`）
- [ ] 检查是否有并发/多线程条件竞争

**关键搜索模式：**
```bash
# 查找所有头部构造
grep -rn "sprintf.*\\\\" .
grep -rn "printf.*\\\\" .
grep -rn "header\[" .

# 追踪参数来源
grep -B5 "sprintf.*header" . | grep -E "argv|getenv|recv|fgets"

# 查找不完整的过滤
grep -n "strchr.*'\\\\r'" . | grep -v "\\\\n"
```
