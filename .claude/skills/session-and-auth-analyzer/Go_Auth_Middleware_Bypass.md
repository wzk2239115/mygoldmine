# Go_Auth_Middleware_Bypass

**漏洞类型**: Go 认证中间件中权限验证逻辑可被绕过，导致未认证用户可访问受保护资源

---

## Details

### 代码示例

```go
func authMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("Authorization")
        if token == "" {
            token = r.URL.Query().Get("token")  // 允许通过 GET 参数，可被绕过
        }
        // 验证逻辑...
    })
}

// 修复: 明确验证，无备用方式
func authMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("Authorization")
        if token == "" {
            http.Error(w, "Unauthorized", http.StatusUnauthorized)
            return
        }
        // 验证...
    })
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 中间件函数: `authMiddleware()`, `authenticate()`
- 令牌获取: `Header.Get()`, `URL.Query().Get()`
- 多个令牌来源

**L2 跳读定位**:
- 中间件实现
- 令牌验证逻辑

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 单一令牌来源 (header only)
- 验证不可绕过

**L3 逐行分析**:
- 令牌仅来自 Authorization header
- 验证失败返回错误

---

## Classify

确认为漏洞: 多个令牌来源或验证可绕过
误报判定: 单一来源，验证强制
代码异味: 多个令牌检查点

---

## Low risk

- 虽可绕过但有其他验证
- 资源无敏感数据
