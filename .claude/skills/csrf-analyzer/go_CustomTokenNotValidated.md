# Go 自定义 Token 校验缺失漏洞

## Details

### 漏洞成因
部分 Go 项目在未使用现成 CSRF 中间件的情况下，手动生成 Token 并存储于 Cookie 或上下文中，但在验证时仅检查 Token 是否存在、格式正确，或与用户提交值做字符串比较而未与服务端存储的预期值进行匹配。攻击者可复用旧 Token、伪造任意字符串或提交空值绕过，从而执行敏感操作。

### 代码示例

**易受攻击的代码：**
```go
func validateCSRF(c *gin.Context) bool {
    token := c.PostForm("_csrf")
    return token != "" // 仅检查非空
}

r.POST("/profile", func(c *gin.Context) {
    if !validateCSRF(c) {
        c.AbortWithStatus(http.StatusForbidden)
        return
    }
    // 未与服务端存储的 token 对比
    updateProfile(c)
})
```

**另一个不安全示例（只校验格式）：**
```go
if !regexp.MustCompile(`^[a-f0-9]{32}$`).MatchString(token) {
    return false
}
// 未对比 session 中的值
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Token 生成：`rand.Read`, `uuid.New`, `crypto/rand`
- 存储：`session.Set("csrf")`, `context.Set("csrf")`, `redis.Set("csrf:`
- 验证：`if token == ""`, `if token == expected`, `hash := c.GetHeader("X-CSRF")`

**定位步骤：**
1. 搜索 Token 验证函数，确认是否与服务端存储值比对。
2. 检查 Token 是否绑定到 session/cookie。
3. 跳读（L2）确认 Token 在成功使用后是否刷新或删除。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **服务端存储**：Session、Redis、数据库中存储期望 Token。
- **严格比较**：使用 `subtle.ConstantTimeCompare`。
- **一次性**：每次验证后刷新 Token。
- **双重提交 Cookie**：比较 Cookie 与字段值一致。

**定位技巧：**
- 确认 Token 不会被记录在日志或 query string 中泄露。
- 检查多实例部署是否共享 Token 存储。
- 分析 Token 是否包含时间戳并验证过期。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 正确存储 + 常量时间比较 | **L0（快速跳过）** | 风险低 |
| 仅检查存在或格式 | **L3（逐行读）** | 高风险 |
| 验证后不刷新/可重复使用 | **L2（跳读）** | 需优化 |
| Token 与 session 未绑定 | **L4（跨模块追踪）** | 极易被滥用 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 验证逻辑未与服务端存储的 Token 对比或不绑定会话。
2. 端点依赖 Cookie/Session 鉴权。
3. 攻击者可伪造或复用 Token。

#### 误报
以下情况非漏洞：
1. Token 仅用于 API 幂等控制，与 CSRF 无关。
2. 请求通过 HMAC 签名验证（如每次请求都有签名）。
3. 端点使用 Bearer Token，不依赖 Cookie。

#### 代码异味
需记录：
1. Token 存储在全局 map，服务重启即失效（可能导致绕过）。
2. Token 字段名称在不同表单不一致，验证函数容易漏掉。
3. 使用 `strings.EqualFold` 导致大小写绕过。
4. 对空 Token 仅记录日志，但继续执行操作。

## Low risk

### 低风险评级场景

#### 1. 内部管理系统
- **场景：** 操作需管理员权限，且使用审计日志。
- **风险评估：** 攻击面有限，但应修复。

#### 2. 二次验证
- **场景：** 敏感操作需短信/OTP 确认。
- **风险评估：** 提高攻击成本，仍需完善 Token。

#### 3. Token 频繁刷新
- **场景：** 即使未校验值，也会每次请求刷新 Token。
- **风险评估：** 缩小窗口期，但仍不安全。

#### 4. SameSite=Strict Cookie
- **场景：** Cookie 配置 Strict。
- **风险评估：** 部分缓解，仍需修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理后台 + 审计 | 攻击面有限 | 中 |
| 二次验证 | 提高攻击成本 | 中 |
| Token 频繁刷新 | 缩短窗口 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |

