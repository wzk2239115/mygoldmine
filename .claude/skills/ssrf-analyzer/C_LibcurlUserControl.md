# C/C++ Libcurl 用户可控 URL 请求审计指南

## 快速审计清单

### 代码特征识别（追踪数据流）
- **核心漏洞点**：`curl_easy_setopt(curl, CURLOPT_URL, user_input)`
- **必查路径**：HTTP 参数（GET/POST）→ 解析/拼接 → CURLOPT_URL → curl_easy_perform()
- **常见来源**：HTTP 参数、请求头、Cookie、JSON 字段、路径参数
- **隐蔽形式**：URL 动态拼接、字符串格式化、协议构造、端口注入
- **快速定位**：全局搜索 `curl_easy_setopt` 和 `curl_easy_perform`，逆向追踪参数来源

### 必查保护机制（优先级排序）

| 检查项 | 代码标志 | 合规标准 | 常见缺陷 |
|--------|---------|---------|---------|
| **协议白名单** | `CURLOPT_PROTOCOLS` | 仅 `CURL_PROTO_HTTP\|CURL_PROTO_HTTPS` | 缺失或使用 `~CURL_PROTO_FILE` 黑名单 |
| **重定向协议** | `CURLOPT_REDIR_PROTOCOLS` | 必须 ≤ CURLOPT_PROTOCOLS，或禁用重定向 | 仅限协议但允许重定向到 ftp:// 等 |
| **重定向限制** | `CURLOPT_FOLLOWLOCATION` | 禁用（0）或最多 5 次 | 默认启用、无上限、与协议限制不同步 |
| **IP 范围验证** | 调用前解析和检查逻辑 | 拒绝私有 IP：127.0.0.0/8、10.0.0.0/8、172.16.0.0/12、192.168.0.0/16、169.254.0.0/16、::1、fc00::/7 | 仅检查域名、忽略 IPv6、DNS 绕过 |
| **DNS 防护** | `CURLOPT_RESOLVE` 或缓存机制 | 预设白名单 DNS 或双重验证 | 易被 DNS rebinding、时间窗口攻击 |
| **响应限制** | `CURLOPT_MAXFILESIZE` | 设置合理上限（如 10MB） | 无限制导致内存耗尽或信息泄露 |
| **超时控制** | `CURLOPT_TIMEOUT` + `CURLOPT_CONNECTTIMEOUT` | 设置合理超时（≤10s） | 无超时或过长导致悬挂和资源耗尽 |

## 漏洞判定决策树

### 必然漏洞场景
1. **直接 URL 注入**：用户控制完整 URL（含协议/主机/端口）+ 无任何验证
2. **协议绕过**：缺少 CURLOPT_PROTOCOLS 限制 → file://、dict://、gopher://、ldap:// 访问内部资源
3. **IP 绕过**：无 IP 范围检查 → 127.0.0.1、169.254.169.254（AWS metadata）、内网 IP
4. **重定向协议切换**：协议限制仅在初始请求，重定向可切换到 file:// 或 ftp://
5. **DNS rebinding**：多线程环境无 DNS 缓存 → 初次检查合法，实际请求到恶意 IP

### 低风险条件（需全部满足）
✓ URL 协议/主机由后端决定，用户仅控制查询参数或路径片段
✓ 参数值未包含 `://`、`@`、`:` 等 URL 元字符（严格白名单）
✓ `CURLOPT_PROTOCOLS = CURL_PROTO_HTTP|CURL_PROTO_HTTPS` + `CURLOPT_REDIR_PROTOCOLS` 同值或禁用重定向
✓ 请求前调用 URL 解析并验证 IP 地址，拒绝私有范围
✓ 使用 `CURLOPT_MAXFILESIZE` 限制响应大小
✓ 不向用户返回响应体内容（仅返回状态码）

### 高风险红旗信号
🚩 黑名单验证（`!contains("localhost")`）而非白名单
🚩 仅检查 URL 前缀（`startsWith("https://api.trusted")`） → `https://api.trusted.attacker.com` 绕过
🚩 使用字符串函数 strstr()/strncmp() 而非正式 URL 解析库
🚩 URL 编码处理不当（仅检查原始字符串）
🚩 IPv6 格式 `[::1]` 或 127.0.0.1 八进制/十六进制表示绕过检查
🚩 `CURLOPT_FOLLOWLOCATION` 启用但未设 `CURLOPT_REDIR_PROTOCOLS`
🚩 多线程调用 curl 但无全局 DNS 缓存机制

## 实战审计技巧

### 1. 快速定位漏洞代码
```bash
# 搜索所有 curl 请求点
grep -rn "curl_easy_perform\|CURLOPT_URL" *.c *.h

# 逆向追踪用户输入（以函数栈追踪）
# 例：get_user_url() → build_request() → curl_easy_setopt()
```

### 2. 验证协议限制的正确性
```c
// ❌ 错误：不完整的黑名单
curl_easy_setopt(curl, CURLOPT_PROTOCOLS, ~CURL_PROTO_FILE);

// ✅ 正确：明确的白名单
curl_easy_setopt(curl, CURLOPT_PROTOCOLS, CURL_PROTO_HTTP | CURL_PROTO_HTTPS);
curl_easy_setopt(curl, CURLOPT_REDIR_PROTOCOLS, CURL_PROTO_HTTPS);
```

### 3. IP 范围验证的陷阱
```c
// ❌ 常见错误：仅检查主机名
if (strstr(url, "localhost") == NULL) { /* 允许 */ }

// ❌ 错误：仅检查 IPv4
struct in_addr addr; inet_aton(host, &addr);
if (!is_private_ipv4(addr)) { /* 允许 */ }

// ✅ 正确：使用 getaddrinfo() 获取实际 IP
struct addrinfo *res;
getaddrinfo(host, NULL, NULL, &res);
// 验证 res->ai_addr（同时支持 IPv4/IPv6）
```

### 4. 时间窗口攻击（DNS rebinding）
```c
// ❌ 易受攻击：检查后可能 DNS 结果改变
validate_domain(url);  // 第一次 DNS 解析
curl_easy_perform(curl);  // 第二次 DNS 解析（不同结果）

// ✅ 防护：预设 DNS 或双重验证
curl_easy_setopt(curl, CURLOPT_RESOLVE, "example.com:443:93.184.216.34");
// 或在 perform 前再次验证 IP
```

### 5. URL 解析和检查的顺序
```
用户输入 URL 字符串
  ↓
URL 标准化（decode、规范化大小写、移除 ../ 等）
  ↓
协议检查（仅 http/https）
  ↓
主机名解析 → IP 地址
  ↓
私有 IP 范围检查（IPv4 + IPv6）
  ↓
端口检查（禁用非标准端口：25、110 等）
  ↓
curl_easy_perform()
```

## 风险评级指南

**高危（CVSS > 7.0）**：直接 URL 注入 + 无协议限制 → RCE / 信息泄露
**中危（CVSS 4.0-6.9）**：协议限制但无 IP 检查 → 内网扫描、元数据泄露
**低危（CVSS < 4.0）**：严格白名单验证 + 网络隔离 + 不返回响应体

### 检查 CVE 历史
- **CVE-2021-22911**：libcurl DNS rebinding 漏洞（已修复 7.75.0+）
- **CVE-2020-8169**：重定向协议限制绕过（7.70.0-7.71.0）
- 建议：使用 libcurl 7.84.0+ 版本