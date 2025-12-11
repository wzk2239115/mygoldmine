---
name: unauth-route-scanner
description: 未授权路由扫描技能：从路由扫描结果中提取无需认证即可访问的API端点，为后续安全分析提供攻击面清单。
---

## 概述与边界

- **聚焦**：提取项目中无需认证即可访问的API端点，生成未授权访问路由清单
- **输入依赖**：`web-auth-analyzer` 产物（认证机制分析和角色体系分析）
- **不做**：漏洞利用、深度安全分析（由下游技能完成）

### 核心约束：全面接口发现

**重要：必须尽可能找到所有满足条件的接口，不允许遗漏任何潜在攻击面。**

**关键要求：必须执行三层认证验证**
- 不能仅依赖路径特征判断（如 `/internal/` 等内部路径）
- 必须验证三层认证：**L1 路由注册层**、**L2 Handler实现层**、**L3 业务逻辑层**
- 特别关注条件注册路由和同类路由认证不一致的情况
- 避免遗漏"看起来像内部路由但实际上无认证"的接口

扫描范围必须覆盖：

| 接口类型 | 说明 | 常见特征 |
|---------|------|----------|
| **公开接口** | 对外暴露的 API | `/api/*`, `/v1/*`, `/public/*` |
| **未公开接口** | 未在文档中声明但存在的接口 | 注释掉的路由、测试接口、遗留代码 |
| **内部接口** | 仅供内部服务调用或内部网络访问 | `/internal/*`, `X-Internal-*` 头校验 |
| **外部接口** | 第三方集成回调 | `/webhook/*`, `/callback/*`, `/notify/*` |
| **调试接口** | 开发调试用途 | `/debug/*`, `/test/*`, `/_/*` |
| **管理接口** | 运维管理端点 | `/actuator/*`, `/metrics`, `/admin/*` |
| **特殊配置激活接口** | 需特定配置/环境变量启用 | `if (DEBUG)`, `@ConditionalOnProperty` |

**特殊配置激活接口识别方法**：

```python
# 条件启用的路由
if os.getenv('ENABLE_DEBUG'):
    @app.route('/debug/info')
    def debug_info(): ...

if settings.DEBUG:
    router.add_route('/test/reset', reset_handler)
```

```java
// Spring 条件注解
@ConditionalOnProperty(name = "app.debug.enabled")
@GetMapping("/debug/dump")
public String dump() { ... }

@Profile("dev")
@RestController
public class DevController { ... }
```

```javascript
// 环境变量控制
if (process.env.NODE_ENV === 'development') {
    app.get('/dev/seed', seedHandler);
}
```

**隐藏接口发现策略**：
1. 搜索被注释的路由定义
2. 检查条件编译/条件加载的代码块
3. 分析配置文件中的 feature flag
4. 检查测试文件中引用的未公开接口
5. 搜索 `TODO`/`FIXME`/`HACK` 注释附近的路由

## 工具使用

### quick-scan.py 使用说明

`quick-scan.py` 是一个基于 tree-sitter 的路由扫描工具，用于从项目中提取所有路由注册信息。

#### 快速扫描方法

运行 `quick-scan.py` 脚本进行快速路由扫描，自动识别和提取项目中的路由注册信息。
```bash
# 扫描指定目录（输出到标准输出）
python3 ./quick-scan.py /path/to/project

# 输出到文件
python3 ./quick-scan.py /path/to/project --output routes.md
```

**脚本覆盖范围**：
- ✅ **路由识别**：自动识别主流框架的路由注册模式（Express、Flask、Spring、Gin 等）
- ✅ **路由提取**：提取 HTTP 方法、路径、Handler 函数名、文件位置等信息
- ✅ **多语言支持**：支持 Go、JavaScript/TypeScript、Python、Java、PHP、Ruby 等
- ❌ **认证检查**：脚本仅提取路由信息，不进行认证分析（需结合上游产物手动分析）
- ❌ **风险分级**：风险分级需要结合路由功能和认证状态进行手动判定

**提示词规则覆盖**：
- 以下章节中的路由识别模式（2.2-2.10）已由脚本自动实现，以下内容为参考说明
- 三层认证验证（3.1-3.2）需要结合脚本提取的路由信息和上游产物进行手动分析
- 未授权路由识别标准（4.1-4.6）需要结合脚本结果和上游产物进行手动判定

## 执行流程

### 1. 读取上游产物

**必需输入**：
- 认证分析结果：`.workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md`

从上游产物中获取：
- 认证机制是否可绕过
- 路由分类概览
- 无需认证的路由列表

### 2. 路由识别方法（主流语言/框架）

> **脚本覆盖说明**：`quick-scan.py` 脚本已自动实现以下路由识别功能，使用 tree-sitter AST 分析准确提取路由信息。以下内容为参考说明，帮助理解脚本的工作原理。

#### 2.1 通用思路

- **查找路由声明位置**：路由表文件、装饰器/注解、注册函数（router、app、server）、中间件挂载点
- **识别前缀与分组**：`group/prefix/subrouter`、`namespace`、`Area`、`MapControllerRoute` 等
- **识别动态参数**：`:param`、`{param}`、`<type:param>`、正则/通配符（`*`, `**`），以及方法限定（GET/POST/...）
- **关联中间件/过滤器**：auth/role/guard/interceptor，标记优先级与认证需求

> **脚本实现**：脚本使用 tree-sitter 查询自动识别上述模式，无需手动正则匹配。

#### 2.2 Node.js / TypeScript（Express/Koa/Fastify/Nest）

> **脚本覆盖**：✅ 已由 `quick-scan.py` 自动实现，使用 tree-sitter 查询识别 Express、Koa、Fastify、NestJS 路由模式。

**路由特征**：
- Express：`app.METHOD(path, ...)`、`router.METHOD(path, ...)`、`router.use(prefix, ...)`；文件：`routes/*.js/ts`、`app.js`、`server.js`
- Koa-Router：`router.get/post/...`、`router.use(prefix, nestedRouter.routes())`
- Fastify：`fastify.route({ method, url, ... })`、`fastify.register(plugin, { prefix })`
- NestJS：`@Controller(prefix)` + `@Get/@Post/@Patch/@Delete`；`setGlobalPrefix`

**匹配正则**：
```regex
\w+\s*\.\s*(get|post|put|patch|delete|options|head|all|use)\s*\(\s*['"`]
(express\.Router|Router)\s*\(\s*\)
\w+\s*\.\s*(route|register)\s*\(\s*\{
@(Controller|Get|Post|Put|Patch|Delete|Options|Head|All)\s*\(\s*['"`]?
```

> 注：字符类中单引号、双引号、反引号的正确写法是 `['"`]`，反引号无需转义。

#### 2.3 Python（Flask/FastAPI/Django）

**路由特征**：
- Flask：`@app.route` / `@blueprint.route`，`url_prefix`；`methods=["GET","POST"]`
- FastAPI：`APIRouter(prefix=...)` + `@router.get/post/...`；`app.include_router(router, prefix=...)`
- Django：`urlpatterns = [ path(...), re_path(...), include(...) ]`；DRF `DefaultRouter`/`SimpleRouter`

**匹配正则**：
```regex
@\w+\s*\.\s*(route|get|post|put|patch|delete)\s*\(\s*['"]
APIRouter\s*\(\s*(prefix\s*=\s*['"])?
(path|re_path|url)\s*\(\s*['"]
include\s*\(\s*['"]
```

#### 2.4 Java（Spring MVC / Spring Boot）

> **脚本覆盖**：✅ 已由 `quick-scan.py` 自动实现，使用 tree-sitter 查询识别 Spring Boot 路由注解。

**路由特征**：
- 类级 `@RequestMapping("/api")` + 方法级 `@GetMapping("/x")` 等组合
- 路径变量 `/{id}`、通配符 `/**`
- 常见端点：Actuator `/actuator/**`，Swagger `/v2/api-docs`、`/swagger-ui`

**匹配正则**（脚本已实现，以下为参考）：
```regex
@(RequestMapping|RestController|Controller)\s*(\(\s*(['"]|value\s*=\s*['"]))?
@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)\s*\(\s*(['"]|value\s*=\s*['"]|path\s*=\s*['"])?
```

#### 2.5 Go（Gin/Echo/Chi/Fiber/Mux/net/http）

> **脚本覆盖**：✅ 已由 `quick-scan.py` 自动实现，使用 tree-sitter 查询识别 Go 主流框架路由模式（gorilla/mux、Gin、Echo、Chi、net/http 等）。

**路由特征**：
- **Gin**：`r.GET/POST`，`r.Group("/api")`；中间件 `Use`
- **Echo**：`e.GET/POST`，`e.Group("/api")`；路由模板 `/:id/*`
- **Chi**：`r.Route("/api", func(r chi.Router){ r.Get(...) })`，`Mount`
- **Fiber**：`app.Get/Post`，`app.Group("/api")`
- **net/http 标准库**：`http.HandleFunc("/path", handler)`，`mux := http.NewServeMux()`，`mux.Handle(...)`
- **gorilla/mux**：`r.HandleFunc("/path", handler)`，`r.Methods("GET", "POST")`，`r.PathPrefix("/api")`
- **httprouter**：`router.GET/POST("/path", handler)`
- **Beego**：`beego.Router`，`@router` 注释路由
- **Iris**：`app.Get/Post`，`Party` 分组

**匹配正则**：
```regex
# Gin/Echo
\w+\s*\.\s*(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Any|Handle|Group|Add|Match)\s*\(\s*["']

# Chi/Fiber
\w+\s*\.\s*(Get|Post|Put|Patch|Delete|Options|Head|Route|Mount|Connect|Trace|With|All|Use)\s*\(\s*["']

# net/http 标准库
http\s*\.\s*(HandleFunc|Handle)\s*\(\s*["']
\w+\s*\.\s*(HandleFunc|Handle)\s*\(\s*["'].*,\s*http\.HandlerFunc

# gorilla/mux
\w+\s*\.\s*(HandleFunc|Handle)\s*\(\s*["']
\w+\s*\.\s*Methods\s*\(\s*http\.Method
\w+\s*\.\s*Path\s*\(\s*["']
\w+\s*\.\s*PathPrefix\s*\(\s*["']
mux\.(NewRouter|Router)

# httprouter
\w+\s*\.\s*(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Handler|ServeFiles)\s*\(\s*["']

# Beego
beego\.(Router|NSRouter|NSNamespace|Include|Get|Post|Put|Patch|Delete)
@router\s+

# Iris
\w+\s*\.\s*(Party|PartyFunc)\s*\(\s*["']
```

#### 2.6 PHP（Laravel / Symfony）

> **脚本覆盖**：✅ 已由 `quick-scan.py` 自动实现，使用 tree-sitter 查询识别 Laravel、Symfony 路由模式。

**路由特征**：
- Laravel：`routes/web.php`、`routes/api.php`；`Route::get/post/put/delete`，`Route::group`，`Route::resource/apiResource`
- Symfony：`config/routes/*.yaml` / 注解 / 属性路由

**匹配正则**（脚本已实现，以下为参考）：
```regex
Route\s*::\s*(get|post|put|patch|delete|options|any|match|resource|apiResource|group)\s*\(\s*['"]
Route\s*::\s*(prefix|middleware|namespace|group)\s*\(
#\[(Route|Get|Post|Put|Patch|Delete)\s*\(\s*['"]
@(Route|Get|Post|Put|Patch|Delete)\s*\(\s*['"]
```

#### 2.7 Ruby on Rails

> **脚本覆盖**：✅ 已由 `quick-scan.py` 自动实现，使用 tree-sitter 查询识别 Rails 路由模式。

**路由特征**：
- `config/routes.rb`：`resources :users`、`namespace :admin`、`scope path: "/api"`、`match`/`get/post`

**匹配正则**（脚本已实现，以下为参考）：
```regex
(get|post|put|patch|delete|match|root)\s+['"]
(resources?|namespace|scope|constraints)\s+[:'"]
```

#### 2.8 .NET（ASP.NET Core）

> **脚本覆盖**：✅ 已由 `quick-scan.py` 自动实现，使用 tree-sitter 查询识别 ASP.NET Core 路由模式。

**路由特征**：
- Minimal APIs：`app.MapGet/MapPost/...`；`MapGroup("/api")`
- MVC/Controllers：`[Route("api/[controller]")]` + `[HttpGet("x")]`

**匹配正则**（脚本已实现，以下为参考）：
```regex
\w+\s*\.\s*(MapGet|MapPost|MapPut|MapPatch|MapDelete|MapMethods|MapGroup)\s*\(\s*["']
\[(Route|HttpGet|HttpPost|HttpPut|HttpPatch|HttpDelete)\s*\(\s*["']?
```

#### 2.9 JavaScript 前后端一体框架（Next.js / Nuxt）

> **脚本覆盖**：⚠️ 部分支持。脚本可通过文件路径识别 Next.js/Nuxt API Routes，但动态路由参数解析需要手动分析。

**路由特征**：
- Next.js API Routes：`pages/api/*` 或 `app/api/*/route.{js,ts}`；动态 `[id]`，catch-all `[...slug]`
- Nuxt 3 Nitro：`server/api/**/*.ts`

**匹配方式**：基于文件路径匹配（脚本已实现）
```
pages/api/**/*.{js,ts}
app/api/**/route.{js,ts}
server/api/**/*.ts
```

#### 2.10 通用匹配（兜底）

> **脚本覆盖**：⚠️ 部分支持。脚本优先使用框架特定的 tree-sitter 查询，对于未识别的框架会尝试通用模式匹配。

当框架特定正则无法匹配时，使用宽松匹配（脚本已实现，以下为参考）：
```regex
\b(route|router|endpoint|api|controller)\b.*\b(get|post|put|patch|delete)\b
['"`]\/[a-zA-Z0-9_\-\/\{\}\:\*\[\]]+['"`]
```

> **注意**：通用匹配可能产生误报，需结合上下文确认。脚本会自动过滤测试文件以减少误报。

### 3. 三层认证验证流程

> ⚠️ **关键改进**：为避免遗漏"看起来像内部路由但实际上无认证"的接口，必须执行三层认证验证。

现代 Web 框架通常采用多层认证架构，仅检查路由注册层认证不足以保证安全：

**认证层次模型（三层）**：
1. **L1 - 路由注册层**：路由注册时显式声明的认证中间件（如 Express middleware、Spring Interceptor、Go middleware）
2. **L2 - Handler 实现层**：在 handler 函数内部（前 15-20 行）执行的认证检查代码
3. **L3 - 业务逻辑层**：数据访问前的细粒度权限检查（IAM、RBAC、ACL 等）

> **注意**：L3 业务逻辑层的检查属于深度安全分析范围，由下游技能 `route-deep-analyzer` 负责。本技能聚焦 L1 和 L2 层的认证验证。

#### 3.1 三层认证验证步骤

对**每个路由**执行以下检查：

**L1：路由注册层检查**

检查路由注册时是否显式声明了认证中间件：

```go
// Go - Gin/Echo/Chi 等框架
router.GET("/api/data", authMiddleware, handler)     // ✓ 有认证
router.POST("/internal/info", handler)               // ✗ 无认证，需检查 L2

// Go - 标准库 net/http + mux
r.Handle("/api/users", authMiddleware(http.HandlerFunc(handler)))  // ✓ 有认证
r.HandleFunc("/internal/config", handler)                         // ✗ 无认证，需检查 L2
```

```python
# Python Flask
@app.route('/api/data')
@login_required  # ✓ 有认证
def get_data(): ...

@app.route('/internal/info')  # ✗ 无认证，需检查 L2
def get_info(): ...
```

```javascript
// Node.js Express
router.get('/api/data', authMiddleware, handler);  // ✓ 有认证
router.post('/internal/info', handler);            // ✗ 无认证，需检查 L2
```

**L2：Handler 实现层检查**

读取 handler 函数的**前 15-20 行代码**，检查是否包含认证逻辑：

| 语言 | 认证检查模式示例 | 正则匹配模式 |
|------|----------------|-------------|
| Go | `if !s.IsValid(w, r)` | `if\s*!\s*\w+\.(IsValid\|IsAuth\|CheckAuth\|Authenticate)` |
| Go | `if err := authenticate(r); err != nil` | `if\s+(err\s*:=\s*)?\w*[Aa]uth\w*\([^)]*\)\s*(;)?\s*(err\s*!=\s*nil)?` |
| Go | `cred, ok := getCredential(r)` | `\w+,\s*\w+\s*:=\s*get(Credential\|Auth\|Token)` |
| Python | `if not is_authenticated(request)` | `if\s+not\s+\w*auth\w*\(` |
| Python | `@login_required` 装饰器 | `@\w*(login\|auth)\w*required` |
| Java | `if (!isAuthorized(request))` | `if\s*\(\s*!\s*\w*[Aa]uth\w*\(` |
| Node.js | `if (!req.user) return res.status(401)` | `if\s*\(\s*!\s*req\.(user\|auth\|session)` |
| PHP | `if (!Auth::check())` | `if\s*\(\s*!\s*Auth::(check\|user\|guest)` |

**L3：业务逻辑层检查**

> 本技能**不执行** L3 层检查，该层由下游技能 `route-deep-analyzer` 负责深度分析。

L3 层检查包括：
- 数据库查询前的资源所有权验证
- IAM/RBAC/ACL 策略检查
- 细粒度字段级权限控制

#### 3.2 高风险模式识别

**模式 1：内部路径 + L1/L2 双无认证**
- **路径特征**：`/internal/*`, `/_internal/*`, `/admin/*`, `/debug/*`, `/config/*`
- **风险**：路径暗示内部使用，开发者可能假设受全局保护而未添加认证
- **判定条件**：L1 = ✗ **且** L2 = ✗
- **行动**：标记为**高危**，优先报告

**模式 2：条件注册路由**
- **特征**：路由注册代码位于条件语句内部
- **示例**：
  ```go
  if globalIsDistErasure {  // 仅在分布式模式下注册
      router.Methods(http.MethodPost).Path("/internal/config/verify").HandlerFunc(handler)
  }
  ```
- **风险**：特定环境下才暴露，测试覆盖可能不全
- **行动**：标记所有条件注册路由，记录触发条件

**模式 3：同路径组认证不一致**
- **场景**：同一前缀下的路由，部分有认证，部分无认证
- **示例**：
  ```
  /admin/users     → L1=✓, L2=✓  (安全)
  /admin/roles     → L1=✓, L2=✓  (安全)
  /admin/config    → L1=✗, L2=✗  (高危！)
  ```
- **风险**：开发遗漏或误解认证继承
- **行动**：对比同前缀路由，标记异常项

**模式 4：公开路径但有敏感操作**
- **路径特征**：`/api/public/*`, `/webhook/*`，但 handler 执行写操作或读取敏感数据
- **判定依据**：结合上游 `web-auth-analyzer` 的路由功能分析
- **行动**：标记为"疑似误设计为公开"，需人工确认

---

### 4. 未授权路由识别标准

> **脚本覆盖说明**：❌ 未授权路由识别和风险分级**未**由脚本实现，需要结合以下内容进行手动分析：
> - 脚本提取的路由信息（方法、路径、Handler 等）
> - 上游 `web-auth-analyzer.md` 产物的认证分析结果
> - 三层认证验证结果（3.1 节）
> - 路由功能分析（Handler 执行的操作类型）

> **重要**：以下识别标准必须在执行三层认证验证（3.1）的基础上进行。

#### 4.1 区分"设计为公开" vs "遗漏认证"

**关键问题**：如何判断一个无认证的路由是**故意设计为公开**还是**开发遗漏**？

**判定流程**：

```
路由无 L1/L2 认证
    ↓
匹配常见公开路由模式？
    ↓ 是
    → 标记为"设计公开（低危）"
    ↓ 否
检查路径语义 + handler 功能
    ↓
符合以下任一条件？
  - 路径包含 internal/admin/config/debug
  - Handler 执行写操作（UPDATE/DELETE/INSERT）
  - Handler 读取敏感数据（用户信息、凭证、配置）
  - Handler 执行特权操作（系统管理、权限变更）
    ↓ 是
    → 标记为"疑似遗漏认证（高危/中危）"
    ↓ 否
    → 标记为"需人工确认（中危）"
```

#### 4.2 明确设计为公开的路由（安全）

以下路由类型通常**无需认证**，属于**正常设计**：

| 路由类型 | 示例路径 | 识别特征 | 风险等级 |
|---------|---------|----------|---------|
| 静态资源 | `/public/*`, `/static/*`, `/assets/*`, `/css/*`, `/js/*`, `/images/*` | 路径前缀明确 | 安全 |
| 健康检查 | `/health`, `/healthz`, `/ping`, `/status`, `/readiness`, `/liveness` | 运维监控端点 | 安全 |
| API文档 | `/swagger*`, `/api-docs`, `/openapi*`, `/docs/*` | 文档端点 | 低危* |
| 登录注册 | `/login`, `/register`, `/signup`, `/auth/login` | 认证流程入口 | 安全 |
| 密码重置 | `/forgot-password`, `/reset-password`, `/password/reset` | 密码恢复流程 | 安全 |
| OAuth回调 | `/oauth/callback`, `/auth/callback`, `/saml/acs` | OAuth/SAML 回调 | 安全 |
| Webhook | `/webhook/*`, `/hooks/*`, `/callback/*` | 外部服务回调 | 低危* |
| 验证码 | `/captcha`, `/verify-code`, `/recaptcha` | 人机验证 | 安全 |
| 公开 API | `/api/public/*`, `/open/*`, `/v1/public/*` | 明确标记为 public | 低危* |

> *标记为"低危"的原因：虽然设计为公开，但可能泄露敏感信息（如 API 文档暴露内部接口结构）或被滥用（如 webhook 被伪造）。

#### 4.3 疑似遗漏认证的路由（高危/中危）

根据三层认证验证结果，以下情况判定为**疑似遗漏认证**：

**判定条件**：L1 = ✗ **且** L2 = ✗ **且**满足以下任一特征：

1. **路径语义暗示内部使用**
   - 包含关键词：`internal`, `admin`, `config`, `debug`, `test`, `dev`, `private`, `system`, `manage`

2. **Handler 执行敏感操作**（需结合上游 `web-auth-analyzer` 分析）
   - 数据库写操作（INSERT/UPDATE/DELETE）
   - 文件系统操作（上传、删除、修改）
   - 系统配置修改
   - 用户权限变更

3. **Handler 读取敏感数据**
   - 用户个人信息
   - 系统配置、环境变量
   - 数据库凭证、API密钥
   - 内部业务数据

#### 4.4 代码级认证缺失识别示例

根据 `web-auth-analyzer` 产物中的分析结果，识别以下情况：

**无认证中间件/装饰器的路由**：
```python
# Python Flask - 无 @login_required
@app.route('/api/data')
def get_data():
    return data

# Python FastAPI - 无 Depends(get_current_user)
@router.get('/api/items')
async def list_items():
    return items
```

```javascript
// Express - 无 auth 中间件
app.get('/api/users', (req, res) => {
    res.json(users);
});

// NestJS - 无 @UseGuards(AuthGuard)
@Get('items')
findAll() {
    return this.itemsService.findAll();
}
```

```java
// Spring - 无 @PreAuthorize 或 SecurityConfig 排除
@GetMapping("/api/products")
public List<Product> getProducts() {
    return productService.findAll();
}
```

```go
// Gin - 无 auth 中间件组
r.GET("/api/info", func(c *gin.Context) {
    c.JSON(200, info)
})
```

**认证配置排除的路由**：
```yaml
# Spring Security 配置排除
security:
  ignored:
    - /api/public/**
    - /actuator/health
```

```javascript
// Express 中间件排除
app.use('/api', authMiddleware.unless({
    path: ['/api/login', '/api/register', '/api/public']
}));
```

#### 4.5 上游产物依赖与格式要求

**必需输入**：`.workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md`

**必须包含的信息**：

| 字段 | 说明 | 用途 |
|------|------|------|
| `认证机制可绕过` | 是/否 | 判定是否需要特殊标记所有认证路由 |
| `路由分类概览` | 路由总数、需认证路由数、公开路由数 | 统计基础数据 |
| `无需认证的路由列表` | 路径、方法、文件位置 | 作为初步筛选依据 |
| `认证中间件列表` | 中间件名称、文件位置 | 用于 L1 层认证检查 |
| `路由功能分析`（可选） | Handler 执行的操作类型 | 辅助判定"设计公开 vs 遗漏认证" |

**如何处理上游产物缺失**：
- 如果 `web-auth-analyzer.md` 不存在，**必须报错并终止**，不可独立运行
- 如果产物中缺少部分可选字段，则该部分检查降级为手动确认

#### 4.6 认证可绕过的路由（特殊标记）

当 `web-auth-analyzer` 判定认证机制存在绕过风险时，以下路由需**特殊标记**：

| 绕过类型 | 受影响路由范围 | 标记方式 |
|---------|--------------|---------|
| **JWT 算法混淆** | 所有使用该 JWT 保护的路由 | 标记为"认证可绕过（高危）" |
| **认证逻辑短路** | 存在条件绕过的特定路由 | 单独标记受影响路由 |
| **默认凭证存在** | 管理端点、特权接口 | 标记为"默认凭证风险（高危）" |
| **Token 验证可选** | 允许匿名 fallback 的敏感端点 | 标记为"匿名可访问（中危）" |

### 5. 风险分级

| 风险等级 | 描述 | 路由特征 |
|---------|------|----------|
| **高危** | 敏感数据暴露 | 用户数据、配置信息、内部接口 |
| **中危** | 功能滥用风险 | 批量操作、资源消耗型接口 |
| **低危** | 信息泄露风险 | 版本信息、调试端点、公开数据 |
| **安全** | 设计为公开 | 静态资源、登录注册、健康检查 |

### 6. 输出格式

> **关键要求**：输出报告中必须包含三层认证验证（3.1）的结果，对每个未授权路由明确标识：
> 1. **L1 路由注册层** 和 **L2 Handler实现层** 认证检查状态
> 2. 条件注册信息（如有）
> 3. 同路径组对比结果（如有异常）

#### 6.1 产物文件

输出路径：`.workspace/tasks/{TASK_ID}/unauth-route-scanner.md`

```markdown
# 未授权访问路由清单

## 概述

- **扫描时间**：{timestamp}
- **总路由数**：{total_routes}
- **未授权路由数**：{unauthenticated_count}
- **认证可绕过**：{auth_bypassable: 是/否}

## 风险统计

| 风险等级 | 数量 | 占比 |
|---------|------|------|
| 高危 | {high_count} | {high_percent}% |
| 中危 | {medium_count} | {medium_percent}% |
| 低危 | {low_count} | {low_percent}% |
| 安全 | {safe_count} | {safe_percent}% |

## 高危未授权路由

### 详细示例：/internal/config/verify（三层认证验证缺失）

| 属性 | 值 |
|------|---|
| HTTP 方法 | POST |
| 路径 | /internal/config/verify |
| 路由注册位置 | cmd/config-main.go:146 |
| Handler 定义位置 | cmd/config-main.go:132 |
| **L1 - 路由注册层** | ✗ 无认证中间件 |
| **L2 - Handler实现层** | ✗ 无认证检查代码 |
| **条件注册** | ✓ if globalIsDistErasure（仅分布式模式注册） |
| **同路径组对比** | ✗ 其他 /internal/* 路由都有 `validateAdminReq()` 检查 |
| **敏感操作** | 读取系统配置 + 环境变量 |
| **风险等级** | **高危** |
| **判定依据** | 路径包含 "internal" + L1/L2 双无认证 + 读取敏感配置 |

**认证缺失证据**：

```go
// 路由注册（无中间件）- L1 = ✗
if globalIsDistErasure {
    router.Methods(http.MethodPost).Path("/internal/config/verify").HandlerFunc(
        httpTraceAll(configVerifyHandler))  // ← 仅有 tracing 包装，无认证中间件
}

// Handler 实现（无认证检查）- L2 = ✗
func configVerifyHandler(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    cfg := globalServerConfig.Clone()  // ← 直接获取敏感配置，无认证检查

    writeSuccessResponseJSON(w, cfg)  // ← 直接返回
}
```

**同路径组认证对比**：

| 路径 | L1 | L2 | 状态 |
|------|----|----|------|
| /internal/health | ✗ | ✓ `validateAdminReq()` | 安全 |
| /internal/metrics | ✗ | ✓ `validateAdminReq()` | 安全 |
| /internal/trace | ✗ | ✓ `validateAdminReq()` | 安全 |
| **/internal/config/verify** | **✗** | **✗** | **高危** ⚠️ |

### 其他高危未授权路由

| # | 方法 | 路径 | 文件位置 | 风险说明 | L1 | L2 |
|---|------|------|---------|----------|----|----|
| 1 | GET | /api/admin/users | src/routes/admin.js:30 | 用户列表泄露 | ✗ | ✗ |
| 2 | POST | /debug/pprof/heap | cmd/debug.go:88 | 内存dump泄露 | ✗ | ✗ |

## 中危未授权路由

| # | 方法 | 路径 | 文件位置 | 风险说明 | L1 | L2 |
|---|------|------|---------|----------|----|----|
| 1 | POST | /api/export | src/routes/data.js:88 | 数据导出无限制 | ✗ | ✗ |
| 2 | GET | /api/stats | src/routes/stats.js:15 | 统计信息泄露 | ✗ | ✗ |

## 低危未授权路由

| # | 方法 | 路径 | 文件位置 | 风险说明 | L1 | L2 |
|---|------|------|---------|----------|----|----|
| 1 | GET | /api/version | src/routes/info.js:5 | 版本信息泄露 | ✗ | ✗ |

## 设计为公开的路由（安全）

| # | 方法 | 路径 | 文件位置 | 说明 |
|---|------|------|---------|------|
| 1 | GET | /health | src/app.js:10 | 健康检查端点 |
| 2 | POST | /api/login | src/routes/auth.js:20 | 登录入口 |

## 待深度分析路由清单

> **重要**：以下清单供下游技能 `route-deep-analyzer` 使用，包含所有需要进一步分析的未授权路由。

**说明**：
- 此清单汇总所有高危、中危、低危未授权路由（排除"安全"等级）
- 按风险等级排序：高危 → 中危 → 低危
- 包含路由的完整信息，便于下游技能直接使用
- 下游任务将基于此清单执行深度安全分析

| # | 风险等级 | 方法 | 路径 | 文件位置 | 行号 | L1 | L2 | 风险说明 |
|---|---------|------|------|---------|------|----|-------|----------|
| 1 | 高危 | POST | /internal/config/verify | cmd/config-main.go | 146 | ✗ | ✗ | 读取系统配置 + 环境变量 |
| 2 | 高危 | GET | /api/admin/users | src/routes/admin.js | 30 | ✗ | ✗ | 用户列表泄露 |
| 3 | 高危 | POST | /debug/pprof/heap | cmd/debug.go | 88 | ✗ | ✗ | 内存dump泄露 |
| 4 | 中危 | POST | /api/export | src/routes/data.js | 88 | ✗ | ✗ | 数据导出无限制 |
| 5 | 中危 | GET | /api/stats | src/routes/stats.js | 15 | ✗ | ✗ | 统计信息泄露 |
| 6 | 低危 | GET | /api/version | src/routes/info.js | 5 | ✗ | ✗ | 版本信息泄露 |

**统计信息**：
- 待分析路由总数：{total_routes_for_analysis}
- 高危：{high_count}
- 中危：{medium_count}
- 低危：{low_count}

## 认证绕过相关路由

> 以下路由因认证机制存在绕过风险而被标记

| # | 方法 | 路径 | 文件位置 | 绕过原因 |
|---|------|------|---------|----------|
| 1 | GET | /api/admin/users | src/routes/admin.js:30 | JWT 算法可切换为 none |
```

## 与其他技能的协作

### 上游依赖

| 技能 | 产物 | 用途 |
|------|------|------|
| `web-auth-analyzer` | web-auth-analyzer.md | 获取认证机制和角色体系分析 |

### 下游消费

此技能产物供以下技能使用：

| 技能 | 用途 |
|------|------|
| `route-deep-analyzer` | 对未授权路由进行深度功能分析 |

## 输出要求

### 产物输出

**Markdown 报告**：`.workspace/tasks/{TASK_ID}/unauth-route-scanner.md`

### 下游任务生成

根据未授权路由数量和风险等级，推荐下游分析任务。

**重要说明**：
- 下游技能 `route-deep-analyzer` 应该从产物文件的 **"待深度分析路由清单"** 章节获取需要分析的路由列表
- 该清单包含所有需要进一步分析的未授权路由（高危、中危、低危），排除了"安全"等级的路由
- 清单格式统一，包含路由的完整信息（方法、路径、文件位置、行号、L1/L2认证状态、风险说明）

**输出格式（JSON）**：

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/unauth-route-scanner.md",
      "skill": "route-deep-analyzer",
      "dependencies": [
        ".workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md",
        ".workspace/tasks/{PROFILE_TASK_ID}/project-profile.md"
      ]
    }
  ]
}
```

**字段说明**：
- `artifact`: 本技能产物文件路径
- `skill`: 下游技能名称
- `dependencies`: 下游技能所需的依赖产物

### 重要约束

- **必须读取上游产物**：不可独立运行，需依赖 `web-auth-analyzer.md` 的输出
- **必须执行三层认证验证**：对每个路由执行 L1（路由注册层）和 L2（Handler实现层）认证检查，避免遗漏
- **风险分级必须明确**：每个未授权路由必须标注风险等级和判定依据
- **必须包含认证验证结果**：报告中需包含 L1/L2 认证检查状态、条件注册信息、同路径组对比结果
- **不遗漏高危路由**：即使数量较多，高危路由必须全部列出，不可仅展示部分
- **区分"设计公开" vs "遗漏认证"**：按照 4.1 节的判定流程明确分类
- **特别关注条件注册路由**：条件注册的路由需分析其触发条件和默认状态
- **必须生成待深度分析路由清单**：报告中必须包含统一的"待深度分析路由清单"章节，汇总所有需要下游分析的路由（高危、中危、低危），供下游技能直接使用
- **JSON 输出必须有效**：确保 JSON 格式正确，便于下游程序化处理

## 附录：检查思路参考

> **脚本覆盖说明**：以下检查思路为手动分析方法，脚本**未**实现这些功能。这些思路用于指导如何结合脚本提取的路由信息进行深度分析。

由于不同项目的技术栈和代码结构差异较大，本附录不提供通用脚本，而是提供检查思路供参考。

### 检查思路 1：识别无 Handler 认证检查的路由（L2 层）

**思路**：
1. 提取路由注册代码，获取 handler 函数名
2. 定位 handler 函数定义位置
3. 读取 handler 函数前 15-20 行代码
4. 搜索认证检查关键词（见 3.1 节 L2 层正则模式）
5. 如未找到，标记为 L2 = ✗

**关键词示例**（Go）**：
- `IsValid`, `IsAuth`, `CheckAuth`, `Authenticate`
- `authenticate`, `checkAuth`, `validateToken`, `verify`
- `getCredential`, `getCred`, `parseToken`

### 检查思路 2：对比同路径组认证一致性

**思路**：
1. 按路径前缀分组（如 `/admin/*`, `/internal/*`）
2. 对每组路由执行 L1/L2 检查
3. 统计认证模式分布
4. 标记异常项（少数派）

**示例输出**：
```
/admin 路径组（共 10 个路由）:
  - L1=✗, L2=✓: 9 个（主流模式）
  - L1=✗, L2=✗: 1 个 ⚠️ （异常，需重点关注）
```

### 检查思路 3：枚举条件注册的路由

**思路**：
1. 搜索路由注册代码
2. 检查其上方 3-5 行是否有 `if`/`switch` 语句
3. 提取条件表达式
4. 记录触发条件和路由信息

**Go 示例模式**：
```go
if globalIsDistErasure {
    router.Methods(...).Path(...).HandlerFunc(...)
}
```

**Java 示例模式**：
```java
@ConditionalOnProperty(name = "app.debug.enabled")
@GetMapping("/debug/dump")
```

### 检查思路 4：定位内部路径但无认证的路由（高风险模式 1）

**思路**：
1. 搜索路径包含以下关键词的路由：
   - `internal`, `admin`, `config`, `debug`, `test`, `dev`, `private`, `system`, `manage`
2. 对这些路由执行 L1/L2 检查
3. 如 L1 = ✗ 且 L2 = ✗，标记为高危

**重点关注**：
- `/internal/*` 路径：通常暗示内部使用
- `/admin/*` 路径：通常需要管理员权限
- `/config/*`, `/debug/*`：通常敏感操作
