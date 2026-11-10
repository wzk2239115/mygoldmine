---
name: audit-coverage-planner
description: 规划审计覆盖与待验证假设。用于在项目画像后识别入口、危险操作、信任边界、权限和配置条件，生成可核实的覆盖记录、假设清单和下一批任务；不把读过文件当成已覆盖，不把未发现漏洞当成安全。
---

# 审计覆盖规划

## 何时使用

- `security-orchestrator` 完成项目画像后，分派边界分析之前。
- AI 基础设施、Web、智能合约或靶场项目都可以使用；已有知识卡和 Jev 初筛时优先读取。
- 需要复审旧区域，或有新源码、新调用方、新检查视角、新技能版本、新验证条件时。

## 提前退出

- 没有可读的项目画像、源码目录或审计报告时，记录缺失原因并退出；不要凭空生成覆盖结论。
- 当前任务预算已用完，或已有暂停标记 `.workspace/findings/.coverage-paused` 时，只保存当前记录，不新增任务。
- 只有目录清单、没有源码访问能力时，只记录入口线索，状态写 `unchecked`。

## 输入

- 项目画像：`.workspace/tasks/<PROFILE_TASK_ID>/project-profile.json` 或 `project-profile.md`
- 知识卡：`knowledge/project-types/`、`knowledge/projects/`、`knowledge/false-positives/README.md`
- 已发布技能规则：`.claude/skills/rsi-shared-experience/rules/index.json`、`knowledge/project-rules/<project>/index.json`
- 可选初筛：`triage/jev-infra.json`，只用于安排阅读顺序，不是候选问题
- 已有记录：`.workspace/findings/coverage-ledger.json`、`.workspace/findings/hypotheses/`
- 历史反馈：`rsi/stage-feedback/index.json`、已发布阶段技能版本

## 步骤

1. 读取画像和知识卡，列出已识别入口、危险操作、信任边界、权限条件和配置开关。只写有路径或明确识别依据的条目。
2. 为每个代码区域或入口建立覆盖条目，至少记录：
   - 项目与源码版本；
   - 代码区域或入口；
   - 检查视角；
   - 待验证假设；
   - 已有证据与缺失证据；
   - 历史尝试；
   - 下一步动作；
   - 所用技能名称与 `SKILL.md` 的 SHA-256；
   - 结论与限制。

   技能版本只记录实际加载过的技能。没有加载技能时，在该条目的 `warnings` 中写缺失原因，状态保持 `unchecked` 或 `needs_evidence`，不得写成 `analyzed`。
3. 状态只能使用以下六种：
   - `unchecked`：尚未检查
   - `analyzed`：已分析但未确认
   - `needs_evidence`：待补证据
   - `blocked`：执行受阻
   - `counterevidence`：已有反证
   - `runtime_confirmed`：运行确认
4. 区分“已分析”和“已覆盖”。读过文件、运行过扫描器或调用过技能都不等于覆盖完成；只有证据和结论都记录后才改变状态。技能未加载、提前退出或只读取了目录时，写入 `warnings` 并保留原状态，不写完成。
5. 写入 `.workspace/findings/coverage-ledger.json`，再运行：
   ```bash
   python3 "$MYGOLDMINE_HOME/scripts/audit/coverage_ledger.py" validate \
     --ledger .workspace/findings/coverage-ledger.json
   python3 "$MYGOLDMINE_HOME/scripts/audit/coverage_ledger.py" plan \
     --ledger .workspace/findings/coverage-ledger.json \
     --out .workspace/findings/coverage-plan.json
   ```
6. 按计划推荐任务。优先顺序由脚本计算，信号包括：
   - 未覆盖的高风险入口与条件组合；
   - 待补证据数量和缺失证据类型；
   - 已有反证与运行确认的分布；
   - 历史复审是否带来新证据；
   - 独立保留样例上的漏检或误报记录（只有存在可信标签时使用）。
7. 每次选择任务时写明原因：为什么这次先看这里，哪些信号改变了优先级。不能只用候选数量、读取行数、调用链长度、思考轮数或模型自评分排序。
8. 把计划中的任务交给编排器；由编排器用 `add-task`/`add-tasks` 写入 `security-orchestrator-tasks.json`，不要自行执行边界分析。

## 波次规则

- 每波最多 6 个分析任务；总波次最多 3 波；本次审计运行的分析任务总数最多 18 个。达到任一上限时，保存当前记录并写暂停标记 `.workspace/findings/.coverage-paused`，不再追加任务。
- 任务数是预算上限，不是目标配额。按实际入口、信任边界、风险信号和调用链依赖分配；不得为了凑满每波数量而把同一条调用链拆成重复任务，也不得因为仓库很大就平均抽取少量目录后宣称覆盖。仓库规模超出预算时，优先覆盖高风险且可达的入口，并将其余区域明确保留为 `unchecked`/`needs_evidence`。
- 第一波优先做基础设施信任边界深挖，交给基础设施分析智能体（`infra-analyst`）。后续波次读取上一波结果，按项目画像的推荐技能（`recommended_skills`）、未覆盖高风险入口和待补证据条目生成任务。
- 负责源码分析并产出证据/假设的技能任务交给 `audit-skill-worker`，由它用原生技能加载方式执行；按技能说明中的适用范围、所需输入、分析职责和输出契约判断，不以技能名称或后缀分类。基础设施分析智能体只负责基础设施信任边界深挖，不与同一入口、调用链和检查视角的技能任务重复。
- 选择顺序如下：
  1. 项目画像的推荐技能中，已有明确入口、调用方或配置条件的任务；
  2. 尚未覆盖的高风险入口、信任边界和配置条件；
  3. 状态为 `needs_evidence` 且缺失证据类型明确的任务；
  4. 已有反证或运行确认后暴露出的相邻缺口。
- 没有对应入口、调用方或配置条件的技能不安排任务，并在 `warnings` 中记录“缺少入口，跳过 <技能名>”。不要因为项目类型命中就无条件加载技能。
- coverage 任务去重只用于避免重复派工：同一源码版本下，区域、检查视角、待验证假设和技能版本均相同才视为重复任务；记录 `dedup_key`、`dedup_reason` 和跳过原因。该任务键不用于合并漏洞候选或判定两个候选是同一漏洞，候选归并遵循 `hypothesis-critic` 的漏洞身份规则。
- 每波结束都更新覆盖记录；上一波没有新证据时，下一波只能来自仍未覆盖的入口或预算内的随机复查。
- 任务交接必须携带已确认的入口、调用链和依赖关系、相关证据及 `file:line`、已检查的视角、明确反证/防护、尚缺证据、覆盖条目 ID 和已尝试动作。接收任务的 worker 应复用这些事实并指出自己的新增检查；不能把上游假设当成事实，也不能因不同 worker 使用不同 Skill 而丢失上下文。
- 波次停止或预算耗尽时，逐条列出仍未解决的高风险假设及缺失证据，并保留 `needs_evidence` 或 `blocked` 状态。只有完成了约定检查、记录证据和结论的范围才能记为已分析；被跳过、失败或预算截断的范围不得记作已覆盖或安全。

## 覆盖记录要求

- `skill_versions` 必须写入实际加载过的技能名与对应 `SKILL.md` 的 SHA-256；未加载技能时只写 `warnings`，不写完成。
- 结论只描述已识别范围和限制，不写“全仓库已覆盖”，也没有可信标签时不写“真实召回率”。

## 输出

- `.workspace/findings/coverage-ledger.json`：覆盖与假设记录
- `.workspace/findings/coverage-plan.json` 和 `.md`：排序后的下一批任务
- `.workspace/findings/hypotheses/<COVERAGE_ID>.md`：由后续追踪技能补齐
- 推荐任务 JSON：`wave`、`coverage_id`、`skill`、`artifact`、`reason`、`priority`、`dedup_key`、`expected_evidence`、`status`

记录格式和评分规则见 [references/ledger-schema.md](references/ledger-schema.md)。

## 限制

- 没有完整分母时只报告已识别范围，不声称全仓库覆盖率。
- 没有可信标签时不计算真实召回率。
- 未发现漏洞不等于安全；环境受阻不等于误报。
- 不把静态命中、扫描器数量或读取文件数当成候选问题或效果证明。
- 波次和任务数量上限用于控制预算，不代表剩余区域已经安全。

## 交接

- 传统分析技能任务交给传统分析任务执行者（`audit-skill-worker`），由它按任务描述加载对应技能。
- 基础设施信任边界深挖交给基础设施分析智能体（`infra-analyst`）。
- 高风险或待补证据条目交给 `audit-hypothesis-tracer` 深入追踪。
- 合并、去重和可达性校准交给 `hypothesis-critic`。
- 需要复审时交给 `audit-review-planner`，由它记录复审原因和预算。
- 结束前把记录和计划作为证据交给 `stage-skill-learning`，只提交技能候选，不自行发布。


## 阶段二实际读取旁证

阶段二启用读取采集后，每波规划前运行下面的命令，读取 .workspace/findings/read-coverage/summary.json：

    python3 "$MYGOLDMINE_HOME/scripts/audit/read_coverage.py" summary

以其中的文件、实际返回行范围、源码摘要、审计意图和覆盖编号关联现有条目。不同意图检查同一代码分别保留；优先补未检查区域、未检查视角和缺失证据。没有数据、搜索命中、未关联意图、未知范围和采集异常都不能推定为审计完成。该文件没有全仓库分母，不计算全仓库覆盖率；模型不得改写原始观测。
