# Go 响应头 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `w.Header().Set(key, value)` - http.ResponseWriter
- `w.Header().Add(key, value)` - 添加响应头
- `http.Header.Set()` 直接设置
- 自定义响应头写入

**快速定位核心操作：**
1. 搜索关键字：`Header().Set`、`Header().Add`、`WriteHeader`
2. 追踪头值来源：`r.URL.Query()`、`r.Header.Get()`、`r.FormValue()`
3. 检查是否存在 CRLF 过滤
4. 追踪从请求到响应头的完整链路

**快速定位保护机制：**
- 值检查：`if strings.ContainsAny(value, "
") { panic() }`
- 黑名单：`strings.Replacer` 替换特殊字符
- 白名单验证：正则表达式检查
- 框架防护：Go 1.8+ net/http 某些版本自动检测

**代码示例：**
```go
// 危险：用户输入直接设置为响应头
func handler(w http.ResponseWriter, r *http.Request) {
    value := r.URL.Query().Get("custom")
    w.Header().Set("X-Custom", value)  // 危险：未过滤 CRLF
    w.WriteHeader(http.StatusOK)
}

// 危险：form 数据直接拼接
func submitForm(w http.ResponseWriter, r *http.Request) {
    name := r.FormValue("name")
    w.Header().Add("X-Name", name)  // 危险
    fmt.Fprint(w, "OK")
}

// 危险：请求头转发
func proxy(w http.ResponseWriter, r *http.Request) {
    customHeader := r.Header.Get("X-Custom")
    w.Header().Set("X-Forwarded", customHeader)  // 危险
}
```

## Classify

**漏洞（Critical）：**
- 用户输入直接用于响应头
- 无 CRLF 过滤
- 允许响应分割

**误报：**
- 响应头值硬编码
- Go 框架已自动过滤
- 官方库处理

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接拼接

## Low risk

**以下情况评为低风险：**
- 响应头值硬编码
- 严格 CRLF 过滤
- 白名单验证
- 内部系统来源且已验证

## 审计专业技巧

### 追踪数据流的关键点

1. **识别信息来源**
   - `r.URL.Query().Get("param")` - URL 参数（高危）
   - `r.FormValue("field")` - 表单数据（高危）
   - `r.Header.Get("header")` - 请求头（高危）
   - `r.Cookie()` - Cookie（高危）
   - `r.Body` 读取 - 请求体（高危）
   - 配置文件、环境变量 - 低风险
   - 硬编码字符串 - 无风险

2. **检查过滤位置**
   - 在 `Set()` 调用前 vs 调用后：**必须在调用前过滤**
   - 过滤只在代码片段中 vs 统一在中间件：**中间件防护更可靠**
   - 是否存在绕过路径：检查其他代码分支

3. **验证过滤的完整性**
   ```go
   // 危险：仅替换 \r\n，仍可用 \n 或 \r
   strings.Replace(value, "\r\n", "", -1)

   // 较安全：同时替换 CR、LF、CRLF
   value = strings.ReplaceAll(value, "\r", "")
   value = strings.ReplaceAll(value, "\n", "")

   // 最安全：白名单验证
   if !regexp.MustCompile(`^[a-zA-Z0-9_-]+$`).MatchString(value) {
       return errors.New("invalid")
   }
   ```

### 真实漏洞 vs 误报的区分

**真实漏洞的特征：**
- 用户输入直接进入 `Set()` 或 `Add()`，无验证
- 多个代码分支可能绕过检查
- 框架版本较旧（Go < 1.8），缺乏内置保护
- 响应头 key 也来自用户输入（二阶漏洞可能）
- 链接到 CRLF，实际可执行响应分割或 HTTP 头注入

**常见的误报情况：**
- `w.Header().Set("Content-Type", "application/json")` - 完全硬编码
- `w.Header().Set("X-Custom", sanitizeHeader(value))` - 有专门的清理函数
- `w.Header().Set("Location", url.URL.String())` - 已使用标准库处理
- 在全局中间件中统一过滤，所有 `Set()` 调用都被保护
- 框架本身（如 Gin、Echo）已在 `SetHeader()` 层防护
- 值从数据库读取但 DB 是内部可信源

**灰色地带的判断：**
- 响应头值来自用户，但只允许特定格式（需检查格式验证的严格性）
- 在生产代码中有注释 `// TODO: sanitize` - 标记为中危
- 多层框架的防护不清楚 - 需要追踪到最底层验证

### 测试 CRLF 注入的方法

1. **基础注入测试**
   ```
   ?custom=test%0d%0aSet-Cookie:%20admin=true
   ?custom=test\r\nContent-Length:%200
   ```

2. **检查 Go 版本自动防护**
   ```go
   // Go 1.8+ net/http 会自动拒绝响应头中的 CRLF
   // 但自定义中间件或框架可能绕过
   // 需要实际测试确认
   ```

3. **漏洞确认的流程**
   - 输入：`name=test\r\nX-Injected:%20value`
   - 预期响应：包含注入的新响应头
   - 实际现象：Go 标准库版本会拒绝，返回 400 或忽略注入部分

### 审计时的常见陷阱

1. **假设框架完全防护** - 需要逐行检查，框架升级可能改变行为
2. **只看本文件** - 全局中间件、初始化代码可能在其他文件
3. **忽视间接赋值** - `var header = userInput; w.Header().Set("X-Custom", header)`
4. **没有考虑合并请求** - 拉取请求中改动了防护代码
5. **版本依赖不清** - Go 版本、框架版本影响防护能力

### 实战审计清单

- [ ] 确认输入来源（URL、Form、Header、Body）
- [ ] 追踪数据流到 `Header().Set/Add()` 的调用
- [ ] 验证是否存在 CRLF/LF/CR 的过滤
- [ ] 检查过滤是在 `Set()` 前还是后
- [ ] 确认过滤函数的完整性（白名单 > 黑名单）
- [ ] 查看是否有多条代码路径可能绕过过滤
- [ ] 检查框架自身的保护（版本号）
- [ ] 测试注入向量的实际可行性
- [ ] 记录风险等级及依赖的假设条件
