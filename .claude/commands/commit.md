---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Generate conventional commit message and execute git commit
argument-hint: [optional: commit scope or type hint]
---


# Git Commit 命令

> 遵循 Conventional Commits 规范的 Git 提交命令

## 使用方式

### Claude Code
在 Claude Code 中通过命令面板（`Cmd+Shift+P` / `Ctrl+Shift+P`）或快捷键调用此命令。

### Claude Code
在 Claude Code 中通过斜杠命令 `/commit` 或参数提示调用此命令。

### 功能
AI 将帮助你：

1. **分析当前更改**：自动识别修改的文件和变更类型
2. **生成提交信息**：根据变更内容生成符合 Conventional Commits 规范的提交信息
3. **执行提交**：确认后自动执行 `git add` 和 `git commit`

### 当前状态检查
命令会自动检查：
- Git 状态：`git status --short`
- 已暂存更改：`git diff --cached --stat`
- 未暂存更改：`git diff --stat`
- 最近提交：`git log --oneline -5`

## Commit 规范

### 提交类型（Type）

- `feat`: 新功能
- `fix`: 问题修复
- `refactor`: 重构（不改变功能）
- `docs`: 文档更新
- `test`: 测试相关
- `chore`: 备份/杂项/工具配置
- `style`: 代码格式调整（不影响代码运行）
- `perf`: 性能优化

### 提交格式

```text
<type>: <subject>

[optional body]

[optional footer]
```

### 提交信息要求

- **主题行（Subject）**：
  - 简洁明了（建议 50 字符以内）
  - 使用祈使语气（"添加" 而非 "已添加"）
  - 聚焦 "为什么" 而非 "做了什么"
- **正文（Body）**（可选）：
  - 详细说明变更原因和影响
  - 复杂变更建议包含详细说明
- **页脚（Footer）**（可选）：
  - 关联 Issue：`Closes #123`
  - 破坏性变更：`BREAKING CHANGE: 描述`

### 示例

```bash
# 新功能
feat: 添加用户登录功能

# 问题修复
fix: 修复登录页面验证码不显示的问题

# 文档更新
docs: 更新 README 中的快速开始指南

# 重构
refactor: 重构用户认证模块，提取公共方法

# 测试
test: 添加用户登录功能的单元测试

# 备份
chore: 备份功能实施前状态 - 20241201-1430
```

## 工作流程

1. **检查更改**：
   - 检查 `git status` 查看所有修改的文件
   - 检查 `git diff` 查看未暂存的更改
   - 检查 `git diff --cached` 查看已暂存的更改
   - 理解变更的性质和目的

2. **确定提交类型**：
   - 根据修改的文件类型和内容判断提交类型
   - 参考上述提交类型列表

3. **生成提交信息**：
   - 格式：`<type>: <subject>`
   - 主题简洁（50 字符以内）
   - 使用祈使语气
   - 聚焦变更原因

4. **用户确认**：
   - 显示生成的提交信息
   - 等待用户确认或修改
   - 对于复杂变更，可添加详细正文

5. **执行提交**：
   - 使用 `git add` 暂存相关文件
   - 使用 `git commit` 执行提交
   - 验证提交是否成功

## 注意事项

### 提交前检查
- ✅ 确保代码已通过必要的检查（lint、测试等）
- ✅ 提交信息应清晰描述变更内容
- ✅ 遵循项目的分支管理策略
- ✅ 对于复杂变更，建议在 body 中详细说明

### 安全提醒
- ⚠️ **不要提交包含敏感信息的文件**（`.env`、`credentials.json`、密钥文件等）
- ⚠️ 检查 `.gitignore` 确保敏感文件已被排除
- ⚠️ 提交前检查是否有硬编码的密码、API 密钥等

### 最佳实践
- 每个提交只包含一个逻辑变更（原子性提交）
- 提交信息使用中文，清晰描述变更
- 复杂功能分多次提交，便于代码审查和回滚

## 后悔药机制（重要）

**随时存档，git commit 是你的后悔药**

### 核心原则
每次 AI 助手（Claude/Claude Code）完成一个独立的小任务，立刻 git commit 保存当前状态。万一后续出现 Bug，可以轻松回溯，避免大量的返工和 Token 浪费。

### 提交时机
在以下情况**必须**执行 git commit：
1. ✅ **每个独立小任务完成后** - 功能点、修复、重构等
2. ✅ **每个阶段验收通过后** - 需求、设计、实现、测试各阶段
3. ✅ **重要决策点** - 架构变更、技术选型确定后
4. ✅ **可工作的中间状态** - 即使功能未完全完成，但当前状态可运行

### 提交策略
- **原子性提交**：每个提交只包含一个逻辑变更
- **清晰描述**：提交信息要能清楚说明本次变更
- **可回溯性**：确保每个提交都是可回退的稳定状态
- **节省 Token**：通过频繁提交，避免大范围返工

### 回溯示例
```bash
# 查看提交历史
git log --oneline

# 查看提交详情
git show <commit-hash>

# 回退到上一个稳定状态（只读，不修改工作区）
git checkout <commit-hash>

# 或创建新分支继续修复
git checkout -b fix/issue-name <commit-hash>

# 软回退（保留更改）
git reset --soft <commit-hash>

# 硬回退（丢弃更改，谨慎使用）
git reset --hard <commit-hash>
```

## 相关命令

### Git 命令
- `git status`: 查看 Git 状态
- `git diff`: 查看具体变更内容
- `git log`: 查看提交历史
- `git show`: 查看提交详情

### Claude Code/Claude 命令
- `code.review`: 代码审查
- `code.refactor`: 代码重构
- `test.governance`: 测试治理

------

**最后更新**: 2025-11-30 16:10:35
**维护者**: Documentation Team
**版本**: 1.0.0
