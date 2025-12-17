# Go Set-Cookie 值 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `http.SetCookie(w, cookie)` - 标准设置 Cookie
- `cookie := &http.Cookie{...}` 构造
- `w.Header().Set("Set-Cookie", value)` 直接设置
- Cookie 值包含用户输入

**快速定位核心操作：**
1. 搜索关键字：`SetCookie`、`&http.Cookie`、`Set-Cookie`
2. 追踪 Cookie 值来源：`Query().Get()`、`FormValue()`、会话数据
3. 检查是否存在 CRLF 过滤
4. 追踪 Cookie 构造全过程

**快速定位保护机制：**
- 值检查：`if strings.ContainsAny(value, "
")`
- 替换：`strings.ReplaceAll(value, "
", "")`
- 白名单验证：`regexp.MatchString()` 检查
- URL 编码：`url.QueryEscape()`

**代码示例：**
```go
// 危险：用户输入直接作为 Cookie 值
func setCookie(w http.ResponseWriter, r *http.Request) {
    token := r.URL.Query().Get("token")
    cookie := &http.Cookie{
        Name:  "session",
        Value: token,  // 危险：未验证
    }
    http.SetCookie(w, cookie)
}

// 危险：Form 数据设置 Cookie
func setAuthCookie(w http.ResponseWriter, r *http.Request) {
    auth := r.FormValue("auth")
    cookie := &http.Cookie{
        Name:  "auth",
        Value: auth,  // 危险
        Path:  "/",
    }
    http.SetCookie(w, cookie)
}

// 危险：直接拼接
func setCookieHeader(w http.ResponseWriter, r *http.Request) {
    val := r.Header.Get("X-Token")
    w.Header().Set("Set-Cookie", "token=" + val)  // 危险
}
```

## Classify

**漏洞（Critical）：**
- 用户输入直接用于 Cookie 值
- 无 CRLF 过滤
- 导致响应分割

**误报：**
- Cookie 值硬编码
- 系统生成的 Token
- 框架管理的 Cookie

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接拼接

## Low risk

**以下情况评为低风险：**
- Cookie 值硬编码
- 严格 CRLF 过滤
- 白名单验证
- 内部来源且已验证
