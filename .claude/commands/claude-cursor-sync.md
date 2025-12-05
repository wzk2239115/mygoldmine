---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Sync configurations between Claude and Cursor platforms
argument-hint: 
---


# Claude 和 Claude Code 配置同步

> 在 Claude 和 Claude Code 平台之间同步配置，支持双向同步

## 任务

执行配置同步，支持：
- **正向同步**：
  - 命令配置：将 `.ai-config/commands/` 中的源配置同步到 `.claude/commands/` 和 `.cursor/commands/`
  - Hooks 配置：将 `.claude/hooks/` 中的配置同步到 `.cursor/hooks/`
  - Skills 配置：将 `.claude/skills/` 中的配置同步到 `.cursor/skills/`
- **反向同步**：检测并同步目标配置的变更回源文件

## 当前支持的配置类型

- **命令配置** (`.ai-config/commands/` → `.claude/commands/` 和 `.cursor/commands/`)
  - 支持双向同步
  - 自动处理平台差异（frontmatter、占位符等）

- **Hooks 配置** (`.claude/hooks/` → `.cursor/hooks/`)
  - 支持双向同步
  - 自动处理环境变量替换（`CLAUDE_PROJECT_DIR` → `CURSOR_PROJECT_DIR`）
  - 自动处理路径替换（`.claude/` → `.cursor/`）
  - 保持文件可执行权限

- **Skills 配置** (`.claude/skills/` → `.cursor/skills/`)
  - 支持双向同步
  - 递归同步整个目录结构
  - 自动处理环境变量替换（`CLAUDE_PROJECT_DIR` → `CURSOR_PROJECT_DIR`）
  - 自动处理路径替换（`.claude/` → `.cursor/`）
  - 保持文件可执行权限

## 未来计划

未来将支持更多配置类型的同步：
- `mcp.json` - MCP 服务器配置
- `commands.json` - Claude Code 命令配置
- 其他共享配置文件

## 执行步骤

### 1. 运行同步脚本

**智能同步（默认）**：
```bash
./.ai-config/claude-cursor-sync.sh
```

脚本会智能执行：
1. **优先检测反向同步**：检查 `.claude/commands/`、`.cursor/commands/`、`.cursor/hooks/` 和 `.cursor/skills/` 是否有变更
   - 如果同一个命令文件在 `.claude/` 和 `.cursor/` 中都有变更，会分别检测并分别列出
2. **处理反向同步**：如有变更，询问是否先同步回源文件（推荐选择 Y）
   - 如果同一文件在两个平台都有变更，会按顺序同步（后同步的会覆盖先同步的）
   - **建议**：如果同一文件在两个平台都有变更，建议先手动合并后再同步
3. **执行正向同步**：将源配置同步到目标配置
   - 命令配置：`.ai-config/commands/` → `.claude/commands/` 和 `.cursor/commands/`
   - Hooks 配置：`.claude/hooks/` → `.cursor/hooks/`
   - Skills 配置：`.claude/skills/` → `.cursor/skills/`

这样可以确保：
- 目标文件的变更不会丢失
- 源文件始终是最新的单一真相源
- 避免覆盖目标文件的手动修改

**仅检测反向同步**：
```bash
./.ai-config/claude-cursor-sync.sh --check-reverse
```

仅检测以下目录中的配置是否有变更，不执行正向同步：
- `.claude/commands/` - Claude 命令配置
- `.cursor/commands/` - Cursor 命令配置
- `.cursor/hooks/` - Cursor Hooks 配置（与 `.claude/hooks/` 对比）
- `.cursor/skills/` - Cursor Skills 配置（与 `.claude/skills/` 对比）

**注意**：如果同一个命令文件在 `.claude/` 和 `.cursor/` 中都有变更，会分别检测并分别列出。

### 2. 智能同步流程

**同步优先级**：
1. **反向同步优先**：脚本会先检测目标文件的变更，优先处理反向同步
2. **正向同步随后**：反向同步完成后（或没有变更时），执行正向同步

**如果在目标目录中修改了文件**：

如果在 `.claude/` 或 `.cursor/` 中直接修改了配置文件：

1. **自动检测**：运行同步时，脚本会**首先**检测目标配置的变更
2. **智能提示**：检测到变更后，默认询问是否同步回源文件（推荐选择 Y）
3. **手动检测**：运行 `./.ai-config/claude-cursor-sync.sh --check-reverse` 仅检测变更

**反向同步处理逻辑**：
- **命令配置**：
  - Claude 版本：自动移除 frontmatter（YAML 格式的 `---` 块）
  - Claude Code 版本：直接使用（无 frontmatter）
  - 自动还原占位符：将平台特定值（如 `Claude Code` 或 `Cursor`）还原为 `Claude Code`，将规则路径还原为 ``CLAUDE.md` 和 `.claude/` 目录`
  - **冲突处理**：如果同一个文件在 `.claude/` 和 `.cursor/` 中都有变更，脚本会分别检测并分别同步。**注意**：后同步的版本会覆盖先同步的版本，建议先手动合并冲突后再同步
- **Hooks 配置**：
  - 自动还原环境变量：`CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}` → `CLAUDE_PROJECT_DIR:-$(pwd)`
  - 自动还原路径：`.cursor/` → `.claude/`
  - 保持文件可执行权限
- **Skills 配置**：
  - 自动还原环境变量：`CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}` → `CLAUDE_PROJECT_DIR:-$(pwd)`
  - 自动还原路径：`.cursor/` → `.claude/`
  - 递归同步整个目录结构
  - 保持文件可执行权限

**注意**：修改目标配置后，务必同步回源文件，以保持配置的一致性。

### 3. 验证同步结果

检查关键文件是否正确生成：

```bash
# 检查 Claude 版本（应有 frontmatter）
head -10 .claude/commands/dev.md

# 检查 Claude Code 版本（无 frontmatter）
head -5 .cursor/commands/dev.md
```

### 4. 报告结果

同步完成后，报告：
- 同步的文件数量
- 是否有错误
- 反向同步的变更（如有）
- 建议的下一步（如：提交更改）

## 平台差异说明

| 项目 | Claude | Claude Code |
|------|--------|--------|
| Frontmatter | 自动添加 `allowed-tools`, `description`, `argument-hint` | 无 |
| `Claude Code` | Claude Code | Claude Code |
| ``CLAUDE.md` 和 `.claude/` 目录` | `CLAUDE.md` 和 `.claude/` 目录 | `CLAUDE.md` 和 `.claude/` 目录 |

## 常见问题

### 如果脚本执行失败

手动检查：
1. `.ai-config/commands/` 目录是否存在（命令配置源目录）
2. `.claude/hooks/` 目录是否存在（hooks 配置源目录）
3. `.claude/skills/` 目录是否存在（skills 配置源目录）
4. 源文件是否有语法错误
5. 目标目录权限是否正确
6. 脚本是否有执行权限：`chmod +x ./.ai-config/claude-cursor-sync.sh`

### 如果同一文件在两个平台都有变更

如果检测到同一个命令文件（如 `dev.md`）在 `.claude/commands/` 和 `.cursor/commands/` 中都有变更：

1. **脚本行为**：脚本会分别检测并分别同步，后同步的版本会覆盖先同步的版本
2. **推荐做法**：
   - 先手动比较两个版本的差异
   - 手动合并冲突内容
   - 将合并后的内容写入源文件（`.ai-config/commands/`）
   - 运行正向同步，确保两个平台版本一致

### 如果需要添加新命令

1. 在 `.ai-config/commands/` 创建新的 `.md` 文件
2. 使用 `Claude Code` 和 ``CLAUDE.md` 和 `.claude/` 目录` 占位符
3. 在 `.ai-config/claude-cursor-sync.sh` 的 `get_description()` 和 `get_argument_hint()` 函数中添加对应的 description 和 argument-hint
4. 运行同步脚本：`./.ai-config/claude-cursor-sync.sh`

### 如果需要添加新 Hook

1. 在 `.claude/hooks/` 创建新的 hook 文件（`.sh`, `.py`, `.ts` 等）
2. 使用 `CLAUDE_PROJECT_DIR` 环境变量和 `.claude/` 路径
3. 运行同步，脚本会自动：
   - 将 `CLAUDE_PROJECT_DIR` 替换为 `CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}`
   - 将 `.claude/` 路径替换为 `.cursor/`
   - 保持文件可执行权限
4. 如需反向同步，修改 `.cursor/hooks/` 中的文件后运行同步即可

### 如果需要添加新 Skill

1. 在 `.claude/skills/` 创建新的 skill 目录和文件
2. 使用 `CLAUDE_PROJECT_DIR` 环境变量和 `.claude/` 路径
3. 运行同步，脚本会自动：
   - 递归同步整个目录结构
   - 将 `CLAUDE_PROJECT_DIR` 替换为 `CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}`
   - 将 `.claude/` 路径替换为 `.cursor/`
   - 保持文件可执行权限
4. 如需反向同步，修改 `.cursor/skills/` 中的文件后运行同步即可


## 使用示例

### 示例 1：智能同步（无变更）

```bash
$ ./.ai-config/claude-cursor-sync.sh

[INFO] 检测反向同步需求...

[INFO] 未检测到目标文件的变更

[INFO] 开始正向同步命令配置...
[INFO] 源目录: /path/to/.ai-config/commands
[INFO] 目标: /path/to/.claude/commands, /path/to/.cursor/commands

  → dev.md (Claude)
  → dev.md (Claude Code)
  ...

[INFO] 正向同步完成！共处理 15 个命令文件
```

### 示例 2：检测到反向同步需求（优先处理）

```bash
$ ./.ai-config/claude-cursor-sync.sh

[INFO] 检测反向同步需求...

[WARN] 检测到以下文件在目标目录中被修改：

  - test-governance.md (Claude)
  - dev.md (Claude Code)
  - hooks/post-tool-use-tracker.sh (cursor)
  - skills/skill-rules.json (cursor)
  - skills/backend-dev-guidelines/SKILL.md (cursor)

检测到目标文件有变更，是否先同步回源文件？(Y/n): y

[INFO] 开始反向同步...
  ← test-governance.md (从 claude 同步回源文件)
  ← dev.md (从 cursor 同步回源文件)

[INFO] 开始反向同步 hooks...
  ← post-tool-use-tracker.sh (Hook ← Cursor)

[INFO] 开始反向同步 skills...
  ← skill-rules.json (Skill ← Cursor)
  ← backend-dev-guidelines/SKILL.md (Skill ← Cursor)

[INFO] 反向同步完成！
[INFO] 反向同步已完成，源文件已更新

[INFO] 开始正向同步命令配置...
[INFO] 源目录: /path/to/.ai-config/commands
[INFO] 目标: /path/to/.claude/commands, /path/to/.cursor/commands

  → dev.md (Claude)
  → dev.md (Claude Code)
  ...

[INFO] 正向同步完成！共处理 15 个命令文件

[INFO] 开始正向同步 hooks 配置...
[INFO] 源目录: /path/to/.claude/hooks
[INFO] 目标: /path/to/.cursor/hooks

  → post-tool-use-tracker.sh (Hook → Cursor)
  → skill-activation-prompt.sh (Hook → Cursor)
  ...

[INFO] Hooks 正向同步完成！共处理 8 个 hook 文件

[INFO] 开始正向同步 skills 配置...
[INFO] 源目录: /path/to/.claude/skills
[INFO] 目标: /path/to/.cursor/skills

[INFO] Skills 正向同步完成！共处理 45 个文件
```

### 示例 3：仅检测反向同步

```bash
$ ./.ai-config/claude-cursor-sync.sh --check-reverse

[INFO] 检测反向同步需求...

[WARN] 检测到以下文件在目标目录中被修改：

  - test-fix.md (Claude)

检测到目标文件有变更，是否先同步回源文件？(Y/n): y

[INFO] 开始反向同步...
  ← test-fix.md (从 claude 同步回源文件)

[INFO] 反向同步完成！
```

**注意**：`--check-reverse` 模式下，如果检测到变更，仍会询问是否执行反向同步。如果选择不执行，脚本会直接退出，不执行正向同步。


**最后更新**: 2025-11-30 16:10:35
**维护者**: Configuration Team
**版本**: 1.0.0
