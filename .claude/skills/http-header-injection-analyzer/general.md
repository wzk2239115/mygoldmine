# HTTP Header Injection 通用审计指南

## 概述

HTTP Header Injection 是指攻击者通过在HTTP请求头或响应头中注入恶意数据，导致服务器行为异常的漏洞类型。该漏洞可导致CRLF注入、HTTP响应分割、Host头攻击、缓存中毒、HTTP走私等多种严重安全问题。此指南为跨语言的通用审计参考。

---

## 核心漏洞类型

| 漏洞类型 | 原理 | 典型表现 | 影响 |
|---------|------|--------|------|
| **CRLF注入** | 响应头未过滤 `\r\n` | HTTP响应分割、XSS | 会话劫持、缓存中毒 |
| **Host头攻击** | Host头未验证，用于业务逻辑 | OAuth回调、邮件链接伪造 | 账户接管、SSRF |
| **请求头注入** | 代理/客户端传递用户输入头 | 代理转发污染 | HTTP走私、授权绕过 |
| **X-转发头** | Vary头缺失或X-Forwarded-*污染 | 缓存键包含用户数据 | 缓存中毒 |
| **HTTP/2降级** | 协议转换时规范化不一致 | 大小写转换差异 | 绕过安全检查 |

---

## 语言快速参考

### 响应头相关函数（CRLF注入高风险）

| 语言 | 设置响应头 | 危险程度 | 快速检查 |
|------|----------|--------|--------|
| **Python** | `response.headers[]`, `make_response()`, `HttpResponse[]` | 🔴 高 | 搜索 `response[`、`headers[` + 用户参数 |
| **Java** | `response.setHeader()`, `response.addHeader()` | 🔴 高 | 搜索 `setHeader`、`addHeader` + 参数追踪 |
| **Go** | `w.Header().Set()`, `w.Header().Add()` | 🔴 高 | 搜索 `Header().Set` + 值来源 |
| **PHP** | `header()`, `setcookie()` | 🔴 高 | 搜索 `header(` + 参数验证 |
| **NodeJS** | `res.setHeader()`, `res.set()`, `res.header()` | 🔴 高 | 搜索 `setHeader` + 用户输入 |
| **C/C++** | 手动拼接 + `write()/send()` | 🔴 高 | 搜索 `sprintf/strcat` + `\r\n` |
| **Rust** | `response.headers_mut().insert()` | 🔴 高 | 搜索 `headers.insert` + 头名/值 |

### 请求头相关函数（注入高风险）

| 语言 | 获取/设置请求头 | 危险程度 | 快速检查 |
|------|----------------|--------|--------|
| **Python** | `requests.headers[]`, `httpx.headers[]` | 🔴 高 | 搜索 `headers[` + 用户输入 |
| **Java** | `HttpClient.setHeader()`, `HttpEntity.addHeader()` | 🔴 高 | 搜索 `HttpClient/HttpRequest` + 头操作 |
| **Go** | `req.Header.Set()`, `req.Header.Add()` | 🔴 高 | 搜索 `Header().Set` 在客户端 |
| **PHP** | `curl_setopt(CURLOPT_HTTPHEADER)`, `stream_context_set_option()` | 🔴 高 | 搜索 `CURLOPT_HTTPHEADER` + 参数 |
| **NodeJS** | `http.ClientRequest.setHeader()`, `axios.headers[]` | 🔴 高 | 搜索 `setHeader` 在客户端代码 |
| **C/C++** | `curl_easy_setopt(CURLOPT_HTTPHEADER)` | 🔴 高 | 搜索 `CURLOPT_HTTPHEADER` 调用 |
| **Rust** | `client.request().header()` | 🔴 高 | 搜索 `request().header` + 参数 |

### Host头相关函数（业务逻辑风险）

| 语言 | 获取Host | 使用场景 | 快速检查 |
|------|----------|--------|--------|
| **Python** | `request.host`, `request.url_root` | 重定向、邮件链接 | 搜索 `request.host` + URL构造 |
| **Java** | `request.getHeader("Host")`, `request.getServerName()` | OAuth、密码重置 | 搜索 `getServerName` + URL拼接 |
| **Go** | `r.Host`, `r.Header.Get("Host")` | 反向代理、缓存键 | 搜索 `r.Host` + 业务逻辑 |
| **PHP** | `$_SERVER['HTTP_HOST']`, `$_SERVER['SERVER_NAME']` | 重定向、邮件 | 搜索 `HTTP_HOST` + URL使用 |
| **NodeJS** | `req.hostname`, `req.headers.host` | 多租户路由 | 搜索 `req.hostname` + 路由 |
| **C/C++** | 自定义解析HTTP头 | 应用级路由 | 搜索 Host 头解析逻辑 |
| **Rust** | `headers.get("host")` | 请求处理 | 搜索 `Host` header 提取 |

---

## 通用审计流程

### 第1步：快速定位（L1关键词扫描，5分钟）

**通用关键词搜索**
```bash
# 1. 响应头设置
grep -rn "\.headers\[.*\].*=" --include="*.{py,java,go,php,js,rs,cpp,c}"
grep -rn "setHeader\|addHeader\|set_header" --include="*.{py,java,go,php,js,rs,cpp,c}"
grep -rn "response\[.*\].*=" --include="*.py"
grep -rn "header(" --include="*.php"

# 2. Host头使用
grep -rn "\.host\|\.Host\|getHost\|HTTP_HOST\|server_name" --include="*.{py,java,go,php,js,rs}"

# 3. 重定向/Location
grep -rn "redirect\|Location:" --include="*.{py,java,go,php,js,rs}"

# 4. 请求头设置
grep -rn "requests\.headers\|HttpClient.*Header\|Header().Set" --include="*.{py,java,go,php,js,rs}"

# 5. 缓存相关
grep -rn "cache.set\|cache.get\|redis.*header" --include="*.{py,java,go,php,js,rs}"
```

### 第2步：参数追踪（L2跳读，10-15分钟）

对每个找到的函数调用点：
1. 确认参数来源是否为用户输入
2. 检查参数流向：是否直接进入响应头/请求头/业务逻辑
3. 检查中间是否有过滤/验证

**过滤标志**
```python
# CRLF过滤迹象
replace('\r', ''), replace('\n', '')
strip(), split('\n'), split('\r\n')
re.sub(r'[\r\n]', '')

# 白名单验证迹象
if header_name in ALLOWED_HEADERS
in_list = [item for item in allowed if ...]
switch/case 或 dictionary lookup

# 正则验证迹象
re.match(), regex.IsMatch(), Pattern.matches()
```

### 第3步：漏洞确认（L3-L4逐行读，5-10分钟）

- 确认用户输入确实进入了响应头/请求头
- 确认无有效过滤或过滤不完整
- 评估框架/库版本是否自动过滤
- 确定风险等级

---

## 漏洞判定决策树

```
发现HTTP头操作
├─ 参数来自用户输入？
│  ├─ NO → 标记安全（L0跳过）
│  └─ YES ↓
├─ 头类型是什么？
│  ├─ 响应头 → 检查CRLF过滤
│  ├─ 请求头 → 检查代理转发风险
│  ├─ Host头 → 检查业务逻辑使用
│  └─ 其他 → 检查特定风险 ↓
├─ 存在过滤机制？
│  ├─ YES (完整) → 低风险✓
│  ├─ YES (不完整) → 中风险⚠
│  └─ NO ↓
├─ 框架/库自动过滤？
│  ├─ YES (版本已验证) → 低风险✓
│  └─ NO ↓
└─ 确认漏洞 ✗
```

---

## 常见漏洞模式

### 模式1：CRLF注入（所有语言通用）

**识别特征**
```python
# Python: response[user_key] = user_value
# Java: response.setHeader(name, value)
# Go: w.Header().Set(key, value)
# PHP: header($user_input)
# NodeJS: res.setHeader(key, value)
```

**风险等级**：🔴 高
**修复**：`value.replace('\r', '').replace('\n', '')`

### 模式2：Host头业务使用（所有语言通用）

**识别特征**
```
request.host / request.Host / r.Host / $_SERVER['HTTP_HOST']
└─ 用于URL构造/重定向/缓存键/认证
```

**风险等级**：🟠 中-高
**修复**：白名单验证 + 使用相对URL

### 模式3：代理转发污染

**识别特征**
```
for k, v := range src.Header { dst.Header[k] = v }  // 无黑名单
```

**风险等级**：🟠 中
**修复**：敏感头黑名单（Content-Length, Transfer-Encoding）

### 模式4：缓存中毒

**识别特征**
```
cache_key = request.host + request.uri
```

**风险等级**：🟠 中
**修复**：使用URL路径和查询参数，不用Host

### 模式5：HTTP/2降级

**识别特征**
```
HTTP/2 → HTTP/1.1 转换
头名大小写转换不一致
```

**风险等级**：🟠 中
**修复**：框架升级或配置规范化

---

## 审计等级（L0-L4）

| 等级 | 代码特征 | 审计策略 | 时间 |
|------|--------|--------|------|
| **L0** | 内部常量、无用户输入 | 快速跳过 | 1分钟 |
| **L1** | 关键词搜索到但参数不明 | 全局追踪参数流向 | 5分钟 |
| **L2** | 单文件、用户输入明显 | 检查所有操作点 | 10分钟 |
| **L3** | 多文件、中间件处理 | 跨文件追踪、一致性检查 | 20分钟 |
| **L4** | 自定义框架、协议转换 | 深度代码分析 + 测试 | 30分钟+ |

---

## 快速修复清单

| 漏洞类型 | 一句话修复 | 优先级 |
|---------|----------|--------|
| CRLF注入 | `value = value.replace('\r', '').replace('\n', '')` | P0 |
| Host验证 | `if req.host not in ALLOWED: abort(400)` | P0 |
| URL重定向 | 使用相对URL或预定义域名 | P0 |
| 代理转发 | 实现敏感头黑名单过滤 | P1 |
| 缓存中毒 | 缓存键移除Host头 | P1 |
| HTTP/2降级 | 框架升级+规范化配置 | P1 |

---

## 参考文档

- [OWASP: HTTP Response Splitting](https://owasp.org/www-community/HTTP_Response_Splitting)
- [CWE-113: Improper Neutralization of CRLF Sequences in HTTP Headers](https://cwe.mitre.org/data/definitions/113.html)
- [RFC 7230: HTTP/1.1 Message Syntax](https://tools.ietf.org/html/rfc7230)
- [RFC 7540: HTTP/2](https://tools.ietf.org/html/rfc7540)
- [HTTP Request Smuggling](https://portswigger.net/research/http-request-smuggling)

---

## 文档导航

### Python
- [Python_Response_Header_CRLF_Injection.md](Python_Response_Header_CRLF_Injection.md)
- [Python_Request_Header_User_Input.md](Python_Request_Header_User_Input.md)
- [Python_Host_Header_Unvalidated.md](Python_Host_Header_Unvalidated.md)
- [Python_Cache_Poisoning_Missing_Vary.md](Python_Cache_Poisoning_Missing_Vary.md)
- [Python_HTTP2_Downgrade_Header_Case.md](Python_HTTP2_Downgrade_Header_Case.md)

### Java
- [Java_Host_Header_Unvalidated.md](Java_Host_Header_Unvalidated.md)
- [Java_Servlet_Response_Header_Injection.md](Java_Servlet_Response_Header_Injection.md)
- [Java_HTTP_Client_Header_Injection.md](Java_HTTP_Client_Header_Injection.md)
- [Java_Spring_Response_Header_CRLF.md](Java_Spring_Response_Header_CRLF.md)
- [Java_HTTP2_Downgrade_Parsing.md](Java_HTTP2_Downgrade_Parsing.md)

### Go
- [Go_Response_Header_CRLF_Injection.md](Go_Response_Header_CRLF_Injection.md)
- [Go_Host_Header_Proxy_Unvalidated.md](Go_Host_Header_Proxy_Unvalidated.md)
- [Go_Header_Set_User_Input.md](Go_Header_Set_User_Input.md)
- [Go_Cache_Poisoning_Vary_Header.md](Go_Cache_Poisoning_Vary_Header.md)
- [Go_HTTP2_Downgrade_Normalization.md](Go_HTTP2_Downgrade_Normalization.md)

### PHP
- [PHP_Header_Function_CRLF_Injection.md](PHP_Header_Function_CRLF_Injection.md)
- [PHP_Server_Variable_Header_Injection.md](PHP_Server_Variable_Header_Injection.md)
- [PHP_Host_Header_Redirect_Unvalidated.md](PHP_Host_Header_Redirect_Unvalidated.md)
- [PHP_Request_Header_Parsing_Injection.md](PHP_Request_Header_Parsing_Injection.md)
- [PHP_HTTP2_Downgrade_Inconsistency.md](PHP_HTTP2_Downgrade_Inconsistency.md)

### Node.js
- [NodeJS_Response_Header_CRLF_Injection.md](NodeJS_Response_Header_CRLF_Injection.md)
- [NodeJS_SetHeader_User_Input.md](NodeJS_SetHeader_User_Input.md)
- [NodeJS_Host_Header_Unvalidated.md](NodeJS_Host_Header_Unvalidated.md)
- [NodeJS_Cache_Poisoning_Header_Key.md](NodeJS_Cache_Poisoning_Header_Key.md)
- [NodeJS_HTTP2_Downgrade_Case_Handling.md](NodeJS_HTTP2_Downgrade_Case_Handling.md)

### C/C++
- [C_Response_Header_CRLF_Injection.md](C_Response_Header_CRLF_Injection.md)
- [C_Host_Header_Parsing_Injection.md](C_Host_Header_Parsing_Injection.md)
- [C_Libcurl_Header_User_Input.md](C_Libcurl_Header_User_Input.md)
- [C_HTTP2_Downgrade_Parsing.md](C_HTTP2_Downgrade_Parsing.md)

### Rust
- [Rust_HTTP2_Downgrade_Normalization.md](Rust_HTTP2_Downgrade_Normalization.md)
- [Rust_Host_Header_Unvalidated.md](Rust_Host_Header_Unvalidated.md)
- [Rust_HeaderMap_User_Input.md](Rust_HeaderMap_User_Input.md)
- [Rust_Hyper_Response_Header_CRLF.md](Rust_Hyper_Response_Header_CRLF.md)

### 技能速查
- [SKILL.md](SKILL.md) - 审计技能速查表
