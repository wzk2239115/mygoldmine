# Go Host头未验证 - 反向代理场景

## Details

### 漏洞成因与常见模式

Go反向代理应用中，若Host头未验证直接用于构造后端请求URL、缓存键、或认证逻辑，可导致SSRF、缓存中毒、认证绕过等攻击。

#### 模式1：反向代理直接转发Host头

```go
// ✗ 漏洞：直接使用Host头构造后端URL
func proxyHandler(w http.ResponseWriter, r *http.Request) {
    backend := "http://" + r.Host + r.RequestURI
    resp, _ := http.Get(backend)  // 未验证Host
    io.Copy(w, resp.Body)
    // 攻击: Host: internal.admin.local
}
```

#### 模式2：基于Host头的路由选择

```go
// ✗ 漏洞：多租户场景未验证Host
func tenantRouter(w http.ResponseWriter, r *http.Request) {
    tenant := strings.Split(r.Host, ".")[0]  // 提取子域名
    backendURL := fmt.Sprintf("http://%s-backend.internal", tenant)
    proxy := httputil.NewSingleHostReverseProxy(parseURL(backendURL))
    proxy.ServeHTTP(w, r)
    // 攻击: Host: admin-backend.internal.attacker.com
}
```

#### 模式3：缓存键使用未验证Host

```go
// ✗ 漏洞：缓存键包含Host头
func cacheHandler(w http.ResponseWriter, r *http.Request) {
    cacheKey := r.Host + r.RequestURI
    if cached, ok := cache.Get(cacheKey); ok {
        w.Write(cached)  // 攻击者可污染缓存
        return
    }
    // 正常处理...
}
```

#### 模式4：认证回调URL使用Host

```go
// ✗ 漏洞：OAuth回调地址未验证
func oauthHandler(w http.ResponseWriter, r *http.Request) {
    callbackURL := "https://" + r.Host + "/oauth/callback"
    redirectURL := oauthConfig.AuthCodeURL(state, oauth2.SetAuthURLParam("redirect_uri", callbackURL))
    http.Redirect(w, r, redirectURL, 302)
}
```

#### 模式5：密码重置链接使用Host

```go
// ✗ 漏洞：密码重置链接可被投毒
func resetPassword(w http.ResponseWriter, r *http.Request) {
    email := r.FormValue("email")
    token := generateToken(email)
    resetLink := fmt.Sprintf("https://%s/reset?token=%s", r.Host, token)
    sendEmail(email, resetLink)  // 发送到攻击者控制的域名
}
```

#### 安全实现参考

```go
// ✓ 安全：Host头白名单验证
var allowedHosts = map[string]bool{
    "example.com":     true,
    "www.example.com": true,
    "api.example.com": true,
}

func secureProxy(w http.ResponseWriter, r *http.Request) {
    // ✓ 白名单验证
    if !allowedHosts[r.Host] {
        http.Error(w, "Invalid Host", 400)
        return
    }

    backend := "http://internal-backend" + r.RequestURI
    resp, _ := http.Get(backend)
    io.Copy(w, resp.Body)
}
```

### 审计检查清单

| 优先级 | 检查项 | 审计方法 | 审计等级 |
|--------|--------|---------|----------|
| **P0** | Host头用于URL构造 | 搜索 `r.Host` + 字符串拼接URL，检查白名单 | **L2-L3** |
| **P0** | 反向代理转发 | 搜索 `httputil.ReverseProxy\|NewSingleHostReverseProxy` + Host使用 | **L3** |
| **P0** | 密码重置/邮件链接 | 搜索 `r.Host` + `sendEmail\|smtp` 组合 | **L2-L3** |
| **P1** | 缓存键构造 | 搜索 `cache.Get\|Set` + Host头，检查是否有Vary头 | **L3** |
| **P1** | 多租户路由 | 搜索 `strings.Split(r.Host` 子域名提取，检查验证逻辑 | **L3** |
| **P2** | OAuth回调URL | 搜索 `oauth\|callback` + Host头拼接 | **L2-L3** |
| **P3** | X-Forwarded-Host | 搜索 `X-Forwarded-Host` 头使用，检查是否信任代理 | **L2** |

### 审计等级判定

| 等级 | 代码特征 | 审计策略 |
|------|---------|---------|
| **L0** | Host头仅用于日志，无业务逻辑 | 快速跳过，确认无URL构造 |
| **L1** | Host头用于非关键展示 | 关键词扫描：确认无 `http.Get/Post` 组合 |
| **L2** | 单文件内Host头用于URL构造 | 跳读：检查是否有白名单 `map[string]bool` |
| **L3** | 跨模块Host头传递 | 逐行读：追踪方法参数传递链 |
| **L4** | 反向代理全局中间件 | 跨模块追踪：检查 `http.Handler` 链式调用 |

---

## Classify

### 确认漏洞的标准

1. **直接威胁**：Host头用于构造后端请求URL、密码重置链接、OAuth回调等关键场景
2. **无验证机制**：代码中无白名单检查、无正则匹配验证
3. **可利用性**：攻击者可通过修改Host头触发漏洞（非TLS SNI严格绑定场景）

### 判定为误报的情况

1. **已有白名单**：存在 `allowedHosts map` 或 `switch r.Host` 白名单验证
2. **基础设施防护**：负载均衡器/反向代理配置强制验证Host头
3. **单域名应用**：应用仅绑定单一域名，无多租户场景
4. **仅内部使用**：反向代理仅转发到固定内部地址，Host头不影响目标

### 代码异味识别

1. **不完整验证**：仅检查Host头是否包含某个字符串，未严格匹配
2. **X-Forwarded-Host盲信**：直接使用 `r.Header.Get("X-Forwarded-Host")` 无验证
3. **注释依赖**：代码注释"由Nginx验证"，但无代码层防御
4. **域名后缀匹配**：使用 `strings.HasSuffix(host, ".example.com")` 可被 `evil-example.com` 绕过

### 审计专业技巧 - 真实漏洞vs误报区分

#### 1. 流量入口追踪法

**核心原则**：区分Host头是否**真正可被攻击者控制**

| 场景 | 是否可控 | 判断方法 | 风险等级 |
|------|--------|---------|---------|
| HTTP直连 | ✅ 完全可控 | 协议为HTTP或Websocket | **真实漏洞** |
| HTTPS自签证书 | ✅ 完全可控 | 客户端可跳过证书验证 | **真实漏洞** |
| HTTPS浏览器访问 | ❌ 受限 | 浏览器验证证书+SNI | **低风险** |
| 内网API调用 | ❌ 受限 | 仅内部系统可访问 | **误报** |
| CDN后端 | ❌ 受限 | CDN已验证Host头 | **误报** |

**实战技巧**：查看 `TLS证书绑定情况`、`HTTP_ROUTER配置`、`反向代理前置情况`

#### 2. 白名单编码缺陷识别

**假白名单案例**

```go
// ✗ 错误示例1：包含匹配绕过
validHosts := []string{"example.com"}
if strings.Contains(r.Host, "example.com") {  // 被 "attacker-example.com" 绕过
    processRequest()
}

// ✗ 错误示例2：后缀匹配绕过
if strings.HasSuffix(r.Host, ".example.com") {  // 被 "evil-example.com" 绕过
    processRequest()
}

// ✗ 错误示例3：正则过宽
if regexp.MatchString("^example\\.com.*", r.Host) {  // 被 "example.com.attacker.com" 绕过
    processRequest()
}

// ✓ 正确示例：精确匹配
validHosts := map[string]bool{
    "example.com": true,
    "www.example.com": true,
}
if !validHosts[r.Host] {
    http.Error(w, "Forbidden", 403)
    return
}
```

**审计技巧**：搜索所有 `Host验证关键词`：`Contains/HasPrefix/HasSuffix/MatchString/Split`，逐行审查匹配逻辑

#### 3. 多层级验证判定法

**关键问题**：单层防护 vs 多层防护

```go
// 案例：密码重置链接
func resetPassword(email string) {
    token := generateSecureToken()  // 第1层：Token本身有时效性+不可预测
    resetLink := fmt.Sprintf("https://%s/reset?token=%s", r.Host, token)  // 使用Host

    // 第2层防护判定
    if sendEmail(email, resetLink) {
        // 检查是否有额外验证
        // - 邮箱确认？
        // - IP地址绑定？
        // - 短信确认？
    }
}
```

**风险评分公式**：
- 无验证：100分（严重漏洞）
- 仅Token防护：70分（中危）
- Token + 邮箱确认：40分（低危）
- Token + 邮箱 + 短信：20分（建议修复）

#### 4. 缓存污染影响范围评估

**真实漏洞判定清单**

```
□ 缓存的数据被多用户共享？
□ 缓存命中率 > 10%？（影响范围大）
□ Host头直接参与缓存Key？（非Vary头方式）
□ 缓存过期时间 > 1小时？
□ 无请求签名/HMAC验证？
```

若上述全部为是 → **真实中危漏洞**
若仅部分为是 → **低风险/建议修复**

#### 5. 反向代理目标判定法

**关键问题**：Host头影响的后端地址是什么？

```go
// 案例1：影响关键系统 → 真实漏洞
backendURL := fmt.Sprintf("http://%s-backend.internal:8080", extractTenant(r.Host))
// 可被操纵访问：admin-backend.internal, finance-backend.internal

// 案例2：目标地址固定 → 误报
backendURL := "http://192.168.1.100:8080"  // 目标硬编码
headers := r.Header.Clone()
headers.Set("X-Original-Host", r.Host)  // 仅用于日志
proxy.ServeHTTP(w, r)

// 案例3：目标地址仅受部分影响 → 低风险
backendURL := "http://backend." + strings.Split(r.Host, ".")[0] + ":8080"
// 若只有子域名部分可控，影响有限
```

**审计技巧**：
1. 找到Host头使用点
2. 追踪其流向：是否进入URL构造、Header设置、缓存Key
3. 判断目标地址是否可被控制：固定IP→误报，动态构造→漏洞

#### 6. 真实漏洞案例库

**已验证的真实漏洞特征**：

1. **OAuth令牌泄露**：Host头用于设置`redirect_uri`，无验证 → **P0**
2. **密码重置劫持**：Host头直接用于邮件链接，邮件服务商可转发 → **P0**
3. **缓存中毒**：Host用于缓存Key，返回给所有用户 → **P1**
4. **反向代理SSRF**：Host用于后端地址构造，可访问内网 → **P0**
5. **多租户逃逸**：Host的子域名用于提取租户ID，无严格校验 → **P1**

**常见误报特征**：

1. Host头仅用于日志记录
2. Host头用于UI展示（favicon、静态资源路径不含敏感信息）
3. Host头有多层硬件级验证（CDN + WAF + LB）
4. 应用为纯API服务，客户端采用SDK绑定域名

---

## Low risk

### 低风险场景判定标准

满足以下任一条件时，可评估为低风险（仍需标注并建议修复）：

1. **有限暴露场景**
   - 应用仅部署内网，外部无法访问
   - 前置有经过验证的WAF/CDN配置Host白名单
   - TLS证书绑定特定域名，SNI严格验证

2. **业务影响受限**
   - Host头仅影响日志记录、监控标识
   - 密码重置有额外短信/邮箱验证
   - 缓存按用户会话隔离，中毒影响范围小

3. **部分防护措施**
   - 存在基础格式验证（长度、字符集）但不够严格
   - 反向代理目标地址有内网隔离
   - 有请求频率限制

4. **可审计性强**
   - 所有Host头使用已集中在工具函数中
   - 存在监控告警，异常Host会触发事件
   - 代码中有TODO标注需添加验证

### 评级建议

- **低风险 + 内网环境**：建议下一迭代添加白名单
- **低风险 + WAF防护**：代码层仍应加固，不依赖外部
- **低风险 + 多因素验证**：优先级降低，但需明确禁止未验证使用Host