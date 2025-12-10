---
name: route-scanner
description: 专业路由扫描技能：具备主流语言/框架的API端点扫描能力，可以快速发现项目中的所有API端点。
---

## 概述与边界

- 聚焦API端点扫描：发现项目中的所有API端点，包括公开API和内部API。
- 不做：漏洞扫描、漏洞利用、漏洞利用链推导。

**重要：不要遗漏任何API端点，包括内部API和公开API。对于上游任务给定的分析结果，需要进一步确认是否存在遗漏。**

## 执行流程

**第一步：识别路由功能模块**

在执行任何路由解析之前，必须先识别所有路由功能模块：

1. 根据项目的语言/框架类型，搜索可能包含路由注册的文件
2. 按业务功能、目录结构、路由前缀划分功能模块
3. 统计功能模块的数量
4. 根据模块数量决定后续处理方式：
   - 模块数量 ≥ 2：触发拆分机制，为每个模块生成子任务
   - 模块数量 = 1：继续执行详细的路由解析

## 主流语言/框架路由识别方法

### 通用思路
- 查找路由声明位置：路由表文件、装饰器/注解、注册函数（router、app、server）、中间件挂载点。
- 识别前缀与分组：`group/prefix/subrouter`、`namespace`、`Area`、`MapControllerRoute` 等。
- 识别动态参数：`:param`、`{param}`、`<type:param>`、正则/通配符（`*`, `**`），以及方法限定（GET/POST/...）。
- 关联中间件/过滤器：auth/role/guard/interceptor，标记优先级与认证需求。

### Node.js / TypeScript（Express/Koa/Fastify/Nest）

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

### Python（Flask/FastAPI/Django）

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

### Java（Spring MVC / Spring Boot）

**路由特征**：
- 类级 `@RequestMapping("/api")` + 方法级 `@GetMapping("/x")` 等组合
- 路径变量 `/{id}`、通配符 `/**`
- 常见端点：Actuator `/actuator/**`，Swagger `/v2/api-docs`、`/swagger-ui`

**匹配正则**：
```regex
@(RequestMapping|RestController|Controller)\s*(\(\s*(['"]|value\s*=\s*['"]))?
@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)\s*\(\s*(['"]|value\s*=\s*['"]|path\s*=\s*['"])?
```

### Go（Gin/Echo/Chi/net/http）

**路由特征**：
- Gin：`r.GET/POST`，`r.Group("/api")`；中间件 `Use`
- Echo：`e.GET/POST`，`e.Group("/api")`；路由模板 `/:id/*`
- Chi：`r.Route("/api", func(r chi.Router){ r.Get(...) })`，`Mount`
- net/http：`http.HandleFunc("/path", handler)`
- gorilla/mux：`r.HandleFunc("/path", handler)`

**匹配正则**：
```regex
\w+\s*\.\s*(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Any|Handle|Group)\s*\(\s*["']
\w+\s*\.\s*(Get|Post|Put|Patch|Delete|Options|Head|Route|Mount)\s*\(\s*["']
http\s*\.\s*(HandleFunc|Handle)\s*\(\s*["']
\w+\s*\.\s*(HandleFunc|Handle|PathPrefix)\s*\(\s*["']
```

### PHP（Laravel / Symfony）

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

### Ruby on Rails

**路由特征**：
- `config/routes.rb`：`resources :users`、`namespace :admin`、`scope path: "/api"`、`match`/`get/post`

**匹配正则**：
```regex
(get|post|put|patch|delete|match|root)\s+['"]
(resources?|namespace|scope|constraints)\s+[:'"]
```

### .NET（ASP.NET Core）

**路由特征**：
- Minimal APIs：`app.MapGet/MapPost/...`；`MapGroup("/api")`
- MVC/Controllers：`[Route("api/[controller]")]` + `[HttpGet("x")]`

**匹配正则**：
```regex
\w+\s*\.\s*(MapGet|MapPost|MapPut|MapPatch|MapDelete|MapMethods|MapGroup)\s*\(\s*["']
\[(Route|HttpGet|HttpPost|HttpPut|HttpPatch|HttpDelete)\s*\(\s*["']?
```

### JavaScript 前后端一体框架（Next.js / Nuxt）

**路由特征**：
- Next.js API Routes：`pages/api/*` 或 `app/api/*/route.{js,ts}`；动态 `[id]`，catch-all `[...slug]`
- Nuxt 3 Nitro：`server/api/**/*.ts`

**匹配方式**：基于文件路径匹配，无需正则
```
pages/api/**/*.{js,ts}
app/api/**/route.{js,ts}
server/api/**/*.ts
```

### 通用匹配（兜底）

当框架特定正则无法匹配时，使用宽松匹配：
```regex
\b(route|router|endpoint|api|controller)\b.*\b(get|post|put|patch|delete)\b
['"`]\/[a-zA-Z0-9_\-\/\{\}\:\*\[\]]+['"`]
```

**注意**：通用匹配可能产生误报，需人工确认。

### 识别步骤

1) **定位路由入口**：根据项目语言/框架，使用上述正则表达式搜索路由注册文件
2) **解析前缀与分组**：提取 `prefix/group/namespace/include`，自顶向下拼接路径
3) **提取 HTTP 方法与路径模板**：记录动态参数、正则/通配符；方法默认值（未指定时多为 GET）
4) **关联中间件/鉴权**：收集 auth/role/guard/interceptor；标注认证要求
5) **输出端点列表**：`method`, `path`, `file`, `line`, `auth_hint`, `group_prefix`；标记高风险端点

# 路由模块拆分机制

## 触发条件

当检测到路由功能模块数量 **≥ 2 个**时，触发拆分机制。

**模块识别标准**：
- 按业务功能划分的路由分组（如 `users`、`orders`、`products`）
- 独立的路由文件或目录（如 `routes/user.js`、`routes/order/`）
- 框架定义的路由前缀分组（如 `/api/v1/users`、`/api/v1/orders`）

## 处理流程

1. **生成模块清单**：列出所有功能模块及其包含的文件
2. **识别功能模块**：根据路由前缀、目录结构、业务分组识别功能模块
3. **按模块拆分任务**：为每个功能模块生成一个独立的 `route-scanner` 任务

## 拆分输出格式

1. **生成模块清单**：`.workspace/tasks/{TASK_ID}/route-modules-inventory.md`
2. **为每个模块生成子任务**

```json
{
  "split": true,
  "total_modules": 5,
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/route-module-users.md",
      "skill": "route-scanner"
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/route-module-orders.md",
      "skill": "route-scanner"
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/route-module-products.md",
      "skill": "route-scanner"
    }
  ]
}
```

## 模块清单格式

每个 `route-module-{name}.md` 文件内容：

```markdown
# 路由模块分析任务

## 模块信息
- **模块名称**：users
- **路由前缀**：/api/v1/users
- **框架类型**：Express

## 包含文件
| 文件路径 | 描述 |
|---------|------|
| src/routes/user.js | 用户路由主文件 |
| src/routes/user/profile.js | 用户资料相关路由 |
| src/routes/user/settings.js | 用户设置相关路由 |

## 分析范围
仅分析该模块包含的文件中的路由注册，输出端点列表。
```

## 注意事项

- **禁止省略任何模块**：每一个检测到的功能模块都必须创建对应的子任务，不允许跳过或合并
- 子任务收到单个模块时，仅分析该模块包含的文件，不再触发拆分
- 子任务完成后按正常流程输出端点列表和下游 `route-function-analyzer` 任务

# 输出要求

1. API端点数量大于10，规则如下：

- API端点按照分类输出到多个文件中，文件路径规则为：
    .workspace/tasks/{TASK_ID}/route-scanner-result-{category}.md
- 任务运行过程中及时生成对应文档，避免累计到最后导致任务失败。
- 每个md文件对应一个下游的任务，技能为：route-function-analyzer
- 端点审计任务依赖authentication-analyzer的分析结果，需要给定该任务产物路径作为输入。
- 总结输出规则（JSON格式）：
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/route-scanner-result-{category-01}.md",
            "skill": "route-function-analyzer",
            "dependencies": [
                ".workspace/tasks/{AUTH_TASK_ID}/authentication-analyzer-result.md"
            ]
        },
        {
            "artifact": ".workspace/tasks/{TASK_ID}/route-scanner-result-{category-02}.md",
            "skill": "route-function-analyzer",
            "dependencies": [
                ".workspace/tasks/{AUTH_TASK_ID}/authentication-analyzer-result.md"
            ]
        }
    ]
}
```

**依赖路径说明**：
- `{TASK_ID}` 为当前任务 ID（如 `orch-002`）
- `{AUTH_TASK_ID}` 为 authentication-analyzer 任务的 ID，需从 orchestrator-tasks.json 中查找对应任务
    
2. API端点数量小于10，规则如下：
- 将API端点输出到.workspace/tasks/{TASK_ID}/route-scanner-result.md文件中
- 生成一个下游的任务，技能为：route-function-analyzer
- 端点审计任务依赖authentication-analyzer的分析结果，需要给定该任务产物路径作为输入。
- 总结输出规则（JSON格式）：
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/route-scanner-result.md",
            "skill": "route-function-analyzer",
            "dependencies": [
                ".workspace/tasks/{AUTH_TASK_ID}/authentication-analyzer-result.md"
            ]
        }
    ]
}
```