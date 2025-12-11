---
name: normal-route-scanner
description: 普通用户路由扫描技能：从项目中提取普通用户（非管理员）可访问的API端点，为后续安全分析提供攻击面清单。
---

## 概述与边界

- **聚焦**：提取项目中普通用户（非管理员）可访问的API端点
- **输入依赖**：`web-auth-analyzer` 产物（认证分析和角色体系分析）
- **不做**：漏洞利用、深度安全分析（由下游技能完成）

### 核心约束：全面接口发现

**重要：必须尽可能找到所有满足条件的接口，不允许遗漏任何潜在攻击面。**

扫描范围必须覆盖：

| 接口类型 | 说明 | 常见特征 |
|---------|------|----------|
| **公开接口** | 对外暴露的用户 API | `/api/user/*`, `/api/profile/*` |
| **未公开接口** | 未在文档中声明但存在的接口 | 注释掉的路由、测试接口、遗留代码 |
| **内部接口** | 仅供内部服务调用 | `/internal/*`, `X-Internal-*` 头校验 |
| **外部接口** | 第三方集成回调 | `/webhook/*`, `/callback/*`, `/notify/*` |
| **调试接口** | 开发调试用途（需认证） | `/debug/*`, `/test/*`, `/_/*` |
| **特殊配置激活接口** | 需特定配置/环境变量启用 | `if (DEBUG)`, `@ConditionalOnProperty` |

**特殊配置激活接口识别方法**：

```python
# 条件启用的路由
if os.getenv('ENABLE_BETA_FEATURES'):
    @app.route('/api/beta/feature')
    @login_required
    def beta_feature(): ...

if settings.FEATURE_FLAGS.get('new_payment'):
    router.add_route('/api/payment/v2', payment_v2_handler)
```

```java
// Spring 条件注解
@ConditionalOnProperty(name = "app.feature.beta")
@PreAuthorize("isAuthenticated()")
@GetMapping("/api/beta/export")
public String betaExport() { ... }

@Profile("!prod")
@RestController
public class TestController { ... }
```

```javascript
// Feature flag 控制
if (config.features.experimentalApi) {
    app.get('/api/experimental/:action', authMiddleware, experimentalHandler);
}
```

**隐藏接口发现策略**：
1. 搜索被注释的路由定义
2. 检查条件编译/条件加载的代码块
3. 分析配置文件中的 feature flag
4. 检查测试文件中引用的未公开接口
5. 搜索 `TODO`/`FIXME`/`HACK` 注释附近的路由
6. 分析 A/B 测试相关的路由配置

## 工具使用

### quick-scan.py 使用说明

`quick-scan.py` 是一个基于 tree-sitter 的路由扫描工具，用于从项目中提取所有路由注册信息。

#### 基本用法

```bash
# 扫描指定目录（输出到标准输出）
python3 ./quick-scan.py /path/to/project
```

## 执行流程

### 1. 读取上游产物

**必需输入**：
- 认证分析结果：`.workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md`

从上游产物中获取：
- 认证机制是否可绕过
- 角色体系定义
- 管理员专属路由前缀
- 权限控制实现方式

### 2. 路由识别方法（主流语言/框架）

#### 2.1 通用思路

- **查找路由声明位置**：路由表文件、装饰器/注解、注册函数（router、app、server）、中间件挂载点
- **识别前缀与分组**：`group/prefix/subrouter`、`namespace`、`Area`、`MapControllerRoute` 等
- **识别动态参数**：`:param`、`{param}`、`<type:param>`、正则/通配符（`*`, `**`），以及方法限定（GET/POST/...）
- **关联中间件/过滤器**：auth/role/guard/interceptor，标记优先级与认证需求

#### 2.2 Node.js / TypeScript（Express/Koa/Fastify/Nest）

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

**路由特征**：
- 类级 `@RequestMapping("/api")` + 方法级 `@GetMapping("/x")` 等组合
- 路径变量 `/{id}`、通配符 `/**`
- 常见端点：Actuator `/actuator/**`，Swagger `/v2/api-docs`、`/swagger-ui`

**匹配正则**：
```regex
@(RequestMapping|RestController|Controller)\s*(\(\s*(['"]|value\s*=\s*['"]))?
@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)\s*\(\s*(['"]|value\s*=\s*['"]|path\s*=\s*['"])?
```

#### 2.5 Go（Gin/Echo/Chi/Fiber/Mux/net/http）

**路由特征**：
- Gin：`r.GET/POST`，`r.Group("/api")`；中间件 `Use`
- Echo：`e.GET/POST`，`e.Group("/api")`；路由模板 `/:id/*`
- Chi：`r.Route("/api", func(r chi.Router){ r.Get(...) })`，`Mount`
- Fiber：`app.Get/Post`，`app.Group("/api")`
- net/http：`http.HandleFunc("/path", handler)`，`ServeMux`
- gorilla/mux：`r.HandleFunc`，`PathPrefix`，`Methods`
- httprouter：`router.GET/POST`
- Beego：`beego.Router`，`@router` 注释路由
- Iris：`app.Get/Post`，`Party` 分组

**匹配正则**：
```regex
# Gin/Echo
\w+\s*\.\s*(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Any|Handle|Group|Add|Match)\s*\(\s*["']

# Chi/Fiber
\w+\s*\.\s*(Get|Post|Put|Patch|Delete|Options|Head|Route|Mount|Connect|Trace|With|All|Use)\s*\(\s*["']

# net/http 标准库
http\s*\.\s*(HandleFunc|Handle|ListenAndServe|NewServeMux)\s*\(
ServeMux

# gorilla/mux
\w+\s*\.\s*(HandleFunc|Handle|PathPrefix|Methods|Path|Queries|Schemes|Host)\s*\(
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

**路由特征**：
- Laravel：`routes/web.php`、`routes/api.php`；`Route::get/post/put/delete`，`Route::group`，`Route::resource/apiResource`
- Symfony：`config/routes/*.yaml` / 注解 / 属性路由

**匹配正则**：
```regex
Route\s*::\s*(get|post|put|patch|delete|options|any|match|resource|apiResource|group)\s*\(\s*['"]
Route\s*::\s*(prefix|middleware|namespace|group)\s*\(
#\[(Route|Get|Post|Put|Patch|Delete)\s*\(\s*['"]
@(Route|Get|Post|Put|Patch|Delete)\s*\(\s*['"]
```

#### 2.7 Ruby on Rails

**路由特征**：
- `config/routes.rb`：`resources :users`、`namespace :admin`、`scope path: "/api"`、`match`/`get/post`

**匹配正则**：
```regex
(get|post|put|patch|delete|match|root)\s+['"]
(resources?|namespace|scope|constraints)\s+[:'"]
```

#### 2.8 .NET（ASP.NET Core）

**路由特征**：
- Minimal APIs：`app.MapGet/MapPost/...`；`MapGroup("/api")`
- MVC/Controllers：`[Route("api/[controller]")]` + `[HttpGet("x")]`

**匹配正则**：
```regex
\w+\s*\.\s*(MapGet|MapPost|MapPut|MapPatch|MapDelete|MapMethods|MapGroup)\s*\(\s*["']
\[(Route|HttpGet|HttpPost|HttpPut|HttpPatch|HttpDelete)\s*\(\s*["']?
```

#### 2.9 JavaScript 前后端一体框架（Next.js / Nuxt）

**路由特征**：
- Next.js API Routes：`pages/api/*` 或 `app/api/*/route.{js,ts}`；动态 `[id]`，catch-all `[...slug]`
- Nuxt 3 Nitro：`server/api/**/*.ts`

**匹配方式**：基于文件路径匹配
```
pages/api/**/*.{js,ts}
app/api/**/route.{js,ts}
server/api/**/*.ts
```

#### 2.10 通用匹配（兜底）

当框架特定正则无法匹配时，使用宽松匹配：
```regex
\b(route|router|endpoint|api|controller)\b.*\b(get|post|put|patch|delete)\b
['"`]\/[a-zA-Z0-9_\-\/\{\}\:\*\[\]]+['"`]
```

> **注意**：通用匹配可能产生误报，需结合上下文确认。

### 3. 普通用户路由识别标准

#### 3.1 定义：普通用户可访问的路由

普通用户路由 = 需要登录认证 + 非管理员专属

**包含**：
- 需要登录但无角色限制的路由
- 限制为普通用户角色的路由（如 `@Roles('user')`）
- 登录用户都可访问的通用功能路由

**排除**：
- 无需认证的公开路由（由 `unauth-route-scanner` 处理）
- 管理员/超级管理员专属路由
- 内部/调试路由

#### 3.2 识别方法

**识别需要认证的路由**：

```python
# Python Flask - 有 @login_required 但无 @admin_required
@login_required
@app.route('/api/profile')
def get_profile():
    return profile

# Python FastAPI - 有 Depends(get_current_user) 但无管理员检查
@router.get('/api/orders')
async def list_orders(user: User = Depends(get_current_user)):
    return orders
```

```javascript
// Express - 有 auth 中间件但无 admin 中间件
app.get('/api/profile', authMiddleware, (req, res) => {
    res.json(profile);
});

// NestJS - 有 @UseGuards(AuthGuard) 但无 @Roles('admin')
@UseGuards(AuthGuard)
@Get('orders')
findOrders() {
    return this.ordersService.findAll();
}
```

```java
// Spring - 需要认证但无管理员角色要求
@GetMapping("/api/profile")
@PreAuthorize("isAuthenticated()")
public Profile getProfile() {
    return profileService.get();
}
```

```go
// Gin - 在 auth 中间件组内但不在 admin 组内
authGroup := r.Group("/api", authMiddleware)
{
    authGroup.GET("/profile", getProfile)
    authGroup.GET("/orders", listOrders)
}
```

**排除管理员路由的特征**：

| 排除特征 | 示例 |
|---------|------|
| 路径前缀 | `/admin/*`, `/management/*`, `/internal/*`, `/superuser/*` |
| 角色装饰器 | `@Roles('admin')`, `@RequireRole('admin')`, `@admin_required` |
| 权限注解 | `@PreAuthorize("hasRole('ADMIN')")`, `roles=['admin']` |
| 中间件 | `AdminGuard`, `adminMiddleware`, `IsAdminMiddleware` |
| 权限配置 | `permission: 'admin'`, `is_staff=True`, `is_superuser=True` |

#### 3.3 认证可绕过时的处理

当 `web-auth-analyzer` 判定认证机制可绕过时：
- **包含管理员路由**：因为攻击者可能绕过认证访问这些路由
- 在产物中标注：`认证绕过风险: 是`
- 将管理员路由单独分组标记

### 4. 风险分级

| 风险等级 | 描述 | 路由特征 |
|---------|------|----------|
| **高危** | 敏感操作 | 支付、密码修改、权限变更、数据删除 |
| **中危** | 数据修改 | 个人信息修改、订单操作、文件上传 |
| **低危** | 数据读取 | 查看个人资料、订单列表、消息记录 |

### 5. 输出格式

#### 5.1 产物文件

输出路径：`.workspace/tasks/{TASK_ID}/normal-route-scanner.md`

```markdown
# 普通用户路由清单

## 概述

- **扫描时间**：{timestamp}
- **总路由数**：{total_routes}
- **普通用户路由数**：{normal_user_count}
- **认证可绕过**：{auth_bypassable: 是/否}

## 风险统计

| 风险等级 | 数量 | 占比 |
|---------|------|------|
| 高危 | {high_count} | {high_percent}% |
| 中危 | {medium_count} | {medium_percent}% |
| 低危 | {low_count} | {low_percent}% |

## 高危普通用户路由

| # | 方法 | 路径 | 文件位置 | 功能说明 | 风险说明 |
|---|------|------|---------|---------|----------|
| 1 | POST | /api/payment | src/routes/payment.js:25 | 支付接口 | 支付操作无二次验证 |
| 2 | PUT | /api/password | src/routes/user.js:80 | 修改密码 | 密码修改敏感操作 |

## 中危普通用户路由

| # | 方法 | 路径 | 文件位置 | 功能说明 | 风险说明 |
|---|------|------|---------|---------|----------|
| 1 | PUT | /api/profile | src/routes/user.js:45 | 修改个人资料 | 可能存在越权修改 |
| 2 | POST | /api/upload | src/routes/file.js:30 | 文件上传 | 需检查文件类型限制 |

## 低危普通用户路由

| # | 方法 | 路径 | 文件位置 | 功能说明 |
|---|------|------|---------|---------|
| 1 | GET | /api/profile | src/routes/user.js:20 | 查看个人资料 |
| 2 | GET | /api/orders | src/routes/order.js:15 | 订单列表 |

## 因认证绕过而包含的管理员路由

> 以下路由因认证机制可绕过而被纳入分析范围

| # | 方法 | 路径 | 文件位置 | 原始权限要求 |
|---|------|------|---------|-------------|
| 1 | GET | /admin/users | src/routes/admin.js:30 | admin |
| 2 | DELETE | /admin/data | src/routes/admin.js:55 | admin |
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
| `route-deep-analyzer` | 对普通用户路由进行深度分析 |

## 输出要求

### 产物输出

**Markdown 报告**：`.workspace/tasks/{TASK_ID}/normal-route-scanner.md`

### 下游任务生成

每个普通用户路由清单对应一个 `route-deep-analyzer` 任务：

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/normal-route-scanner.md",
      "skill": "route-deep-analyzer",
      "dependencies": [
        ".workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md"
      ]
    }
  ]
}
```

### 重要约束

- **必须读取上游产物**：不可独立运行，需依赖 web-auth-analyzer 的输出
- **必须排除公开路由**：公开路由由 `unauth-route-scanner` 处理，避免重复
- **风险分级必须明确**：每个路由必须标注风险等级和原因
- **JSON 输出必须有效**：确保 JSON 格式正确，便于下游程序化处理
- **认证绕过时包含管理员路由**：当认证可绕过时，需要将管理员路由也纳入分析
