---
name: workspace-scanner
description: 工作区扫描技能：判断工程是否由多个相对独立的子工程组成，并为每个子工程或单一工程生成 project-profiler 任务。
---

# 概述与边界

- **聚焦工作区结构分析**：快速判断当前工程是单一项目还是包含多个相对独立的子工程（Monorepo / Multi-project）
- **不做**：项目分类、技术栈分析、漏洞扫描（这些由 `project-profiler` 负责）

## 输入参数

- `TASK_ID`（必填）：任务编号，用于生成输出路径
- `SCAN_RANGE`（可选）：子工程分析范围描述，如"分析前10个子工程"、"分析第5到第10个子工程"，默认分析前 5 个

## 判定标准

### Monorepo / 多子工程的特征

运行 `quick-scan.py` 脚本进行快速扫描，并生成文件树。
```bash
python3 ./quick-scan.py {source_dir}
python3 ./quick-scan.py .
```

**脚本覆盖范围**：
- ✅ **文件树生成**：自动生成项目文件树结构
- ✅ **目录结构分析**：自动识别项目目录层级和结构
- ✅ **配置文件识别**：自动识别依赖配置文件（package.json、pom.xml、go.mod 等）
- ❌ **工作区类型判定**：工作区类型（单一项目/Monorepo）需要结合脚本结果进行手动判定
- ❌ **子工程识别**：子工程的识别和独立性判断需要结合项目结构进行手动分析

### 单一项目的特征

- 只有一个顶层依赖配置文件
- 没有工作区/模块配置
- 没有明显的子项目目录结构

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

### 3. 子工程数量限制处理

当检测到多子工程时，按以下规则处理：

1. **默认限制**：最多分析前 5 个子工程
2. **自定义限制**：通过 `SCAN_RANGE` 参数调整（如"分析第6到第10个子工程"）
3. **超限处理**：
   - 在工作区分析报告中列出**所有**检测到的子工程（完整列表）
   - 仅为限制范围内的子工程生成 `project-profiler` 任务
   - 在报告中明确标注哪些子工程被跳过

**示例输出（检测到 12 个子工程，限制为前 5 个）**：
```markdown
## 子工程列表

检测到 **12** 个子工程，根据限制配置（`SCAN_RANGE: 分析前5个子工程`），仅分析前 **5** 个。

### 将被分析的子工程（1-5）
| 子工程名称 | 相对路径 | 依赖配置文件 | 主要语言 |
|-----------|---------|-------------|---------|
| frontend  | packages/frontend | package.json | TypeScript |
| backend   | packages/backend | package.json | TypeScript |
| ...       | ...     | ...         | ...     |

### 未被分析的子工程（6-12）
| 子工程名称 | 相对路径 | 依赖配置文件 | 主要语言 |
|-----------|---------|-------------|---------|
| service-a | services/service-a | pom.xml | Java |
| ...       | ...     | ...         | ...     |

> 如需分析其他子工程，请使用 `SCAN_RANGE` 参数指定范围（如"分析第6到第10个子工程"）。
```

### 4. 注意事项

- `{TASK_ID}` 由上游 orchestrator 传入，需替换为实际值（如 `orch-001`）
- 子工程路径使用相对路径，相对于工作区根目录
- 排除明显的非独立工程目录：`node_modules/`、`vendor/`、`dist/`、`build/`、`.git/`、`docs/`、`examples/`、`test/`、`tests/`
