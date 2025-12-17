# C/C++ HTTP/2降级解析不一致

## 基本信息
- **难度等级：** ★★★★★ | **审计时间：** 45-60分钟
- **关键词搜索：** `http2`, `nghttp2`, `h2`, `:authority`, `:method`, `:path`, `tolower`, `strcasecmp`, `HPACK`
- **快速检查：** 是否处理HTTP/2请求，头字段大小写和伪头字段处理是否正确

## 漏洞成因

HTTP/2协议强制所有头字段小写并使用伪头字段（`:authority`、`:method`等），而HTTP/1.1使用Title-Case头和请求行。C/C++实现的HTTP服务器或代理在协议转换时，若头字段规范化不一致、伪头字段处理不当，可能导致请求走私、安全检查绕过、缓存中毒等攻击。

### 常见漏洞模式

```c
// ✗ 漏洞：大小写敏感的头匹配
int check_content_type(const char *headers) {
    // HTTP/2头是小写：content-type
    // 此检查可能被HTTP/2请求绕过
    if (strstr(headers, "Content-Type: application/json")) {
        return 1;
    }
    return 0;
}
```

```c
// ✗ 漏洞：HTTP/2伪头处理不当
void h2_to_h1_convert(nghttp2_session *session, http_request *req) {
    // 从HTTP/2帧中提取头
    const char *method = get_header(":method");
    const char *path = get_header(":path");
    const char *authority = get_header(":authority");

    // 构造HTTP/1.1请求
    sprintf(req->line, "%s %s HTTP/1.1\r\n", method, path);
    sprintf(req->headers, "Host: %s\r\n", authority);

    // 问题：如果攻击者同时发送:authority和Host头，可能导致不一致
}
```

```c
// ✗ 漏洞：头字段规范化不一致
void normalize_headers(http_headers *headers) {
    for (int i = 0; i < headers->count; i++) {
        // 简单的首字母大写，可能与HTTP/2不兼容
        headers->names[i][0] = toupper(headers->names[i][0]);
    }
    // HTTP/2的:method等伪头被错误处理
}
```

```c
// ✗ 漏洞：安全检查使用大小写敏感比较
int is_blocked_header(const char *name) {
    const char *blocked[] = {"X-Forwarded-For", "X-Real-IP", NULL};
    for (int i = 0; blocked[i]; i++) {
        if (strcmp(name, blocked[i]) == 0) {  // 大小写敏感
            return 1;
        }
    }
    return 0;
    // HTTP/2的x-forwarded-for（小写）绕过检查
}
```

```c
// ✓ 修复：大小写不敏感比较
int is_blocked_header_safe(const char *name) {
    const char *blocked[] = {"x-forwarded-for", "x-real-ip", NULL};
    for (int i = 0; blocked[i]; i++) {
        if (strcasecmp(name, blocked[i]) == 0) {  // 大小写不敏感
            return 1;
        }
    }
    return 0;
}

void safe_h2_to_h1(nghttp2_session *session, http_request *req) {
    // 优先使用:authority，忽略Host头
    const char *authority = get_pseudo_header(":authority");
    const char *host = get_header("host");

    // 使用:authority作为Host
    if (authority) {
        set_header(req, "Host", authority);
    }
    // 删除可能冲突的Host头
    remove_header(req, "host");
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | HTTP/2伪头处理 | 搜索 `:authority\|:method\|:path\|:scheme`，检查转换逻辑 |
| **P0** | 大小写敏感头比较 | 搜索 `strcmp.*header\|strstr.*Header`，检查是否使用strcasecmp |
| **P1** | 协议降级逻辑 | 搜索 `h2.*h1\|http2.*http1`，检查转换函数 |
| **P1** | nghttp2回调处理 | 搜索 `nghttp2_on_header_callback`，检查头处理逻辑 |
| **P2** | HPACK解码 | 搜索 `hpack\|nghttp2_hd`，检查解码后的头处理 |
| **P2** | 头字段规范化 | 搜索 `toupper\|tolower.*header`，检查规范化一致性 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 仅HTTP/1.1，无HTTP/2支持 | 快速跳过 |
| **L1** | 使用成熟HTTP/2库，默认配置 | 关键词扫描确认无自定义处理 |
| **L2** | 简单的协议转换 | 跳读检查伪头和Host处理 |
| **L3** | 自定义头处理逻辑 | 逐行审计规范化代码 |
| **L4** | 复杂代理/网关实现 | 跨模块追踪协议转换全流程 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 应用处理HTTP/2请求并转换为HTTP/1.1
2. 存在大小写敏感的头检查或伪头处理不当
3. 安全功能依赖受影响的头检查

### 典型漏洞特征（满足任一项即确认）
- ✗ `strcmp(header_name, "Content-Type")`大小写敏感比较
- ✗ HTTP/2的`:authority`和HTTP/1.1的`Host`共存时处理不一致
- ✗ 伪头字段（`:method`）被当作普通头处理
- ✗ 安全黑名单使用大小写敏感匹配

### 安全排除（任一项充分）
- ✓ 使用`strcasecmp()`进行所有头比较
- ✓ 仅使用HTTP/1.1，无HTTP/2支持
- ✓ HTTP/2库自动处理头规范化
- ✓ 代理层统一规范化后再转发

### 灰色判定（风险较低但需注意）
- 仅内部服务间通信
- 大小写差异仅影响非安全功能
- 使用第三方库但版本不确定

---

## 实现建议

### 核心防护方案

**方案1：大小写不敏感的头比较**
```c
#include <strings.h>  // strcasecmp

int get_header_value(http_headers *headers, const char *name, char *value, size_t size) {
    for (int i = 0; i < headers->count; i++) {
        if (strcasecmp(headers->names[i], name) == 0) {
            strncpy(value, headers->values[i], size - 1);
            value[size - 1] = '\0';
            return 1;
        }
    }
    return 0;
}
```

**方案2：正确的伪头处理**
```c
void h2_to_h1_safe(h2_request *h2_req, h1_request *h1_req) {
    // 1. 从伪头构造请求行
    snprintf(h1_req->request_line, sizeof(h1_req->request_line),
             "%s %s HTTP/1.1\r\n",
             h2_req->method,   // 来自:method
             h2_req->path);    // 来自:path

    // 2. :authority作为Host头（优先于任何Host头）
    set_header(h1_req, "Host", h2_req->authority);

    // 3. 复制其他头，跳过伪头
    for (int i = 0; i < h2_req->header_count; i++) {
        const char *name = h2_req->headers[i].name;
        if (name[0] == ':') continue;  // 跳过伪头
        if (strcasecmp(name, "host") == 0) continue;  // 跳过Host
        add_header(h1_req, name, h2_req->headers[i].value);
    }
}
```

**方案3：安全的头黑名单**
```c
int is_blocked_header_safe(const char *name) {
    // 使用小写形式的黑名单
    static const char *blocked[] = {
        "x-forwarded-for",
        "x-real-ip",
        "x-forwarded-host",
        NULL
    };

    for (int i = 0; blocked[i]; i++) {
        if (strcasecmp(name, blocked[i]) == 0) {
            return 1;
        }
    }
    return 0;
}
```

### 检查清单
- [ ] 所有头比较使用strcasecmp()
- [ ] HTTP/2伪头正确转换为HTTP/1.1元素
- [ ] :authority优先于Host头
- [ ] 安全黑名单使用大小写不敏感匹配
- [ ] 测试HTTP/2请求的小写头绕过

---

## 审计专业技巧

### 真实漏洞 vs 误报区分

#### 漏洞场景1：多协议网关中的伪头覆盖

**真实漏洞代码：**
```c
// ✗ nghttp2_hd缺陷：HTTP/2重复伪头问题
void handle_http2_headers(nghttp2_session *session) {
    const nghttp2_nv *nva = NULL;
    size_t nvlen = 0;
    nghttp2_hd_deflate_get_hd_table(session);

    // 错误：允许多个:authority伪头
    for (size_t i = 0; i < nvlen; i++) {
        if (strcmp((const char*)nva[i].name, ":authority") == 0) {
            set_host_header(nva[i].value);  // 只处理最后一个
        }
    }
}
```

**误报排除：**
- HTTP/2库版本>2.x且启用`nghttp2_hd_deflate_verify`验证
- 使用HAProxy/nginx标准配置，自动过滤重复伪头
- 框架层（如Go http/2）自动normalize所有头

**区分技巧：**
- 搜索`for.*header`循环，确认是否存在头重复覆盖逻辑
- 检查nghttp2版本和编译选项：`NGHTTP2_STRICT_HEADERS`标志
- 在HTTP/2 RFC 7540要求验证的地方是否跳过检查

---

#### 漏洞场景2：跨层头转换的大小写不一致

**真实漏洞特征：**
```c
// ✗ 低级别库统一小写，高级别库使用Title-Case导致不匹配
// 底层（nghttp2）
void on_header_recv(nghttp2_session *s, const nghttp2_frame_hd *fh,
                     const nghttp2_nv *nv, void *user_data) {
    // nv->name 总是小写（HTTP/2规范）
    headers_store(nv->name, nv->value);  // "content-type"
}

// 高级别业务逻辑
int auth_check(http_request *req) {
    // 使用Title-Case搜索
    if (strstr(req->headers, "Authorization: Bearer")) {  // 大小写敏感
        return verify_token();
    }
    return 0;  // 漏掉"authorization: bearer"
}
```

**误报排除标准：**
- 有统一的头规范化层（middleware）在所有访问前标准化
- 使用ORM/框架的头访问API（自动处理大小写）
- 明确文档记录：仅处理HTTP/1.1，HTTP/2由反向代理处理

**实战审计技巧：**
```bash
# 搜索大小写敏感的头访问
grep -rn "strcmp.*[Aa]uthorization\|strstr.*Content-Type" src/
grep -rn "strcmp.*header\|strcasecmp.*header" src/

# 统计结果：
# strcmp → 可能是漏洞
# strcasecmp → 安全（需进一步验证调用方）
```

---

#### 漏洞场景3：WAF/安全过滤绕过

**真实漏洞：**
```c
// ✗ WAF黑名单大小写敏感，HTTP/2请求绕过
int waf_filter(http_headers *headers) {
    for (int i = 0; i < headers->count; i++) {
        if (strcmp(headers->names[i], "X-Original-URL") == 0) {  // 大小写敏感
            log_attack("Detected X-Original-URL header");
            return -1;
        }
    }
    return 0;
}

// HTTP/1.1请求被拦截：X-Original-URL: /admin
// HTTP/2请求绕过：x-original-url: /admin (小写被允许)
```

**确认漏洞的3步法：**
1. **代码层**：找到安全检查函数，确认使用`strcmp`而非`strcasecmp`
2. **协议层**：确认应用同时处理HTTP/2（头小写）和HTTP/1.1（头任意大小写）
3. **影响层**：追踪检查结果是否影响关键安全功能（认证、授权、日志）

**误报避免：**
- 仅检查HTTP/1.1且明确排除HTTP/2路径 ✓
- WAF位于应用层前，在代理层已normalize ✓
- 黑名单检查不影响请求处理（仅日志） ✗ 需要报告

---

### 审计工作流程

#### 第一步：协议支持确认（2分钟）
```bash
# 关键字搜索
grep -rn "nghttp2\|http2\|h2\|ALPN" .  # 文件数量
grep -rn "connection:.*upgrade\|HTTP/2" src/  # 协议协商

# 输出分析：
# - 0结果 → 只支持HTTP/1.1，跳过审计
# - 存在nghttp2 → 进行深度审计
# - 有proxy配置 → 检查代理配置是否处理转换
```

#### 第二步：头处理函数梳理（10分钟）
```bash
# 列出所有头访问函数
grep -rn "strcmp.*header\|strcasecmp\|get_header\|Header" src/ | \
  grep -E "(function|void|int|char\*)" | sort | uniq

# 构建函数调用图
# 找到：头读取 → 头验证 → 头使用 的完整路径
```

#### 第三步：关键路径验证（20分钟）
- **安全敏感头**：Authorization, Cookie, X-Forwarded-*
- **协议敏感头**：Host, :authority, :method, :path
- **检查敏感头**：Content-Length, Content-Type, Transfer-Encoding

对每个敏感头：
1. 追踪其来源（HTTP/2伪头或HTTP/1.1头）
2. 检查访问代码是否大小写敏感
3. 验证该头影响的业务逻辑

#### 第四步：协议转换验证（15分钟）
如果代码同时处理HTTP/1.1和HTTP/2：
```c
// 关键检查点：
// 1. HTTP/2 → HTTP/1.1 转换函数是否存在
// 2. 伪头（:开头）是否正确分离
// 3. 转换过程中头是否统一normalize

// 审计checklist：
grep -n ":\(authority\|method\|path\|scheme\)" src/  // 伪头处理
grep -n "h2.*h1\|http2.*http1\|downgrade" src/      // 转换逻辑
```

---

### 常见误报与排除

| 误报特征 | 实际情况 | 排除方法 |
|---------|---------|---------|
| 找到`strcmp`+header | 仅在日志/监控中使用 | 追踪该检查结果，若无影响安全功能则排除 |
| nghttp2库存在 | 但禁用了特定功能 | 检查编译选项和`nghttp2_option_set_*`配置 |
| HTTP/2支持存在 | 但所有请求经过WAF normalize | 确认WAF在转换前对所有头调用`tolower`或`strcasecmp` |
| 自定义头处理 | 但只处理业务头 | 确认系统头（Authorization等）由框架处理 |
| 大小写敏感比较 | 但仅用于注释解析 | 确认该数据不影响安全决策 |

---

### 高级审计技巧

#### 1. 头冲突利用检测
如果发现HTTP/2和HTTP/1.1混用，构造冲突场景：
```
HTTP/2请求：
:method: GET
:path: /
:authority: attacker.com
Host: victim.com

转换为HTTP/1.1后：
GET / HTTP/1.1
Host: attacker.com  (来自:authority)
Host: victim.com    (来自原Host头)

检查代码：对于重复头的处理（first-wins vs last-wins）
```

#### 2. 版本和补丁确认
```bash
# 检查nghttp2版本
grep -rn "nghttp2_version\|NGHTTP2_VERSION" .
# 对标CVE数据库：
# - CVE-2020-11080: HPACK解码漏洞
# - CVE-2019-9511-9516: HTTP/2帧管理漏洞
```

#### 3. 跨层审计
- **OS层**：`SO_REUSEADDR`, `SO_KEEPALIVE`等socket选项
- **协议层**：HPACK编解码、帧序列验证
- **应用层**：头的业务逻辑处理

---

## 修复优先级

1. **立即修复**：安全检查使用大小写敏感比较
2. **本周修复**：统一使用大小写不敏感的头访问函数
3. **可选加强**：实现正确的HTTP/2到HTTP/1.1转换
4. **长期优化**：使用成熟的HTTP/2库并跟踪安全更新
