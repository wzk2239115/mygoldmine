# Claude 安全分析工作区配置

本目录包含 Claude Code 的专用安全漏洞分析配置，提供完整的 OWASP TOP14 漏洞分析能力，适用于代码安全审计、漏洞研究和安全工具开发。

## 目录结构

```
.claude/
├── config.json          # 工作区主配置（语言、规则、工作流）
├── settings.json        # Claude Code 权限和钩子配置
├── settings.local.json  # 本地覆盖配置
├── agents/              # 专用智能体（4个安全分析智能体）
├── commands/            # 自定义斜杠命令（26个，与 Cursor 同步）
├── hooks/               # 自动化钩子脚本（3个核心钩子）
└── skills/              # 可自动激活的技能模块（20+个安全分析技能）
```

## 核心组件

### 智能体 (Agents) - 4个安全分析智能体

本工作区专注于安全漏洞分析，包含以下专用智能体：

| 智能体 | 用途 |
|--------|------|
| `security-orchestrator` | 安全分析总协调器（V2架构），协调项目画像、威胁建模、漏洞扫描和报告生成全流程 |
| `report-generator` | 安全报告生成器，生成详细的安全分析报告 |
| `skill-runner` | 技能运行器，管理和执行安全分析技能 |

调用方式：`"使用 [智能体名称] 智能体来 [任务]"` 或通过 Task 工具调用

### 命令 (Commands) - 26个（与 Cursor 同步）

包含完整的开发工作流命令，关键安全相关命令包括：

| 命令 | 功能 |
|------|------|
| `/security-audit [focus-area] | --full` | 执行全面的安全评估和漏洞分析 |
| `/build-and-fix [max-iterations]` | 自动检测项目类型，运行构建并迭代修复错误 |
| `/commit [scope]` | 生成规范化 Git 提交信息并执行提交 |
| `/code-review <file-path> | <directory> | --staged` | 全面的代码架构审查和质量评估 |
| `/test-fix <test-path> | --all | --middleware` | 调试和修复失败的测试用例 |
| `/project-init <project-name> [--type]` | 使用最佳实践和标准结构初始化新项目 |

其他命令支持开发、测试、文档、调试等完整工作流。

### 技能 (Skills) - 20+个安全分析技能

本工作区包含完整的安全漏洞分析技能集，基于 OWASP TOP14 漏洞分类：

**核心安全分析技能：**
- `web-auth-analyzer` - API认证与角色体系分析
- `project-profiler` - 项目画像构建
- `unauth-route-scanner` - 未授权API端点扫描
- `normal-route-scanner` - 普通用户路由扫描
- `route-deep-analyzer` - API端点深度分析
- `code-security-analyzer` - 代码安全分析
- `sensitive-info-scanner` - 敏感信息泄露审计
- `vtr-scanner` - 靶场类型识别
- `task-manage` - 任务管理工作流

**漏洞专项分析技能（来自 TOP14 子模块）：**
- `sql-injection-analyzer` - SQL注入分析
- `xss-analyzer` - 跨站脚本攻击分析
- `command-injection-analyzer` - 命令注入分析
- `path-traversal-lfi-rfi-analyzer` - 路径遍历和文件包含分析
- `csrf-analyzer` - 跨站请求伪造分析
- `ssrf-analyzer` - 服务器端请求伪造分析
- `xml-xpath-injection-analyzer` - XML/XPath注入分析
- `idor-analyzer` - 不安全的直接对象引用分析
- `insecure-file-uploads-analyzer` - 不安全文件上传分析
- `code-injection-analyzer` - 代码注入分析
- `ldap-injection-analyzer` - LDAP注入分析
- `http-header-injection-analyzer` - HTTP头注入分析
- `open-redirect-analyzer` - 开放重定向分析

技能通过 `.claude/skills/TOP14/` git 子模块集成，支持自动激活。

### 钩子 (Hooks) - 3个Python钩子

| 钩子 | 触发时机 | 功能 |
|------|----------|------|
| `operation-logger.py` | PostToolUse | 记录所有工具操作，包括工具类型、输入、输出和时间戳，支持stdout/stderr输出记录 |
| `protect-tasks-json.py` | PreToolUse | 保护tasks.json文件不被意外修改 |
| `security-orchestrator-stop.py` | 手动调用 | 安全分析流程停止控制 |

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

### 安全漏洞分析工作流

1. **启动安全分析**：使用 `/security-audit --full` 命令执行完整安全评估
2. **项目分析**：智能体自动进行项目画像、威胁建模和漏洞扫描
3. **专项分析**：根据项目类型自动激活相应的安全分析技能
4. **报告生成**：自动生成详细的安全分析报告

### 组件调用方式

1. **技能**：根据项目文件和上下文自动激活相应的安全分析技能
2. **智能体**：通过 Task 工具调用或明确指令，如 "使用 security-orchestrator 智能体分析项目"
3. **命令**：在对话中输入 `/命令名` 调用，如 `/security-audit --full` 执行全面安全审计
4. **钩子**：自动记录操作日志、保护任务文件和控制分析流程

## 作为安全分析模板使用

本配置已专门化为安全漏洞分析工作区，适用于：

1. **代码安全审计项目**：直接使用现有配置进行安全分析
2. **安全工具开发**：基于现有技能和智能体扩展安全分析能力
3. **安全研究环境**：利用完整的漏洞分析技能集进行研究

### 自定义配置

将 `.claude/` 目录复制到新项目后，根据安全分析需求：
1. 调整 `settings.json` 中的权限和 MCP 服务器配置
2. 根据需要添加或修改安全分析技能
3. 更新智能体配置以适应特定的安全分析场景
4. 确保 `.claude/skills/TOP14/` 子模块正确初始化

---

**让 AI 成为我们最好的编程伙伴！**
