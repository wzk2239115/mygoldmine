# C/C++ Host头解析注入

## 基本信息
- **难度等级：** ★★★★☆ | **审计时间：** 30-45分钟
- **关键词搜索：** `Host:`, `strstr`, `sscanf`, `strtok`, `getenv("HTTP_HOST")`, `SERVER_NAME`, `parse_header`, `http_request`
- **快速检查：** Host头解析后是否直接用于URL构造、重定向、或后端请求

## 漏洞成因

C/C++中解析HTTP请求的Host头时，若未验证其内容直接用于业务逻辑（URL构造、重定向、密码重置链接、代理转发等），攻击者可通过控制Host头实现开放重定向、密码重置投毒、SSRF、缓存中毒等攻击。

### 常见漏洞模式

```c
// ✗ 漏洞：Host头直接用于重定向URL
void handle_redirect(int sock, const char *request) {
    char host[256];
    char *host_line = strstr(request, "Host: ");
    if (host_line) {
        sscanf(host_line, "Host: %255s", host);
    }

    char response[1024];
    snprintf(response, sizeof(response),
             "HTTP/1.1 302 Found\r\n"
             "Location: https://%s/dashboard\r\n\r\n", host);
    send(sock, response, strlen(response), 0);
    // 攻击: Host: evil.com -> 重定向到 https://evil.com/dashboard
}
```

```c
// ✗ 漏洞：CGI程序使用HTTP_HOST环境变量
int main() {
    char *host = getenv("HTTP_HOST");
    char reset_link[512];
    char *token = generate_token(email);

    snprintf(reset_link, sizeof(reset_link),
             "https://%s/reset?token=%s", host, token);
    send_email(email, reset_link);
    // 攻击者控制Host头发送钓鱼链接
    return 0;
}
```

```c
// ✗ 漏洞：代理转发使用Host头
void proxy_request(int client_sock, const char *request) {
    char host[256];
    parse_host_header(request, host, sizeof(host));

    // 连接到Host指定的后端
    int backend = connect_to_host(host, 80);  // SSRF风险
    forward_request(client_sock, backend, request);
}
```

```c
// ✗ 漏洞：缓存键使用未验证的Host头
void cache_response(const char *request, const char *response) {
    char host[256];
    char cache_key[512];

    parse_host_header(request, host, sizeof(host));
    snprintf(cache_key, sizeof(cache_key), "%s:%s", host, get_path(request));
    cache_store(cache_key, response);
    // 缓存中毒：攻击者用evil.com的Host污染缓存
}
```

```c
// ✓ 修复：白名单验证Host头
const char *ALLOWED_HOSTS[] = {"example.com", "www.example.com", NULL};

int validate_host(const char *host) {
    for (int i = 0; ALLOWED_HOSTS[i]; i++) {
        if (strcasecmp(host, ALLOWED_HOSTS[i]) == 0) {
            return 1;
        }
    }
    return 0;
}

void safe_redirect(int sock, const char *request) {
    char host[256];
    parse_host_header(request, host, sizeof(host));

    if (!validate_host(host)) {
        strcpy(host, "example.com");  // 默认安全值
    }

    char response[1024];
    snprintf(response, sizeof(response),
             "HTTP/1.1 302 Found\r\n"
             "Location: https://%s/dashboard\r\n\r\n", host);
    send(sock, response, strlen(response), 0);
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | Host头用于重定向 | 搜索 `Host:.*Location\|Location.*host`，检查验证逻辑 |
| **P0** | HTTP_HOST用于链接构造 | 搜索 `getenv.*HTTP_HOST\|HTTP_HOST.*snprintf` |
| **P0** | 代理转发Host头 | 搜索 `connect.*host\|proxy.*Host`，检查SSRF风险 |
| **P1** | 密码重置/邮件链接 | 搜索 `host.*token\|host.*email\|host.*reset` |
| **P1** | 缓存键使用Host | 搜索 `cache.*host\|host.*cache_key` |
| **P2** | 日志记录Host | 搜索 `log.*host`，评估日志注入风险 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 使用配置文件中的固定域名 | 快速跳过，无Host头使用 |
| **L1** | Host头仅用于日志 | 关键词扫描确认无安全影响 |
| **L2** | 单文件内Host用于URL构造 | 跳读检查白名单验证 |
| **L3** | Host头跨函数传递 | 逐行追踪数据流 |
| **L4** | 自定义HTTP服务器/代理 | 跨模块审计所有Host使用点 |

---

## 审计专业技巧

### 真实漏洞与误报区分经验

#### 场景1：代理转发中的SSRF风险识别
```c
// ✗ 真实漏洞：无限制的代理转发
void proxy_handler(const char *request) {
    char host[256];
    sscanf(request, "Host: %255s", host);

    // 关键：使用Host头直接连接，无任何过滤
    connect_to_upstream(host, 80);  // SSRF风险
}

// ✓ 假阳性排除：配置限制的代理白名单
void safe_proxy_handler(const char *request) {
    char host[256];
    sscanf(request, "Host: %255s", host);

    // 白名单检查 - 这是安全的
    if (!is_allowed_upstream(host)) {
        reject_request(403);
    }
    connect_to_upstream(host, 80);
}
```

**区分要点**：
- 真实漏洞：连接到任意Host指定的服务器
- 误报排除：有前置的白名单验证、DNS解析限制、内网检测

#### 场景2：密码重置链接中的钓鱼风险
```c
// ✗ 真实漏洞：完全信任Host头
void send_reset_email(const char *request, const char *email) {
    char host[256];
    sscanf(request, "Host: %255s", host);  // 直接取值

    char link[512];
    snprintf(link, sizeof(link), "https://%s/reset?token=...", host);
    // 攻击：Host: attacker.com -> 重置链接指向恶意网站
    send_email(email, link);
}

// ✓ 安全：使用配置的域名
#define RESET_HOST "accounts.example.com"
void send_reset_email_safe(const char *request, const char *email) {
    char link[512];
    snprintf(link, sizeof(link), "https://" RESET_HOST "/reset?token=...");
    send_email(email, link);
}

// ⚠ 灰色地带：验证但可能不够严格
void send_reset_email_partial(const char *request, const char *email) {
    char host[256];
    sscanf(request, "Host: %255s", host);

    // 只检查后缀 - 可能被绕过：evil.com.example.com
    if (strchr(host, '.') && strstr(host, "example.com")) {
        char link[512];
        snprintf(link, sizeof(link), "https://%s/reset?token=...", host);
        send_email(email, link);  // 风险：后缀检查不够严格
    }
}
```

**审计建议**：
- 搜索 `getenv.*HTTP_HOST` + `email\|token\|reset\|link` 的组合
- 检查验证函数是前缀检查还是完整比对
- 内部系统但支持自定义域名时，需白名单

#### 场景3：缓存中毒的真假判断
```c
// ✗ 真实漏洞：未验证Host被用作缓存键
void cache_endpoint(const char *request) {
    char host[256], path[256];
    sscanf(request, "Host: %255s", host);
    sscanf(request, "GET %255s", path);

    char key[512];
    snprintf(key, sizeof(key), "%s|%s", host, path);

    // 原始响应被缓存，所有访问该路径的用户都会被投毒
    if (!cache_get(key, response)) {
        generate_response(request, response);
        cache_set(key, response);
    }
}

// ✓ 误报排除：多租户应用中的合理设计
void safe_multi_tenant_cache(const char *request) {
    char host[256];
    sscanf(request, "Host: %255s", host);

    // 经过验证的Host被用为租户标识 - 这是正常的
    if (!validate_host(host)) return;

    char key[512];
    snprintf(key, sizeof(key), "%s|%s", host, path);
    cache_set(key, response);  // 按租户隔离缓存 - 安全
}
```

**判定标准**：
- 真实漏洞：任意Host值都被缓存，导致跨域污染
- 误报排除：多租户系统中，Host是验证过的租户标识

#### 场景4：重定向的开放重定向vs安全重定向
```c
// ✗ 真实漏洞：无限制重定向
void redirect_handler(const char *request) {
    char host[256];
    sscanf(request, "Host: %255s", host);

    // 攻击：Host: evil.com -> 重定向到 https://evil.com/...
    send_redirect("https://%s/dashboard", host);
}

// ✓ 安全：本地路径重定向
void safe_redirect_local(const char *request) {
    char path[256];
    sscanf(request, "GET %255s", path);

    // 只重定向到本地路径，不涉及Host头
    send_redirect("/dashboard");
}

// ⚠ 需深入分析：相对路径重定向
void redirect_relative(const char *request) {
    // Location: /../../evil.com - 依然指向本域
    // 这是安全的，因为浏览器会解析为本域
    send_redirect("/dashboard");
}

// ⚠ 边界情况：302重定向到同域的不同路径
void safe_same_domain_redirect(const char *request) {
    char host[256];
    sscanf(request, "Host: %255s", host);

    // 只有在Host通过严格验证后才能使用
    if (strcasecmp(host, "trusted.example.com") == 0) {
        send_redirect("https://%s/dashboard", host);  // 安全
    }
}
```

**审计流程**：
1. 找到所有重定向点（搜索 `Location:`、`send_redirect`）
2. 追踪Location值的来源
3. 检查是否包含Host头且无验证
4. 验证是否为相对路径（安全）或绝对路径（需白名单）

### 高效审计技巧

**技巧1：关键字组合搜索**
```bash
# 快速定位高风险代码
grep -r "Host.*Location\|location.*host" .
grep -r "getenv.*HTTP_HOST" . | grep -v "strcasecmp\|strcmp"
grep -r "connect.*host\|proxy.*host" . | grep -v "whitelist\|validate"
```

**技巧2：验证函数强度分级**
| 验证方式 | 强度 | 结论 |
|---------|------|------|
| `strcasecmp(host, expected) == 0` | 强 | 安全 |
| `strstr(host, "example.com")` | 弱 | 可被绕过 |
| `正则表达式 ^domain\.example\.com$` | 强 | 安全 |
| `只检查后缀` | 中 | 风险：evil.example.com.evil.net |

**技巧3：上下文判断（3行原则）**
- 向前看3行：是否有Host的白名单检查
- 向后看3行：Host值如何被使用
- 搜索同函数内的所有Host使用点

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. Host头从请求中解析并用于业务逻辑
2. 无白名单验证或格式检查
3. 影响安全功能（重定向、链接生成、代理转发）

### 典型漏洞特征（满足任一项即确认）
- ✗ `snprintf(url, size, "https://%s/path", host)`用于重定向
- ✗ `getenv("HTTP_HOST")`用于密码重置链接
- ✗ `connect(host, port)`代理转发，host来自请求头
- ✗ 缓存键直接使用未验证的Host值

### 安全排除（任一项充分）
- ✓ 白名单验证：`strcmp(host, "example.com")`
- ✓ 使用配置文件中的固定域名
- ✓ 格式验证：正则匹配合法域名格式
- ✓ Host头仅用于日志记录，无业务影响

### 灰色判定（风险较低但需注意）
- 内网服务，外部攻击者无法访问
- 有基础格式检查但不够严格
- 代理场景但后端有额外验证

---

## 实现建议

### 核心防护方案

**方案1：白名单验证**
```c
#define MAX_ALLOWED_HOSTS 10
const char *ALLOWED_HOSTS[MAX_ALLOWED_HOSTS] = {
    "example.com",
    "www.example.com",
    "api.example.com",
    NULL
};

const char* get_safe_host(const char *request_host) {
    for (int i = 0; ALLOWED_HOSTS[i]; i++) {
        if (strcasecmp(request_host, ALLOWED_HOSTS[i]) == 0) {
            return request_host;
        }
    }
    return ALLOWED_HOSTS[0];  // 默认值
}
```

**方案2：格式验证**
```c
#include <regex.h>

int is_valid_hostname(const char *host) {
    regex_t regex;
    int result;

    // 匹配合法域名格式
    if (regcomp(&regex, "^[a-zA-Z0-9][-a-zA-Z0-9]*\\.[a-zA-Z]{2,}$", REG_EXTENDED)) {
        return 0;
    }
    result = regexec(&regex, host, 0, NULL, 0);
    regfree(&regex);
    return result == 0;
}
```

**方案3：使用配置文件**
```c
// config.h
#define APP_BASE_URL "https://example.com"

// 使用
snprintf(reset_link, sizeof(reset_link),
         APP_BASE_URL "/reset?token=%s", token);
```

### 检查清单
- [ ] 所有Host头使用点添加白名单验证
- [ ] 代理转发场景验证目标Host合法性
- [ ] 密码重置链接使用配置的固定域名
- [ ] 缓存键使用验证后的Host值
- [ ] 测试Host头注入：`Host: evil.com`

---

## 修复优先级

1. **立即修复**：Host头用于代理转发或密码重置链接
2. **本周修复**：所有Host使用点添加白名单验证
3. **可选加强**：使用配置文件替代动态Host获取
4. **长期优化**：统一Host验证函数，集中管理
