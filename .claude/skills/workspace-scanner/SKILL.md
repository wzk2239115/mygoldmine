---
name: workspace-scanner
description: 工作区扫描技能：判断工程是否由多个相对独立的子工程组成，并为每个子工程或单一工程生成 project-profiler 任务。
---

# 概述与边界

- **聚焦工作区结构分析**：快速判断当前工程是单一项目还是包含多个相对独立的子工程（Monorepo / Multi-project）
- **不做**：项目分类、技术栈分析、漏洞扫描（这些由 `project-profiler` 负责）

## 判定标准

### Monorepo / 多子工程的特征

1. **包管理器工作区配置**：
   - `package.json` 含 `workspaces` 字段
   - `pnpm-workspace.yaml` 存在
   - `lerna.json` 存在
   - `rush.json` 存在

2. **多模块项目配置**：
   - Maven: `pom.xml` 含 `<modules>` 标签
   - Gradle: `settings.gradle` 含 `include` 语句
   - Go: `go.work` 存在（Go 1.18+ workspace）
   - .NET: `*.sln` 解决方案文件引用多个 `*.csproj`

3. **目录结构特征**：
   - `packages/` 或 `apps/` 目录下有多个独立子目录，每个含独立的依赖配置文件
   - `services/` 目录下有多个独立微服务
   - 顶层目录下存在多个独立的 `package.json`、`pom.xml`、`go.mod` 等

4. **独立子工程的判定条件**（满足任一）：
   - 有独立的依赖配置文件（`package.json`、`pom.xml`、`build.gradle`、`go.mod`、`Cargo.toml`、`requirements.txt`、`composer.json`）
   - 有独立的入口文件或启动脚本
   - 有独立的 README 或文档

### 单一项目的特征

- 只有一个顶层依赖配置文件
- 没有工作区/模块配置
- 没有明显的子项目目录结构

## 扫描流程

### 步骤 1: 检测工作区配置

```bash
# 检查 Node.js monorepo
cat package.json 2>/dev/null | grep -q '"workspaces"' && echo "npm-workspaces"
ls pnpm-workspace.yaml 2>/dev/null && echo "pnpm-workspace"
ls lerna.json 2>/dev/null && echo "lerna"
ls rush.json 2>/dev/null && echo "rush"

# 检查 Java 多模块
grep -l '<modules>' pom.xml 2>/dev/null && echo "maven-modules"
grep -l 'include' settings.gradle* 2>/dev/null && echo "gradle-modules"

# 检查 Go workspace
ls go.work 2>/dev/null && echo "go-workspace"

# 检查 .NET 解决方案
ls *.sln 2>/dev/null && echo "dotnet-solution"
```

### 步骤 2: 扫描子工程目录

如果检测到工作区配置，进一步扫描子工程：

```bash
# Node.js: 从 package.json workspaces 或 pnpm-workspace.yaml 获取
# Maven: 从 pom.xml <modules> 获取
# Gradle: 从 settings.gradle include 获取
# 通用: 扫描 packages/*/package.json, apps/*/package.json, services/*/pom.xml 等
```

### 步骤 3: 验证子工程独立性

对每个潜在子工程，检查：
- 是否有独立的依赖配置文件
- 是否有可识别的项目结构
- 排除测试目录、示例目录、文档目录等非独立工程

## 输出要求

### 1. 工作区分析文件

**输出路径**：`.workspace/tasks/{TASK_ID}/workspace-analysis.md`

**文件内容格式**：
```markdown
# 工作区分析报告

## 基本信息
- **工作区路径**：{workspace_root}
- **扫描时间**：{scan_time}

## 工作区类型
- [ ] 单一项目
- [ ] Monorepo / 多子工程

## 工作区配置
- **配置类型**：{config_type} (npm-workspaces / pnpm-workspace / lerna / maven-modules / gradle-modules / go-workspace / dotnet-solution / none)
- **配置文件**：{config_file}

## 子工程列表
<!-- 如果是单一项目，此节为空或标注"无子工程" -->

| 子工程名称 | 相对路径 | 依赖配置文件 | 主要语言 |
|-----------|---------|-------------|---------|
| {name}    | {path}  | {config}    | {lang}  |

## 判定依据
{analysis_evidence}
```

### 2. 后续任务推荐

**单一项目**：生成一个 `project-profiler` 任务，分析整个项目

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/workspace-analysis.md",
      "skill": "project-profiler",
      "context": {
        "project_root": ".",
        "is_subproject": false
      }
    }
  ]
}
```

**多子工程**：为每个独立子工程生成一个 `project-profiler` 任务

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/workspace-analysis.md",
      "skill": "project-profiler",
      "context": {
        "project_root": "packages/frontend",
        "is_subproject": true,
        "subproject_name": "frontend"
      }
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/workspace-analysis.md",
      "skill": "project-profiler",
      "context": {
        "project_root": "packages/backend",
        "is_subproject": true,
        "subproject_name": "backend"
      }
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/workspace-analysis.md",
      "skill": "project-profiler",
      "context": {
        "project_root": "packages/shared",
        "is_subproject": true,
        "subproject_name": "shared"
      }
    }
  ]
}
```

### 3. 注意事项

- `{TASK_ID}` 由上游 orchestrator 传入，需替换为实际值（如 `orch-001`）
- 子工程路径使用相对路径，相对于工作区根目录
- 如果子工程数量过多（>20），可考虑按类型分组或提示用户选择重点分析的子工程
- 排除明显的非独立工程目录：`node_modules/`、`vendor/`、`dist/`、`build/`、`.git/`、`docs/`、`examples/`、`test/`、`tests/`
