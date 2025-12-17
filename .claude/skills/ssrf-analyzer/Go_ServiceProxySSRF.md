# Go_ServiceProxySSRF

**漏洞类型**: 微服务通信代理场景中转发用户控制的请求目标

---

## Details

### 代码示例
```go
// 典型场景：API网关/服务代理转发请求
func ProxyHandler(w http.ResponseWriter, r *http.Request) {
    targetURL := r.URL.Query().Get("target")  // 用户可控
    resp, err := http.Get(targetURL)          // 直接请求
    // 或使用 httputil.ReverseProxy
    proxy := httputil.NewSingleHostReverseProxy(url.Parse(targetURL))
    proxy.ServeHTTP(w, r)
}

// 常见模式：服务发现 + 动态路由
serviceAddr := registry.Lookup(r.Header.Get("X-Service-Name")) // 用户可控服务名
client.Do(serviceAddr + r.URL.Path)
```

### 快速定位核心操作 **(L1-L2)**
- **关键函数**：`http.Get/Post`, `http.Client.Do`, `httputil.ReverseProxy`, `grpc.Dial`
- **关键模式**：`NewRequest` + 拼接用户输入作为URL/Host
- **路由转发**：搜索 `proxy`, `forward`, `relay`, `upstream` 关键字
- **服务发现**：`consul`, `etcd`, `registry.Lookup` 结合用户输入的服务名
- **快速扫描**：`r.URL.Query()`, `r.Header.Get()`, `r.PostForm` 后直接用于 URL 构造

### 快速定位保护机制 **(L2-L3)**
- **白名单检查**：
  - 搜索 `allowlist`, `whitelist`, `validHosts`
  - 检查 `strings.HasPrefix/Contains` 是否严格（注意 `evil.com?good.com` 绕过）
  - URL 解析后的 `Host` 字段是否验证（而非完整 URL）
- **协议限制**：检查是否限制 `scheme` 为 `http/https`（排除 `file://`, `gopher://`）
- **内网保护**：
  - 搜索 `net.ParseIP` + `IsPrivate/IsLoopback` 检查
  - 注意 DNS rebinding：是否在请求前解析 IP 并验证
- **关键库**：是否使用 `net.Dialer` 自定义 `Control` 函数拦截连接
- **审计等级**：
  - L1: 存在白名单/IP过滤关键字 → 跳读实现
  - L3: 白名单使用字符串匹配 → 逐行验证绕过可能
  - L4: 白名单逻辑在其他模块 → 跨模块追踪调用链

---

## Classify

### 漏洞判定
- **确认漏洞**：
  1. 目标 URL/Host/Port 任一组件完全用户可控
  2. 无白名单或白名单可绕过（协议走私、CRLF、DNS重绑定）
  3. 可访问内网资源（`127.0.0.1`, `169.254.x.x`, `10.x.x.x` 等）

### 误报排除
- URL 参数仅用于日志/展示，未实际发起请求
- 用户输入仅控制路径参数，Host 硬编码且不可篡改（需确认中间件无 Host 头覆盖）
- 代理目标从配置文件读取，用户输入仅作索引（需确认索引无注入）

### 代码异味
- 使用 `strings.Split` 手动解析 URL 而非 `url.Parse`（易出错）
- 白名单检查在业务逻辑之后（可能被提前 return 绕过）
- 仅过滤 `http://localhost` 但未处理 `http://127.1`, `http://[::1]` 等变种
- 依赖请求库的默认行为阻止内网访问（实际 Go `net/http` 默认不阻止）

---

## Low risk

### 低风险场景
- **严格白名单**：目标域名从不可变配置加载，用户仅选择索引（如 `service1/service2`）且索引验证完备
- **单一固定后端**：URL 拼接用户路径但 `scheme + host + port` 完全固定，且中间件无 Host 覆盖漏洞
- **出口受限环境**：应用运行在严格网络隔离环境，出站流量仅允许特定外部地址（但仍需标注，依赖网络配置非代码本身）
- **二次确认机制**：请求前展示目标地址并要求用户二次授权（降低自动化利用风险）
- **请求已签名**：目标服务校验请求签名，攻击者无法伪造（但仍可探测内网存活）

### 降级依据
- 保护措施在基础设施层（如 WAF/网络策略）而非代码层 → 不应完全忽略，需评估基础设施配置
- 仅能探测端口开放无法读取响应 → 降级但不忽略（信息泄露风险）
- 需要高权限账户触发 → 降级为中危（权限提升场景仍可利用）