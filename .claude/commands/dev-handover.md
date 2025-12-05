---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Execute dev-handover command
argument-hint: 
---


# 上下文交接命令

> 在上下文压缩前进行工作交接，确保工作连续性

## 使用方式

在 Claude Code 中通过命令面板（Cmd+Shift+P）或直接引用此命令，AI 将帮助你进行上下文交接，确保上下文重置后能够无缝继续工作。

## 功能描述

当接近上下文限制时，进行工作交接：更新上下文文档、创建交接笔记、捕获关键信息，确保后续会话能够无缝继续工作。

## 支持的目录结构

此命令支持两种文档结构：

### 1. 规范驱动开发 (`docs/dev/{feature_name}/`)

```
docs/dev/{feature_name}/
├── {feature_name}-requirements.md    # 需求文档
├── {feature_name}-design.md          # 技术设计
├── {feature_name}-tasks.md           # 任务清单
├── {feature_name}-context.md         # 上下文记录 ← 更新此文件
└── {feature_name}-handover.md        # 交接笔记 ← 必要时创建
```

### 2. 快速规划 (`docs/dev-lite/{feature_name}/`)

```
docs/dev-lite/{feature_name}/
├── {feature_name}-plan.md      # 规划文档
├── {feature_name}-context.md   # 上下文 ← 更新此文件
└── {feature_name}-tasks.md     # 任务清单 ← 更新此文件
```

## 必需更新

### 1. 检测活跃工作

首先检查活跃文档：
- 扫描 `docs/dev/*/*-context.md` 查找规范驱动工作
- 扫描 `docs/dev-lite/*/*-context.md` 查找快速规划工作
- 识别需要更新的文档

### 2. 更新上下文文档

对于每个活跃任务，更新上下文文件：

**当前状态**：
- 实现进度百分比
- 已完成的部分、未完成的部分
- 当前阶段（规范驱动）

**本次会话决策**：
- 本次会话做出的关键决策
- 每个决策的理由
- 考虑过的备选方案

**修改的文件**：
| 日期 | 文件 | 修改内容 | 原因 |
|------|------|----------|------|
| ... | ... | ... | ... |

**阻塞/问题**：
- [ ] 问题描述 - 状态: {待解决|已解决}
  - 发现时间
  - 解决方案（如已解决）

**下一步立即行动**：
1. 具体行动 1
2. 具体行动 2

**最后更新时间戳**：YYYY-MM-DD HH:MM

### 3. 更新任务清单

对于 `{feature_name}-tasks.md`：
- 将已完成任务标记为 ✅
- 添加新发现的任务
- 更新进行中任务的当前状态
- 根据需要重新排序优先级

### 4. 创建交接笔记（如需要）

如果有重要工作正在进行，创建 `{feature_name}-handover.md`：

```markdown
# {Feature/Task Name} 交接笔记

> 创建时间: {YYYY-MM-DD HH:MM}

## 当前工作状态

### 正在进行的任务
- **任务**: [描述]
- **进度**: [百分比或描述]
- **正在编辑的文件**:
  - `path/to/file.py:123` - [正在做什么]

### 未提交的更改
检查 `git status` 输出

## 恢复工作步骤

1. 阅读 {feature_name}-context.md 了解背景
2. 查看 {feature_name}-tasks.md 了解任务状态
3. 运行验证命令确认环境正常
4. 继续从 [具体位置] 开始工作

## 验证命令

```bash
# 根据项目类型添加相关命令
pytest tests/ -v
npm test
make check
\```

## 注意事项
- [需要特别注意的点]
- [临时解决方案需要修复]
```

### 5. 捕获难以重新发现的信息

**优先级**：重点捕获从代码难以推断的信息：

- 解决的复杂问题及方法
- 架构决策及理由
- 发现并修复的棘手 bug
- 发现的集成点
- 有效/无效的测试方法
- 进行的性能优化
- 临时解决方案及原因

### 6. 更新记忆（如适用）

- 将新模式或解决方案存储到项目文档
- 更新发现的实体关系
- 添加关于系统行为的观察

## 输出格式

更新后报告：

```
已更新文档:
- docs/dev/{feature_name}/{feature_name}-context.md ✅ (规范驱动开发)
- docs/dev/{feature_name}/{feature_name}-tasks.md ✅
- docs/dev/{feature_name}/{feature_name}-handover.md ✅ (新建)

或

- docs/dev-lite/{feature_name}/{feature_name}-context.md ✅ (快速规划)
- docs/dev-lite/{feature_name}/{feature_name}-tasks.md ✅

下次恢复工作时:
1. 阅读 docs/dev/{feature_name}/{feature_name}-context.md 或 docs/dev-lite/{feature_name}/{feature_name}-context.md
2. 查看 docs/dev/{feature_name}/{feature_name}-tasks.md 或 docs/dev-lite/{feature_name}/{feature_name}-tasks.md
3. 运行 [验证命令]
```

## 相关命令

- `dev`: 完整规范驱动开发（阶段闸门 + TDD）
- `dev-lite`: 轻量级开发（探索性任务）
- `commit`: 提交当前更改


**最后更新**：2025-11-30 16:10:35
**维护者**：Development Team
**版本**：2.0.0
