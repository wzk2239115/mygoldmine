# 系统架构说明

面向开发人员。目标是把“静态审计 → 自动分类 → 动态验收 → 人工展示”做成一条可运行、可审计、可回放的流水线。

## 1. 设计目标

- 候选问题（finding）不直接推给人；先自动评分、去重和路由。
- 只有进入待验收状态的条目才需要人工阅读。
- 待验收必须同时满足：红队实际捕获随机标记（flag）、独立审核（judge）通过、图文报告已生成。
- 每条自动决策和每次验证都留下执行轨迹，供 RSI 回放和策略优化。
- 所有攻击只在隔离环境内进行，随机标记每轮重新生成，攻击者容器不能直接接触标记文件。

非目标：

- 不把“自动归档”当成“确认安全”。
- 不把 AI 插图当漏洞证据。
- 不对公网或未授权目标运行红队。

## 2. 端到端数据流

```text
┌──────────────┐     high/critical     ┌────────────┐
│ watch 轮询    │ ───────────────────▶ │ dispatch   │
│ 分支/commit   │                      │ 绑定身份   │
└──────┬───────┘                      └─────┬──────┘
       │ 其他风险                             │ 自动派发
       └──────────────┐                       ▼
┌──────────────┐       │                ┌──────────────┐
│ 目标源码/镜像 │ ◀─────┴────────────────│ run.sh       │
└──────┬───────┘                         └──────────────┘
       │ run.sh / mine_one / overnight
       ▼
┌──────────────────┐
│ 静态审计报告       │  runs/<project>/<run>/audit-report.json
│ + coverage/证据    │
└──────┬───────────┘
       │ finding_ledger.py（仅完整有效 run）
       ▼
┌──────────────────┐
│ 发现记录表         │  单次编号 / 跨轮同一问题归并
│ 多轮审计历史记录   │  finding-ledger.json
└──────┬───────────┘
       │ build_state.py
       ▼
┌──────────────────┐
│ 自动评分/路由      │  auto-state.json
│ 去重/归档/分诊     │
└──────┬───────────┘
       │ refine_worker.py（后台分批）
       ▼
┌──────────────────┐
│ 自动分类状态       │  refine-state.json / refine-queue.json
│ 分诊/待验证/归档   │
└──────┬───────────┘
       │ flow_worker.py（消费 triage/reproduce）
       ▼
┌──────────────────┐
│ 自动流转状态       │  flow-state.json / flow-queue.json
│ verify / red-team │
└──────┬───────────┘
       │ 候选
       ▼
┌──────────────────┐     ┌────────────────────┐
│ verify-agent      │────▶│ verify-report.json │
│ 静态/环境验证      │     └────────────────────┘
└──────┬───────────┘
       │ 候选 + 图文素材
       ▼
┌──────────────────┐     ┌────────────────────┐
│ red-team lab      │────▶│ flag + trace       │
│ victim/attacker   │     │ agent.jsonl        │
└──────┬───────────┘     └────────────────────┘
       │
       ▼
┌──────────────────┐
│ exploit-judge     │  judge.json: approved / rejected
└──────┬───────────┘
       │ approved + report-illustrated.md + scene.webp
       ▼
┌──────────────────┐
│ 待验收 / 人工验收   │  review queue
└──────────────────┘
```

### 批量审计过程设计

批量审计阶段负责产生**可追溯的静态候选**，不直接把模型结论当作已验证漏洞。执行链如下：

| 阶段 | 设计与职责 | 关键产物/边界 |
|---|---|---|
| 选择项目并批量审计 | 看板通过 `POST /api/targets/github-branches` 读取公开仓库的分支引用，只下载当前页分支的提交对象并在页内按提交时间排序，分别标记默认分支和本页最新分支，接口每页最多返回 50 条、默认返回 10 条，分支列表与页面结果使用短时缓存；通过 `GET /api/targets/browse` 为本地目录选择器列出服务器可见子目录，再通过 `POST /api/targets/import` 导入公开 GitHub 仓库或服务器本地目录，登记 `ui/data/projects.json` 与 `targets/manifest.json` 后调用 `run.sh` 完整流程；项目清单记录项目名称、源码位置和版本。批量模式由 `parallel_mine.sh` 控制并发和失败重试，`overnight.sh` 提供后台启动、状态查看、停止和恢复；每个项目使用独立审计目录 | GitHub 仅接受公开 HTTPS 地址，分支查询通过 `tree:0` 过滤只读取提交对象，不下载目录树和源码，临时目录在结束后删除；目录浏览不读取文件内容；已有目录不强制更新，已有实时审计的项目不能重复启动。已有完整成功报告的项目默认跳过；批量运行状态与项目产物分离 |
| 持久项目沙箱 | `sandbox.sh` 为每次审计运行启动独立容器，源码只读挂载到 `/target`，批量审计和交互命令行复用 `/workspace/repo`；主流程 `verify-agent` 默认用独立断网容器 | 不挂载 Docker 套接字，启用 `cap-drop ALL` 和 `no-new-privileges`；密钥不写入沙箱状态 |
| 整理审计线索并拆分任务 | Jev 为代码块生成 0 到 1 的优先检查分数（priority）、达到阈值的风险信号（flags）和已有防护措施（mitigations）；`security-orchestrator` 再结合项目结构与攻击面拆分检查任务 | 这些信息只用于安排检查顺序，不直接生成候选问题；除模型 API 和指定初筛服务外不访问公网 |
| 增量报告 | 审计开始即创建报告骨架，每个子任务完成后增量更新；候选问题必须带文件与行号、根因、影响、复现思路和修复建议 | `raw.jsonl` 保留真实动作流，`claude.rendered.log` 供人阅读，`audit-report.md/json` 保存结论 |
| 质量与运行状态 | `check_report.py` 检查固定结构、必填字段和系统语言；`run-meta.json` 记录尝试次数、退出码、超时、中断和 `reports_complete` | 模型正常退出但报告不合格仍算失败；草稿和质量不合格报告不发布到发现记录表 |
| 总时限与恢复 | 所有尝试和重试共享总时间预算；`progress_guard.py` 按环境准备、模型调用和工具执行的真实事件判断进展；`durable_recovery.py` 校验并复用分支成果，隔离失败任务 | 已完成且校验匹配的产物不重新执行；恢复源证据不可变，恢复后继续未完成工作和第 4 阶段 |
| 发布到下游 | 完整有效报告进入发现记录表；`run.sh` 默认继续执行图文报告、第 4 阶段 `verify-agent`、第 5 阶段红队批量执行与独立审核，再编译状态和自动分类 | 静态候选问题仍需验证和红队证据才能进入下一阶段，不能跳过验证通过条件 |
| 经验与挖掘修复候选 | 第 6 阶段重建红蓝经验并生成共享或仓库专属修复候选；候选经独立前后运行评估后才发布，下一轮挖掘加载已发布规则 | 候选目录、真实评估、活动规则与版本回滚记录分离；生成候选本身不改变生产挖掘 |

`run.sh` 在单项目批量审计前执行第 0 阶段环境构建：`phase0_env.sh` 默认直接启动 `environment-builder` 智能体，由智能体检查源码、选择构建方式、调用确定性构建工具、阅读日志、修复并验收环境；智能体没有产出可用环境时才执行确定性备用方案，明确关闭智能体时只执行备用方案。报告完整性检查通过后依次执行 `visual_report.sh`（图文报告和场景图）、`phase4_verify_agent.sh`（真实 `verify-agent` 和隔离执行器）、`phase5_redteam.sh`（红队批量执行和独立审核）以及 `post_validation.sh`（红蓝经验和挖掘修复候选），最后重算待人工验收条件。环境构建失败、报告不完整、验证结论为 `blocked` 或红队未通过时都保留明确状态，不伪装成 `ready` 或 `confirmed`。批量审计负责找候选并保留证据，候选验证负责核实候选，隔离环境验证负责证明可利用性，三者不能互相替代。

### 正式八节点执行链与运行状态

看板首页、系统架构页和运行详情共用 `GET /api/runs/:project/:runId/pipeline`，固定展示八个节点：`environment-builder` 环境构建、`security-orchestrator` 安全审计编排、`attack-scene-director` 攻击场景设计、`verify-agent` 蓝队验证、`redteam-lab-builder` 红队场景构建、`scripts/redteam/agent.py` 红队执行、`exploit-judge` 独立审核、`mining-repair-learner` 经验学习。接口分别读取 `<run>.meta/env-phase.json`、审计报告、`visual-summary.json`、蓝队汇总、红队汇总和学习产物，不把整次运行的一个总状态复制到所有节点。状态分为已完成、降级、受阻、失败、运行中、未开始和已跳过；智能体失败但最终使用备用方案得到产物时标记降级，下游未实际启动时保持未开始，不伪装成智能体完成。首页默认显示最新项目，项目筛选可切换目标；实时运行时按 5 秒轮询。六个候选处理状态的计数与这条执行链分开，不混用两种“节点”含义。

每个节点都可以打开自己的只读执行轨迹。环境、场景、蓝队和独立审核启动器统一保留 Claude Code 原生 `stream-json`；安全编排读取 `raw.jsonl`，经验学习读取 `rsi/learner.jsonl`。`ui/server/agentic-traces.mjs` 按节点和具体调用索引日志，同一节点存在多次调用时要求选择具体轮次、候选或红队运行，不能混成一条会话。`scripts/ccui/import_trace.py` 复用 `import_runs.py` 的转换逻辑，把选中的流式日志导入第三方 Claude Code 会话界面；`GET /api/runs/:project/:runId/ccui?node=<节点>&trace=<调用>` 只返回只读回放，不启动新智能体。旧文本日志保留文本查看；红队执行是独立模型循环，展示 `agent.jsonl` 结构化执行轨迹，不标记为 Claude Code 会话。

### 持久沙箱生命周期

第 0 阶段生成的镜像以 `mygoldmine:dev` 为基础，同时包含 Claude Code 和目标依赖。`run.sh` 默认通过 `scripts/env/sandbox.sh` 为每次审计运行创建独立持久容器；`PERSIST_SANDBOX=0` 可退回一次性容器。沙箱名称和元数据保存在 `<run>.meta/sandbox.json`，不保存模型密钥。

```bash
# 创建/查看（run.sh 默认自动创建）
bash scripts/env/sandbox.sh start --project <project> --run-dir <run> --source <source>
bash scripts/env/sandbox.sh status --project <project> --run-dir <run>

# 在同一 /workspace/repo 中继续探索
bash scripts/env/sandbox.sh exec --project <project> --run-dir <run> -- <command>
bash scripts/env/sandbox.sh shell --project <project> --run-dir <run>

# 离线验证；run.sh 在第 4 阶段前自动断开持久沙箱网络
bash scripts/env/sandbox.sh isolate --project <project> --run-dir <run>
bash run.sh --verify-only <run>

# stop 保留容器与工作副本；remove 才删除容器
bash scripts/env/sandbox.sh stop --project <project> --run-dir <run>
bash scripts/env/sandbox.sh remove --project <project> --run-dir <run>
```

批量审计使用 `/target` 的只读源码生成 `/workspace/repo`，人工命令行可继续进入这个工作副本。主流程 `phase4_verify_agent.sh` 默认让每条验证程序（harness）在独立断网容器运行；`run_verify.sh` 仍支持显式 `--sandbox` 复用已断网沙箱，但要求同一工作副本串行执行。恢复审计运行时若不能共享原运行的产物挂载，自动回退到独立执行路径；沙箱创建失败也不阻断批量审计。

## 3. 核心组件

| 路径 | 职责 |
|---|---|
| `scripts/env/sandbox.sh` | 管理每次审计运行的持久沙箱生命周期、交互命令行、网络隔离与工作副本复用 |
| `scripts/mine/mine_one_docker.sh` | 进入持久沙箱或启动一次性审计容器，生成原始报告并触发视觉报告与自动分类 |
| `scripts/mine/progress_guard.py` | 根据共享总时限和真实进展区分环境准备、模型调用与工具执行的停滞，并统一处理超时 |
| `scripts/mine/durable_recovery.py` | 持久化分支成果、隔离失败并恢复未完成工作，恢复后继续第 4 阶段 |
| `scripts/workflow/finding_ledger.py` | 扫描全部有效审计报告，为每次发现的候选问题保留单独编号，归并多轮审计中的同一问题，并生成历史发现记录表 |
| `scripts/workflow/build_state.py` | 基于发现记录表合并验证结果、CVE 和人工状态，重算红队证据来源链并生成待人工验收条件 |
| `scripts/workflow/refine_worker.py` | 按来源哈希重算路由，归档低价值条目，让高分条目进入下一阶段 |
| `scripts/workflow/flow_worker.py` | 处理 `triage` 和 `reproduce`：调用候选验证、补充图文报告、触发红队并写回自动流转状态 |
| `scripts/verify/run_verify.sh` | 在独立容器或已断网的持久沙箱中验证单条候选问题 |
| `scripts/verify/auto_verify.sh` | 手工静态预筛，只输出 `inconclusive` 或 `blocked`；不是主流程验证器 |
| `scripts/verify/phase4_verify_agent.sh` | 主流程第 4 阶段：调用真实 `verify-agent` 编写验证程序，再交给 `run_verify.sh` |
| `scripts/redteam/lab.py` | 创建受限的目标端与攻击端容器、内部网络和随机标记，并提供执行工具 |
| `scripts/redteam/agent.py` | 通过兼容 OpenAI 接口的模型进行红队多轮交互，只从真实工具输出捕获随机标记 |
| `scripts/redteam/judge.py` | 校验确定性证据来源链并独立审核；候选运行可用 `RSI_VALIDATION_TRAJECTORY` 隔离轨迹输出 |
| `scripts/redteam/batch.py` | 按候选问题构建并预检隔离环境，运行攻击端，调用独立审核 |
| `scripts/redteam/phase5_redteam.sh` | 主流程第 5 阶段：从当前审计运行选择候选问题，调用批量执行与独立审核，刷新待人工验收条件 |
| `scripts/rsi/post_validation.sh` | 主流程第 6 阶段：重建红蓝经验并调用 `Claude Code` 学习节点，不直接发布 |
| `.claude/agents/mining-repair-learner.md` | 组合多个技能归纳红蓝经验，输出共享或仓库专属修复 Markdown |
| `.claude/skills/verification-experience-analyzer/`、`repair-scope-analyzer/`、`mining-repair-learning/` | 分析验证证据、判断修复作用域并组织已有知识与漏洞分析技能 |
| `audit_rsi/mining_driver.py` | 让候选实际参与隔离挖掘、蓝队验证和红队审核，按真实结果发布或拒绝；批量模式自动选择留出项目 |
| `scripts/mine/repair_context.py` | 把已发布共享规则与当前项目规则注入下一次挖掘，隔离其他项目规则 |
| `scripts/mine/visual_report.sh` | 主流程图文报告：视觉模型、场景图和 `report-illustrated.md` |
| `scripts/watch/watch.py` | 轮询仓库提交、静态 diff 评分，按项目和分支绑定 commit，并自动派发高风险事件到 `run.sh` |
| `scripts/watch/daemon.sh` | 常驻轮询与自动派发；`WATCH_AUTO_RUN=0` 只监控不挖掘 |
| `.claude/skills/project-cartographer/` | 视觉模型、结构与覆盖图、攻击场景图、image2 插图 |
| `ui/` | 看板、表格、项目地图、持续监控、系统架构和运行详情 |
| `audit_rsi/` | 经验构建、标签合并、验证资源只读建议，以及挖掘修复候选、真实前后运行评估、分作用域发布和回滚 |
| `rsi_version/` | 确定后不再修改的候选版本、发布复核和回滚存储 |

## 4. 身份、状态与优先级

每条候选问题有两层身份：`occurrence_id=project/run_id/local_id` 精确定位一次观测，`semantic_id` 由项目、规范化证据路径、根因和 CWE 汇聚多轮审计语义。每次挖掘运行另外记录 `branch` 和 `commit`；持续监控按“项目 → 分支/commit → 运行”绑定身份，派发器使用独立工作副本固定目标提交，不移动用户当前分支。历史报告独有的候选问题不会因新审计运行而消失；运行中或质量不合格的草稿不会替代最新完整报告。旧 `project:id` 状态仅在语义唯一时兼容，存在歧义时不猜测继承。

状态优先级：

```text
state.json（人工） > curated.json（人工种子） > flow-state.json（自动流转） > refine-state.json（自动分类） > auto-state.json（自动状态编译） > inbox
```

| 状态 | 含义 | 是否给人看 |
|---|---|---|
| `inbox` | 未处理候选，尚未进入下一阶段 | 默认隐藏 |
| `triage` | 自动分类进入分诊；自动流转后台任务会调用 `verify-agent` | 流程视图 |
| `reproduce` | CVE 分级候选或验证结论为 `confirmed`；等待或已进入红队验证（尚未证明可利用） | 流程视图 |
| `cve` | CVE 去重与跟踪 | 流程视图 |
| `archived` | 可重算的低优先级归档，不是安全结论 | 默认隐藏 |
| `closed` | 人工关闭、误报、重复或已知问题 | 流程视图 |
| `review` | 可信红队、独立审核和图文检查全部通过 | 人工验收 |

## 5. 自动分类后台任务（`refine`）

输入：第 2 版固定结构的发现记录表和现有自动与人工状态。输出 `refine-state.json`、`refine-queue.json` 和 `rsi/trajectories/refine.jsonl`。

规则：

- 每条决策保存 `source_hash`；原始报告、验证结果、CVE 或人工证据变化时重新计算。
- 已归档项获得 `confirmed` 验证结论后重新进入队列并转为 `reproduce`。
- 弱指纹只标记 `duplicate_candidate`；高危和严重问题不凭弱指纹直接归档。
- CVE 分级候选或 `confirmed` 验证结论进入 `reproduce`；严重和高危问题进入 `triage`；其他低分项进入 `archived`。
- 所有决策可回放；`archived` 不删除原始报告。
- `--loop` 在空队列时等待并继续扫描，不会因暂时 `pending=0` 退出；新审计运行和新证据能持续进入经验链。

## 6. 自动流转后台任务（`flow`）

输入：最新发现记录表、`refine-state.json`、`auto-state.json` 和人工状态。输出 `flow-state.json`、`flow-queue.json` 和 `rsi/trajectories/flow.jsonl`。

规则：

- 只处理 `triage` 和 `reproduce`；人工状态高于自动流转，自动流转高于自动分类。
- `triage` 调用 `phase4_verify_agent.sh --finding-id`；`confirmed` 转为 `reproduce`，`rejected` 转为 `closed`，`blocked` 和 `inconclusive` 保持 `triage` 并记录尝试次数。
- `reproduce` 先补图文报告，再调用 `phase5_redteam.sh --finding-id`；独立审核结论为 `approved` 后调用 `build_state.py` 重算待人工验收条件。
- 每次尝试记录 `flowAttempts`、`flowOutcome`、产物路径和 `flowNextAt`；默认最多一次，避免对同一失败候选无限重试。
- 环境清单缺失、镜像不存在或 Docker 不可用时只记录 `blocked`，不伪造验证结果；设置 `FLOW_BUILD_ENV=1` 时会对已知目标调用第 0 阶段构建环境后重试。`FLOW_WORKER=1` 时随看板启动，默认关闭以避免意外消耗模型。
- CVE 跟踪仍由人工或 `docs/cve-*.json` 产物推进，自动流转不会自动创建 CVE 编号。

## 7. 动态验收隔离环境契约

每个候选问题使用独立的验证环境，由 `redteam-lab-builder` 生成到 `labs/<project>/<finding-id>/`。验证场景绑定候选问题内容哈希和源码版本；构建与结构化校验都通过后才可执行。攻击端只能在攻击容器中执行命令，并通过隔离网络访问目标 HTTP 服务。当前只执行 HTTP 服务场景，其他类型不执行并标记为“暂不支持（`blocked`）”，不能用 HTTP 包装冒充。

不变量：

- 使用 Docker 内部网络，目标端不发布宿主机端口
- 目标端和攻击端均启用 `cap-drop`、`no-new-privileges`，并限制进程数、内存和 CPU
- 随机标记只由验证程序以只读方式挂载到目标端的 `/flag`
- 攻击端不挂载宿主机目录、随机标记或 Docker 套接字，场景不声明 `mounts` 或 `volumes`
- 随机标记只能从真实工具输出捕获；最终回答本身不是证据
- 轨迹记录工具事件、输出 SHA-256、随机标记 SHA-256 和捕获事件
- 轨迹与智能体日志都是不可信数据，独立审核不能被其中的指令带偏

## 8. 独立审核契约

`judge.json` 使用完整固定结构，包含 `verdict`、`intended_vulnerability`、`flag_provenance`、`no_cheat`、`environment_plausible`、`reproducible`、`minimal`、`confidence`、`reason`、`concerns` 和 `recommended_status`。审核结论为 `approved` 时，全部必要布尔字段必须为 JSON `true`，且 `recommended_status` 为 `runtime-validated`。

程序在调用独立审核和接收结果时都会重算确定性证据来源链；缺字段、字符串布尔、旧审核文件或哈希不一致均拒绝。待人工验收条件的构建还会再次验证结果中记录的证据来源链，旧“仅独立审核通过”结果不能绕过。安全验证通过后，人工验收队列仍要求图文报告和场景图；视觉素材本身不是漏洞证据。

## 9. 图文报告

`project-cartographer` 生成：

- `visual-model.json`：结构、覆盖、攻击树和攻击者与受害者场景
- `project-map.svg`、`coverage-tree.svg`、`attack-*.svg`
- `scene-*.svg`：准确的双方步骤
- `scene-*.webp`：image2 叙事插图
- `report-illustrated.md`：供人工验收的图文报告

插图必须标注“AI 插图，非漏洞证据”。视觉素材不能替代轨迹和独立审核。

## 10. RSI 学习流程

系统现有三条相互独立的学习支路：验证资源学习、红队验证程序改进和挖掘修复。验证资源学习仍是**只读建议模式**（`shadow`），不会改变生产状态；挖掘修复则可以经过真实前后运行评估后发布到共享技能或当前项目规则，并由下一轮挖掘实际加载。三条支路不能互相冒充：只读验证策略不会因为挖掘修复发布功能存在就自动上线，验证程序候选也仍不直接修改执行器。

真实运行会留下动作前上下文、动作、结果、成本和证据来源链；策略学习验证动作的收益，独立留出验证集与非回归检查决定候选能否进入发布复核。系统不会让模型直接改写自己，也不会把最终报告回放包装成在线发现能力。

当前验证资源的只读建议模式已跑通，但训练支持 91 条全部为静态证据（`static`），可用于动作训练的可信样本（`trusted`）为 0；回放状态为 `insufficient`，没有前后结果变化（`flips`）产物。因此验证动作策略仍停留在只读建议，不发布为生产策略。

架构页按以下六步展示经验与挖掘修复的关系：

```text
01 真实轨迹（verification / redteam 经验）
  → 02 标签与证据等级（runtime / judge / manual；static 不冒充 trusted）
  → 03 成本与收益评估（固定五动作词表做 ridge utility regression；当前仅 deep_read 25 条、defer 66 条有样本）
  → 04 跨项目验证与前后结果对比（留出验证、同动作回放、真实挖掘结果对照）
  → 05 只读建议（recommendation_only=true，state_change=none）
  → 06 挖掘修复发布（独立支路：共享或仓库专属规则，经真实前后运行评估后发布）
  └──────────────── 发布后的新真实结果回到 01
```

第 06 步不是只读验证策略的自动升级，而是 `audit_rsi/mining_repair.py` 提供的独立挖掘修复链路。`trusted_support=0` 时验证动作仍以 `static-only / no_trusted_utility_targets` 继续生成只读建议；挖掘修复若只有静态证据，也只能保持候选状态。回放只描述同动作的实际收益，真实前后运行对照只描述观测变化，两者都不宣称因果评估。

红队验证程序形成第二条学习支路，与验证动作成本与收益评估分开：

```text
红队真实运行与步骤轨迹
  → 按固定规则找出反复出现的执行失败（按失败原因等分组，统计出现次数、成本和候选修改位置）
  → 白名单内的验证程序提案（稳定 candidate_id，mutation=none）
  → 独立比较配对项的前后结果变化，再进行候选与发布复核
  → 受控变更后的新红队轨迹
```

这条支路只生成候选证据与提案，不自动修改验证程序；`validated` 也不等于已经发布。

`audit_rsi/adapters/raw_trace.py` 另行把真实 Claude `stream-json` 转为动作轨迹，保留 `Task` 和 `Agent` 父子拓扑、实际结果和成本；历史动作被选中的概率（propensity）未知时保持 `null`。最终报告重建树只用于旧回放，不能证明未探索分支的发现效果。

常用命令：

```bash
python3 -m audit_rsi experience-build --runs runs --output rsi/verification-experience.jsonl
python3 -m audit_rsi label-sample --pool rsi/verification-experience.jsonl --output rsi/verification-label-sample.jsonl --limit 100
python3 -m audit_rsi label-plan --pool rsi/verification-experience.jsonl --output rsi/verification-label-plan.jsonl --report rsi/verification-label-plan.json --limit 100
# 人工填写 verdict/evidence_class 后合并，再训练和生成只读建议
python3 -m audit_rsi label-merge --pool rsi/verification-experience.jsonl --labels rsi/verification-label-sample.jsonl --output rsi/verification-experience-labeled.jsonl
python3 -m audit_rsi verify-train --pool rsi/verification-experience-labeled.jsonl --output rsi/verification-policy.json --holdout-project <project>
python3 -m audit_rsi verify-shadow --pool rsi/verification-experience-labeled.jsonl --train rsi/verification-policy.json --output ui/data/verification-shadow.json
python3 -m audit_rsi verify-replay --pool rsi/verification-experience-labeled.jsonl --train rsi/verification-policy.json --holdout-project <project> --output rsi/verification-replay.json
python3 -m audit_rsi verify-flips --baseline <baseline.jsonl> --candidate <candidate.jsonl> --holdout-project <project> --output rsi/verification-flips.json
python3 -m audit_rsi redteam-experience --runs runs/redteam --output rsi/redteam-experience.jsonl --steps-output rsi/redteam-steps.jsonl
python3 -m audit_rsi redteam-weakness --runs runs/redteam --output rsi/redteam-weakness.json
python3 -m audit_rsi harness-propose --weakness rsi/redteam-weakness.json --output rsi/harness-candidates.json --limit 3
python3 -m audit_rsi harness-validate --candidate <candidate.json> --flips rsi/verification-flips.json --output rsi/harness-validated.json
```

未知结论不等于误报；缺少合法标注倾向、留出验证集、标签覆盖或支持度时，只输出 `insufficient` 或只读建议，不发布为生产策略。回放只报告相同动作实际获得的收益，不宣称因果提升。`verify-flips` 按同一问题编号（semantic）比较两个真实经验池的 F→P 和 P→F、稳定项、配对覆盖与未知结论转移，用于观测非回归，不把不同审计运行的结果解释成反事实或因果效果。候选进入下一阶段的默认通过条件为 `paired_coverage>=0.8`、至少一个 F→P 且零 P→F；覆盖不足时为 `insufficient`，有修复但出现回归时为 `rejected`，满足条件才为 `accepted`。`mutation=none`，`accepted` 仍需候选复核和既有发布检查。版本发布复核统计各项检查结果，失败候选仍可查询和回滚。

`redteam-experience` 将审计运行级结果与攻击端步骤级工具事件分开：记录角色、动作、成本、返回码、输出哈希、失败分类和证据等级，不复制原始攻击命令、输出正文或随机标记。只有确定性证据来源链可重算的捕获才自动成为运行时标签；独立审核结论为 `approved` 时还要求审核状态与重算结果一致。`not_captured`、篡改轨迹和未复核结果保持未知，不成为误报或可信奖励。

`redteam-weakness` 按固定规则归类这些轨迹中的重复失败：以项目类型、攻击模型、失败原因、严重度和候选修改位置作为分组条件，分别输出包含该类失败的运行次数（`support`）、失败事件次数（`event_support`）、平均模型调用次数和平均耗时。模型超时（`model_timeout`）、隔离环境异常（`lab_unhealthy`）、未捕获（`not_captured`）、工具失败和结构化输出失败对应不同的执行器修改位置。该产物只供后续评估（`candidate_only`），不修改执行器（`mutation=none`）；任何候选修改仍须通过独立回放与回归检查。

`harness-propose` 只允许修改白名单允许的范围，为每个提案生成稳定 `candidate_id`、目标失败、证据哈希、保留行为和验证要求；不会直接修改验证程序。`harness-validate` 重算提案身份并检查前后结果变化，只有 `accepted` 才标记为 `validated`，身份篡改、回归或证据不足均不能通过。候选提案和验证结果都可审计、可回放，仍需后续发布复核。

经验构建同时读取 `verdict.json`、`verify-report.json` 和 `auto-state.json`：自动路由提供 `deterministic-auto-state` 动作及倾向，候选验证提供静态或运行时结果，不能把有结果但无动作的样本静默丢弃。运行时验证与人工整理记录可自动获得确定标签来源；静态验证只进入只读建议的学习；独立审核仍需独立标签复核，不自动获得标签选择概率。

`label-plan` 在普通分层抽样之外优先补齐完全缺少可信样本的项目和动作，再考虑补充覆盖；无动作记录不进入人工标注队列。每个任务保留单次观测与同一问题编号、抽样原因、分层配额和标签选择概率，并过滤敏感上下文。该计划只提高标注效率，不把未知结论自动变成可信样本。

智能体可以辅助做源码级静态标注，但必须使用 `evidence_class=static` 和 `adjudication.method=agent-static`，不能冒充人工、运行时或独立审核证据。只有静态标签时只读建议明确为 `static-only / no_trusted_utility_targets`，即使训练产生了不同建议，也不得视为已验证提升或生产候选。

### 挖掘修复学习（已接入，候选默认不发布）

`run.sh` 在第 4 阶段蓝队验证和第 5 阶段红队审核后执行第 6 阶段 `scripts/rsi/post_validation.sh`，先重建红蓝经验并形成带证据的种子，再由 `Claude Code` 启动 `mining-repair-learner`。学习节点使用 `verification-experience-analyzer`、`repair-scope-analyzer`、`mining-repair-learning`，并按候选根因调用证据优先、可达性、误报模式、项目知识和现有漏洞分析技能，将修复写到 `rsi/mining-repairs/agentic/*.md`。随后主流程自动调用 `mining-repair-drive`：把候选 `Markdown` 写入独立上下文，在 `rsi/mining-repairs/attempt-runs/` 重新执行挖掘、报告完整性检查、蓝队验证和红队审核，再用这次真实候选运行评估发布或拒绝。`--skip-mining-repair` 可跳过整个学习阶段；`--mine-only` 也会跳过。候选重跑不进入正式 `runs/`，候选红队轨迹通过 `RSI_VALIDATION_TRAJECTORY` 写入独立评估目录，不污染正式经验。批量 `parallel_mine.sh` 在项目结束后执行同一智能体学习阶段，并自动从未参与来源训练的项目中选择留出项目重跑共享候选；`--skip-mining-repair` 可关闭。无需人工执行离线命令才能完成学习。

修复分两种作用域：

- 共享修复写入 `.claude/skills/rsi-shared-experience/rules/`，至少需要两个具有可信证据的来源项目，并必须在与来源项目隔离的留出项目上通过真实前后运行评估。
- 仓库专属修复写入 `knowledge/project-rules/<project>/`，只评估并加载对应项目，不能进入其他项目的提示词或智能体加载清单。
- 可信证据只包括实际运行、独立审核和人工结论；静态证据可以生成候选，但发布检查会以 `no_trusted_source_evidence` 拒绝。

`mining-repair-drive` 使用正式运行作为修复前基线，并把候选实际参与的新运行作为修复后结果。误报修复必须至少抑制一个既有误报、降低误报率、保留全部基线正确结论且没有新增误报；已确认调查模式必须带来至少一个新的正确结论，同时满足相同的非回归条件。未知结论不当作误报，候选消失只对既有误报计为抑制，对既有正确结论计为丢失。`mining-repair-cycle` 仍可比较外部提供的经验集合，但只是离线调试入口，不是主流程的替代品，也不单独证明候选规则导致了结果变化。

发布时重算候选身份、内容哈希和评估身份，在 `rsi/mining-repairs/versions/` 保存本次内容、前一内容和清单元数据。已发布共享规则由 `scripts/mine/repair_context.py` 与项目规则一起注入下一次挖掘；超过提示词预算时保留索引并要求智能体按需读取。容器通过只读挂载获得 `audit_rsi`、共享技能和项目知识。回滚只允许针对当前最新活动版本，防止覆盖后续修复。

```bash
# 单项目主流程：候选生成、隔离重跑、红蓝验证、评估和仓库专属发布自动完成
bash run.sh <source>

# 批量主流程：共享候选自动选择留出项目重跑，接受项发布并供后续项目加载
bash scripts/mine/parallel_mine.sh

# 调试入口：直接驱动候选重跑，或只生成候选
python3 -m audit_rsi mining-repair-drive \
  --scope project --project <project> --target <source> \
  --baseline-run <run> --image <env-image> --miner-image mygoldmine:dev \
  --output <driver.json>
python3 -m audit_rsi mining-repair-propose \
  --pool rsi/verification-experience.jsonl \
  --additional-pool rsi/verification-experience-labeled.jsonl \
  --ledger ui/data/finding-ledger.json \
  --output rsi/mining-repairs/candidates

# 查看实际加载内容、回滚活动版本
python3 -m audit_rsi mining-repair-context --project <project>
python3 -m audit_rsi mining-repair-rollback --version <mrv_...>
```

## 11. 运行手册

```bash
# 全量看板
bash scripts/ui/start.sh

# 自动分类后台任务
bash scripts/workflow/refine_worker.sh start
bash scripts/workflow/refine_worker.sh status

# 自动流转后台任务（triage -> verify -> reproduce/closed，reproduce -> red-team -> review）
bash scripts/workflow/flow_worker.sh start
bash scripts/workflow/flow_worker.sh status
bash scripts/workflow/flow_worker.sh once

# 单条红队验证
python3 scripts/redteam/agent.py --finding <finding.json> --victim-image <image>
python3 scripts/redteam/judge.py --run-dir <redteam-run>

# 17 条批次
python3 scripts/redteam/batch.py --dry-run
python3 scripts/redteam/batch.py
```

## 12. 失败时如何处理

| 现象 | 处理 |
|---|---|
| 没有隔离环境场景 | `blocked_no_lab`，不进入验收 |
| 目标端未启动 | `LabError`，保留运行目录和容器日志 |
| 红队未捕获随机标记 | `not_captured`，不进入待人工验收 |
| 红队直接读取随机标记文件 | 独立审核拒绝 |
| 独立审核证据不足 | `needs_review`，不要猜测 |
| 图片生成失败 | 保留 SVG，不阻塞报告 |
| 后台任务并发 | 文件锁防止双实例 |

## 13. 开发扩展点

新增项目隔离环境：

1. 构建可直接启动的目标端镜像。
2. 确认服务在 `--internal` 网络内健康。
3. 确定随机标记如何只通过目标漏洞暴露。
4. 按候选问题和输入来源绑定，写入 `labs/<project>/<finding-id>/scenario.json`。
5. 用演示候选问题运行一遍 `agent.py` 和 `judge.py`，确认确定性证据来源链校验通过。
6. 再把真实候选问题加入 `docs/redteam-candidates.json`。

新增独立审核规则：

- 只改 `exploit-judge.md` 和 `judge.py` 的输出结构，不改变红队工具权限。
- 独立审核不能调用攻击工具，不能修改轨迹、候选问题或结果。

## 14. 架构说明维护

根目录 `AGENTS.md` 定义了同步契约。模块、数据流、候选问题身份、状态通过条件、API、恢复机制、安全边界或 RSI 发布关系变化时，同一轮修改必须核对本文和 `ui/src/components/ArchitectureView.jsx`；用户入口变化还要核对 README。局部且不改变行为的修复不需要机械更新，但不能保留已知过时描述。

架构页是面向使用者的三级实现摘要：第一级用整体漫画地图展示批量审计、自动分类与验证、红队与验收、核心组件、RSI 学习流程五个区域；第二级展示中层阶段和组件，其中 RSI 区域区分验证资源只读建议、红队验证程序候选和可发布的挖掘修复，展示共享与仓库专属作用域、真实前后运行评估、下一轮加载和回滚；第三级才展示输入输出、执行规则、对应脚本与输出文件、失败时如何处理和优化检查点。漫画由 360 平台的 `bytedance/doubao-seedream-5.0-pro` 生成，仅用于叙事，不代替准确的节点关系或安全证据。本文是面向开发人员的完整契约，两者都不能把计划、静态标签、只读建议或未评估候选描述成已验证、已发布的生产能力。修改模块职责或契约时，也要同步对应中层节点和实现详情，不能只改视觉或标题。

### 项目导入进度

导入弹窗通过 `POST /api/targets/import-stream` 接收逐行 JSON 状态事件，在提交按钮下方显示排队、源码准备、版本登记、审计启动和命令输出，以及等待时间。失败信息保留在弹窗内。原有 `POST /api/targets/import` 接口保持可用；点击取消或关闭导入连接会停止排队、下载或启动过程；本次新建源码目录会清理，已有目录和本地源码保留。已登记的项目恢复导入前记录，已启动的审计调用停止命令，运行产物保留供排查。取消后可重试，新请求会等待清理完成。此状态仅表示导入与启动过程，不表示完整审计已完成。

### 按提交版本导入

公开仓库导入使用 `POST /api/targets/github-commits` 直接读取提交历史，每页 10 条，显示短提交编号、时间与说明，默认选最新提交，支持加载更多。读取列表不下载源码，相同页短暂缓存并合并并发请求。导入按完整提交编号浅下载、检出并核对版本。

已有有效提交只有与所选版本相同才复用；不同版本须换项目标识。仅含 `.git`、来源匹配且没有有效提交的未完成目录，以及空目录，会移动到 `backups/incomplete-imports` 后重试。其他已有内容不会自动移动。下载失败、超时或取消会清理本次新建且尚未登记的目录。

下载耗时显示为实际已用时间，不是倒计时。仓库下载不设固定总时长上限；每次收到下载命令标准输出或错误输出都重置空闲计时，连续 3 分钟无输出才停止并允许重试。列表请求和启动审计仍保留各自超时。

看板扫描同时识别主运行目录和带有 `status.json` 的相邻 `.meta` 状态目录。启动早期只有状态目录时，项目也会显示在侧栏；两种目录同时存在时只统计一次，不把 `.meta` 当作独立运行。

节点轨迹转换为 Claude 会话后，使用 `scripts/ccui/index_trace.mjs` 同步登记到会话数据库，再返回对应会话地址。转换缓存与数据库登记分开处理，登记失败显示错误，不进入项目选择空页。环境部分可用时显示降级，不显示完整完成。轨迹面板提供消息数量、同步和新窗口入口。

### 沙箱源码准备与复用

沙箱创建操作按运行目录加锁，容器启动后同步复制源码，复制成功才写入工作副本就绪标记并返回。持久沙箱中的审计入口检查就绪标记后直接复用工作副本，不再清空或二次复制；停止后再次启动保留已有修改。复制失败不发布就绪状态，并停止新建容器。旧版或未准备完成的沙箱缺少标记时拒绝启动审计，需用新的运行目录重建，原工作副本保留。独立临时容器仍由入口准备源码，清理失败会直接报错。

安全审计节点在没有主会话或主会话为空时，展示本次运行的启动日志（相邻状态目录中的 wrapper.log）。复制源码失败会标明审计智能体未启动；生成主会话后优先展示真实会话。历史运行日志保持原始结果，不因代码修复改成成功。

### 删除项目

侧栏项目右侧提供删除按钮。确认后删除项目登记、发现记录与对应运行目录，不提供撤销或恢复接口；源码目录保留。项目仍在运行时禁止删除。删除使用 `DELETE /api/targets/:project`，后续重新导入是新建审计，不恢复旧记录。

### 串行阶段状态

监督脚本按实际调用顺序记录 `pipeline-stage.json`：环境准备、安全审计、攻击场景、蓝队验证、红队处理、经验学习。红队批处理在调用场景构建、执行、独立审核前更新当前节点与候选编号；不同候选会依次重复这些步骤。看板只将当前节点显示为运行中，尚未到达的节点显示等待，不使用整次任务存活状态推断每个节点运行，也不将初始占位值当成已跳过。旧运行缺少阶段文件时按已有阶段日志和产物兼容推断。完成、降级等最终结果仍以真实产物为准。

中断记录按最后执行阶段展示：该阶段保留已有结果，未完成时标注已中断；后续没有执行记录的阶段标注未执行。旧记录结合环境日志识别中断位置，不把启动前中断误报为安全审计失败。

项目侧边栏提供“重新审计”：通过 `POST /api/targets/:project/restart` 读取已登记的源码目录，调用完整审计主流程并创建新的运行目录，保留历史记录。源码不重新下载，项目正在运行时拒绝重复启动；重新审计与导入共用串行启动队列。启动后自动选择该项目并刷新看板。

项目没有显式图标配置时，优先使用本地同名项目图片 `ui/public/logos/<项目标识>.png`；没有图片时才显示默认图标。删除后重新导入也会恢复已有图片。

打开执行轨迹时，看板先检查轨迹服务；默认本机回环服务未运行时自动启动，并合并并发启动请求。启动日志写入 `runs/ccui-home/service.log`，只恢复查看服务，不重新启动审计智能体。自定义远程服务不由看板启动。

“设置 → 配置模型”可分别设置安全审计、蓝队验证、红队验证、环境构建、攻击场景设计与独立审核模型。配置经校验后保存至 `config/stage-models.json`；可选阶段留空时跟随审计模型。候选列表只读取已有模型名称，不返回服务密钥。新导入和重新审计在启动时将配置传入主脚本并固定为本次任务的模型参数；已有任务不受影响。运行状态通过 `stage_models` 保存本次各阶段模型。命令行的场景与审核模型在参数解析完成后计算，避免选项未生效。模型名称必须在对应的既有服务中可用，此入口不配置服务地址或密钥。

新启动任务的默认安全审计时限为 24 小时（86400 秒），各启动入口保持一致；看板从本次运行记录读取实际时限，不使用固定的显示值。已启动任务保留启动时传入的时限，配置修改不伪装为已延长历史任务。环境构建和验证阶段仍使用各自时限。

红队模型默认跟随安全审计模型，设置中留空即可跟随；不再默认使用 flint。红队按模型的服务前缀读取已有服务地址与鉴权配置，并去除服务前缀后发送请求；缺少配置时明确失败，不回退到旧模型服务。密钥不会写入看板配置或运行结果。


### 环境构建指令约束

环境构建技能与智能体定义以本次验收目标决定依赖范围，默认先满足轻量审计需要；导入、CPU 测试与 GPU 训练分别验收，不默认安装全部开发或训练依赖。指令要求先做平台和下载源预检、按实际日志检查进展、修正原因后重试，并保留失败方案及真实限制。

这轮调整仅更新 Markdown 指令，不改变现有智能体超时、Docker 构建超时、备用流程、缓存实现或页面进度展示。已有 Dockerfile 仍可能被备用流程复用；指令要求智能体在预算内明确处理并如实报告，不表示脚本已经提供自动降级或独立构建管理。新启动的环境构建智能体加载新指令，正在执行的会话不会自动重新加载。

环境构建指令进一步区分预检与安装：预检只读取必要元数据，安装验证必须进入正式 Docker 构建；禁止在临时容器内安装依赖。先验证最小方案，再按指定验收路径补齐依赖；持续版本回溯须先诊断约束。检查保留原命令退出码，避免管道筛选掩盖超时。这些是智能体指令要求，未新增脚本级强制检查。

环境构建指令默认优先交付满足当前审计需要的沙箱，达到明确的最小要求后停止扩建；允许带真实限制的部分可用结果，不以完整部署、全部测试通过或就绪标签作为默认目标。必要能力及既有隔离边界仍须验证，不因追求快速交付而放宽。该要求属于技能指令，不改变脚本的状态判定。

环境构建技能选择性参考 Docker 的构建分层与缓存指导、Repo2Run 的具体验收标准和 SetupX 的有证据修复经验。指令要求按平台与版本核对历史经验，在本次输出目录保留构建说明，并保留已验证方案；未接入外部框架、数据库或自动快照回退，仍以够用的审计沙箱为默认目标。来源链接记录在技能文件中。

执行轨迹的会话索引缓存统一写入相邻的 `<运行目录>.meta/ccui-session.json` 或 `.meta/ccui-sessions/`，包括批量导入入口；查看环境轨迹不会创建或占用尚未启动的审计输出目录。旧缓存可由原始轨迹重新生成，历史审计结果不改写。输出目录非空时拒绝覆盖的检查保持不变。

环境构建指令要求优先核对已有镜像的源码对应关系、平台与实际镜像编号，通过必要断网验收后直接复用。仅修正清单、补充验收记录或修复辅助脚本不触发重建；保留原始构建时间并另记本次验收时间。只有构建输入不匹配、镜像不可用或指定验收被具体缺失项阻塞时才构建。此项属于智能体指令，未新增脚本级自动复用机制，新启动的环境构建会话生效。

攻击场景设计仍由智能体按技能执行。启动器在调用 Claude 命令行前去除模型的服务前缀，配置兼容服务地址、鉴权和子智能体模型；显式连接配置优先，未设置时沿用环境构建阶段的 360 服务及已有凭据。启动时仅加载项目及本地项目设置，排除用户级设置中的其他模型服务。凭据只传入子进程环境，不写入任务或轨迹。

审计编排退出前对实际运行目录的报告执行既有质量检查，反馈缺失字段供智能体修正；原有退出检查次数上限和最终报告质量门槛保留。恢复报告标记为 `coverage.analysis_mode=assembly-only` 时，轨迹入口明确显示恢复汇总；约定的同项目 `-recovery` 运行还关联原始完整审计，两个会话分别缓存。恢复成功只代表汇总流程完成，不代表重新扫描或漏洞验证通过。

节点轨迹抽屉提供“重新运行此节点”。当前支持攻击场景设计和蓝队验证：复用选定运行的报告，使用设置中的当前阶段模型，将报告快照、新日志与产物保存到 `<run>.meta/node-retries/<node>/<id>/`。前置产物缺失或项目仍在运行时拒绝启动；同项目节点重跑互斥，项目重跑也检查该锁。界面显示最新节点状态及历史轨迹；仅更新该节点展示，不自动执行后续阶段，也不覆盖原始报告、验证结论或历史成功状态。其他节点尚不支持独立重跑，按钮说明原因。


### 结构化阶段交付

新增 `scripts/stages/submission.py`，通过 MCP 函数 `submit_stage_result` 接收实际产物路径、简短说明和限制。审计、环境构建、场景设计、蓝队验证、红队场景构建、独立审核及经验学习的 Claude 启动入口加载此工具；红队独立模型循环提供同名结构化动作。智能体可多次提交，返回 `needs_revision` 和具体缺失项，修正后再次提交；通过后返回 `accepted`、产物 SHA-256 和检查范围，每次记录独立保存于指定输出目录的 `.stage-submissions/<stage>/`。

当前检查范围明确为 `artifact_contract`：复用报告质量检查、场景格式检查、审核结论格式检查；环境额外核对实际 Docker 镜像编号和已声明验收记录，场景设计检查设计文件与同名图片。其余交付检查文件结构及状态。提交成功不等于漏洞验证通过，不以模型自述替代执行证据；原有动态验收、来源绑定、随机标记核验、阶段脚本检查和人工验收仍须通过。这一轮不把收据自动升级为整条流程成功，历史任务没有收据时也不伪造补写。工具使用受限输出目录，拒绝越界路径和符号链接越界。已接入输出位置的交付记录可在节点轨迹选择器查看。

恢复汇总中没有重新执行环境构建时，环境节点关联同项目原始运行中的环境构建会话，并标为“原始运行”，不再误报暂无轨迹；若恢复运行确实启动过新构建，则展示本次记录。


阶段技能改进现支持八阶段分别提炼通用与仓库专属规则，按版本加载并记录本轮快照；候选经独立前后对照评估后才发布，支持回退。终态与单节点重跑采集各阶段反馈，保留缺失、受阻和不确定状态。连续迭代使用有轮数和无改善停止条件的命令行控制器，默认不自动启动；没有可信评估套件时只积累候选。详见 [阶段技能改进说明](stage-skill-evolution.md)。


### 验证阶段的模型连接与报告传递

蓝队、攻击场景、红队场景构建和独立审核共用 `scripts/stages/claude_connection.py`，统一模型前缀、服务地址和鉴权；Claude 命令只读取项目及本地项目设置，避免个人设置将模型切换到其他服务。红队批处理通过 `--report` 校验本轮报告、绑定项目与运行编号并记录内容摘要，不依赖仅包含已结束运行的发现记录表；未指定报告的离线入口仍按指定历史发现解析。蓝队与红队的全部受阻、部分受阻分别记录为 `blocked`、`partial`，主流程汇总为降级，看板依据实际结果展示，不能仅凭汇总文件存在就显示完成。历史运行产物保持原样。
