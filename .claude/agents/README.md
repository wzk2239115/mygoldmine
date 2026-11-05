# 项目子代理

本目录是 mygoldmine 使用的 Claude Code 项目子代理。这里只维护本项目需要的职责、输入输出和边界；工具名、发现顺序、权限等通用规则以 Claude Code 官方文档为准，不在仓库里复制整份上游说明。

## 调用方式

- 显式调用：`@.claude/agents/security-orchestrator.md 审计当前项目`
- 指定 agent 启动：`claude --agent security-orchestrator`
- 由编排 agent 通过 `Agent` 工具启动子代理。
- 宿主机当前使用 `Claude Code 2.1.318`；工具名称以会话实际提供的列表为准。原生工作流通过 `Workflow` 工具执行，不能仅凭提示中的关键词判断是否启动。
- 子代理在独立上下文运行，只把最终结果返回主对话。

## 代理清单

### 编排与报告

| 代理 | 职责 | 主要输入 | 主要输出 |
|---|---|---|---|
| `security-orchestrator` | 判断项目类型，按 Web 或智能体基础设施路径分派扫描、验证和报告任务；项目画像后先做覆盖与假设规划，再安排有理由的复审 | 代码仓库、可选扫描器范围 | `.workspace/tasks/security-orchestrator-tasks.json`、覆盖与假设记录、审计报告 |
| `skill-runner` | 兼容入口：按旧任务格式加载并执行一个指定技能，返回后续任务推荐；安全审计默认技能加载已改用原生 Skill 工具 | `TASK_ID`、工作区文件、技能名 | `.workspace/tasks/<TASK_ID>/`、`summary.md`、任务 JSON |
| `report-generator` | 汇总上游结果，生成人工可读和机器可读报告 | 任务清单、候选问题与验证结果 | `.workspace/reports/audit-report.md|json` |

### 环境与验证

| 代理 | 职责 | 主要输入 | 主要输出 |
|---|---|---|---|
| `environment-builder` | 在第 0 阶段主导源码检测、环境构建、失败修复和运行验收；确定性构建脚本仅作为工具或备用方案 | 源码目录、构建模式、第 0 阶段环境变量 | `env/<project>/env-manifest.json`、镜像、构建日志 |
| `runner-builder` | 处理审计运行镜像的依赖缺失、解释器或命令问题；只更新受控运行依赖并执行镜像冒烟 | 结构化失败证据、运行依赖清单 | `runner-build.json`、新的运行镜像编号 |
| `verify-agent` | 对单条候选问题做最小化、非武器化验证 | 候选问题、环境镜像、源码 | `runs/<project>/verify/<id>/verify-report.md|json`、四态结论 |

### 基础设施分析

| 代理 | 职责 | 主要输入 | 主要输出 |
|---|---|---|---|
| `infra-analyst` | 使用原生 Grep、Glob 和 Skill 工具，按信任边界阅读源码，产出带 `file:line` 的候选问题和待核实假设 | 项目画像、信任边界、`recommended_skills`、覆盖记录、知识卡 | `.workspace/findings/infra-<boundary>.json|md`、覆盖记录更新 |
| `audit-skill-worker` | 在第 2、3 波按推荐技能和覆盖缺口加载传统分析技能，产出带证据的候选问题和覆盖更新 | 技能名、信任边界或覆盖缺口、项目画像、知识卡 | `.workspace/findings/` 中的候选问题、覆盖记录更新 |
| `hypothesis-critic` | 合并、去重、挑战证据，校准可达性和严重度 | `infra-*.json`、技能分析结果、知识卡、可选验证报告 | `.workspace/reports/findings.normalized.json`、审阅记录 |

### 红队与裁判

| 代理 | 职责 | 主要输入 | 主要输出 |
|---|---|---|---|
| `redteam-lab-builder` | 构建隔离的受害者与攻击者环境，设计只能通过目标漏洞获得的随机标记 | 候选问题、源码、环境清单 | `labs/<project>/<finding-id>/scenario.json`、隔离环境报告或 `BLOCKED.md` |
| `exploit-judge` | 独立审核红队轨迹和随机标记来源，排除作弊路径 | 轨迹、候选问题、结果、随机标记哈希 | `judge.json` |

### 知识、视觉与供应链

| 代理 | 职责 | 主要输入 | 主要输出 |
|---|---|---|---|
| `knowledge-scribe` | 把已验证经验写回知识库 | 归一化候选问题、验证报告、本次审计运行的元信息 | `knowledge/cases/`、项目知识卡、误报记录、CVE 卡片 |
| `mining-repair-learner` | 组合验证经验、作用域、证据和项目知识等技能，生成挖掘修复 | 带证据的种子候选、红蓝经验、相关技能与知识 | `rsi/mining-repairs/agentic/*.md`，不直接发布 |
| `stage-skill-learner` | 综合八阶段反馈并选择目标阶段；需要重写时提交 SkillOpt 请求 | 阶段反馈索引、覆盖记录、复审计划、验证与审核结果 | `rsi/stage-learning-run.json`、`rsi/skillopt-requests/*.json`，不直接发布 |
| `attack-scene-director` | 把候选问题设计成攻击场景插图；插图不作为证据 | 报告 JSON、视觉模型、可选验证报告 | 场景设计 JSON、绘图提示词、image2 插图 |
| `diff-auditor` | 审查单次提交的供应链风险；只读证据，不执行仓库代码 | 项目、提交哈希、仓库路径、静态报告 | `llm-audit.json` |

`diff-auditor` 依赖 `.claude/skills/supply-chain-diff-audit/`，并由 `scripts/watch/watch.py` 调用。

### 恢复

| 代理 | 职责 | 主要输入 | 主要输出 |
|---|---|---|---|
| `recovery-infra-worker` | 只处理一个指定信任边界的恢复任务 | 信任边界、知识卡、进度摘要 | 该边界的候选问题、待核实假设和覆盖情况 |
| `recovery-report-assembler` | 汇总已落盘产物，标明部分失败和未覆盖范围 | 输入目录、必要源码 | 完整报告与明确的缺口列表 |

## Frontmatter 约定

```markdown
---
name: example-agent
description: |
  一句话职责。
  Use when ...
model: inherit
tools: Read, Grep, Glob, Skill, Write
---
```

- `name` 使用小写字母和连字符，必须与文件名一致。
- `description` 写清职责和触发场景，避免空泛的“专家”描述。
- `model` 默认 `inherit`；只有需要更强推理的编排 agent 固定 `opus`。
- `tools` 使用当前工具名。读取源码和检索优先使用原生 `Grep`、`Glob`，加载技能使用原生 `Skill`；只有真正启动子代理的 agent 才加入 `Agent`，例如 `security-orchestrator`。
- `skill-runner` 仅保留为兼容入口，不再作为安全审计的默认技能加载器；安全审计由原生 `Skill` 工具实际加载传统分析技能。
- 不在 frontmatter 里写 `Task`；它只是旧别名。
- 任务管理命令统一由 `.claude/skills/task-manage/SKILL.md` 提供，不要在多个 agent 里重复维护完整命令表。

## 共同边界

- 只分析本地源码；除明确授权的模型和召回服务外不访问公网。
- 不写可直接武器化的 exploit，不写反弹 shell、持久化或横向移动代码。
- 不把静态命中、关键词命中或 image2 插图当成已验证漏洞。
- 不把 `partial`、`blocked`、`inconclusive` 写成 `ready` 或 `confirmed`。
- `environment-builder`、`runner-builder`、`verify-agent` 和红队隔离环境需要 Docker 权限，必须在宿主机或专用执行节点运行，不在审计容器内运行。
- `runner-builder` 只处理审计运行镜像，不接收目标项目依赖缺失或单个红队候选场景失败。
- 面向人的标题、摘要、影响和修复建议遵循 `docs/expression-guide.md`。

## 维护方式

- 新增、删除或重命名 agent 时，同步更新本页清单；如果改变了用户入口，也要同步根 `README.md`。
- 修改 agent 的输入输出、状态语义或安全边界时，检查 `docs/system-architecture.md` 是否需要更新。
- 上游规则变化时，直接链接官方文档，不在这里复制：
  - Tools reference: https://code.claude.com/docs/en/tools-reference
  - Subagents: https://code.claude.com/docs/en/sub-agents
  - Skills: https://code.claude.com/docs/en/skills
  - Hooks: https://code.claude.com/docs/en/hooks

`pipeline-coordinator` 使用 `pipeline-workflow` 技能和保存的原生工作流协调固定节点；候选选择与交付检查仍由现有执行器负责。

环境构建智能体通过持久任务执行长构建，使用读取、监测和指定任务停止工具；宿主机等待真实终态后再接续验收。节点协调只登记或查询任务，不在模型工具调用中长时间阻塞。
