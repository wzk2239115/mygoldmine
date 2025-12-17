# Go CSP 不安全配置审计指南

## Details

### 核心问题示例

```go
// 典型场景1：HTTP处理器中的不安全CSP配置
func unsafeCSPHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Security-Policy", "script-src 'unsafe-inline'")
    w.WriteHeader(http.StatusOK)
    fmt.Fprint(w, `<script>alert('xss')</script>`)
}

// 典型场景2：通配符白名单
func wildcardCSPHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Security-Policy", "script-src *")
    w.WriteHeader(http.StatusOK)
}

// 典型场景3：中间件全局配置
func cspMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Security-Policy", "default-src 'unsafe-inline'; script-src 'unsafe-eval' *")
        next.ServeHTTP(w, r)
    })
}

// 典型场景4：模板渲染的不安全内容注入
func templateHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Security-Policy", "script-src 'unsafe-inline'")
    userInput := r.URL.Query().Get("content")
    tmpl := template.New("page")
    tmpl.Parse(`<div>` + userInput + `</div>`) // 直接拼接用户输入
    tmpl.Execute(w, nil)
}

// 典型场景5：Gin框架中的不安全CSP
func setupGinRouter() *gin.Engine {
    router := gin.Default()
    router.Use(func(c *gin.Context) {
        c.Header("Content-Security-Policy", "script-src * 'unsafe-inline'; style-src *")
        c.Next()
    })
    return router
}

// 典型场景6：条件性的不安全配置（开发环境泄露至生产）
func cspByEnv(w http.ResponseWriter, r *http.Request) {
    policy := "script-src 'self'"
    if os.Getenv("ENV") != "production" {
        policy = "script-src 'unsafe-inline' 'unsafe-eval' *"
    }
    w.Header().Set("Content-Security-Policy", policy)
}
```

### 快速定位核心操作 **【L1: 关键词扫描】**

审计时通过以下关键词扫描定位CSP头配置位置：
- **w.Header().Set("Content-Security-Policy"** - 直接设置响应头的核心操作
- **Header.Add("Content-Security-Policy"** - 追加CSP指令的方式
- **"script-src 'unsafe-inline'"** - 最常见的不安全配置
- **"script-src 'unsafe-eval'"** - 允许动态代码执行
- **"script-src \*"** 或 **"default-src \*"** - 通配符白名单
- **"style-src 'unsafe-inline'"** - CSS不安全内联
- **CSPMiddleware** / **cspMiddleware** / **SecurityHeaders** - 中间件相关函数
- **template.Parse** / **template.Execute** - 模板渲染时结合CSP配置
- **os.Getenv("ENV")** / **os.Getenv("ENVIRONMENT")** - 环境相关条件判断（检查配置是否因环境不同导致安全性降低）

### 快速定位保护机制 **【L2: 跳读】**

检查CSP策略配置位置和时机：
```go
// 扫描Go代码中的以下关键位置
w.Header().Set() / w.Header().Add()        // HTTP响应头设置点
func(w http.ResponseWriter, r *http.Request) // 所有HTTP处理函数签名
http.HandlerFunc / Handler interface      // 处理链中的拦截点
middleware / use()                         // 中间件链注册
init() / setupRouter()                     // 应用启动初始化

// 高风险CSP指令特征
script-src 'unsafe-inline'                 // 允许内联脚本
script-src 'unsafe-eval'                   // 允许eval/Function
script-src *                               // 允许任意脚本源
default-src 'unsafe-inline'                // 默认指令包含unsafe-inline
default-src 'unsafe-eval'                  // 默认指令包含unsafe-eval
default-src *                              // 默认允许任意源
```

关键文件位置检查 **【L3: 逐行读】**：
- **服务器入口** - main.go, server.go中的路由定义和中间件注册
- **HTTP处理器** - handler.go, controller.go中每个处理函数的响应头设置
- **中间件层** - middleware/, middlewares/文件夹中的全局CSP中间件
- **配置文件** - config.go, config.yml, .env中的策略字符串定义
- **路由配置** - router.go, routes/文件夹中按路由设置的不同CSP策略
- **框架初始化** - gin.go, echo.go, fiber.go等框架相关初始化文件

跨模块追踪 **【L4: 跨模块追踪】**：
- 追踪CSP策略字符串的来源：从环境变量、配置文件、常量定义到实际使用位置
- 检查处理函数中是否存在用户输入与模板渲染的结合（如unsafe-inline + 模板注入）
- 验证中间件链中是否存在覆盖行为（后置中间件是否覆盖了安全的CSP设置）
- 追踪错误处理路由是否也应用了相同CSP策略

## Classify

### 研判标准

**确定为漏洞的条件（同时满足）：**
1. HTTP响应头中设置了`Content-Security-Policy`指令
2. 指令包含以下任一不安全配置：
   - `'unsafe-inline'`（允许内联脚本和样式）
   - `'unsafe-eval'`（允许动态代码执行）
   - 通配符源如`*`或无限制的协议如`data:`
3. 存在用户可控的内容注入渠道（URL参数、POST body、Cookie、外部API响应等）
4. 该处理函数返回包含HTML/JavaScript的动态内容

**升级为高危的额外条件：**
- CSP指令同时包含多个不安全值（如`'unsafe-inline' 'unsafe-eval'`）
- 存在明确的模板注入或动态脚本加载（template.Parse拼接用户输入）
- 中间件级别的全局不安全CSP配置覆盖所有路由
- 配置与敏感业务关联（认证、支付、个人信息处理等）

### 研判为误报的条件：

1. **仅用于错误页面或静态响应**
   - unsafe-inline仅用于显示错误消息提示（内容完全由系统生成，无用户输入）
   - 该路由明确声明为内部管理后台（通过路由前缀/admin验证）

2. **受限的框架安全保证**
   - Go的`text/template`包进行了HTML转义（使用`{{.}}`语法，非`{{.Safe}}`）
   - `html/template`自动对所有输出进行转义
   - 虽有unsafe-inline但实际渲染内容经过严格的模板转义

3. **特殊场景的业务必要性**
   - 特定功能需要内联脚本（如富文本编辑器的实时预览、可视化图表库）
   - 已通过其他安全机制补偿（如严格的输入校验、CSP nonce/hash、subresource integrity等）

### 代码异味的研判：

1. **开发配置泄露** - 存在条件判断读取`ENV`、`DEBUG`等标志，开发环境使用unsafe配置但未确认生产是否修复
2. **硬编码的宽松策略** - CSP策略为`script-src *`或`default-src *`的注释中无明确业务说明
3. **配置不一致** - 同一应用的不同处理函数设置了不同的CSP策略，或中间件和处理函数冲突

## Low risk

### 允许低风险评级的场景

1. **完全系统生成的静态内容**
   - 响应内容完全来自应用内部硬编码（如错误页面、帮助页面）
   - 不存在任何用户输入通道进入模板渲染
   - 使用`text/template`或`html/template`的自动转义机制

2. **严格的输入校验与沙箱执行**
   - 若使用unsafe-inline用于代码高亮等需求，输入已通过正则表达式或白名单校验
   - 使用Go的`restricted` template功能或沙箱库（如goja）限制执行能力
   - 可验证的源代码中无动态脚本注入的数据流

3. **特定功能的最小权限CSP**
   - 仅在特定路由（如API、AJAX端点）上应用unsafe配置，其他路由保持严格策略
   - unsafe-inline/unsafe-eval与其他指令配合限制范围（如`script-src 'unsafe-inline' 'self'`而非`*`）
   - 配置变更记录完整，明确说明业务必要性和风险评估

4. **多层防护确保安全性**
   - 虽有unsafe-inline但采用以下补偿：
     - 所有动态内容经过HTML转义（使用html/template的自动转义）
     - 实施CSP nonce或hash机制限制脚本加载
     - 配合X-Content-Type-Options: nosniff、X-XSS-Protection等防护头
     - 使用HTTPOnly Cookie，防止JavaScript访问敏感令牌
   - 安全边界由多个防护层共同维护，即使单一防护失效也不致命
