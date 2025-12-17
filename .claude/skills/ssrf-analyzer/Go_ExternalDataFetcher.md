# Go - 外部数据拉取 SSRF 漏洞审计

## Details

### 代码示例

```go
// ❌ 典型漏洞模式
func FetchExternalData(w http.ResponseWriter, r *http.Request) {
    targetURL := r.URL.Query().Get("url")
    resp, err := http.Get(targetURL)  // 直接使用用户输入，致命漏洞
    if err != nil {
        http.Error(w, err.Error(), 400)
        return
    }
    defer resp.Body.Close()
    io.Copy(w, resp.Body)  // 将内网响应回显给攻击者
}

// 常见易漏报的变种
- http.Post(userURL, "application/json", body)  // POST 也容易被忽视
- client.Do(req)  其中仅 req.Header 有验证但 req.URL 无防护
- image.Decode(http.Get(url))  // 外层嵌套导致验证遗漏
- websocket.Dial(url)  // WebSocket 常被遗漏
```

### 快速定位核心操作 (L1: 关键词扫描)

**HTTP 客户端层**:
- `http.Get`, `http.Head`, `http.Post`, `http.PostForm`
- `http.NewRequest`, `http.NewRequestWithContext`
- `client.Do(`, `client.Get(`, `client.Post(`
- **易遗漏**: `Timeout`, `Client{}` 初始化但无显式 Transport 配置

**底层网络**:
- `net.Dial`, `net.DialTimeout`, `net.DialUDP`, `net.Listen`
- `net.ResolveTCPAddr`, `net.ResolveIPAddr`

**数据流源点** (必须逐个追踪):
- `r.URL.Query().Get()`, `r.PostFormValue()`, `r.Header.Get()`
- `json.Unmarshal(req.Body, &struct{URL string})`
- `yaml.Unmarshal`, `toml.Decode` - 配置文件也可能成为注入点
- **关键**: 跨模块调用，参数可能从其他函数传入

**第三方库** (优先级低但需检查):
- `resty`, `grequests`, `fasthttp`, `colly`

### 快速定位保护机制 (L2-L4: 分层验证)

**L2 - URL 验证逻辑** (必读):
- `strings.HasPrefix(url, "http")` - **弱保护**，被 `//example.com` 绕过
- `url.Parse()` 后检查 `u.Host` - 需验证是否包含端口号混淆
- 正则匹配 - 检查是否存在 Unicode/编码绕过
- **危险信号**: 仅验证主机名而未验证协议、端口、IP 地址类型

**L3 - 网络层防护** (逐行读):
```go
// 标准保护模式
transport := &http.Transport{
    Dial: (&net.Dialer{Timeout: 5 * time.Second}).Dial,
    DisableKeepAlives: true,
    MaxIdleConns: 100,
}
client := &http.Client{Transport: transport}
// ⚠️  检查 Dial 函数是否有 IP 范围验证
```
- `CheckRedirect: nil` - **致命缺陷**，30x 重定向无限制
- `Timeout: 0` - 无超时导致慢速扫描

**L4 - 跨模块防护** (追踪调用链):
- `func validateURL(url string) error` - 必须读取实现，检查黑/白名单逻辑
- 配置加载: `config.GetAllowedDomains()` - 需确认配置来源是否可被用户控制
- middleware 中的 URL 处理 - 同一 handler 被多个 middleware 包装时需检查执行顺序

## Classify

### 判定为漏洞

- **完全无验证**: `http.Get(userInput)` 直接使用，无任何过滤
- **验证绕过**:
  - 仅检查协议为 `http://` 但用户可用 `http://127.0.0.1/`
  - 黑名单仅含 `127.0.0.1`，遗漏 `localhost`, `0.0.0.0`, IPv6 `::1`
  - 检查前缀 `allowed.com` 被 `allowed.com.attacker.com` 绕过
  - 使用 `strings.Contains()` 而非精确匹配
- **重定向无限制**: 未设置 `CheckRedirect` 或仅记录日志不拦截
- **响应回显**: 将 HTTP 响应直接写入 response body，攻击者可读取内网数据

### 判定为误报

- **硬编码 URL**: 常量、配置文件中的允许列表（需确认文件权限）
- **完整白名单防护**:
  ```go
  // 示例：真正安全的实现
  allowedDomains := map[string]bool{"api.example.com": true, "cdn.example.com": true}
  u, _ := url.Parse(userURL)
  if !allowedDomains[u.Host] { return error }
  if u.Scheme != "https" { return error }
  ```
- **IP 范围限制**: Dialer 自定义实现了 CIDR 黑名单检查（`10.0.0.0/8`, `169.254.0.0/16`）
- **环境隔离**: 容器无法访问宿主机网络（namespace 隔离），但需确认网络策略

### 判定为代码异味 (需进一步验证)

- 黑名单防护但不完整（遗漏 IPv6、hostname 别名、DNS rebinding）
- 超时设置过长（> 30s）导致可被用于 DoS
- 客户端有验证但服务端缺失，架构风险

## Risk Indicators

### 高危信号 (Critical)
- 直接将查询参数传给 `http.Get/Post` 无任何校验
- 使用 `strings.HasPrefix()` 做白名单（易绕过）
- `CheckRedirect` 为 `nil` 或返回 `nil`（允许所有重定向）
- 响应体直接 `io.Copy()` 到 HTTP response

### 中危信号 (Medium)
- 黑名单防护但仅含 `127.0.0.1`（遗漏 `localhost`, IPv6 等）
- 超时 > 10s
- 正则验证但未考虑 Unicode/URL 编码绕过
- Dialer 未自定义 DialContext

### 低危信号 (Low)
- URL 白名单但可动态添加（检查配置更新权限）
- 仅允许 HTTPS 但无证书固定
- 超时 5-10s 且需要跨域的业务场景

## Low Risk Scenarios

- **严格白名单**: 精确匹配 host + 协议，domain list 不可动态修改
- **仅 HTTPS**: 强制 `u.Scheme == "https"` 且 `tls.Config{InsecureSkipVerify: false}`
- **无响应回显**: 仅校验目标可达性，不返回响应体（HEAD 请求）
- **超短超时**: < 2s，限制扫描网络范围
- **管理员功能**: 权限控制严格，每次请求都有审计日志
- **网络隔离**: 容器/VM 网络命名空间隔离，明确无法访问内部服务