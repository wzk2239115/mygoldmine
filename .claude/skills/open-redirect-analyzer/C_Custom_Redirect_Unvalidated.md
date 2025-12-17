## C/C++ 自定义重定向函数用户可控参数审计指南

---

### Details

#### 漏洞触发点

C/C++ 应用中常见的自定义重定向函数通常通过手动构建 HTTP 响应来实现：

```c
// 典型的自定义重定向实现
void redirect_user(const char *url) {
    printf("HTTP/1.1 302 Found\r\n");
    printf("Location: %s\r\n", url);
    printf("Content-Length: 0\r\n");
    printf("\r\n");
}

// CGI 环境下的重定向
void send_redirect(const char *target_url) {
    printf("Status: 302\r\n");
    printf("Location: %s\r\n\n", target_url);
}
```

**核心风险**：自定义重定向函数直接将用户控制的参数（通过 GET/POST 参数、HTTP 头、Cookie 等）拼接到 `Location` 响应头中，未对 URL 的合法性、协议、域名等进行任何验证。攻击者可通过控制重定向参数，将用户重定向至恶意网站进行钓鱼、凭证盗取或恶意代码分发。

---

#### 快速定位核心操作 **[L1: 关键词扫描]**

在 C/C++ 项目中快速定位重定向代码：

**重定向函数签名和关键字**
- `printf("Location: %s"...)` - 格式化输出 Location 头
- `sprintf(buffer, "Location: %s"...)` - 缓冲区构建 Location 头
- `fprintf(stdout, "Location: %s"...)` - 文件流输出重定向
- `send_header()`, `write_header()`, `redirect()`, `send_redirect()` - 自定义重定向函数
- `302`, `301`, `303`, `307`, `308` - HTTP 重定向状态码
- `Location:`（冒号后紧跟参数） - Location 响应头值

**搜索关键词**
- `Location`（带冒号）
- `302`, `301`, `303`, `307`, `308`
- `printf`, `sprintf`, `fprintf`, `vprintf` 配合重定向
- `redirect`, `send_redirect`, `goto_url`
- `strncpy`, `strcpy`, `memcpy` 用于拼接重定向 URL

**典型危险代码模式**

```c
// 模式 1：直接从 QUERY_STRING 获取重定向目标
void handle_login(void) {
    const char *redirect_url = getenv("QUERY_STRING");
    // 提取 redirect=xxx 参数
    printf("Location: %s\r\n\r\n", redirect_url);
}

// 模式 2：从表单参数构建重定向
void process_form(char *post_data) {
    char redirect_target[512];
    sscanf(post_data, "target=%511s", redirect_target);
    printf("Status: 302\r\nLocation: %s\r\n\n", redirect_target);
}

// 模式 3：通过 HTTP 头获取重定向参数
void handle_request(const char *referer) {
    char location[256];
    snprintf(location, sizeof(location), "Location: %s\r\n", referer);
    fputs(location, stdout);
}

// 模式 4：Cookie 中的重定向参数
void redirect_from_cookie(const char *session_id) {
    char redirect_url[1024];
    sprintf(redirect_url, "Location: /dashboard?session=%s\r\n", session_id);
    puts(redirect_url);
}

// 模式 5：路径拼接的重定向
void redirect_to_path(const char *user_path) {
    char full_url[512];
    strcpy(full_url, "https://");
    strcat(full_url, user_path);
    printf("Location: %s\r\n\r\n", full_url);
}
```

---

#### 快速定位保护机制 **[L2-L4: 跳读/逐行读/跨模块追踪]**

**第一阶段**（L2：跳读）：查看重定向语句周围 5-10 行代码
- 检查重定向前是否调用了验证函数（如 `validate_url()`, `is_safe_redirect()`, `check_whitelist()`）
- 检查是否存在 `strstr()`, `strncmp()`, `strchr()` 等字符串操作用于 URL 验证
- 检查是否有对 `://`, `//`, `http`, `https` 等的检查
- 观察是否存在域名或路径的白名单判断

**第二阶段**（L3：逐行读）：完整阅读重定向相关函数
- 追踪重定向参数的来源（`getenv()`, `getparam()`, 函数参数、全局变量）
- 识别参数是否经过任何长度限制、字符过滤、编码转换
- 检查是否有 URL 解析逻辑（手动提取协议、域名、路径部分）
- 检查是否存在缓冲区溢出风险（参数长度未验证直接放入固定大小数组）

**第三阶段**（L4：跨模块追踪）：追踪参数流转过程
- 参数从获取（`getenv()`, 解析请求）到使用的完整流程
- 验证函数在参数流中的位置和有效性
- 检查是否存在多个入口点或绕过验证的路径
- 追踪验证函数的实现，确认逻辑是否存在缺陷

**关键防护方案的检查清单**

| 防护机制 | 检查要点 | 审计等级 |
|---------|---------|---------|
| **白名单验证** | 重定向目标是否与预定义 URL 列表精确匹配 | L2 |
| **URL 结构解析** | 是否手动或通过库解析 URL（协议、域名、路径分离） | L2 |
| **协议限制** | 是否验证仅允许 http 或 https 协议 | L3 |
| **域名检查** | 是否验证域名属于本域或可信域名列表 | L3 |
| **路径限制** | 是否仅允许相对路径或特定前缀的路径 | L2 |
| **长度验证** | 参数长度是否在合理范围内进行了检查 | L2 |
| **字符过滤** | 是否对 URL 中的特殊字符进行了过滤 | L3 |
| **URL 编码处理** | 重定向参数是否可能被双编码或编码绕过 | L3 |
| **缓冲区安全** | 参数拷贝是否使用了安全函数（`strncpy` vs `strcpy`） | L2 |
| **完整链路追踪** | 参数从入口到 printf 的完整验证流程 | L4 |

**安全代码示例（用于对比）**

```c
// 正确的实现方式 - 白名单验证
#define MAX_SAFE_URLS 10
static const char *allowed_urls[] = {
    "/dashboard",
    "/profile",
    "/settings",
    "https://trusted.example.com/oauth",
    "https://partner.example.com/api"
};

int is_safe_redirect(const char *url) {
    // 相对路径检查
    if (url[0] == '/' && url[1] != '/') {
        // 白名单验证相对路径
        for (int i = 0; i < MAX_SAFE_URLS; i++) {
            if (strncmp(url, allowed_urls[i], strlen(allowed_urls[i])) == 0) {
                return 1;
            }
        }
        return 0;
    }

    // 绝对 URL 检查 - 必须是 https 且在可信域名列表内
    if (strncmp(url, "https://", 8) == 0) {
        const char *domain_end = strchr(url + 8, '/');
        size_t domain_len = (domain_end) ? domain_end - (url + 8) : strlen(url + 8);

        for (int i = 0; i < MAX_SAFE_URLS; i++) {
            if (strstr(allowed_urls[i], "https://") &&
                strncmp(url, allowed_urls[i], domain_len + 8) == 0) {
                return 1;
            }
        }
        return 0;
    }

    return 0;
}

void handle_login(const char *next_page) {
    if (!is_safe_redirect(next_page)) {
        printf("Status: 400\r\n\r\n");
        return;
    }

    printf("Status: 302\r\n");
    printf("Location: %s\r\n", next_page);
    printf("Content-Length: 0\r\n\r\n");
}
```

---

### Classify

#### 如何研判漏洞/误报/代码异味

**确认为真实漏洞（High/Critical）**

1. **参数可控且直接使用**：重定向 URL 完全来自用户输入（QUERY_STRING、POST 数据、HTTP 头、Cookie），在进入 `printf` 或类似输出函数前未经任何验证
2. **无有效防护机制**：
   - 不存在任何白名单检查或域名验证
   - 只有黑名单过滤（如简单的 `strstr(url, "evil.com")` 检查，易被编码或绕过）
   - 仅检查路径但不检查协议（允许 `javascript://` 或 `data://` 等协议）
3. **完整利用链**：用户可重定向到任意外部网站（如 `http://attacker.com`、`//attacker.com`、`https://evil.com/phishing`）
4. **应用场景关键**：重定向发生在身份验证（登录后跳转）、授权流程（OAuth callback）、支付完成等关键功能

**判定为误报（False Positive）**

满足以下任何一条：
1. **严格的精确白名单**：重定向目标必须完全匹配预定义的 URL 列表，使用 `strcmp()` 或 `strncmp()` 进行精确比较，不接受参数化
2. **相对路径隔离**：应用明确检查重定向目标是否为相对路径（以 `/` 开头但不以 `//` 开头），拒绝所有包含 `://` 的 URL
3. **严格的协议和域名验证**：
   - 检查协议仅为 `http://` 或 `https://`
   - 检查域名精确属于本域或预定义的可信域名列表
   - 使用安全的字符串函数进行验证
4. **缓冲区安全**：所有参数拷贝使用 `strncpy()`, `strncat()` 等带长度限制的函数，有明确的长度检查
5. **整体防御**：即使应用本身防护不完美，部署在 WAF、API 网关、防火墙后，该漏洞被阻止

**代码异味（Code Smell）**

- 存在 TODO 注释提示"需要添加 URL 验证"但未实现
- 验证函数存在逻辑缺陷（如仅检查 URL 前缀 `strncmp(url, "http", 4)` 而不检查完整协议）
- 使用黑名单方式过滤恶意字符串（如检查 `strstr(url, "evil") == NULL`），容易被编码绕过
- 多个重定向点，部分有保护，部分没有（防护不一致）
- 参数长度检查存在，但验证逻辑在长度检查之后（可能被缓冲区溢出利用）
- 代码中有注释表明原本打算实现验证但被注释掉了

---

### Low risk

#### 以下情况应给予低风险评级

1. **完整的精确白名单验证**
   - 重定向目标被严格限制在明确定义的 URL 列表中
   - 使用 `strcmp()` 或 `strncmp()` 进行逐字符精确匹配
   - 白名单包含的是完整的绝对 URL（如 `https://trusted.example.com/page`）或相对路径（如 `/dashboard`）
   - 不允许用户参数化或自定义重定向目标

2. **相对路径隔离**
   - 应用明确检查重定向目标是否为相对路径
   - 检查逻辑：拒绝任何包含 `://` 的 URL；拒绝以 `//` 开头的 URL（协议相对 URL）
   - 检查方式：`strstr(url, "://") == NULL && (url[0] != '/' || url[1] != '/')`
   - 相对路径自动在本应用域名下解析

3. **严格的协议和域名验证**
   - 使用安全的字符串函数（不是 `strcpy`, `sprintf` 直接拼接）进行 URL 解析
   - 验证步骤：
     - 检查协议：`strncmp(url, "https://", 8) == 0` 或仅允许 http 和 https
     - 提取域名：`strstr(url, "://") + 3` 之后，直到第一个 `/`
     - 验证域名：与本域或预定义的可信域名列表进行精确匹配
   - 拒绝 IP 地址、IPv6 地址、特殊协议（`javascript://`, `data://`, `file://`）

4. **长度和字符限制**
   - URL 长度限制在合理范围内（如 2048 字符），并在使用前检查
   - 使用 `strncpy()`, `strncat()` 而不是 `strcpy()`, `strcat()`
   - 所有 `strcpy` 均被替换为带长度限制的变体

5. **上下文特定的低风险场景**
   - 重定向用于内部系统调用，用户无法直接控制参数（如后台定时任务的跳转）
   - 重定向目标来自数据库，而数据库中的 URL 仅由管理员维护、受严格访问控制
   - 重定向仅用于非敏感页面（如静态错误页面、过期提示页面）
   - 重定向参数在应用初始化时硬编码或从受保护的配置文件读取

6. **多层防御**
   - 即使应用本身验证不够完善，已部署在 WAF、Web 服务器、API 网关等防御层后
   - WAF 规则明确阻止重定向到外部域名或包含恶意特征的 URL
   - 企业安全策略文档中明确说明了这类重定向的防护措施

---
