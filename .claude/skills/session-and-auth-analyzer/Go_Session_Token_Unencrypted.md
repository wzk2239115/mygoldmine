# Go_Session_Token_Unencrypted

**漏洞类型**: Go Gorilla Sessions 中会话令牌未加密传输，存在会话劫持风险

---

## Details

### 代码示例

```go
// 不安全: HTTP 传输
session.Options = &sessions.Options{
    Path:     "/",
    MaxAge:   86400,
    Secure:   false,  // 允许 HTTP
    HttpOnly: true,
}

// 修复
session.Options = &sessions.Options{
    Path:     "/",
    MaxAge:   86400,
    Secure:   true,   // HTTPS only
    HttpOnly: true,
    SameSite: http.SameSiteLaxMode,
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `Secure: false`
- `session.Options`

**L2 跳读定位**:
- 会话配置代码

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- `Secure: true`

**L3 逐行分析**:
- 生产环境必须 HTTPS
- 应用强制 HTTPS 重定向

---

## Classify

确认为漏洞: `Secure: false` 或未设置
误报判定: `Secure: true` 且应用强制 HTTPS

---

## Low risk

- 虽无加密但有其他防护
- HSTS 强制 HTTPS
