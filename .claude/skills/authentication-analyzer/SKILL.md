---
name: authentication-analyzer
description: 专业认证分析技能：分析API端点认证要求，包括认证方式、认证参数、认证流程等。
---

## 概述与边界

- 聚焦API端点认证要求分析：分析API端点认证要求，包括认证方式、认证参数、认证流程等。

## 主流语言/框架认证要求分析方法

### 通用思路
- 路由入口：定位路由表/装饰器/注册函数（router、app、server）及默认路由目录，识别分组/前缀。
- 路径拼装：自顶向下收集 `prefix/group/namespace/include`，拼接完整路径模板，标注动态参数/通配符。
- 方法默认值：提取 HTTP 方法，未声明时记录框架默认（多为 GET）。
- 鉴权挂载点：收集中间件/filters/guards/interceptors/`RequireAuthorization`/角色声明，区分全局、分组、端点级。
- 认证方式与参数：辨识 `token/basic/oauth/apikey/cookie/session` 等及携带位置（header/query/body/cookie）。
- 输出清单：形成端点列表含 `method/path/file/line/auth_hint/group_prefix`，并标记高风险端点（debug/admin/config/internal）。
- 重点缺口：优先记录缺少鉴权或可绕过的公开端点，明确公开 vs 需授权。

### .NET（ASP.NET Core）
- Minimal APIs：`app.MapGet/MapPost/...`；全局 `MapGroup("/api")`。
- MVC/Controllers：`[Route("api/[controller]")]` + `[HttpGet("x")]`；`MapControllerRoute` 模板。
- 端点元数据：`RequireAuthorization` / filters 指示鉴权。

### JavaScript 前后端一体框架（Next.js / Nuxt）
- Next.js API Routes：`pages/api/*` 或 `app/api/*/route.{js,ts}`；文件路径即路由；动态 `[id]`，catch-all `[...slug]`。
- Nuxt 3 Nitro：`server/api/**/*.ts`；文件名到路由映射。

### 识别步骤（建议执行）
1) 定位路由入口：按语言规则搜索 `route|router|RequestMapping|Controller|MapGet|Route::|resources` 等；扫描框架默认路由文件夹。
2) 拼装路径：提取 `prefix/group/namespace/include`，自顶向下拼接完整路径，记录动态参数/通配符。
3) 确认方法：提取 HTTP 方法；未指定时记录框架默认（多为 GET）。
4) 关联鉴权：收集全局/分组/端点级的 auth/role/guard/interceptor/`RequireAuthorization`；标注认证要求与认证方式/参数。
5) 输出清单：列出 `method/path/file/line/auth_hint/group_prefix`，标记高风险端点（debug/admin/config/internal），突出缺少鉴权的路径。

# 输出要求

1. 分析结果保存到.workspace/tasks/{TASK_ID}/authentication-analyzer-result.md文件中
2. 不需要生成下游任务
