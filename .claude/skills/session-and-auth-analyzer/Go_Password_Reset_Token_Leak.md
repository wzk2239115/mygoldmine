# Go_Password_Reset_Token_Leak

**漏洞类型**: Go 密码重置功能中，重置令牌泄露到日志或错误信息中，导致令牌被记录和可被获取

---

## Details

### 代码示例

**易受攻击的代码模式**:
```go
// 示例1: 重置令牌直接写入日志
func generateResetToken(userID string) string {
    token := generateSecureToken()
    log.Printf("Generated reset token for user %s: %s", userID, token)
    // 令牌在日志中可见
    return token
}

// 示例2: 错误处理中泄露令牌
func verifyResetToken(token string) (string, error) {
    user, err := findUserByToken(token)
    if err != nil {
        return "", fmt.Errorf("Token verification failed: %s", token)
        // 错误消息包含令牌
    }
    return user.ID, nil
}

// 示例3: Debug 输出包含令牌
func resetPassword(token, newPassword string) error {
    log.Debugf("Processing password reset with token: %s", token)
    // Debug 日志可能被启用到生产环境
    return updatePassword(token, newPassword)
}

// 示例4: 令牌在 HTTP 请求中被记录
func handleResetRequest(w http.ResponseWriter, r *http.Request) {
    token := r.URL.Query().Get("token")
    log.Printf("Received request: %s", r.RequestURI)
    // RequestURI 包含完整的 URL，含令牌
}

// 示例5: 邮件发送中泄露令牌
func sendResetEmail(email, token string) error {
    log.Printf("Sending reset email to %s with token %s", email, token)
    // 邮件发送日志包含令牌
    return sendEmail(email, "Please reset your password")
}

// 示例6: Panic 或 crash logs
func criticalResetOperation(token string) {
    defer func() {
        if r := recover(); r != nil {
            log.Fatalf("Critical error processing token %s: %v", token, r)
            // Panic 日志包含令牌
        }
    }()
}

// 示例7: 数据库查询日志
func getResetTokenRecord(token string) (*TokenRecord, error) {
    query := fmt.Sprintf("SELECT * FROM reset_tokens WHERE token = '%s'", token)
    log.Printf("Executing query: %s", query)
    // SQL 查询日志包含令牌
    return db.QueryRow(query).Scan(...)
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 日志输出: `log.Printf()`, `log.Fatalf()`, `log.Debugf()`, `logrus`, `zap`
- 令牌相关: `token`, `resetToken`, `reset_token`, `password_reset`
- 敏感数据模式: `token = `, `Token:`, `%s`, `%v` 格式化令牌
- 错误处理: `fmt.Errorf()`, `errors.New()` 中包含令牌
- 请求记录: `RequestURI`, `RawQuery`, `r.URL`

**L2 跳读定位**:
- 密码重置函数: `generateResetToken()`, `sendResetEmail()`, `verifyResetToken()`
- 日志调用: 所有包含 token 变量的日志行
- 错误返回: 错误消息中是否包含令牌
- 邮件发送: 发送重置邮件的函数

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- Token 日志缺失: 无日志输出令牌
- 令牌脱敏: 日志中仅显示前几字符, 如 `token[:8]`
- 日志级别: Debug 日志是否在生产禁用

**L3 逐行分析**:
- 日志敏感性:
  - 所有 log 调用是否避免输出完整令牌
  - 是否实现了令牌脱敏函数
  - 敏感日志是否限制在 Debug 级别
- 错误处理:
  - 错误消息中是否包含令牌
  - 是否有通用的错误返回而非具体令牌信息
  - 用户看到的错误是否隐藏敏感信息
- 请求日志:
  - HTTP 请求记录是否包含完整 URL
  - 是否过滤了查询参数中的敏感信息
  - 中间件是否记录了令牌
- 邮件相关:
  - 邮件发送日志是否包含令牌或邮件内容
  - 邮件模板中是否有日志输出

**L4 跨模块追踪**:
- 追踪所有日志输出，检查是否包含令牌
- 检查日志库的配置 (logrus, zap 等)
- 验证日志存储和访问权限
- 检查监控和警报系统是否会输出令牌
- 审查容器或平台的日志收集配置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 日志中直接输出完整的重置令牌
- 错误消息包含令牌信息
- HTTP 请求日志记录了完整的 URL (包含 token 参数)
- 邮件发送日志包含令牌
- Panic 或崩溃日志包含令牌

**误报判定**:
- 日志中仅显示令牌的前几字符或哈希值
- Debug 日志在生产环境禁用
- 敏感信息用占位符表示 (如 ****)
- 有日志审计和访问控制

**代码异味**:
- 有多个日志调用，某些包含令牌，某些不包含
- 注释中提到"不要记录令牌"但代码仍然记录
- 令牌作为函数参数，自动被包含在日志中
- 使用 %v 或 %s 格式化包含令牌的结构体

---

## Low risk

### 低风险场景

**访问控制**:
- 日志仅限内部访问，无公网暴露
- 日志服务有严格的访问控制和审计

**日志保护**:
- 日志文件加密存储
- 定期清理旧日志
- 有日志完整性验证

**监控**:
- 实时检测日志中的敏感数据泄露
- 检测到令牌日志时自动告警和轮换令牌
