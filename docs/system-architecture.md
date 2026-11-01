# 系统架构说明

面向开发人员。目标是把“静态挖掘 → 精炼 → 动态验收 → 人工展示”做成一条可运行、可审计、可回放的流水线。

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
│ 跨 run 历史台账    │  finding-ledger.json
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
│ 精炼状态           │  refine-state.json / refine-queue.json
│ 分诊/复现/归档     │
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
| 发布到下游 | 完整有效报告进入 Finding Ledger；`run.sh` 可继续执行 Phase 4 自动验证，之后连接视觉报告、状态编译和精炼 | 静态 finding 仍需 verify / red-team 证据才能晋级，不能跳过验证门 |

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
| `scripts/mine/mine_one_docker.sh` | 进入持久沙箱或启动一次性审计容器，生成原始报告并触发视觉/精炼 |
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
| `audit_rsi/` | 经验构建、标签合并、效用训练、holdout 回放、统计门禁和只读 shadow |
| `rsi_version/` | 不可变候选版本、发布复核和回滚存储 |

## 4. 身份、状态与优先级

每个 finding 有两层身份：`occurrence_id=project/run_id/local_id` 精确定位一次观测，`semantic_id` 由项目、规范化证据路径、根因和 CWE 汇聚跨 run 语义。历史报告独有的 finding 不会因新 run 而消失；运行中或质量不合格的草稿不会替代最新完整报告。旧 `project:id` 状态仅在语义唯一时兼容，存在歧义时不猜测继承。

状态优先级：

```text
state.json（人工） > curated.json（人工种子） > refine-state.json（worker） > auto-state.json（自动） > inbox
```

| 状态 | 含义 | 是否给人看 |
|---|---|---|
| `inbox` | 原始池，未晋级 | 默认隐藏 |
| `triage` | 自动评分进入分诊 | 流程视图 |
| `reproduce` | 有明确 confirmed verify，待复现/补 PoC | 流程视图 |
| `cve` | CVE 去重/跟踪 | 流程视图 |
| `archived` | 可重算的低优先级归档，不是安全结论 | 默认隐藏 |
| `closed` | 人工关闭/FP/重复/已知 | 流程视图 |
| `review` | 可信红队 + judge + 图文全部通过 | 人工验收 |

## 5. 自动精炼 worker

输入：schema v2 台账 + 现有自动/人工状态。输出 `refine-state.json`、`refine-queue.json` 和 `rsi/trajectories/refine.jsonl`。

规则：

- 每条决策保存 `source_hash`；raw、verify、CVE 或人工证据变化时重新计算。
- 已归档项获得 confirmed verify 后可唤醒到 reproduce。
- 弱指纹只标记 duplicate_candidate；High/Critical 不凭弱指纹直接归档。
- CVE Tier、verify confirmed → reproduce；Critical/High → triage；其他低分项 → archived。
- 所有决策可回放；archived 不删除原始报告。

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

## 9. RSI 回路

当前优先落地 Verification-RSI，而不是把最终报告回放包装成在线发现能力：

```text
Finding Ledger + refine/validation + verify/人工标签
  → verification-experience.jsonl（身份、pre-action context、倾向、效用和血缘）
  → 分层抽样/人工标签合并
  → 强正则效用模型 + baseline 对照
  → 统计门禁 → shadow → 不可变候选版本
```

`audit_rsi/adapters/raw_trace.py` 另行把真实 Claude stream-json 转为 action 轨迹，保留 Task/Agent 父子拓扑、实际结果和成本；未知 propensity 保持 null。最终报告重建树只用于旧回放，不能证明未探索分支的发现效果。

常用命令：

```bash
python3 -m audit_rsi experience-build --runs runs --output rsi/verification-experience.jsonl
python3 -m audit_rsi label-sample --pool rsi/verification-experience.jsonl --output rsi/verification-label-sample.jsonl --limit 100
# 人工填写 verdict/evidence_class 后合并，再训练和生成只读建议
python3 -m audit_rsi label-merge --pool rsi/verification-experience.jsonl --labels rsi/verification-label-sample.jsonl --output rsi/verification-experience-labeled.jsonl
python3 -m audit_rsi verify-train --pool rsi/verification-experience-labeled.jsonl --output rsi/verification-policy.json --holdout-project <project>
python3 -m audit_rsi verify-shadow --pool rsi/verification-experience-labeled.jsonl --train rsi/verification-policy.json --output ui/data/verification-shadow.json
python3 -m audit_rsi verify-replay --pool rsi/verification-experience-labeled.jsonl --train rsi/verification-policy.json --holdout-project <project> --output rsi/verification-replay.json
```

unknown 不等于 FP；无合法标注倾向、holdout、标签覆盖或支持度时只输出 insufficient/shadow，不生产 promote。回放只报告 matched-action realized utility，不宣称因果 uplift。版本发布复核统计 gate，失败候选仍可查询和回滚。

agent 可以辅助做源码级静态标注，但必须使用 `evidence_class=static` 和 `adjudication.method=agent-static`，不能冒充 human/runtime/judge。只有 static 标签时 shadow 明确为 `static-only / no_trusted_utility_targets`，即使训练产生了不同建议，也不得视为已验证提升或生产候选。

## 10. 运行手册

```bash
# 全量看板
bash scripts/ui/start.sh

# 精炼 worker
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

架构页是面向使用者的三级实现摘要：第一级用整体漫画地图展示挖掘工厂、精炼与验证、红队与验收、核心组件、学习与视觉五个区域；第二级只展示该区域的中层阶段和组件；第三级才展示输入输出、设计契约、实现入口、失败语义和优化检查点。漫画由 360 平台的 `bytedance/doubao-seedream-5.0-pro` 生成，仅用于叙事，不代替准确的节点关系或安全证据。本文是面向开发人员的完整契约，两者都不能把计划、静态标签或 shadow 描述成已验证、已发布的生产能力。修改模块职责或契约时，也要同步对应中层节点和实现详情，不能只改视觉或标题。
