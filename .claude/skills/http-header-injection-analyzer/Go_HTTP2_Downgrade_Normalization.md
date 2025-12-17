# Go HTTP/2降级 - 头字段规范化不一致

## 基本信息
- **难度等级：** ★★★★★ | **审计时间：** 45-60分钟
- **关键词搜索：** `http2`, `h2`, `ALPN`, `CanonicalHeaderKey`, `textproto`, `httputil.ReverseProxy`, `Transport`, `TLSNextProto`
- **快速检查：** 是否存在HTTP/2到HTTP/1.1转换，头字段大小写处理是否一致

## 漏洞成因

HTTP/2强制头字段小写（如`:authority`、`content-type`），而HTTP/1.1使用Title-Case（如`Content-Type`）。当Go应用作为代理将HTTP/2请求转发为HTTP/1.1时，若头字段规范化处理不一致，可能导致请求走私、安全检查绕过、缓存中毒等攻击。

### 常见漏洞模式

```go
// ✗ 漏洞：手动处理HTTP/2头，大小写不一致
func proxyHandler(w http.ResponseWriter, r *http.Request) {
    // HTTP/2请求头是小写：content-type
    // 检查使用Title-Case，可能被绕过
    if r.Header.Get("Content-Type") == "application/json" {  // 大小写不匹配
        // 安全检查
    }

    // 转发时可能保留原始大小写
    forwardRequest(r)
}
```

```go
// ✗ 漏洞：ReverseProxy未正确处理HTTP/2伪头
func setupProxy() *httputil.ReverseProxy {
    proxy := &httputil.ReverseProxy{
        Director: func(req *http.Request) {
            // :authority 伪头可能被错误处理
            req.Host = req.Header.Get(":authority")  // HTTP/2伪头
            req.Header.Del(":authority")  // 删除后可能不完整
        },
    }
    return proxy
}
```

```go
// ✗ 漏洞：自定义头规范化逻辑有缺陷
func normalizeHeaders(h http.Header) http.Header {
    normalized := make(http.Header)
    for k, v := range h {
        // 未使用标准规范化，可能导致不一致
        normalized[strings.Title(strings.ToLower(k))] = v
    }
    return normalized
}
```

```go
// ✗ 漏洞：忽略HTTP/2的伪头字段处理
func h2Handler(w http.ResponseWriter, r *http.Request) {
    // HTTP/2的:method, :path, :scheme, :authority需要特殊处理
    method := r.Header.Get(":method")  // 不应直接从Header获取
    if method == "" {
        method = r.Method  // 应该使用Request字段
    }
    // 攻击者可能发送冲突的:method头和请求行
}
```

```go
// ✓ 修复：使用标准规范化函数
import "net/textproto"

func safeNormalizeHeaders(h http.Header) http.Header {
    normalized := make(http.Header)
    for k, v := range h {
        // 使用标准库的规范化方法
        canonicalKey := textproto.CanonicalMIMEHeaderKey(k)
        normalized[canonicalKey] = v
    }
    return normalized
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | HTTP/2代理转发 | 搜索 `httputil.ReverseProxy\|http2.Transport`，检查头处理逻辑 |
| **P0** | 伪头字段处理 | 搜索 `:authority\|:method\|:path\|:scheme`，验证处理方式 |
| **P1** | 自定义头规范化 | 搜索 `strings.Title\|strings.ToLower` + Header，检查一致性 |
| **P1** | 安全检查绕过 | 搜索 `Header.Get` + 安全逻辑，验证大小写处理 |
| **P2** | TLS协议协商 | 搜索 `TLSNextProto\|ALPN`，检查HTTP/2支持配置 |
| **P2** | 混合协议场景 | 搜索 `http.Server` + `http2.Server`，检查降级处理 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 仅HTTP/1.1，无HTTP/2支持 | 快速跳过，确认无h2配置 |
| **L1** | 标准库HTTP/2，无自定义处理 | 关键词扫描，Go标准库自动处理 |
| **L2** | 使用ReverseProxy，默认配置 | 跳读检查Director函数 |
| **L3** | 自定义头处理逻辑 | 逐行审计规范化代码 |
| **L4** | 复杂代理架构，多协议转换 | 跨模块追踪所有协议转换点 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 应用处理HTTP/2请求并转换为HTTP/1.1（代理、网关场景）
2. 头字段规范化逻辑不使用`textproto.CanonicalMIMEHeaderKey`
3. 安全检查或业务逻辑依赖特定头字段大小写

### 典型漏洞特征（满足任一项即确认）
- ✗ 手动拼接`strings.Title(strings.ToLower(k))`而非标准函数
- ✗ 直接访问HTTP/2伪头（`:authority`）而非使用Request字段
- ✗ 安全检查使用硬编码大小写（`"Content-Type"`）
- ✗ ReverseProxy.Director中手动操作头字段

### 安全排除（任一项充分）
- ✓ 仅使用HTTP/1.1，无HTTP/2支持
- ✓ 使用Go标准库，未自定义头处理
- ✓ 所有头访问使用`Header.Get()`（自动规范化）
- ✓ 安全检查使用大小写不敏感比较

### 灰色判定（风险较低但需注意）
- 仅内部服务间通信，攻击面有限
- 使用第三方代理库，版本可能有修复
- 头字段差异仅影响非安全功能

---

## 审计专业技巧

### 真实漏洞 vs 误报区分指南

#### 场景1：Header.Get()的大小写问题

**误报案例：**
```go
// 看似不安全，实际安全
if r.Header.Get("content-type") == "application/json" {
    // Go的Header.Get()内部会自动规范化，无论传入何种大小写
    // textproto.CanonicalMIMEHeaderKey会转换为"Content-Type"
    // 这不是漏洞！
}
```

**判定方法：**
- ✓ 安全：只要使用了`Header.Get()`，无论大小写输入，库函数会自动规范化
- ✗ 真漏洞：绕过`Header.Get()`的自定义访问方式

```go
// 真实漏洞：直接访问内部map
contentType := r.Header["content-type"]  // 错误！区分大小写
if contentType[0] == "application/json" {
    // 可以被绕过：攻击者发送Content-Type会被跳过
}
```

#### 场景2：HTTP/2伪头的标准处理

**误报案例：**
```go
// 看似问题，实际Go标准库已处理
func handler(w http.ResponseWriter, r *http.Request) {
    // :authority伪头已由Go HTTP/2处理，自动映射到r.Host和r.RequestURI
    // 在业务代码中不应该看到":authority"头
}
```

**判定方法：**
- ✓ 安全：使用`r.Host`、`r.Method`、`r.RequestURI`这些预处理字段
- ✗ 真漏洞：在业务逻辑中手动访问`:authority`、`:method`等伪头

```go
// 真实漏洞：手动处理伪头导致冲突
func proxyHandler(r *http.Request) {
    // 攻击者可能同时发送:method伪头和Request.Method不一致
    methodFromHeader := r.Header.Get(":method")  // HTTP/2伪头
    if methodFromHeader != "" && methodFromHeader != r.Method {
        // 不一致！导致安全检查错误
    }
}
```

#### 场景3：ReverseProxy的安全性评估

**误报案例：**
```go
// 看似有问题，实际安全
proxy := httputil.NewSingleHostReverseProxy(target)
// 默认配置下，go已正确处理HTTP/2到HTTP/1.1转换
// 头字段会正确规范化为Title-Case
```

**判定方法：**
- ✓ 安全：使用默认的`NewSingleHostReverseProxy`或标准的`ReverseProxy`
- ✗ 真漏洞：自定义Director覆盖头处理逻辑

```go
// 真实漏洞：自定义Director破坏规范化
proxy := &httputil.ReverseProxy{
    Director: func(req *http.Request) {
        // 自定义修改头字段，可能破坏规范化
        for k, v := range req.Header {
            req.Header[strings.ToLower(k)] = v  // 改成小写！
            delete(req.Header, k)
        }
        // 转发时不再是标准的Title-Case，后端服务可能无法识别
    },
}
```

#### 场景4：安全检查的大小写敏感性

**误报案例：**
```go
// 看似有问题，实际正确
token := r.Header.Get("Authorization")
if token == "" {
    token = r.Header.Get("authorization")  // 冗余但无害
}
// Header.Get已自动规范化，第二行是冗余的但不是漏洞
```

**判定方法：**
- ✓ 安全：任何大小写变体通过`Header.Get()`都能正确获取
- ✗ 真漏洞：绕过Header.Get直接判断

```go
// 真实漏洞：硬编码的map访问
if r.Header["Authorization"] != "" {
    // 攻击者发送"authorization"会被跳过！
    // 或在HTTP/2中发送"authorization"被转为"Authorization"
    // 导致安全检查失效
}
```

### 审计技巧清单

**快速判定流程：**

1. **第一步：确认协议使用**
   - 仅HTTP/1.1 → 低风险，可跳过此专题
   - HTTP/2代理 → 需要深入审计

2. **第二步：检查头访问方式**
   ```bash
   # 搜索直接map访问
   grep -r "r\.Header\[" --include="*.go"
   # 搜索自定义规范化逻辑
   grep -r "strings\.Title\|strings\.ToLower.*Header" --include="*.go"
   # 搜索伪头直接访问
   grep -r ":authority\|:method\|:path" --include="*.go"
   ```

3. **第三步：验证规范化函数**
   - 使用`Header.Get()`：✓ 安全
   - 使用`textproto.CanonicalMIMEHeaderKey`：✓ 安全
   - 自定义规范化：✗ 需深入审计

4. **第四步：检查代理逻辑**
   - 默认ReverseProxy：✓ 安全
   - 无自定义Director：✓ 安全
   - 自定义Director修改头：✗ 可能有漏洞

### 常见误判防范

| 代码特征 | 初判 | 最终判定 | 原因 |
|---------|------|---------|------|
| `r.Header.Get("Content-Type")` | ⚠️ | ✓ 安全 | 自动规范化 |
| `r.Header["content-type"]` | ⚠️ | ✗ 漏洞 | 区分大小写 |
| `proxy := httputil.NewSingleHostReverseProxy(url)` | ⚠️ | ✓ 安全 | 标准库处理 |
| 自定义Director中修改头 | ⚠️ | ✗ 漏洞 | 破坏规范化 |
| `r.Header.Get(":authority")` | ✗ | ✓ 安全 | 返回""，标库已处理 |
| 业务逻辑中使用`:method` | ✗ | ✗ 漏洞 | 可被覆盖 |

### 实战审计检查要点

- 追踪HTTP/2入口到HTTP/1.1出口的完整路径
- 在转换点检查是否有自定义逻辑覆盖标准处理
- 验证安全检查使用的头字段是否会因大小写被绕过
- 对ReverseProxy的Director函数逐行审计
- 测试时尝试发送混合大小写和冲突的头字段

---

## 实现建议

### 核心防护方案

**方案1：使用标准规范化函数**
```go
import "net/textproto"

func getHeader(h http.Header, key string) string {
    canonicalKey := textproto.CanonicalMIMEHeaderKey(key)
    return h.Get(canonicalKey)
}
```

**方案2：安全的ReverseProxy配置**
```go
func safeReverseProxy(target *url.URL) *httputil.ReverseProxy {
    proxy := httputil.NewSingleHostReverseProxy(target)
    originalDirector := proxy.Director

    proxy.Director = func(req *http.Request) {
        originalDirector(req)
        // 不手动操作HTTP/2伪头
        // Host字段由标准库正确处理
    }

    return proxy
}
```

**方案3：大小写不敏感的安全检查**
```go
func checkContentType(r *http.Request, expected string) bool {
    actual := r.Header.Get("Content-Type")  // 自动规范化
    return strings.EqualFold(
        strings.Split(actual, ";")[0],
        expected,
    )
}
```

### 检查清单
- [ ] 所有头字段访问使用`Header.Get()`
- [ ] 自定义规范化使用`textproto.CanonicalMIMEHeaderKey`
- [ ] ReverseProxy不手动操作伪头字段
- [ ] 安全检查使用大小写不敏感比较
- [ ] 测试HTTP/2请求头大小写变体

---

## 修复优先级

1. **立即修复**：代理场景下手动处理HTTP/2伪头字段
2. **本周修复**：统一使用标准库头字段规范化函数
3. **可选加强**：添加HTTP/2到HTTP/1.1转换测试用例
4. **长期优化**：评估是否需要自定义头处理，尽量使用标准库
