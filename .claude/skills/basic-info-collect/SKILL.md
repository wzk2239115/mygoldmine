---
name: basic-info-collect
description: 专业基础信息收集技能：快速收集项目基本信息，并根据项目类型推荐后续分析使用的技能列表。
---

# 概述与边界

- 聚焦项目基础信息收集, 快速判定优先, 可选分类如下：
1. 后端HTTP服务（主流应用类型, 通过HTTP协议提供服务）
2. 前端WEB应用（浏览器上的运行的代码，通常由HTML、CSS、JavaScript等技术栈开发）
3. 安全测试靶场（用于安全测试的靶场，通常包含多个不同类型的漏洞代码示例, 靶场类型与其他类型存在冲突关系, 如果判定为靶场, 则不需要再分析其他类型）

**重要：一个项目可以同时属于多个分类。**

# 分类方法

**识别后端HTTP服务分类方法（快速判定）：**
- 快速判定一：查依赖/锁文件中常见 Web 框架关键字。
- 快速判定二：查入口/路由特征调用（如 app.use、router.get、@RestController、urlpatterns、FastAPI()、gin.Default、Route::get、MapGet）。
- 若快速判定失败，再做深搜。
```bash
# Node.js
rg "express|koa|fastify|nest" package.json yarn.lock pnpm-lock.yaml
rg "app\\.use\\(|router\\.get\\(" src/ server/ app/ -g'*.{js,ts}'

# Python
rg "flask|fastapi|django" requirements.txt pyproject.toml
rg "urlpatterns|FastAPI\\(|flask\\.Flask\\(" src/ app/ -g'*.py'
# 快速判定（入口文件）：rg "uvicorn|gunicorn|hypercorn" Procfile Dockerfile* Makefile*

# Java
rg "spring-boot|spring-web" pom.xml build.gradle* gradle.lockfile
rg "@RestController|@RequestMapping" src/ -g'*.java'
# 快速判定（入口类）：rg "SpringApplication\\.run" src/ -g'*.java'

# Go
rg "gin-gonic|echo|chi" go.mod
rg "gin\\.Default\\(|echo\\.New\\(|chi\\.NewRouter\\(" . -g'*.go'

# PHP
rg "laravel|symfony/http-foundation" composer.json
rg "Route::get\\(|Route::post\\(" routes/ app/ -g'*.php'
# 快速判定（入口）：rg "public/index\\.php|artisan" -g'*.php'

# .NET
rg "AspNetCore" *.csproj
rg "MapGet\\(|MapControllers\\(" . -g'*.cs'
# 快速判定（Program.cs）：rg "WebApplication\\.CreateBuilder" . -g'Program.cs'
```

**对于后端 HTTP 服务，后续分析需要使用的技能列表如下（禁止添加其他技能）: **
- route-scanner 技能：扫描API端点，识别路由信息。
- authentication-analyzer 技能：分析API端点认证要求。

2. 前端 WEB 应用

**识别 WEB 应用方法（快速判定优先）：**
- 快速判定一：查依赖/锁文件中常见 Web 框架关键字。
- 快速判定二：查入口/路由特征调用（如 React、Vue、Angular、Svelte、Next、Nuxt）。
- 若快速判定失败，再做深搜。

**对于前端WEB应用，目前不需要继续分析，直接跳过。**

3. 安全测试靶场

**识别安全测试靶场方法（快速判定优先）：**
- 快速判定一：项目说明文档通常会明确指出是项目靶场为出于教学目的而构建的安全测试靶场, 可以重点关注。
- 快速判定二: 项目目录结构中会包含多个不同类型的漏洞代码示例。

**对于安全测试靶场，后续分析需要使用的技能列表如下（禁止添加其他技能）: **
- vtr-scanner 技能：扫描靶场类型，识别测试类型。

# 输出要求

1. **优先使用用户指定了输出路径，默认输出到.workspace/tasks/{TASK_ID}/project-profile.md文件中**

2. 总结输出格式（JSON格式）：
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/project-profile.md",
            "skill": "basic-info-collect"
        }
    ]
}
```