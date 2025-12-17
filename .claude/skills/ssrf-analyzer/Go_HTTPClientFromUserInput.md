# Go HTTP Client 用户输入 SSRF

## 漏洞成因
`http.Get()`、`http.Post()` 或自定义 `*http.Client` 直接使用用户可控输入构造 URL 并发起网络请求，未进行白名单校验、协议限制或目标地址验证，导致攻击者可访问内网资源、私有云元数据服务（AWS/阿里云/GCP 元数据）、执行端口扫描或发起 DoS 攻击。风险等级：**高**。

---

## 快速定位（秒级扫描）

### 关键词速查表
| 危险等级 | 搜索词 | 说明 |
|---------|--------|------|
| 🔴 必扫 | `http.Get(`、`http.Post(`、`http.Head(`、`http.Do(` | 直接网络请求 |
| 🔴 必扫 | `(&http.Client{})\.Get`、`client\.Do(` | 自定义客户端请求 |
| 🟠 追踪 | `Query.Get`、`r.URL.Query()`、`json.Unmarshal` | 参数来源 |
| 🟠 追踪 | `os.Getenv`、`viper.GetString`、`config.Get` | 配置文件/环境变量 |
| 🟡 检查 | `fmt.Sprintf`、`url.URL{Scheme:`、`net.JoinHostPort` | URL 拼接方式 |
| 🟡 检查 | `Transport`、`Dialer`、`DialContext` | 自定义连接逻辑 |

---

## 审计三板斧：黑名单陷阱与绕过技巧

### 陷阱 1：不完整的内网地址过滤
```go
// ❌ 只禁止127.0.0.1和localhost
if host == "127.0.0.1" || host == "localhost" {
    return fmt.Errorf("invalid host")
}
```
**绕过方式**：
- `127.0.0.2` ～ `127.0.0.255`（同一环回网络）
- `0.0.0.0`、`0.0.0.1`（全0地址、广播地址）
- `169.254.169.254`（AWS 元数据服务）
- IPv6：`[::1]`、`[::ffff:127.0.0.1]`、`[::ffff:0:127.0.0.1]` 映射地址
- `10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16` 私网段
- 短写 IP：`2130706433`（十进制的 127.0.0.1）、`017700000001`（八进制）

### 陷阱 2：字符串匹配误用
```go
// ❌ 使用Contains或HasSuffix
if !strings.Contains(host, "example.com") {
    return fmt.Errorf("invalid")
}
```
**绕过方式**：
- `example.com.attacker.com`（前缀未验证，域名包含关系）
- `attacker.com?x=example.com`（查询参数注入）
- `example.com@attacker.com`（HTTP 认证信息注入）
- URL 解析库差异：`net.URL.Hostname()` vs `net.URL.Host`（含端口）

### 陷阱 3：DNS 重绑定与 TOCTOU
```go
// ❌ 校验后再连接（时间差攻击）
if ip := net.ParseIP(host); isPrivate(ip) {
    return fmt.Errorf("blocked")
}
time.Sleep(100 * time.Millisecond)  // 攻击者修改 DNS 解析
resp, _ := http.Get("http://" + host)
```
**防护方式**：缓存 IP 地址，每次连接前重新验证；或使用 DNS 预查询 + IP 白名单。

### 陷阱 4：超时可被滥用
```go
// ⚠️ 超时过长允许内网探测
client := &http.Client{Timeout: 30 * time.Second}  // 太长
```
**风险**：无响应的内网服务可被区分，导致端口扫描；应该 < 5秒。

---

## 多维度校验清单（逐行审计）

### Lv.1：协议限制
```
✓ URL 协议必须显式限制为 http/https
✗ 允许 file://、ftp://、gopher://、dict://、ldap://（Go内置支持多协议）
✗ 仅校验 Host 时遗漏协议校验
```

### Lv.2：主机名验证
```
选择 1（推荐）：严格白名单 + net.LookupIP 解析
✓ var allowedHosts = map[string]bool{"api.example.com": true}
✓ u, _ := url.Parse(userURL)
✓ if !allowedHosts[u.Hostname()] { throw }
✓ ips, _ := net.LookupIP(u.Hostname())
✓ for _, ip := range ips { if isPrivate(ip) { throw } }

选择 2（可疑）：黑名单 + 正则
✗ if matched, _ := regexp.MatchString(`^127\.0\.0\.[0-9]+$`, host) → 遗漏::1
✗ if !strings.HasSuffix(host, "example.com") → 被绕过

不安全：regexp.MatchString("safe\\.com", host) 未锚定，可被绕过
```

### Lv.3：私有 IP 检查
```go
// ✓ 正确方式：使用net包内置方法
func isPrivateIP(host string) (bool, error) {
    ips, err := net.LookupIP(host)
    if err != nil {
        return false, err
    }
    for _, ip := range ips {
        if ip.IsPrivate() || ip.IsLoopback() || ip.IsLinkLocalUnicast() {
            return true, nil
        }
    }
    return false, nil
}
```
**关键点**：`net.IP.IsPrivate()` 涵盖 RFC1918、127.0.0.0/8、fc00::/7 等；需同时检查 DNS 解析结果。

### Lv.4：关键参数核查
- 端口白名单：仅允许 80、443（`if port != "" && port != "80" && port != "443" { throw }`）
- 超时设置：`Timeout: 5*time.Second` 防止挂起探测
- 重定向禁用：`CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }`
- 响应大小限制：通过 `io.LimitReader(resp.Body, 1<<20)` 限制 1MB
- 代理配置：检查 `http.ProxyURL` 或代理环境变量是否被篡改

### Lv.5：自定义 Transport 与 Dialer
```go
// 检查是否有 IP 过滤逻辑
transport := &http.Transport{
    DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
        // ⚠️ 需检查这里是否有 IP 过滤
        host, port, _ := net.SplitHostPort(addr)
        if isPrivateIP(host) { return nil, fmt.Errorf("blocked") }
        return (&net.Dialer{}).DialContext(ctx, network, addr)
    },
}
```

---

## 实战审计场景

### 场景 1：代理转发服务
```
关键词：proxy、forward、upstream、fetch
风险：/proxy?url=<SSRF_PAYLOAD>
需检查：代理目标来源、URL 校验强度、是否支持 CONNECT 方法、是否返回全部响应内容
```

### 场景 2：Web 爬虫/内容导入
```
关键词：crawler、scraper、import、fetch、subscribe
风险：用户订阅/导入 URL 内容后缓存或展示
需检查：URL 校验、是否跟随重定向、响应内容是否过滤、是否能访问元数据
```

### 场景 3：Webhook 与回调
```
关键词：webhook、callback、postback、notify
风险：支付/事件通知 URL 由用户指定，可指向内网
需检查：URL 来源、是否校验 IP、是否限制响应大小、日志记录
```

### 场景 4：文件下载与预览
```
关键词：download、preview、thumbnail、imageURL
风险：从用户输入 URL 下载图片、文档，用于缓存/生成缩略图
需检查：URL 校验、文件类型检查、磁盘空间限制
```

---

## 漏洞判定决策树

### 高危漏洞（确认无误）
```
URL 来自用户输入 ✓
    ↓ 无任何校验? → 立即定级【高危】
    ↓ 有校验?
        ↓ 仅黑名单（如仅禁127.0.0.1）? → 【高危】
        ↓ 协议未限制? → 【高危】
        ↓ 使用 http.DefaultClient（无自定义超时）? → 【高危】
        ↓ 可追踪到元数据服务 169.254.169.254? → 【高危】
        ↓ CheckRedirect 未禁用? → 【高危】
        ↓ 响应内容直接返回用户? → 【高危】
```

### 中危漏洞（需进一步判定）
```
✓ 白名单 + net.LookupIP 验证，但未检查 IPv6 映射地址
✓ 响应大小限制 1MB，但可通过流式读取泄露内容
✓ 超时 5 秒，但无速率限制，仍可进行端口扫描
✓ 禁用重定向，但允许相对重定向或 meta refresh
```

### 误报（确认无漏洞）
```
✓ URL 仅来自硬编码常量或 Enum
✓ 强制白名单：allowedHosts map + net.LookupIP 双重检查
✓ 协议硬编码为 https + TLS 1.2+ 强制
✓ 禁用重定向 + 仅返回状态码（HEAD 请求）
✓ 环境物理隔离或云服务天然隔离（已确认）
```

---

## 代码异味速查

| 异味 | 风险 | 示例 |
|-----|-----|------|
| 正则缺少 `^` 和 `$` | 高 | `regexp.MatchString("safe\\.com", host)` |
| 错误被吞掉 | 高 | `if validated, _ := validate(url); !validated {}` |
| 分支校验不一致 | 中 | if-else 仅一支做校验 |
| URL 再次拼接 | 中 | 校验后使用 `url.QueryEscape()` 或追加参数 |
| 使用 Contains | 中 | `strings.Contains(host, "safe.com")` 被绕过 |
| DNS 无缓存 | 低 | 每次 `net.LookupIP()` 都重新查询，可被重绑定 |

---

## 修复建议与验证方式

### ✅ 安全实现参考
```go
var allowedHosts = map[string]bool{
    "api.example.com": true,
    "cdn.example.com": true,
}

func fetchURL(userURL string) ([]byte, error) {
    // 1. 解析 URL
    u, err := url.Parse(userURL)
    if err != nil {
        return nil, fmt.Errorf("invalid URL: %w", err)
    }

    // 2. 协议校验
    if u.Scheme != "https" {
        return nil, fmt.Errorf("only HTTPS allowed, got %s", u.Scheme)
    }

    // 3. 主机白名单
    host := u.Hostname()
    if !allowedHosts[host] {
        return nil, fmt.Errorf("host %s not allowed", host)
    }

    // 4. IP 校验（防 DNS 重绑定）
    ips, err := net.LookupIP(host)
    if err != nil {
        return nil, fmt.Errorf("DNS lookup failed: %w", err)
    }
    for _, ip := range ips {
        if ip.IsPrivate() || ip.IsLoopback() {
            return nil, fmt.Errorf("private IP blocked: %s", ip)
        }
    }

    // 5. 端口校验
    port := u.Port()
    if port != "" && port != "443" && port != "80" {
        return nil, fmt.Errorf("invalid port: %s", port)
    }

    // 6. 自定义客户端
    client := &http.Client{
        Timeout: 5 * time.Second,
        CheckRedirect: func(*http.Request, []*http.Request) error {
            return http.ErrUseLastResponse  // 禁用重定向
        },
    }

    // 7. 发起请求
    req, _ := http.NewRequest("GET", userURL, nil)
    req.Header.Set("User-Agent", "MyApp/1.0")
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    // 8. 响应大小限制
    return io.ReadAll(io.LimitReader(resp.Body, 1<<20))  // 1MB
}
```

### 验证方式
```
1. 尝试访问 http://127.0.0.1 → 应被拒绝
2. 尝试访问 http://169.254.169.254 → 应被拒绝
3. 尝试使用 file://、gopher:// 协议 → 应被拒绝
4. 尝试 IPv6 [::1]、[::ffff:127.0.0.1] → 应被拒绝
5. 尝试重定向到内网地址 → 应被禁止
6. 尝试访问私网段 192.168.1.1、10.0.0.1 → 应被拒绝
```