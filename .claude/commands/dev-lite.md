---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Lite development for exploratory tasks (no stage gates)
argument-hint: Describe what you need planned
---


# 轻量级开发命令

> 为探索性任务创建轻量级规划（无阶段闸门）

## 使用方式

在 Claude Code 中通过命令面板（Cmd+Shift+P）或直接引用此命令，AI 将帮助你创建快速规划文档。

## 何时使用此命令

使用 `/dev-lite` 的场景：
- **探索性任务**：在承诺完整规范驱动流程前需要先调研
- **小型重构**：不需要正式需求文档的快速改进
- **技术调研**：有时间限制的技术方案探索
- **快速原型**：无需正式阶段闸门的快速迭代

如需**正式功能开发**（阶段闸门 + TDD），请使用 `/dev`。

## 输出结构

所有文档存放在 `docs/dev-lite/{feature_name}/` 目录下：

```
docs/dev-lite/{feature_name}/
├── {feature_name}-plan.md      # 规划文档
├── {feature_name}-context.md   # 关键决策、依赖、上下文
└── {feature_name}-tasks.md     # 任务清单（可追踪进度）
```

### 路径命名规范

**`{feature_name}` 命名规则**：
- **格式**：使用 kebab-case（小写字母、数字、连字符）
- **示例**：`user-auth`、`payment-gateway`、`data-export-v2`
- **字符限制**：
  - 仅允许：小写字母（a-z）、数字（0-9）、连字符（-）
  - 禁止：大写字母、空格、下划线、特殊字符
  - 长度：3-50 个字符
- **验证规则**：
  - 必须以字母开头
  - 不能以连字符开头或结尾
  - 不能包含连续连字符（如 `user--auth`）
  - 不能与现有功能重名

## 工作流程

### 1. 分析请求

- 确定规划范围
- 理解当前代码库状态
- 识别关键文件和依赖

### 2. 创建结构化计划

计划应包含以下部分：

- **执行摘要**：计划概述和目标
- **现状分析**：当前系统状态评估
- **实施步骤**：可执行的行动项
- **风险评估**：潜在风险和缓解策略
- **成功标准**：可验证的完成标准

### 3. 任务分解结构

每个任务应包含：

- 任务编号和优先级
- 明确的完成标准
- 任务间依赖关系
- 工作量估算（S/M/L/XL）

### 4. 文件模板

#### {feature_name}-plan.md

```markdown
# {Task Name} 规划文档

> 创建时间: {YYYY-MM-DD}
> 最后更新: {YYYY-MM-DD}

## 执行摘要
[1-2 句话总结目标]

## 现状分析
[当前状态描述]

## 实施步骤

### 阶段 1: [阶段名称]
1. [步骤 1]
2. [步骤 2]

## 风险评估
| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| ... | ... | ... |

## 成功标准
- [ ] [标准 1]
- [ ] [标准 2]
```

#### {feature_name}-context.md

```markdown
# {Task Name} 上下文

> 最后更新: {YYYY-MM-DD HH:MM}

## 背景
[任务背景和动机]

## 关键文件
| 文件 | 用途 |
|------|------|
| ... | ... |

## 决策记录

### {YYYY-MM-DD} - {决策标题}
- **决策**: [内容]
- **原因**: [理由]

## 下一步行动
1. [行动 1]
2. [行动 2]
```

#### {feature_name}-tasks.md

```markdown
# {Task Name} 任务清单

> 最后更新: {YYYY-MM-DD HH:MM}

## 已完成 ✅
- [x] 任务 1

## 进行中 🔄
- [ ] 任务 2 - 当前状态：[描述]

## 待处理 📋
- [ ] 任务 3 (S)
- [ ] 任务 4 (M)
```

## 质量标准

- 计划必须自包含所有必要上下文
- 使用清晰、可执行的语言
- 包含具体的技术细节
- 考虑潜在风险和边界情况

## 上下文参考

- 检查 `PROJECT_KNOWLEDGE.md` 获取架构概览
- 参考 `BEST_PRACTICES.md` 获取编码标准
- 查看 `TROUBLESHOOTING.md` 了解常见问题

## 相关命令

- `dev`: 完整规范驱动开发（阶段闸门 + TDD）
- `dev-docs-update`: 上下文压缩前更新文档
- `dev-lite`: 轻量级开发（本命令）
- `code-review`: 代码架构审查

## 注意事项

- 此命令创建轻量级规划结构
- 如需正式功能开发（需求文档、设计文档、严格 TDD），请使用 `spec-driven-development`
- 创建的任务结构可在上下文重置后保留


**最后更新**：2025-11-30 16:10:35
**维护者**：Development Team
**版本**：2.0.0
