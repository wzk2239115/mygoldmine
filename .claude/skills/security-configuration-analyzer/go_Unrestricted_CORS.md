# Go - Unrestricted CORS

## Details

### 代码示例

**场景1：标准库 net/http 设置通配符 CORS**
```go
func handler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Access-Control-Allow-Origin", "*")  // 危险：允许任意源
    w.Header().Set("Access-Control-Allow-Methods", "*")
    w.Header().Set("Access-Control-Allow-Headers", "*")
    w.Header().Set("Access-Control-Allow-Credentials", "true")  // 危险：通配符+凭据
}
```

**场景2：Gin 框架全局 CORS 中间件**
```go
import "github.com/gin-contrib/cors"

router := gin.Default()
config := cors.DefaultConfig()
config.AllowAllOrigins = true  // 危险：允许所有来源
config.AllowCredentials = true // 危险：与 AllowAllOrigins 冲突
router.Use(cors.New(config))
```

**场景3：Echo 框架宽松配置**
```go
e := echo.New()
e.Use(middleware.CORSWithConfig(middleware.CORSConfig{
    AllowOrigins: []string{"*"},  // 危险：通配符
    AllowMethods: []string{http.MethodGet, http.MethodPut, http.MethodPost, http.MethodDelete},
    AllowCredentials: true,
}))
```

**场景4：动态反射 Origin 无校验**
```go
func corsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        origin := r.Header.Get("Origin")
        w.Header().Set("Access-Control-Allow-Origin", origin)  // 危险：直接反射
        w.Header().Set("Access-Control-Allow-Credentials", "true")
        next.ServeHTTP(w, r)
    })
}
```

**场景5：正则匹配过于宽松**
```go
func checkOrigin(origin string) bool {
    matched, _ := regexp.MatchString(`.*\.example\.com`, origin)
    return matched  // 危险：可匹配 malicious.example.com.attacker.com
}

func handler(w http.ResponseWriter, r *http.Request) {
    origin := r.Header.Get("Origin")
    if checkOrigin(origin) {
        w.Header().Set("Access-Control-Allow-Origin", origin)
    }
}
```

**场景6：环境变量控制的宽松配置**
```go
allowedOrigins := os.Getenv("ALLOWED_ORIGINS")  
if allowedOrigins == "" {
    allowedOrigins = "*"  // 危险：默认通配符
}
w.Header().Set("Access-Control-Allow-Origin", allowedOrigins)
```

**场景7：预检请求 OPTIONS 无限制**
```go
if r.Method == "OPTIONS" {
    w.Header().Set("Access-Control-Allow-Origin", "*")
    w.Header().Set("Access-Control-Allow-Methods", "*")
    w.WriteHeader(http.StatusOK)
    return  // 危险：预检全部放行，实际请求可能被绕过
}
```

### 快速定位核心操作的技巧

**（L1：关键词扫描）**
- CORS 头字段：`Access-Control-Allow-Origin`、`Access-Control-Allow-Credentials`、`Access-Control-Allow-Methods`
- 框架配置：`cors.New`、`cors.Default`、`AllowAllOrigins`、`AllowOrigins`、`CORSConfig`
- 中间件名称：`CORS`、`CORSWithConfig`、`CORSMiddleware`
- 通配符模式：`"*"`、`[]string{"*"}`、`AllowAll`

**（L2：跳读）**
- HTTP 路由初始化：`router.Use()`、`e.Use()`、`http.Handle()` 注册的中间件
- 全局配置文件：`config.yaml`、`cors.json` 中的 `allowed_origins` 字段
- Handler 函数头部：`w.Header().Set()` 连续调用 CORS 相关字段
- 预检请求处理：`if r.Method == "OPTIONS"` 分支的响应头设置

**（L3：逐行读）**
- Origin 校验逻辑：检查是否存在白名单匹配、正则锚点（`^` 和 `$`）
- 反射 Origin：`r.Header.Get("Origin")` 直接赋值给响应头的模式
- 凭据标志矛盾：`AllowCredentials: true` 与 `AllowOrigins: ["*"]` 同时存在
- 动态配置加载：`viper.GetStringSlice("cors.origins")` 的默认值和验证逻辑

**（L4：跨模块追踪）**
- 配置中心来源：Consul、etcd 存储的 CORS 配置是否有变更审计
- 依赖注入：框架（Wire、Dig）注入的 CORS 配置来源和优先级
- 多服务网关：检查 API Gateway（Nginx、Traefik）是否已统一处理 CORS
- 微服务传播：服务间调用是否误传了宽松的 CORS 配置

### 快速定位保护机制的技巧

**（L1：关键词扫描）**
- 白名单机制：`allowedOrigins`、`originWhitelist`、`trustedDomains`
- 验证函数：`validateOrigin`、`checkOrigin`、`isAllowedOrigin`
- 安全配置：`AllowOriginFunc`、`AllowOriginValidator`
- 严格模式：`StrictMode`、`SecureOrigins`

**（L2：跳读）**
- 检查 `AllowOrigins` 数组：是否为具体域名列表（非通配符）
- 确认回调函数：`AllowOriginFunc` 是否包含实际验证逻辑
- 查找正则锚点：`^https://.*\.example\.com$` 格式的严格匹配
- 验证环境隔离：开发/生产环境 CORS 配置是否独立管理

**（L3：逐行读）**
- 白名单匹配完整性：`for` 循环遍历 `allowedOrigins` 是否执行 `==` 精确比较
- 子域名校验细节：是否检查 Origin 协议（`https://` vs `http://`）
- Null Origin 处理：`if origin == "null"` 或空值的拒绝逻辑
- 错误处理：校验失败时是否返回 403 或省略 CORS 头

**（L4：跨模块追踪）**
- 配置优先级：多层 CORS 配置（中间件、路由级、全局）最终生效的优先级
- 反向代理影响：检查 Nginx/Caddy 配置是否覆盖应用层 CORS 设置
- 服务网格策略：Istio/Linkerd CORSPolicy 资源与应用配置一致性
- 动态更新机制：CORS 配置热更新是否有审批流程和回滚能力

**（L0：快速跳过）**
- 测试文件：`*_test.go` 中的 Mock Server 响应头
- 示例代码：`examples/`、`docs/` 中演示用配置
- 开发工具：本地调试代理（如 `localhost:3000`）的临时放行

## Classify

### 确认为漏洞的判定标准
- **生产环境**代码中使用 `Access-Control-Allow-Origin: *` 且处理敏感数据（认证凭据、个人信息）
- 同时设置 `AllowCredentials: true` 和 `AllowOrigins: ["*"]`（部分浏览器虽拒绝但仍属配置错误）
- 直接反射请求 Origin 到响应头无任何校验（`w.Header().Set("...", r.Header.Get("Origin"))`）
- 正则校验缺少锚点导致可匹配恶意子域（如 `example.com` 匹配 `example.com.evil.com`）
- 环境变量控制 CORS 且默认值为通配符或可被非管理员修改

### 误报的常见场景
- **单元测试**中的 `httptest.Server` 设置宽松 CORS 头，仅限测试环境
- 纯公开 API（无认证、无敏感数据）故意设置开放 CORS 以供第三方调用
- 内网服务（IP 白名单保护）的宽松配置，外网无法访问
- 示例代码或文档注释中的占位符配置（明确标注 `// Example only`）
- 使用 build tag（`//go:build dev`）隔离到非生产环境的配置

### 代码异味的判定
- 使用环境变量但缺少默认安全配置（应默认拒绝而非通配符）
- CORS 配置逻辑分散在多个 Handler 中无统一管理
- 正则表达式过于复杂难以审计（如嵌套量词 `.*.*`）
- 存在 TODO/FIXME 注释说明"临时放行"但已超过合理期限
- 预检请求和实际请求的 CORS 逻辑不一致

### 研判流程
1. **确认作用域**：该 CORS 配置影响的端点范围（全局/路由组/单个 Handler）
2. **评估敏感度**：API 是否传输认证 Token、Cookie、用户数据
3. **检查网络环境**：服务是否暴露公网、是否有 WAF/API Gateway 前置保护
4. **追溯配置来源**：硬编码/环境变量/配置文件/配置中心，默认值是什么
5. **验证运行环境**：通过部署清单、容器镜像确认实际生效的配置
6. **历史变更分析**：`git log -S "Allow-Origin"` 追溯 CORS 修改记录和原因

## Low Risk

### 低风险场景评级标准

**场景1：完全公开的只读 API**
- 仅提供公开数据查询（天气信息、汇率、公开文档）
- 无需认证，不涉及用户状态或敏感信息
- API 设计本意就是供任意第三方跨域调用
- 有明确的 API 文档标注"公开接口"

**场景2：内网隔离环境**
- 服务仅监听内网 IP（非 `0.0.0.0`），通过 VPN/专线访问
- 存在网络层隔离（安全组/防火墙规则），外网不可达
- 容器编排平台（K8s）的 NetworkPolicy 限制访问源
- 前置 API Gateway 统一处理 CORS，应用层配置不生效

**场景3：无凭据的跨域请求**
- 明确设置 `AllowCredentials: false`（或未设置，默认 false）
- 请求不携带 Cookie、Authorization Header
- 响应数据无用户关联性（静态资源、公共配置）
- 即使被 CSRF 攻击也无法获取敏感信息

**场景4：临时开发调试环境**
- `if os.Getenv("ENV") == "development"` 条件下的宽松配置
- 本地开发容器（Docker Compose）的临时设置
- 配置有自动过期机制（如 24 小时后自动收紧）
- 开发环境使用独立域名（如 `dev.example.com`）且有访问控制

**场景5：前端同域部署**
- 前后端部署在相同域名和端口（如 `/api` 路径区分）
- 无实际跨域请求场景，CORS 配置虽宽松但不生效
- 使用反向代理（Nginx）统一对外暴露单一源
- 浏览器同源策略本身提供保护

**场景6：第三方库测试 Mock**
- 单元测试中的 `httptest.NewServer()` 模拟 CORS 响应
- 集成测试临时启动的测试服务器
- CI/CD 流水线中一次性容器，每次运行后销毁
- 测试代码明确标注 `// Test fixture only`

**评级升级条件（需提升风险等级）**
- 即使内网环境，但处理支付、密钥、PII 等高敏感数据
- 宽松 CORS 配置可通过外部输入触发（如查询参数控制）
- 配置文件或环境变量可被非管理员修改
- 缺少监控告警，无法检测异常跨域请求
- 代码注释表明"临时方案"但已存在超过 6 个月且无改进计划
- 同一代码库同时服务内外网环境且配置未隔离
