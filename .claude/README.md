# Claude 工作区配置

本目录包含 Claude Code 的通用开发模板配置，可作为新项目的初始化基础。

## 目录结构

```
.claude/
├── config.json          # 工作区主配置（语言、规则、工作流）
├── settings.json        # Claude Code 权限和钩子配置
├── settings.local.json  # 本地覆盖配置
├── agents/              # 专用智能体（12个）
├── commands/            # 自定义斜杠命令（13个，与 Cursor 同步）
├── hooks/               # 自动化钩子脚本
└── skills/              # 可自动激活的技能模块（4个）
```

## 核心组件

### 智能体 (Agents) - 12个

通用开发智能体：

| 智能体 | 用途 |
|--------|------|
| `code-architecture-reviewer` | 代码架构和最佳实践审查 |
| `code-refactor-master` | 综合重构规划和执行 |
| `refactor-planner` | 重构策略制定 |
| `plan-reviewer` | 开发计划审查 |
| `documentation-architect` | 文档创建和更新 |
| `web-research-specialist` | 技术问题网络研究 |
| `auto-error-resolver` | TypeScript 编译错误自动修复 |
| `frontend-error-fixer` | 前端错误调试和修复 |

安全相关智能体：

| 智能体 | 用途 |
|--------|------|
| `security-auditor` | 代码漏洞审查、OWASP 合规 |
| `penetration-tester` | 渗透测试、红队操作 |
| `compliance-specialist` | 法规合规、审计准备 |
| `incident-responder` | 生产事故响应 |

调用方式：`"使用 [智能体名称] 智能体来 [任务]"`

### 命令 (Commands) - 13个（与 Cursor 同步）

| 命令 | 功能 |
|------|------|
| `/commit` | 生成规范化 Git 提交信息 |
| `/build-and-fix` | 自动构建并修复错误 |
| `/test-governance` | 测试治理和覆盖率分析 |
| `/test-fix` | 测试用例调试和修复 |
| `/code-review` | 代码架构审查 |
| `/code-refactor` | 代码结构重构 |
| `/project-init` | 项目初始化 |
| `/requirement-prd` | PRD 需求文档生成 |
| `/document-overview` | 仓库文档概览生成 |
| `/workflow-spec-driven` | 规格驱动开发流程 |
| `/dev-docs` | 开发计划文档生成 |
| `/dev-docs-update` | 开发文档更新 |
| `/security-audit` | 安全漏洞审计 |

### 技能 (Skills) - 4个

| 技能 | 用途 |
|------|------|
| `skill-developer` | 创建和管理 Claude Code 技能的元技能 |
| `backend-dev-guidelines` | Node.js/Express/TypeScript 后端开发模式 |
| `frontend-dev-guidelines` | React/TypeScript/MUI v7 前端开发模式 |
| `error-tracking` | Sentry 错误追踪和监控模式 |

技能触发规则配置在 `skills/skill-rules.json`。

### 钩子 (Hooks) - 2个核心钩子

| 钩子 | 触发时机 | 功能 |
|------|----------|------|
| `skill-activation-prompt.sh` | UserPromptSubmit | 根据提示词和文件上下文自动建议技能 |
| `post-tool-use-tracker.sh` | PostToolUse | 跟踪文件修改以维护上下文 |

## 配置说明

### settings.json

定义权限和钩子配置：
- 自动允许 Edit、Write、MultiEdit、NotebookEdit、Bash 工具
- 配置 MCP 服务器（mysql、sequential-thinking、playwright）
- 设置生命周期钩子

### config.json

定义工作区规则：
- 语言：简体中文
- 文档格式：Markdown
- 版本控制：语义化版本（1.0.md, 2.0.md）

## 使用方式

1. **技能**：根据编辑的文件和提示词内容自动激活
2. **智能体**：通过对话明确调用，如 "使用 security-auditor 智能体审查代码"
3. **命令**：在对话中输入 `/命令名` 调用，如 `/security-audit --full`
4. **钩子**：自动在对应生命周期执行，无需手动干预

## 作为模板使用

将 `.claude/` 目录复制到新项目即可使用。根据项目需要：
1. 修改 `skill-rules.json` 中的 `pathPatterns` 匹配项目结构
2. 按需添加或删除智能体
3. 调整 `settings.json` 中的 MCP 服务器配置

---

**让 AI 成为我们最好的编程伙伴！**
