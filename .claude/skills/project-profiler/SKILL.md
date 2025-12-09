---
name: project-profiler
description: 项目画像技能：构建项目画像，分析技术栈与项目类型，并推荐后续分析技能。
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

**总结输出格式（JSON格式）：**
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/project-profile.md",
            "skill": "route-scanner"
        },
        {
            "artifact": ".workspace/tasks/{TASK_ID}/project-profile.md",
            "skill": "authentication-analyzer"
        }
    ]
}
```

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

**总结输出格式（JSON格式）：**
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/project-profile.md",
            "skill": "vtr-scanner"
        }
    ]
}
```

# 输出要求

## 1. 项目画像文件

**输出路径**：`.workspace/tasks/{TASK_ID}/project-profile.md`（如用户指定了输出路径则优先使用）

**文件内容格式**：
```markdown
# 项目画像

## 基本信息
- **项目名称**：{project_name}
- **项目路径**：{project_root}
- **扫描时间**：{scan_time}

## 项目分类
- [ ] 后端HTTP服务
- [ ] 前端WEB应用
- [ ] 安全测试靶场

## 技术栈
- **主要语言**：{language}
- **框架**：{framework}
- **包管理器**：{package_manager}

## 代码统计
- **文件数量**：{file_count}
- **代码行数**：{lines_of_code}
- **主要目录结构**：
  - src/
  - tests/
  - ...

## 入口点
- **主入口文件**：{entry_file}
- **路由入口**：{router_files}

## 分类依据
{classification_evidence}
```

## 2. 必需包含内容

| 字段 | 必需 | 说明 |
|------|------|------|
| 项目分类 | 是 | 至少勾选一个分类 |
| 主要语言 | 是 | 项目使用的主要编程语言 |
| 框架 | 是 | 使用的Web框架（如有） |
| 文件数量 | 是 | 扫描范围内的文件总数 |
| 分类依据 | 是 | 说明判定分类的依据 |

## 3. 后续任务推荐

根据项目分类，按照对应的「总结输出格式」返回任务列表。

**注意**：
- `{TASK_ID}` 由上游 orchestrator 传入，需替换为实际值（如 `orch-001`）
- 如果项目同时属于多个分类，合并所有分类对应的任务列表
