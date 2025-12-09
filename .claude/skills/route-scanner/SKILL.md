---
name: route-scanner
description: 专业路由扫描技能：具备主流语言/框架的API端点扫描能力，可以快速发现项目中的所有API端点。
---

## 概述与边界

- 聚焦API端点扫描：发现项目中的所有API端点，包括公开API和内部API。
- 不做：漏洞扫描、漏洞利用、漏洞利用链推导。

**重要：不要遗漏任何API端点，包括内部API和公开API。对于上游任务给定的分析结果，需要进一步确认是否存在遗漏。**

## 主流语言/框架路由识别方法

### 通用思路
- 查找路由声明位置：路由表文件、装饰器/注解、注册函数（router、app、server）、中间件挂载点。
- 识别前缀与分组：`group/prefix/subrouter`、`namespace`、`Area`、`MapControllerRoute` 等。
- 识别动态参数：`:param`、`{param}`、`<type:param>`、正则/通配符（`*`, `**`），以及方法限定（GET/POST/...）。
- 关联中间件/过滤器：auth/role/guard/interceptor，标记优先级与认证需求。

### Node.js / TypeScript（Express/Koa/Fastify/Nest）
- Express：`app.METHOD(path, ...)`、`router.METHOD(path, ...)`、`router.use(prefix, ...)`；文件：`routes/*.js/ts`、`app.js`、`server.js`。
- Koa-Router：`router.get/post/...`、`router.use(prefix, nestedRouter.routes())`。
- Fastify：`fastify.route({ method, url, ... })`、`fastify.register(plugin, { prefix })`；插件内再注册子路由。
- NestJS：控制器装饰器 `@Controller(prefix)` + 方法装饰 `@Get/@Post(@Patch @Delete)`；`setGlobalPrefix`；`Routes` 配置。

### Python（Flask/FastAPI/Django）
- Flask：`@app.route` / `@blueprint.route`，关注 blueprint 前缀与 `url_prefix`；方法列表 `methods=["GET","POST"]`。
- FastAPI：`APIRouter(prefix=...)` + `@router.get/post/...`；应用挂载 `app.include_router(router, prefix=...)`；Pydantic 路径/查询参数。
- Django：`urlpatterns = [ path(...), re_path(...), include(...) ]`；子路由 include 递归；Class-Based View 的 `as_view()`；DRF `DefaultRouter`/`SimpleRouter` 自动生成的 `basename` + `list/retrieve` 等。

### Java（Spring MVC / Spring Boot）
- 类级 `@RequestMapping("/api")` + 方法级 `@GetMapping("/x")` 等组合；HTTP 方法从注解推断。
- 路径变量 `/{id}`、通配符 `/**`；生产常见额外端点：Actuator `/actuator/**`，Swagger `/v2/api-docs` `/swagger-ui`。
- 额外配置：`WebMvcConfigurer#addViewControllers`、`RouterFunction`（函数式路由）。

### Go（Gin/Echo/Chi/net/http）
- Gin：`r.GET/POST`，`r.Group("/api")`，子分组再拼前缀；中间件 `Use` 影响鉴权。
- Echo：`e.GET/POST`，`e.Group("/api")`，`g.Use(mw)`；路由模板 `/:id/*`。
- Chi：`r.Route("/api", func(r chi.Router){ r.Get(...) })`，`Mount` 子路由。
- net/http：`http.HandleFunc("/path", handler)`，或自定义 `ServeMux.Handle("/prefix", ...)`。
- gorilla/mux：`r.HandleFunc("/path", handler)`，`r.Handle("/prefix", ...)`。

### PHP（Laravel / Symfony）
- Laravel：`routes/web.php`, `routes/api.php`；`Route::get/post/put/delete`，`Route::group(['prefix' => 'api', 'middleware' => ...], ...)`，`Route::resource/apiResource` 自动生成 CRUD 路由。
- Symfony：`config/routes/*.yaml` / 注解 / 属性路由；`path`、`controller`、`methods`；可有 `prefix`、`requirements`（正则约束）。

### Ruby on Rails
- `config/routes.rb`：`resources :users` 生成 REST 路由；`namespace :admin do ... end`；`scope path: "/api"`；自定义 `match`/`get/post`。

### .NET（ASP.NET Core）
- Minimal APIs：`app.MapGet/MapPost/...`；全局 `MapGroup("/api")`。
- MVC/Controllers：`[Route("api/[controller]")]` + `[HttpGet("x")]`；`MapControllerRoute` 模板。
- 端点元数据：`RequireAuthorization` / filters 指示鉴权。

### JavaScript 前后端一体框架（Next.js / Nuxt）
- Next.js API Routes：`pages/api/*` 或 `app/api/*/route.{js,ts}`；文件路径即路由；动态 `[id]`，catch-all `[...slug]`。
- Nuxt 3 Nitro：`server/api/**/*.ts`；文件名到路由映射。

### 识别步骤（建议执行）
1) 定位路由入口：按语言规则搜索 `route|router|RequestMapping|Controller|MapGet|Route::|resources` 等；扫描框架默认路由文件夹。
2) 解析前缀与分组：提取 `prefix/group/namespace/include`，自顶向下拼接路径。
3) 提取 HTTP 方法与路径模板：记录动态参数、正则/通配符；方法默认值（未指定时多为 GET）。
4) 关联中间件/鉴权：收集与路由同级或分组级的 auth/role/guard/interceptor；标注认证要求。
5) 输出端点列表：`method`, `path`, `file`, `line`, `auth_hint`, `group_prefix`；标记高风险端点（debug/admin/config/internal）。

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