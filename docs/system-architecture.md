# 系统架构说明

面向开发人员。目标是把“静态挖掘 → 自动分类 → 动态验收 → 人工展示”做成一条可运行、可审计、可回放的流水线。

## 1. 设计目标

- 原始 finding 不直接推给人；先自动评分、去重、路由。
- 只有进入 `待验收` 的 case 才需要人工阅读。
- `待验收` 必须同时满足：红队实际捕获 flag、独立 judge 通过、图文报告已生成。
- 每条自动决策和每次验证都留下 trajectory，供 RSI 回放和策略优化。
- 所有攻击只在隔离 lab 内进行，flag 随机，攻击者容器不能直接接触 flag。

非目标：

- 不把“自动归档”当成“确认安全”。
- 不把 AI 插图当漏洞证据。
- 不对公网或未授权目标运行红队。

## 2. 端到端数据流

```text
┌──────────────┐
│ 目标源码/镜像 │
└──────┬───────┘
       │ run.sh / mine_one / overnight
       ▼
┌──────────────────┐
│ 静态审计报告       │  runs/<project>/<run>/audit-report.json
│ + coverage/证据    │
└──────┬───────────┘
       │ finding_ledger.py（仅完整有效 run）
       ▼
┌──────────────────┐
│ Finding Ledger    │  occurrence / semantic 双层身份
│ 多轮审计历史台账   │  finding-ledger.json
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

### 挖掘过程设计

挖掘阶段负责产生**可追溯的静态候选**，不直接把模型结论当作已验证漏洞。执行链如下：

| 阶段 | 设计与职责 | 关键产物/边界 |
|---|---|---|
| 目标与调度 | `parallel_mine.sh` / `overnight.sh` 从 `targets/manifest.json` 选择项目，控制并发、失败重试和断点续跑；每个项目使用独立时间戳 run | 已有完整成功报告的项目默认跳过；编排状态与项目产物分离 |
| 持久项目沙箱 | `sandbox.sh` 为每个 run 启动独立容器，源码只读挂载到 `/target`，挖掘、verify 和交互 shell 复用 `/workspace/repo` | 不挂载 Docker socket，`cap-drop ALL`、`no-new-privileges`；密钥不写入沙箱状态，verify 前断开网络 |
| 召回与协同审计 | Jev 初筛提供 priority、flags 和 mitigations 线索；`security-orchestrator` 组织项目画像、路由/认证、语言与框架攻击面分析，并分派子任务 | Jev 只负责召回，不直接生成 finding；除模型 API 和指定初筛服务外不访问公网 |
| 增量报告 | 审计开始即创建报告骨架，每个子任务完成后增量更新；finding 必须带文件/行号、根因、影响、复现思路和修复建议 | `raw.jsonl` 保留真实动作流，`claude.rendered.log` 供人阅读，`audit-report.md/json` 保存结论 |
| 质量与运行状态 | `check_report.py` 检查 schema、必填字段和系统语言；`run-meta.json` 记录尝试次数、退出码、超时、中断和 `reports_complete` | 模型正常退出但报告不合格仍算失败；草稿和质量不合格报告不发布到台账 |
| Deadline 与恢复 | 所有尝试和重试共享墙钟预算；`progress_guard.py` 按 setup/model/tool 的真实事件判活；`durable_recovery.py` 校验并复用分支成果，隔离失败任务 | 已完成且校验匹配的产物不重跑；恢复源证据不可变，恢复后继续未完成工作和 Phase 4 |
| 发布到下游 | 完整有效报告进入 Finding Ledger；`run.sh` 可继续执行 Phase 4 自动验证，之后连接视觉报告、状态编译和自动分类 | 静态 finding 仍需 verify / red-team 证据才能晋级，不能跳过验证门 |

`run.sh` 在单项目挖掘前还可执行 Phase 0 环境构建，在报告质量门通过后执行 Phase 4 Top-N Critical/High 验证。环境构建失败、报告不完整或验证 blocked 都保留明确状态，不伪装成 ready/confirmed。挖掘负责“找候选并保留证据”，verify 负责“验证候选”，red-team lab 负责“在隔离环境中证明可利用性”，三者不能互相冒充。

### 持久沙箱生命周期

Phase 0 生成的镜像以 `mygoldmine:dev` 为基础，同时包含 Claude Code 和目标依赖。`run.sh` 默认通过 `scripts/env/sandbox.sh` 为每个 run 创建独立持久容器；`PERSIST_SANDBOX=0` 可退回一次性容器。沙箱名称和元数据保存在 `<run>.meta/sandbox.json`，不保存模型密钥。

```bash
# 创建/查看（run.sh 默认自动创建）
bash scripts/env/sandbox.sh start --project <project> --run-dir <run> --source <source>
bash scripts/env/sandbox.sh status --project <project> --run-dir <run>

# 在同一 /workspace/repo 中继续探索
bash scripts/env/sandbox.sh exec --project <project> --run-dir <run> -- <command>
bash scripts/env/sandbox.sh shell --project <project> --run-dir <run>

# 离线验证；run.sh 在 Phase 4 前自动 isolate
bash scripts/env/sandbox.sh isolate --project <project> --run-dir <run>
bash run.sh --verify-only <run>

# stop 保留容器与工作副本；remove 才删除容器
bash scripts/env/sandbox.sh stop --project <project> --run-dir <run>
bash scripts/env/sandbox.sh remove --project <project> --run-dir <run>
```

挖掘使用 `/target` 的只读源码生成 `/workspace/repo`，之后 verify 和人工 shell 都进入这个工作副本。verify 复用沙箱时要求网络数为零，且同一工作副本上的 harness 串行执行，避免并行写入冲突。恢复 run 若不能共享原 run 的产物挂载，自动回退到独立验证容器；沙箱创建失败也保留一次性执行路径，不阻断挖掘。

## 3. 核心组件

| 路径 | 职责 |
|---|---|
| `scripts/env/sandbox.sh` | 每个 run 的持久沙箱生命周期、交互 shell、网络隔离与工作副本复用 |
| `scripts/mine/mine_one_docker.sh` | 进入持久沙箱或启动一次性审计容器，生成原始报告并触发视觉/自动分类 |
| `scripts/mine/progress_guard.py` | 以共享 deadline 和真实进展区分 setup/model/tool idle，超时统一失败语义 |
| `scripts/mine/durable_recovery.py` | 持久化分支成果、隔离失败并恢复未完成工作，recovery 后继续 Phase 4 |
| `scripts/workflow/finding_ledger.py` | 扫描全部有效 run，生成 occurrence/semantic 双层身份和历史台账 |
| `scripts/workflow/build_state.py` | 基于台账合并 verify、CVE 和人工状态，重算红队 provenance 并生成 review 门槛 |
| `scripts/workflow/refine_worker.py` | 按 source hash 重算路由，低价值归档，高分晋级 |
| `scripts/verify/run_verify.sh` | 在独立容器或已断网的持久沙箱中验证单条 finding |
| `scripts/verify/auto_verify.sh` | 批量静态/环境预验证；共享工作副本时串行执行 |
| `scripts/redteam/lab.py` | 创建受限 victim/attacker 容器、内部网络、随机 flag、执行工具 |
| `scripts/redteam/agent.py` | OpenAI-compatible 红队 agent loop，只从真实工具输出捕获 flag |
| `scripts/redteam/judge.py` | 确定性 provenance 校验 + 独立模型审核 |
| `scripts/redteam/batch.py` | 按 finding 构建/预检 lab，保留结构化失败原因 |
| `.claude/skills/project-cartographer/` | 视觉模型、结构/覆盖/攻击场景图、image2 插图 |
| `ui/` | 看板、表格、项目地图、持续监控、系统架构和运行详情 |
| `audit_rsi/` | 经验构建、标签合并、效用训练、留出回放、统计门禁和只读建议（shadow） |
| `rsi_version/` | 不可变候选版本、发布复核和回滚存储 |

## 4. 身份、状态与优先级

每个 finding 有两层身份：`occurrence_id=project/run_id/local_id` 精确定位一次观测，`semantic_id` 由项目、规范化证据路径、根因和 CWE 汇聚多轮审计语义。历史报告独有的 finding 不会因新 run 而消失；运行中或质量不合格的草稿不会替代最新完整报告。旧 `project:id` 状态仅在语义唯一时兼容，存在歧义时不猜测继承。

状态优先级：

```text
state.json（人工） > curated.json（人工种子） > refine-state.json（worker） > auto-state.json（自动） > inbox
```

| 状态 | 含义 | 是否给人看 |
|---|---|---|
| `inbox` | 未处理候选，尚未进入下一阶段 | 默认隐藏 |
| `triage` | 自动评分进入分诊 | 流程视图 |
| `reproduce` | CVE Tier 候选或 confirmed verify；等待验证（尚未复现） | 流程视图 |
| `cve` | CVE 去重/跟踪 | 流程视图 |
| `archived` | 可重算的低优先级归档，不是安全结论 | 默认隐藏 |
| `closed` | 人工关闭/FP/重复/已知 | 流程视图 |
| `review` | 可信红队 + judge + 图文全部通过 | 人工验收 |

## 5. 自动分类 worker（refine）

输入：schema v2 台账 + 现有自动/人工状态。输出 `refine-state.json`、`refine-queue.json` 和 `rsi/trajectories/refine.jsonl`。

规则：

- 每条决策保存 `source_hash`；raw、verify、CVE 或人工证据变化时重新计算。
- 已归档项获得 confirmed verify 后重新进入队列并转为 reproduce。
- 弱指纹只标记 duplicate_candidate；High/Critical 不凭弱指纹直接归档。
- CVE Tier、verify confirmed → reproduce；Critical/High → triage；其他低分项 → archived。
- 所有决策可回放；archived 不删除原始报告。
- `--loop` 在空队列时 sleep 并继续扫描，不会因暂时 pending=0 退出；新 run 和新证据能持续进入经验链。

## 6. 动态验收 lab 契约

lab 由 `redteam-lab-builder` 按 finding 生成到 `labs/<project>/<finding-id>/`。scenario 绑定 finding 内容哈希和 source commit/content hash；builder 退出为 0 且结构化校验通过才算 ready。当前执行器只支持 HTTP，其他 mode 明确 blocked，不能用 HTTP 包装冒充。

不变量：

- internal Docker network，victim 不发布宿主机端口
- victim/attacker 均有 cap-drop、no-new-privileges、PID/内存/CPU 限制
- flag 只由 harness 只读挂载到 victim 的 `/flag`
- attacker 不挂载宿主、flag 或 Docker socket，scenario 不声明 mounts/volumes
- flag 只能从真实工具输出捕获；最终回答本身不是证据
- trace 记录工具事件、输出 SHA-256、flag SHA-256 和捕获事件
- trace/agent 日志是 untrusted data，judge 不能被其指令带偏

## 7. Judge 契约

`judge.json` 使用完整固定 schema，包含 verdict、intended_vulnerability、flag_provenance、no_cheat、environment_plausible、reproducible、minimal、confidence、reason、concerns 和 recommended_status。approved 的全部必要布尔字段必须为 JSON true，且 recommended_status 为 runtime-validated。

程序在调用 judge 和接收结果时都会重算确定性 provenance；缺字段、字符串布尔、旧 judge 文件或哈希不一致均拒绝。review 构建还会再次验证 result 中记录的 provenance，旧“仅 judge approved”结果不能绕过。安全验证通过后，人工 review 队列仍要求图文报告和 scene 图；视觉素材本身不是漏洞证据。

## 8. 图文报告

`project-cartographer` 生成：

- `visual-model.json`：结构/覆盖/攻击树/attacker-victim 场景
- `project-map.svg`、`coverage-tree.svg`、`attack-*.svg`
- `scene-*.svg`：准确的双方步骤
- `scene-*.webp`：image2 叙事插图
- `report-illustrated.md`：给人工验收的图文 case

插图必须标注“AI 插图，非漏洞证据”。视觉素材不能替代 trace 和 judge。

## 9. RSI 学习流程（只读建议）

当前实现是 Verification-RSI 的**只读建议模式**（`shadow`，只生成建议，不改变生产状态），不是已经接管生产审计的 RSI。真实运行会留下动作前上下文、动作、结果、成本和证据来源链；策略学习验证动作的收益，独立留出集与非回归检查决定候选能否进入发布复核。系统不会让模型直接改写自己，也不会把最终报告回放包装成在线发现能力。

当前只读建议模式已跑通，但尚未完成“验证、发布、结果回写”的一整圈：训练支持 91 条全部为 `static`，可用于动作训练的 `trusted` 样本为 0；回放状态为 `insufficient`；没有 `flips` 产物；发布与结果回写尚未接入 `audit_rsi` CLI。

主流程保持以下六步，架构页按相同顺序提供可点击实现详情：

```text
01 真实轨迹（verification / redteam 经验）
  → 02 标签与证据等级（runtime / judge / manual；static 不冒充 trusted）
  → 03 效用学习（固定五动作词表做 ridge utility regression；当前仅 deep_read 25 条、defer 66 条有样本）
  → 04 留出验证 + 同动作回放 + 结果翻转观测
  → 05 只读建议（recommendation_only=true，state_change=none）
  → 06 结果回写（尚未接入：accepted 候选经发布复核后才可进入既有流程）
  └──────────────── 新真实结果回到 01（第 06 步尚未接入）
```

第 06 步是计划中的发布路径，尚未接入 CLI，不是只读建议的自动升级。`trusted_support=0` 时仍停留在第 05 步，以 `static-only / no_trusted_utility_targets` 继续生成只读建议，不发布为生产策略（不生产 promote），也不宣称生产 RSI。回放只描述同动作的实际收益，flips 只描述真实经验集合之间的观测变化，两者都不是因果评估。

红队 harness 形成第二条学习支路，与验证动作效用学习分开：

```text
红队真实 run/step 轨迹
  → 确定性弱点聚类（失败类别、支持度、成本、editable surface）
  → 白名单 harness proposal（稳定 candidate_id，mutation=none）
  → 独立 paired outcome flips + 候选/发布复核
  → 受控变更后的新红队轨迹
```

这条支路只生成候选证据与提案，不自动修改 harness；`validated` 也不等于已经发布。

`audit_rsi/adapters/raw_trace.py` 另行把真实 Claude stream-json 转为 action 轨迹，保留 Task/Agent 父子拓扑、实际结果和成本；未知 propensity 保持 null。最终报告重建树只用于旧回放，不能证明未探索分支的发现效果。

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

unknown 不等于 FP；无合法标注倾向、holdout、标签覆盖或支持度时只输出 insufficient/只读建议（shadow），不生产 promote。回放只报告 matched-action realized utility，不宣称因果 uplift。`verify-flips` 按 semantic 比较两个真实经验池的 F→P/P→F、稳定项、配对覆盖和 unknown 转移，用于观测非回归，不把不同 run 的结果解释成反事实或因果效果。候选门禁默认要求 `paired_coverage>=0.8`、至少一个 F→P 且零 P→F；覆盖不足为 insufficient，有修复但出现回归为 rejected，满足条件才为 accepted。`mutation=none`，accepted 仍需候选复核和既有发布门禁。版本发布复核统计 gate，失败候选仍可查询和回滚。

`redteam-experience` 将 run 级结果与 step 级 attacker 工具事件分开：记录角色、动作、成本、返回码、输出哈希、失败分类和 evidence class，不复制原始攻击命令、输出正文或 flag。只有确定性 provenance 可重算的捕获才自动成为 runtime 标签；judge approved 还要求审核状态与重算结果一致。`not_captured`、篡改轨迹和未复核结果保持 unknown，不成为 FP 或可信奖励。

`redteam-weakness` 对这些轨迹做确定性 Weakness Mining：按项目类型、攻击模型、失败类别、严重度聚类，输出 occurrence 支持度、事件支持度、平均成本和候选 editable surface。`model_timeout`、`lab_unhealthy`、`not_captured`、工具失败和结构化输出失败映射到不同 harness 表面。该产物只是候选证据包，`mutation=none`，候选修改仍须独立回放与非回归门禁。

`harness-propose` 只允许白名单 editable surface，为每个提案生成稳定 `candidate_id`、目标失败、证据哈希、保留行为和验证要求；不会直接修改 harness。`harness-validate` 重算提案身份并调用 outcome flip gate，只有 accepted 才标记 validated，身份篡改、回归或证据不足均不能通过。候选提案和验证结果都可审计、可回放，仍需后续发布复核。

经验构建同时读取 `verdict.json`、`verify-report.json` 和 `auto-state.json`：自动路由提供 `deterministic-auto-state` 动作及倾向，verify 提供 static/runtime 结果，不能把有结果但无动作的样本静默丢弃。runtime verify 与人工 curated 可自动获得确定标签来源；static verify 只进入只读建议的学习；judge 仍需独立标签复核，不自动获得 label propensity。

`label-plan` 在普通分层抽样之外优先补齐完全缺少 trusted 的项目和动作，再考虑 top-up 覆盖；无动作记录不进入人工标注队列。每个任务保留 occurrence/semantic 身份、抽样原因、分层配额和 label propensity，并过滤敏感上下文。该计划只提高标注效率，不把 unknown 自动变成 trusted。

agent 可以辅助做源码级静态标注，但必须使用 `evidence_class=static` 和 `adjudication.method=agent-static`，不能冒充 human/runtime/judge。只有 static 标签时只读建议明确为 `static-only / no_trusted_utility_targets`，即使训练产生了不同建议，也不得视为已验证提升或生产候选。

## 10. 运行手册

```bash
# 全量看板
bash scripts/ui/start.sh

# 自动分类 worker
bash scripts/workflow/refine_worker.sh start
bash scripts/workflow/refine_worker.sh status

# 单条红队
python3 scripts/redteam/agent.py --finding <finding.json> --victim-image <image>
python3 scripts/redteam/judge.py --run-dir <redteam-run>

# 17 条批次
python3 scripts/redteam/batch.py --dry-run
python3 scripts/redteam/batch.py
```

## 11. 失败模式

| 现象 | 处理 |
|---|---|
| 无 lab scenario | `blocked_no_lab`，不进入验收 |
| victim 未启动 | LabError，保留 run 目录和容器日志 |
| 红队拿不到 flag | `not_captured`，不进入 review |
| 红队直接读 flag | judge 拒绝 |
| judge 证据不足 | `needs_review`，不要猜 |
| 图片生成失败 | 保留 SVG，不阻塞报告 |
| worker 并发 | lock file 防止双实例 |

## 12. 开发扩展点

新增项目 lab：

1. 构建可直接启动的 victim image。
2. 确认服务在 `--internal` 网络内健康。
3. 决定 flag 如何只通过目标漏洞暴露。
4. 按 finding/source 绑定写 `labs/<project>/<finding-id>/scenario.json`。
5. 用 demo finding 跑一遍 `agent.py` + `judge.py`，确认确定性 provenance 校验通过。
6. 再把真实 finding 加入 `docs/redteam-candidates.json`。

新增 judge 规则：

- 只改 `exploit-judge.md` 和 `judge.py` 的输出 schema，不改变红队工具权限。
- judge 不能调用攻击工具，不能修改 trace/finding/result。

## 13. 架构说明维护

根目录 `AGENTS.md` 定义了同步契约。模块、数据流、finding 身份、状态门禁、API、恢复机制、安全边界或 RSI 发布关系变化时，同一轮修改必须核对本文和 `ui/src/components/ArchitectureView.jsx`；用户入口变化还要核对 README。局部且不改变行为的修复不需要机械更新，但不能保留已知过时描述。

架构页是面向使用者的三级实现摘要：第一级用整体漫画地图展示挖掘工厂、自动分类与验证、红队与验收、核心组件、RSI 学习流程五个区域；第二级展示该区域的中层阶段和组件，其中 RSI 区域先用“为什么能学习”与当前只读建议边界建立整体认识，再用带方向箭头和结果回写连接的六步流程展示主流程，并单独画出“红队轨迹 → 弱点聚类 → Harness 候选 → 独立评估”的第二支路；第三级才展示输入输出、设计契约、实现入口、失败语义和优化检查点。漫画由 360 平台的 `bytedance/doubao-seedream-5.0-pro` 生成，仅用于叙事，不代替准确的节点关系或安全证据。本文是面向开发人员的完整契约，两者都不能把计划、静态标签或只读建议描述成已验证、已发布的生产能力。修改模块职责或契约时，也要同步对应中层节点和实现详情，不能只改视觉或标题。
