# C/C++ Location 头重定向未验证

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `sprintf(header, "Location: %s", url)` 拼接重定向 URL
- `printf("Location: %s", url)` 直接输出
- `strcat()` 拼接 Location 头

**快速定位核心操作：**
1. 搜索关键字：`Location:`、`sprintf`、`printf` 涉及 URL
2. 追踪 URL 来源：`getenv()`、命令行参数、网络数据
3. 检查是否存在 URL 验证或白名单
4. 检查是否限制了协议和域名

**快速定位保护机制：**
- URL 解析验证：`parse_url()` 或手动 `strstr()` 检查
- 协议限制：检查 `strstr(url, "http://")` 或 `strstr(url, "https://")`
- 域名白名单：比较 Host 部分
- 相对 URL：检查 `url[0] != '/' && strstr(url, "://")`

**代码示例：**
```c
// 危险：用户 URL 直接重定向
void redirect(char *url) {
    char header[512];
    sprintf(header, "Location: %s
", url);  // 危险
    send_response(header);
}

// 危险：getenv 直接使用
void handle_redirect() {
    char *redirect_to = getenv("QUERY_STRING");
    // 解析后...
    printf("Location: %s
", redirect_to);  // 危险
}

// 危险：命令行参数
int main(int argc, char *argv[]) {
    if (argc > 1) {
        printf("Location: %s
", argv[1]);  // 危险
    }
}
```

## Classify

**漏洞（High）：**
- 用户输入直接用于 Location 头
- 无 URL 格式或域名验证
- 允许任意协议跳转
- 开放重定向

**误报：**
- Location 值硬编码
- 使用 URL 解析库且有验证

**代码异味（Medium）：**
- 仅检查协议前缀
- 黑名单检查不完整
- 缺少边界检查

## Low risk

**以下情况评为低风险：**
- Location 值硬编码
- 严格白名单验证
- 仅允许相对 URL + 验证
- 来自内部配置文件

## 审计专业技巧

### 真实漏洞识别经验

#### 1. 危险信号识别
- **直接拼接信号**：`sprintf(header, "Location: %s")`、`printf()`、`strcat()` + 用户输入
  - 即使代码注释说"已验证"，必须跟踪代码路径确认
  - 常见陷阱：变量在不同分支有/无验证

- **来源追踪关键点**：
  - `getenv()` 获取环境变量（CGI 场景）
  - `getarg()`、`getparam()` 获取请求参数
  - 文件读取后直接使用
  - 数据库查询结果未清理

- **隐蔽漏洞特征**：
  - `char *url = ...` 后经过多次函数调用，最后在 Location 头使用
  - 封装的"验证函数"实际未验证（如 `validate_url()` 只检查长度）
  - 条件语句中的验证被 `||` 逻辑错误绕过

#### 2. 常见误报场景

**误报 1：混淆"反序列化"和"重定向"**
```c
// 误报风险：初看像重定向，实际是日志输出
void log_redirect(char *url) {
    char buffer[512];
    sprintf(buffer, "Redirect Location: %s", url);  // 仅日志，无实际重定向
    fprintf(logfile, "%s\n", buffer);
}
```
- **区分点**：检查头是否发送给客户端（`send_header()`、`http_response()` 等）
- **确认方法**：追踪 buffer 的最终去向，是文件/日志还是网络响应

**误报 2："Location: /" 硬编码但检查不严格**
```c
// 可能是误报
char *redirect_path = malloc(256);
strcpy(redirect_path, "Location: /");
strcat(redirect_path, user_input);  // 看起来拼接了
// 但实际上必须确认 user_input 的内容受限
```
- **确认方法**：查看 `user_input` 的赋值，若来自硬编码或白名单则安全

**误报 3：协议检查存在但不完整**
```c
if (strstr(url, "http://") || strstr(url, "https://")) {
    printf("Location: %s", url);  // 看起来检查了协议
}
// 但这个检查是黑名单逻辑反转，存在漏洞
```
- **审计点**：检查逻辑是 `if (safe)` 还是 `if (!safe)`
- **绕过方式**：JavaScript: URL (`javascript:`、`data:`、`//`)

#### 3. 真实漏洞 vs 误报 的关键判断点

| 场景 | 特征 | 判断 |
|------|------|------|
| 硬编码 URL | `sprintf(header, "Location: /home")` | 低风险 |
| 参数拼接 + 路径检查 | `if (url[0]=='/') sprintf(...)` | 中风险（需确认检查充分）|
| 参数拼接 + 无检查 | `sprintf(header, "Location: %s", argv[1])` | 高风险 |
| 文件读取 + 拼接 | 从配置文件读取但未验证格式 | 中风险 |
| 环境变量 + 转义 | `getenv()` 但经过 URL 编码 | 低风险 |

#### 4. 审计清单

**第一步：代码定位**
- [ ] 搜索 `Location:` 关键字的所有出现
- [ ] 搜索 `sprintf`、`printf`、`snprintf`、`strcat` 相关代码
- [ ] 检查是否使用了 `send_header()`、`http_header()` 等发送函数

**第二步：来源分析**
- [ ] 跟踪 URL 变量的赋值链：是硬编码、参数、文件、数据库？
- [ ] 确认数据来源（用户输入、环境变量、网络请求）
- [ ] 检查多个赋值分支，有些分支可能安全，有些不安全

**第三步：验证检查分析**
- [ ] 识别所有 URL 验证代码
  - 协议白名单检查（仅允许 `http://` 和 `https://`）
  - 域名白名单检查
  - 相对路径检查（`url[0] == '/'`）
- [ ] 验证检查是否有逻辑漏洞
  - `if (allow)` vs `if (!allow)` 逻辑反转
  - 黑名单检查不完整（如只检查 `http://` 忽略 `//`）
  - 绕过方式：大小写、Unicode、URL 编码、空字符

**第四步：协议审视**
- [ ] 是否允许 `javascript:`、`data:`、`file://` 等危险协议？
- [ ] 是否允许无协议的 `//` 双斜杠跳转（相对协议）？
- [ ] 是否有绕过 `strstr()` 检查的方式（如 `%2f%2f`、`\x2f\x2f`）？

#### 5. 常见绕过和陷阱

```c
// 陷阱 1：只检查前缀，未检查后续
if (strstr(url, "http") == url) {  // 可被 "httpp://evil.com" 绕过
    printf("Location: %s", url);
}

// 陷阱 2：大小写敏感性
if (strstr(url, "http://")) {  // 被 "HTTP://" 或 "Http://" 绕过
    printf("Location: %s", url);
}

// 陷阱 3：使用了验证函数名但实际未调用
validate_redirect_url(url);  // 函数存在但可能未真正执行
printf("Location: %s", url);

// 陷阱 4：条件逻辑反转
if (!is_valid_url(url)) {
    printf("Location: %s", url);  // 反向逻辑，应该拒绝而非接受
}
```

#### 6. 漏报风险最高的代码模式

- **指针操作**：多层指针传递，难以追踪来源
- **宏定义**：`#define REDIRECT(u) printf("Location: %s", u)` 使用宏
- **异步调用**：HTTP 响应在异步回调中构造
- **条件编译**：某些代码只在特定编译选项下存在
- **模板代码**：C++ 模板中的字符串拼接，需要展开分析
