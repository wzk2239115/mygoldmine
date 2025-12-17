# Go 缓存中毒 - Vary头不完整

## 基本信息
- **难度等级：** ★★★★☆ | **审计时间：** 30-45分钟
- **关键词搜索：** `Vary`, `Cache-Control`, `ETag`, `redis`, `memcache`, `sync.Map`, `http.Handler`, `X-Forwarded`, `Accept-Language`
- **快速检查：** 响应是否被缓存，缓存键是否包含所有影响响应的请求头

## 漏洞成因

当HTTP响应被缓存（CDN/代理/应用层）时，若Vary头未包含所有影响响应内容的请求头，攻击者可利用特定头值污染缓存，使其他用户收到恶意内容。Go应用常见于自定义缓存中间件或CDN配置不当。

### 常见漏洞模式

```go
// ✗ 漏洞：响应内容依赖Accept-Language但Vary头缺失
func handler(w http.ResponseWriter, r *http.Request) {
    lang := r.Header.Get("Accept-Language")
    content := getLocalizedContent(lang)

    w.Header().Set("Cache-Control", "public, max-age=3600")
    // 缺少：w.Header().Set("Vary", "Accept-Language")
    w.Write([]byte(content))
    // 攻击者设置Accept-Language: evil，污染所有用户缓存
}
```

```go
// ✗ 漏洞：X-Forwarded-Host影响响应但未加入Vary
func apiHandler(w http.ResponseWriter, r *http.Request) {
    host := r.Header.Get("X-Forwarded-Host")
    if host == "" {
        host = r.Host
    }
    response := fmt.Sprintf(`{"api_url": "https://%s/api"}`, host)

    w.Header().Set("Cache-Control", "public, max-age=600")
    // 缺少：w.Header().Set("Vary", "X-Forwarded-Host")
    w.Write([]byte(response))
}
```

```go
// ✗ 漏洞：缓存键不包含Cookie但响应依赖用户状态
func cachedHandler(w http.ResponseWriter, r *http.Request) {
    cacheKey := r.URL.Path  // 缺少用户相关因素

    if cached, ok := cache.Get(cacheKey); ok {
        w.Write(cached)
        return
    }

    // 响应内容依赖Cookie中的用户偏好
    prefs := getUserPrefs(r.Cookie("session"))
    content := renderWithPrefs(prefs)
    cache.Set(cacheKey, content)
    w.Write(content)
}
```

```go
// ✗ 漏洞：Vary头不完整，仅包含部分影响因素
func multiFactorHandler(w http.ResponseWriter, r *http.Request) {
    lang := r.Header.Get("Accept-Language")
    encoding := r.Header.Get("Accept-Encoding")
    ua := r.Header.Get("User-Agent")

    content := generateContent(lang, encoding, ua)

    w.Header().Set("Cache-Control", "public, max-age=3600")
    w.Header().Set("Vary", "Accept-Language")  // 缺少Accept-Encoding和User-Agent
    w.Write(content)
}
```

```go
// ✓ 修复：完整的Vary头设置
func safeHandler(w http.ResponseWriter, r *http.Request) {
    lang := r.Header.Get("Accept-Language")
    content := getLocalizedContent(lang)

    w.Header().Set("Cache-Control", "public, max-age=3600")
    w.Header().Set("Vary", "Accept-Language, Accept-Encoding")
    w.Write([]byte(content))
}
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 缓存响应依赖用户头 | 搜索 `Cache-Control.*public\|max-age` + `r.Header.Get`，对比Vary设置 |
| **P0** | X-Forwarded-*影响响应 | 搜索 `X-Forwarded-Host\|X-Forwarded-Proto`，检查是否加入Vary |
| **P1** | 自定义缓存中间件 | 搜索 `sync.Map\|redis.Get\|memcache`，检查缓存键构造 |
| **P1** | Accept-*头影响内容 | 搜索 `Accept-Language\|Accept-Encoding`，验证Vary包含 |
| **P2** | CDN配置审计 | 检查nginx/Varnish配置，确认缓存规则与代码一致 |
| **P2** | Cookie依赖但无Vary | 搜索 `r.Cookie` + 缓存逻辑，检查是否正确隔离 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 无缓存头，响应不被缓存 | 快速跳过，确认Cache-Control: no-store |
| **L1** | 私有缓存，仅浏览器缓存 | 关键词扫描，确认Cache-Control: private |
| **L2** | 公共缓存，单一影响因素 | 跳读检查Vary头是否包含该因素 |
| **L3** | 多请求头影响响应内容 | 逐行追踪所有Header.Get调用，验证Vary完整性 |
| **L4** | 复杂缓存架构（CDN+应用） | 跨层审计，检查各层缓存配置一致性 |

---

## 审计专业技巧

### 真实漏洞与误报区分

**真实漏洞特征（需修复）：**

1. **缓存污染可验证型**
   - 同一URL，通过不同Header值收到不同响应
   - 响应被CDN/代理缓存，第一个请求"赢家通吃"
   - 后续请求无论如何设置Header都收到同一缓存副本
   - **审计技巧**：追踪ETag/Last-Modified，对比多次请求是否完全相同

2. **用户隐私泄露型**
   - 用户A的Accept-Language设置被缓存
   - 用户B访问相同URL却收到用户A的本地化内容
   - **审计技巧**：检查响应中是否包含个性化信息（用户名、邮箱、偏好设置）

3. **跨域污染型**
   - X-Forwarded-Host污染导致不同域名用户收到错误的域名信息
   - 通常导致CSRF或重定向攻击链
   - **审计技巧**：搜索 `X-Forwarded-Host|X-Forwarded-Proto|Host` 的使用，检查是否用于构造URL

**常见误报情况（非漏洞）：**

1. **私有缓存有Vary** ✗ 误报
   ```go
   w.Header().Set("Cache-Control", "private, max-age=3600")
   w.Header().Set("Vary", "Accept-Language")  // 私有缓存，Vary无用但无害
   ```
   - 仅浏览器缓存，攻击者无法污染
   - 修复建议：移除Vary头简化代码，或保留不处理

2. **无缓存头响应** ✗ 误报
   ```go
   // 无Cache-Control和Vary，依赖浏览器默认行为
   w.Header().Set("Vary", "Accept-Language")
   ```
   - 可能被浏览器缓存但無明确缓存策略
   - 优先级低，建议明确设置Cache-Control: no-store

3. **很短的TTL** ⚠ 低风险
   - max-age=1 或 max-age=5，攻击窗口极窄
   - 实际利用难度高，但理论上仍存在漏洞
   - **审计判定**：max-age<30秒可标记为低优先级

4. **内网应用** ⚠ 低风险
   - 只有授权员工访问，攻击者难以利用
   - 检查IP限制：`isInternalIP(r.RemoteAddr)`
   - 但若面向API调用，需谨慎评估

### 实战审计流程

**第一步：快速定位缓存点**
```
搜索关键词：Cache-Control|Vary|sync.Map|redis|memcache|lru
统计：缓存设置数量，分优先级
```

**第二步：追踪请求头使用**
```
对每个Cache-Control: public响应：
1. 逆向追踪所有r.Header.Get()调用
2. 列出影响响应的请求头清单
3. 对比Vary头是否完整包含
```

**第三步：验证缓存隔离**
```go
// 构造测试用例
GET /api/user HTTP/1.1
Accept-Language: zh-CN

// 缓存生成，ETag: "abc123"
// 再次请求不同Header
GET /api/user HTTP/1.1
Accept-Language: en-US

// 若返回相同ETag，证实缓存污染
```

**第四步：评估影响范围**
- 缓存层级：浏览器 < CDN < 反向代理 < 应用
- 暴露信息类型：个性化内容 > 功能性差异 > 无差异
- 攻击可达性：公网 > VPN > 内网

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 响应设置了可被公共缓存的头（`Cache-Control: public`或无`private/no-store`）
2. 响应内容依赖某个请求头（如Accept-Language、X-Forwarded-Host）
3. Vary头未包含该请求头，或缓存键未包含该因素

### 典型漏洞特征（满足任一项即确认）
- ✗ `Cache-Control: public` + `r.Header.Get("Accept-Language")` 但无Vary
- ✗ 缓存键仅为URL路径，但响应依赖Cookie/Header
- ✗ `X-Forwarded-Host`用于构造响应URL但未加入Vary
- ✗ Vary头存在但不完整（漏掉部分影响因素）

### 安全排除（任一项充分）
- ✓ 响应设置`Cache-Control: private`或`no-store`
- ✓ Vary头包含所有影响响应的请求头
- ✓ 缓存键完整包含URL+所有相关Header
- ✓ 仅API响应，无CDN/代理缓存层

### 灰色判定（风险较低但需注意）
- 缓存时间短（max-age < 60），攻击窗口有限
- 内网应用，攻击者难以利用
- 响应内容无敏感信息，仅影响展示

---

## 实现建议

### 核心防护方案

**方案1：完整Vary头设置**
```go
func handler(w http.ResponseWriter, r *http.Request) {
    // 收集所有影响响应的请求头
    varyHeaders := []string{}

    if lang := r.Header.Get("Accept-Language"); lang != "" {
        varyHeaders = append(varyHeaders, "Accept-Language")
    }
    if encoding := r.Header.Get("Accept-Encoding"); encoding != "" {
        varyHeaders = append(varyHeaders, "Accept-Encoding")
    }

    w.Header().Set("Vary", strings.Join(varyHeaders, ", "))
}
```

**方案2：安全缓存键生成**
```go
func generateCacheKey(r *http.Request) string {
    h := sha256.New()
    h.Write([]byte(r.URL.Path))
    h.Write([]byte(r.Header.Get("Accept-Language")))
    h.Write([]byte(r.Header.Get("Accept-Encoding")))
    // 包含所有影响响应的因素
    return hex.EncodeToString(h.Sum(nil))
}
```

**方案3：缓存中间件统一处理**
```go
func CacheMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // 默认设置安全的Vary头
        w.Header().Set("Vary", "Accept-Language, Accept-Encoding, Cookie")
        next.ServeHTTP(w, r)
    })
}
```

### 检查清单
- [ ] 所有可缓存响应设置完整Vary头
- [ ] 缓存键包含所有影响响应的因素
- [ ] X-Forwarded-*头使用时加入Vary或验证
- [ ] 敏感响应设置Cache-Control: private
- [ ] CDN配置与应用代码Vary设置一致

---

## 修复优先级

1. **立即修复**：公共缓存响应依赖X-Forwarded-Host但无Vary
2. **本周修复**：添加完整Vary头，包含所有影响因素
3. **可选加强**：实现缓存键生成器，统一处理缓存隔离
4. **长期优化**：CDN配置审计，建立缓存安全策略
