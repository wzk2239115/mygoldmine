---
name: http-header-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 HTTP 头注入漏洞；重点关注检测 HTTP 请求头、响应头的构造和处理过程中，用户可控输入未经适当验证或过滤直接用于构造 HTTP 头字段，导致 CRLF 注入、HTTP 响应分割、请求头注入、Host 头攻击、HTTP 走私、HTTP/2 降级攻击、缓存中毒等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 HTTP 头注入漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：CRLF 注入（用户输入直接拼接进响应头、未过滤 \r\n 字符）、HTTP 响应分割（响应头构造不当、多行响应头注入）、HTTP 请求头注入（用户输入直接用于构造请求头、未验证头字段格式）、Host 头攻击（Host 头未验证、直接用于业务逻辑、用于 URL 重定向）、HTTP 走私（请求头解析不一致、Content-Length 与 Transfer-Encoding 冲突、前端后端解析差异）、HTTP/2 降级攻击（HTTP/2 到 HTTP/1.1 降级处理不当、头字段大小写处理不一致）、缓存中毒（标头处理不当导致缓存键污染、Vary 头缺失或不当、缓存键包含用户可控头字段）

**HTTP 头注入漏洞（HTTP Header Injection）**

**Attention**  
当项目中涉及 HTTP 请求头或响应头的构造、处理、验证等业务逻辑时，需重点审计用户可控输入是否直接用于构造 HTTP 头字段。此类漏洞通常出现在用户输入直接拼接进响应头（如 Location、Set-Cookie、X-Forwarded-For 等）、Host 头未验证直接用于业务逻辑、请求头解析不一致导致 HTTP 走私、HTTP/2 降级处理不当等场景。常见于 Web 框架的请求处理、响应构造、反向代理配置、负载均衡器配置、缓存系统配置等模块中。

**Early exit**  
若项目完全不涉及 HTTP 请求头或响应头的构造和处理（如纯静态内容服务、无任何 HTTP 头操作逻辑），或所有 HTTP 头字段均为框架自动生成且无任何用户输入参与，则可快速退出对该漏洞类型的审计。

**Cases**

**Python**
Flask/ Django 响应头构造时用户输入直接拼接，未过滤 CRLF 字符，详见：[Python_Response_Header_CRLF_Injection.md](Python_Response_Header_CRLF_Injection.md)
→ 遇到 CRLF 过滤保护机制，详见 [bypassTricks.md § 1.1 换行符编码和变体绕过](bypassTricks.md#11-换行符编码和变体绕过) 和 [§ 6.1 Python 框架绕过](bypassTricks.md#61-python-flaskdjango)
使用 requests 库时用户输入直接用于构造请求头，未验证头字段格式，详见：[Python_Request_Header_User_Input.md](Python_Request_Header_User_Input.md)
→ 遇到请求头验证保护机制，详见 [bypassTricks.md § 3.1 代理转发污染](bypassTricks.md#31-代理转发污染)
Host 头未验证直接用于 URL 重定向或业务逻辑，详见：[Python_Host_Header_Unvalidated.md](Python_Host_Header_Unvalidated.md)
→ 遇到 Host 头白名单保护机制，详见 [bypassTricks.md § 2.1 验证绕过](bypassTricks.md#21-验证绕过) 和 [§ 2.2 URL 重定向链接注入](bypassTricks.md#22-url-重定向链接注入)
HTTP/2 降级处理时头字段大小写处理不一致，详见：[Python_HTTP2_Downgrade_Header_Case.md](Python_HTTP2_Downgrade_Header_Case.md)
→ 遇到 HTTP/2 降级保护机制，详见 [bypassTricks.md § 4.1 大小写敏感性差异](bypassTricks.md#41-大小写敏感性差异) 和 [§ 4.2 协议混淆](bypassTricks.md#42-协议混淆)
反向代理配置中 Vary 头缺失导致缓存键污染，详见：[Python_Cache_Poisoning_Missing_Vary.md](Python_Cache_Poisoning_Missing_Vary.md)
→ 遇到缓存配置保护机制，详见 [bypassTricks.md § 5.1 Vary 头绕过](bypassTricks.md#51-vary-头绕过) 和 [§ 5.2 X-Forwarded-* 污染](bypassTricks.md#52-x-forwarded--污染)

**Java**
Spring MVC 响应头构造时用户输入未过滤 CRLF，详见：[Java_Spring_Response_Header_CRLF.md](Java_Spring_Response_Header_CRLF.md)
→ 遇到 CRLF 过滤保护机制，详见 [bypassTricks.md § 1.1 换行符编码和变体绕过](bypassTricks.md#11-换行符编码和变体绕过) 和 [§ 6.2 Java/Spring 绕过](bypassTricks.md#62-java-spring)
Servlet API 中用户输入直接用于设置响应头，详见：[Java_Servlet_Response_Header_Injection.md](Java_Servlet_Response_Header_Injection.md)
→ 遇到响应头验证保护机制，详见 [bypassTricks.md § 1.2 头字段值过滤绕过](bypassTricks.md#12-头字段值过滤绕过)
Host 头未验证直接用于业务逻辑或 URL 构造，详见：[Java_Host_Header_Unvalidated.md](Java_Host_Header_Unvalidated.md)
→ 遇到 Host 头白名单保护机制，详见 [bypassTricks.md § 2.1 验证绕过](bypassTricks.md#21-验证绕过)
HTTP 客户端请求头构造时用户输入未验证，详见：[Java_HTTP_Client_Header_Injection.md](Java_HTTP_Client_Header_Injection.md)
→ 遇到请求头验证保护机制，详见 [bypassTricks.md § 3.1 代理转发污染](bypassTricks.md#31-代理转发污染)
HTTP/2 到 HTTP/1.1 降级时头字段解析不一致，详见：[Java_HTTP2_Downgrade_Parsing.md](Java_HTTP2_Downgrade_Parsing.md)
→ 遇到 HTTP/2 降级保护机制，详见 [bypassTricks.md § 4.1 大小写敏感性差异](bypassTricks.md#41-大小写敏感性差异) 和 [§ 4.2 协议混淆](bypassTricks.md#42-协议混淆)

**Go**
使用 net/http 包构造响应头时用户输入未过滤，详见：[Go_Response_Header_CRLF_Injection.md](Go_Response_Header_CRLF_Injection.md)
→ 遇到 CRLF 过滤保护机制，详见 [bypassTricks.md § 1.1 换行符编码和变体绕过](bypassTricks.md#11-换行符编码和变体绕过)
http.Header 设置时用户输入直接拼接，未验证格式，详见：[Go_Header_Set_User_Input.md](Go_Header_Set_User_Input.md)
→ 遇到头字段验证保护机制，详见 [bypassTricks.md § 1.2 头字段值过滤绕过](bypassTricks.md#12-头字段值过滤绕过)
Host 头未验证直接用于反向代理转发，详见：[Go_Host_Header_Proxy_Unvalidated.md](Go_Host_Header_Proxy_Unvalidated.md)
→ 遇到 Host 头白名单保护机制，详见 [bypassTricks.md § 2.1 验证绕过](bypassTricks.md#21-验证绕过) 和 [§ 3.1 代理转发污染](bypassTricks.md#31-代理转发污染)
HTTP/2 降级处理时头字段规范化不一致，详见：[Go_HTTP2_Downgrade_Normalization.md](Go_HTTP2_Downgrade_Normalization.md)
→ 遇到 HTTP/2 降级保护机制，详见 [bypassTricks.md § 4.1 大小写敏感性差异](bypassTricks.md#41-大小写敏感性差异) 和 [§ 4.2 协议混淆](bypassTricks.md#42-协议混淆)
缓存中间件中 Vary 头处理不当，详见：[Go_Cache_Poisoning_Vary_Header.md](Go_Cache_Poisoning_Vary_Header.md)
→ 遇到缓存配置保护机制，详见 [bypassTricks.md § 5.1 Vary 头绕过](bypassTricks.md#51-vary-头绕过)

**PHP**
header() 函数使用用户输入时未过滤 CRLF，详见：[PHP_Header_Function_CRLF_Injection.md](PHP_Header_Function_CRLF_Injection.md)
→ 遇到 CRLF 过滤保护机制，详见 [bypassTricks.md § 1.1 换行符编码和变体绕过](bypassTricks.md#11-换行符编码和变体绕过) 和 [§ 6.3 PHP 绕过](bypassTricks.md#63-php)
$_SERVER 变量直接用于构造响应头，详见：[PHP_Server_Variable_Header_Injection.md](PHP_Server_Variable_Header_Injection.md)
→ 遇到响应头验证保护机制，详见 [bypassTricks.md § 1.2 头字段值过滤绕过](bypassTricks.md#12-头字段值过滤绕过)
Host 头未验证直接用于 URL 重定向，详见：[PHP_Host_Header_Redirect_Unvalidated.md](PHP_Host_Header_Redirect_Unvalidated.md)
→ 遇到 Host 头白名单保护机制，详见 [bypassTricks.md § 2.1 验证绕过](bypassTricks.md#21-验证绕过) 和 [§ 2.2 URL 重定向链接注入](bypassTricks.md#22-url-重定向链接注入)
HTTP 请求头解析时用户输入未验证，详见：[PHP_Request_Header_Parsing_Injection.md](PHP_Request_Header_Parsing_Injection.md)
→ 遇到请求头验证保护机制，详见 [bypassTricks.md § 3.1 代理转发污染](bypassTricks.md#31-代理转发污染)
HTTP/2 降级时头字段处理不一致，详见：[PHP_HTTP2_Downgrade_Inconsistency.md](PHP_HTTP2_Downgrade_Inconsistency.md)
→ 遇到 HTTP/2 降级保护机制，详见 [bypassTricks.md § 4.1 大小写敏感性差异](bypassTricks.md#41-大小写敏感性差异) 和 [§ 4.2 协议混淆](bypassTricks.md#42-协议混淆)

**JavaScript / TypeScript (Node.js)**
Express/Koa 响应头设置时用户输入未过滤，详见：[NodeJS_Response_Header_CRLF_Injection.md](NodeJS_Response_Header_CRLF_Injection.md)
→ 遇到 CRLF 过滤保护机制，详见 [bypassTricks.md § 1.1 换行符编码和变体绕过](bypassTricks.md#11-换行符编码和变体绕过) 和 [§ 6.4 Node.js/Express 绕过](bypassTricks.md#64-nodejs-express)
http.setHeader() 使用用户输入时未验证格式，详见：[NodeJS_SetHeader_User_Input.md](NodeJS_SetHeader_User_Input.md)
→ 遇到头字段验证保护机制，详见 [bypassTricks.md § 1.2 头字段值过滤绕过](bypassTricks.md#12-头字段值过滤绕过)
Host 头未验证直接用于业务逻辑，详见：[NodeJS_Host_Header_Unvalidated.md](NodeJS_Host_Header_Unvalidated.md)
→ 遇到 Host 头白名单保护机制，详见 [bypassTricks.md § 2.1 验证绕过](bypassTricks.md#21-验证绕过)
HTTP/2 降级处理时头字段大小写处理不当，详见：[NodeJS_HTTP2_Downgrade_Case_Handling.md](NodeJS_HTTP2_Downgrade_Case_Handling.md)
→ 遇到 HTTP/2 降级保护机制，详见 [bypassTricks.md § 4.1 大小写敏感性差异](bypassTricks.md#41-大小写敏感性差异) 和 [§ 4.2 协议混淆](bypassTricks.md#42-协议混淆)
缓存中间件中缓存键包含用户可控头字段，详见：[NodeJS_Cache_Poisoning_Header_Key.md](NodeJS_Cache_Poisoning_Header_Key.md)
→ 遇到缓存配置保护机制，详见 [bypassTricks.md § 5.1 Vary 头绕过](bypassTricks.md#51-vary-头绕过) 和 [§ 5.2 X-Forwarded-* 污染](bypassTricks.md#52-x-forwarded--污染)

**C/C++**
使用 libcurl 构造请求头时用户输入未验证，详见：[C_Libcurl_Header_User_Input.md](C_Libcurl_Header_User_Input.md)
→ 遇到请求头验证保护机制，详见 [bypassTricks.md § 3.1 代理转发污染](bypassTricks.md#31-代理转发污染)
HTTP 响应头构造时用户输入直接拼接，未过滤 CRLF，详见：[C_Response_Header_CRLF_Injection.md](C_Response_Header_CRLF_Injection.md)
→ 遇到 CRLF 过滤保护机制，详见 [bypassTricks.md § 1.1 换行符编码和变体绕过](bypassTricks.md#11-换行符编码和变体绕过)
Host 头解析时未验证导致注入，详见：[C_Host_Header_Parsing_Injection.md](C_Host_Header_Parsing_Injection.md)
→ 遇到 Host 头白名单保护机制，详见 [bypassTricks.md § 2.1 验证绕过](bypassTricks.md#21-验证绕过)
HTTP/2 降级时头字段解析不一致，详见：[C_HTTP2_Downgrade_Parsing.md](C_HTTP2_Downgrade_Parsing.md)
→ 遇到 HTTP/2 降级保护机制，详见 [bypassTricks.md § 4.1 大小写敏感性差异](bypassTricks.md#41-大小写敏感性差异) 和 [§ 4.2 协议混淆](bypassTricks.md#42-协议混淆)

**Rust**
使用 hyper 库设置响应头时用户输入未过滤，详见：[Rust_Hyper_Response_Header_CRLF.md](Rust_Hyper_Response_Header_CRLF.md)
→ 遇到 CRLF 过滤保护机制，详见 [bypassTricks.md § 1.1 换行符编码和变体绕过](bypassTricks.md#11-换行符编码和变体绕过)
http::HeaderMap 使用用户输入时未验证格式，详见：[Rust_HeaderMap_User_Input.md](Rust_HeaderMap_User_Input.md)
→ 遇到头字段验证保护机制，详见 [bypassTricks.md § 1.2 头字段值过滤绕过](bypassTricks.md#12-头字段值过滤绕过)
Host 头未验证直接用于业务逻辑，详见：[Rust_Host_Header_Unvalidated.md](Rust_Host_Header_Unvalidated.md)
→ 遇到 Host 头白名单保护机制，详见 [bypassTricks.md § 2.1 验证绕过](bypassTricks.md#21-验证绕过)
HTTP/2 降级处理时头字段规范化不一致，详见：[Rust_HTTP2_Downgrade_Normalization.md](Rust_HTTP2_Downgrade_Normalization.md)
→ 遇到 HTTP/2 降级保护机制，详见 [bypassTricks.md § 4.1 大小写敏感性差异](bypassTricks.md#41-大小写敏感性差异) 和 [§ 4.2 协议混淆](bypassTricks.md#42-协议混淆)

---

## HTTP 头注入绕过技巧

在进行 HTTP 头注入漏洞审计时，特别是验证防护机制的有效性，需要了解常见的绕过技巧。参考详细的绕过技巧文档：[bypassTricks.md](bypassTricks.md)

该文档包含：
- CRLF 注入绕过（换行符编码变体、替换顺序问题）
- Host 头绕过（端口号混淆、子域名、IP 表示法、IDN、URL 编码）
- HTTP 请求头注入绕过（代理转发污染、头名大小写变化）
- HTTP/2 降级绕过（大小写敏感性差异、伪头部处理、协议混淆）
- 缓存中毒绕过（Vary 头绕过、X-Forwarded-* 污染、Set-Cookie 污染）
- 特定框架绕过（Python/Flask、Java/Spring、PHP、Node.js/Express）

在验证防护机制时，应使用这些绕过技巧来测试防护的鲁棒性。

---

## 审计技能速查

### 核心四大漏洞类型速览

| 漏洞类型 | 原理 | 风险等级 | 检测难度 | 关键字 |
|---------|------|--------|---------|--------|
| **CRLF注入** | 响应头未过滤 `\r\n`，注入任意头部或响应体 | 🔴 高 | 低 | `\r\n`, CRLF, response.header*, setHeader |
| **Host Header攻击** | Host头未验证，用于重定向/邮件/业务逻辑 | 🟠 中-高 | 中 | `Host:`, `request.host`, `request.header('host')` |
| **HTTP/2 Downgrade** | HTTP/2转HTTP/1.1时头部规范化不一致 | 🟠 中 | 高 | `HTTP/2`, `h2`, `ALPN`, `downgrade` |
| **Cache Poisoning** | Vary头缺失或不完整导致缓存键污染 | 🟠 中 | 中 | `Vary:`, `cache*`, `Cache-Control`, `etag` |

### 按语言快速定位

#### Python 关键词
```
# CRLF注入
response.headers[], response[], make_response(), redirect()

# Host验证
request.host, request.url_root, request.headers['Host']

# 请求头注入
requests.headers, httpx.headers

# 缓存问题
@cache(), cache.set(), redis.set()
```

#### Java 关键词
```
# CRLF注入
response.addHeader(), response.setHeader(), response.writeHead()

# Host验证
request.getHeader("Host"), request.getServerName()

# HTTP客户端
HttpClient.execute(), httpClient.newCall()
```

#### Go 关键词
```
# CRLF注入
w.Header().Set(), w.Header().Add(), http.Header.Set()

# Host验证
r.Host, r.RequestURI, r.Header.Get("Host")

# 代理/转发
httputil.ReverseProxy, Director
```

#### PHP 关键词
```
# CRLF注入
header(), header_remove(), http_response_code()

# Host验证
$_SERVER['HTTP_HOST'], $_SERVER['SERVER_NAME']

# 请求头
getallheaders(), apache_request_headers()
```

#### NodeJS 关键词
```
# CRLF注入
res.setHeader(), res.header(), res.writeHead()

# Host验证
req.get('host'), req.hostname, req.headers.host

# Express中间件
app.use(), router.use()
```

#### C/C++ 关键词
```
# CRLF注入
sprintf(), strcat(), write(), send() (包含\r\n)

# libcurl
curl_easy_setopt(CURLOPT_HTTPHEADER), CURL_SLIST

# HTTP解析
自定义HTTP头解析, socket编程
```

#### Rust 关键词
```
# CRLF注入
response.headers(), headers.insert(), HeaderMap

# Host验证
headers.get("host"), req.headers()

# 框架
actix-web, axum, rocket
```

### 危险函数速查表

#### 🔴 直接危险（无需过滤直接使用即为漏洞）

| 语言 | 危险函数 | 风险原因 | 快速判定 |
|------|---------|--------|---------|
| Python | `response.headers[user_key]` | 头名和值都可控 | 检查key/value来源 |
| Python | `response[user_key]` | 同上 | 同上 |
| Java | `response.addHeader(name, value)` | 参数直接用于头 | 追踪name/value来源 |
| Go | `w.Header().Set(key, value)` | 直接写入响应头 | 检查key/value构造 |
| PHP | `header($user_input)` | 完全用户控制 | 检查输入处理 |
| NodeJS | `res.setHeader(name, value)` | 直接写入 | 追踪参数来源 |

#### 🟠 条件危险（需检查参数来源和过滤）

| 语言 | 危险函数 | 触发条件 | 安全做法 |
|------|---------|---------|---------|
| All | `redirect(user_url)` | Location头可控 | URL白名单+域名验证 |
| All | `Content-Disposition` | 文件名用户输入 | secure_filename() 或白名单 |
| All | `Host` header | 用于业务逻辑 | Host白名单验证 |
| Python/Go | 请求头转发 | 代理中未验证 | 过滤敏感头或白名单 |

### 通用审计流程（10-30分钟）

#### 第1阶段：快速定位（5分钟，L1关键词扫描）
```bash
# 搜索所有响应头设置
grep -rn "\.headers\[.*\]\s*=" --include="*.{py,java,go,php,js,rs}"

# 搜索所有重定向
grep -rn "redirect\|Location:" --include="*.{py,java,go,php,js,rs}"

# 搜索Host使用
grep -rn "\.host\|getHeader.*Host\|HTTP_HOST" --include="*.{py,java,go,php,js,rs}"
```

#### 第2阶段：参数追踪（10-15分钟，L2跳读）
对每个找到的函数调用点：
1. 确定参数的来源（request/user input？）
2. 在代码中回溯参数传递链
3. 检查是否有过滤/验证：
   - CRLF过滤：`replace('\r', '').replace('\n', '')`
   - URL白名单：已知域名列表
   - 正则验证：`/^[a-zA-Z0-9-]+$/` 等

#### 第3阶段：漏洞确认（5-10分钟，L3-L4逐行读）
- 确认用户输入确实进入了响应头/请求头/业务逻辑
- 确认无有效过滤或过滤不完整
- 评估是否可被框架/库自动过滤（需验证版本）
- 确定风险等级和修复优先级

### 判定决策树

```
发现响应头/请求头操作
├─ 参数来自用户输入？
│  ├─ NO → 标记安全（L0跳过审计）
│  └─ YES ↓
├─ 存在CRLF过滤？
│  ├─ YES (完整) → 低风险✓
│  ├─ YES (不完整) → 中风险⚠
│  └─ NO ↓
├─ 存在值白名单？
│  ├─ YES (安全) → 检查逻辑是否可绕过
│  └─ NO ↓
├─ 框架/库自动过滤？
│  ├─ YES (已验证版本) → 低风险✓
│  └─ NO ↓
└─ 漏洞确认 ✗
```

### 修复一句话速查

| 漏洞类型 | 一句话修复 | 优先级 |
|---------|----------|--------|
| CRLF注入 | `value = value.replace('\r', '').replace('\n', '')` | P0 |
| Host验证 | `if request.host not in ALLOWED_HOSTS: abort(400)` | P0 |
| URL重定向 | `if not url.startswith('/'): url = '/'` | P0 |
| 缓存中毒 | `response['Vary'] = 'Host, User-Agent, Accept-Encoding'` | P1 |
| HTTP/2降级 | 升级框架或配置规范化规则 | P1 |

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-http-header-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

