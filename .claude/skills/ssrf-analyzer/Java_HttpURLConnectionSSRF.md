# Java HttpURLConnection SSRF

## 漏洞成因
HttpURLConnection 直接使用用户可控输入构造 URL 并发起网络请求，未进行白名单校验、协议限制或目标地址验证，导致攻击者可访问内网资源、私有云元数据服务（如 AWS/Aliyun/GCP 元数据）、执行端口扫描或发起 DoS 攻击。风险等级：**高**。

---

## 快速定位（秒级扫描）

### 关键词速查表
| 危险等级 | 搜索词 | 说明 |
|---------|--------|------|
| 🔴 必扫 | `HttpURLConnection`、`new URL` | 基础网络请求类 |
| 🔴 必扫 | `openConnection()`、`getInputStream()`、`getResponseCode()` | 触发请求的操作 |
| 🟠 追踪 | `getParameter`、`@RequestParam`、`@PathVariable` | 参数来源 |
| 🟠 追踪 | `readLine`、`ConfigUtils.get`、`properties.getProperty` | 配置文件/外部输入 |
| 🟡 检查 | `String.format`、`+`、`concat`、`String.join` | URL 拼接方式 |

---

## 审计三板斧：黑名单陷阱与绕过技巧

### 陷阱 1：不完整的内网地址过滤
```java
// ❌ 只禁止127.0.0.1和localhost
if (host.equals("127.0.0.1") || host.equals("localhost")) {
    throw new SecurityException("Invalid host");
}
```
**绕过方式**：
- `127.0.0.2` ～ `127.0.0.255`（同一环回网络）
- `0.0.0.0`、`0.0.0.1`（全0地址）
- `169.254.169.254`（AWS 元数据服务）
- IPv6：`[::1]`、`[::ffff:127.0.0.1]` 映射地址
- `10.0.0.1`、`172.16.0.1`、`192.168.1.1`（RFC1918 私网）

### 陷阱 2：字符串匹配误用
```java
// ❌ 使用contains或endsWith
if (!host.contains("example.com")) throw new Exception();
```
**绕过方式**：
- `example.com.attacker.com`（前缀未验证）
- `attacker.com?x=example.com`（查询参数注入）
- `example.com@attacker.com`（认证信息注入）
- URL 解析库差异：`URL#getHost()` vs `URI#getHost()` 行为不同

### 陷阱 3：DNS 重绑定与 TOCTOU
```java
// ❌ 校验后再连接（时间差攻击）
if (InetAddress.getByName(host).isPrivateAddress()) throw new Exception();
Thread.sleep(100); // 攻击者修改 DNS 解析
new URL("http://" + host).openConnection();
```
**防护方式**：缓存 IP 地址，每次连接前重新验证。

---

## 多维度校验清单（逐行审计）

### Lv.1：协议限制
```
✓ URL 协议必须显式限制为 http/https
✗ 允许 file://、jar://、netdoc://、ftp://、ldap://
✗ 使用白名单时遗漏协议校验（仅校验 host）
```

### Lv.2：主机名验证
```
选择 1（推荐）：严格白名单 + InetAddress 解析
✓ List<String> WHITELIST = List.of("api.example.com", "cdn.example.com");
✓ String host = new URL(url).getHost();
✓ InetAddress addr = InetAddress.getByName(host);
✓ if (!addr.getHostAddress().equals("203.0.113.1")) throw new Exception();

选择 2（可疑）：黑名单 + 正则
✗ if (host.matches("^127\\.0\\.0\\.[0-9]+$")) → 遗漏::1、10.0.0.0/8
✗ if (Pattern.compile(".*safe\\.com").matcher(host).find()) → 被绕过

不安全：Pattern.matches(".*safe\\.com", host) 需要对整个字符串匹配，但可被URL encode后绕过
```

### Lv.3：私有 IP 检查
```java
// ✓ 正确方式：使用InetAddress内置方法
InetAddress addr = InetAddress.getByName(host);
if (addr.isPrivateAddress() || addr.isLoopbackAddress()
    || addr.isAnyLocalAddress() || addr.isSiteLocalAddress()
    || addr.isLinkLocalAddress()) {
    throw new SecurityException("Private IP not allowed");
}
```

### Lv.4：关键参数核查
- 端口白名单：仅允许 80、443（if (port != 80 && port != 443) throw)
- 超时设置：`conn.setConnectTimeout(5000)` 防止挂起
- 重定向禁用：`HttpURLConnection.setFollowRedirects(false)` **必须**
- 响应大小限制：`content-length` 不超过 1MB
- 代理配置：检查 `System.setProperty("http.proxyHost")` 是否被篡改

### Lv.5：链式调用追踪
```java
// ⚠️ 多次URL处理 - 需追踪完整链路
String url = sanitize(userUrl);  // 经过校验
String encoded = URLEncoder.encode(url, "UTF-8");
new URL(encoded).openConnection();  // 再次拼接，校验可能失效
```

---

## 实战审计场景

### 场景 1：代理转发服务
```
关键词：proxy、forward、upstream、fetch
风险：http://example.com/proxy?url=<SSRF_PAYLOAD>
需检查：代理目标 URL 来源、是否校验、是否支持 CONNECT 方法、是否返回响应
```

### 场景 2：Web 爬虫/内容聚合
```
关键词：crawler、scraper、fetch、import
风险：fetch 用户提交的 URL 并缓存/展示内容
需检查：URL 校验强度、是否校验 robots.txt、响应内容是否过滤、是否能访问私有元数据
```

### 场景 3：国际化/多区域访问
```
关键词：region、cdn、geolocation、mirror
风险：根据地区动态构造 CDN URL，可能被注入内网地址
需检查：地区参数来源、URL 拼接逻辑、是否支持 IPv6
```

### 场景 4：健康检查与心跳
```
关键词：healthCheck、heartbeat、ping、monitor
风险：监控系统配置的检查 URL，可能指向内网
需检查：URL 是否来自用户输入 or 配置文件、是否限制响应大小
```

---

## 漏洞判定决策树

### 高危漏洞（确认无误）
```
URL来自用户输入 ✓
    ↓ 无任何校验? → 立即定级【高危】
    ↓ 有校验?
        ↓ 仅黑名单（127.0.0.1）? → 【高危】
        ↓ 协议未限制? → 【高危】
        ↓ 可追踪到元数据服务? → 【高危】
        ↓ setFollowRedirects(true)? → 【高危】
        ↓ 响应内容返回用户? → 【高危】
```

### 中危漏洞（需进一步判定）
```
✓ 白名单 + InetAddress 验证，但遗漏私有IP检查
✓ HTTPS + 证书校验开启，但允许自定义 HostnameVerifier 绕过
✓ 响应内容不直接返回，但可通过响应时间推断内网拓扑
```

### 误报（确认无漏洞）
```
✓ URL 仅来自静态常量（ENUM/final 修饰）
✓ 强制白名单：List.of() 硬编码域名 + InetAddress.isPrivateAddress() 双重检查
✓ 协议硬编码为 https + TLSV1.2 强制
✓ 禁用重定向 + 响应仅验证存在性（HEAD 请求）
✓ 环境物理隔离 or 云服务天然隔离（已确认）
```

---

## 代码异味速查

| 异味 | 风险 | 示例 |
|-----|-----|------|
| 正则锚点缺失 | 高 | `matches("safe\\.com")` vs `matches("^[a-z]+\\.safe\\.com$")` |
| try-catch 吞异常 | 高 | `try { validate(url); } catch (Exception e) {}` → 校验失效 |
| 分支校验遗漏 | 中 | if-else 分支中仅一个分支做校验 |
| URL 再拼接 | 中 | 校验后进行 `URLEncoder.encode()` 或参数追加 |
| 使用 startsWith | 中 | `host.startsWith("safe.com")` 未检查端口号 |
| DNS 查询无缓存 | 低 | 每次连接都重新 DNS 解析，可被重绑定 |

---

## 修复建议与验证方式

### ✅ 安全实现参考
```java
private static final Set<String> ALLOWED_HOSTS =
    Set.of("api.example.com", "cdn.example.com");

public void fetchURL(String urlString) throws Exception {
    URL url = new URL(urlString);

    // 1. 协议校验
    if (!"https".equals(url.getProtocol())) {
        throw new SecurityException("Only HTTPS allowed");
    }

    // 2. 主机名白名单
    String host = url.getHost();
    if (!ALLOWED_HOSTS.contains(host)) {
        throw new SecurityException("Host not allowed");
    }

    // 3. IP 校验
    InetAddress addr = InetAddress.getByName(host);
    if (addr.isPrivateAddress() || addr.isLoopbackAddress()) {
        throw new SecurityException("Private IP blocked");
    }

    // 4. 端口校验
    int port = url.getPort() == -1 ? 443 : url.getPort();
    if (port != 443 && port != 80) {
        throw new SecurityException("Invalid port");
    }

    // 5. 连接设置
    HttpURLConnection conn = (HttpURLConnection) url.openConnection();
    conn.setRequestMethod("GET");
    conn.setConnectTimeout(5000);
    conn.setReadTimeout(5000);
    HttpURLConnection.setFollowRedirects(false);  // ⭐ 禁用重定向

    int code = conn.getResponseCode();
    if (code >= 300 && code < 400) {
        throw new SecurityException("Redirect not allowed");
    }
}
```

### 验证方式
```
1. 尝试访问 http://127.0.0.1、http://169.254.169.254 → 应被拒绝
2. 尝试使用 file://、jar:// 协议 → 应被拒绝
3. 尝试重定向到内网地址 → 应被禁止
4. 尝试 IPv6 映射 http://[::ffff:127.0.0.1] → 应被拒绝
```
