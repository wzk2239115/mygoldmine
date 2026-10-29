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

## 3. 核心组件

| 路径 | 职责 |
|---|---|
| `scripts/mine/mine_one_docker.sh` | 启动审计容器、生成原始报告、触发视觉/精炼 |
| `scripts/workflow/build_state.py` | 扫描报告、verify、CVE handoff/adjudication、redteam 结果，生成自动路由和 review 门槛 |
| `scripts/workflow/refine_worker.py` | 后台分批消费原始池，低价值归档，高分晋级 |
| `scripts/verify/run_verify.sh` | 单条 finding 的隔离容器验证 |
| `scripts/verify/auto_verify.sh` | 批量静态/环境预验证 |
| `scripts/redteam/lab.py` | 创建 victim/attacker 容器、内部网络、随机 flag、执行工具 |
| `scripts/redteam/agent.py` | OpenAI-compatible 红队 agent loop，工具只在 attacker 容器执行 |
| `scripts/redteam/judge.py` | 独立模型审核红队轨迹，写 judge.json |
| `scripts/redteam/batch.py` | 17 条候选的红队批次入口；缺 lab 适配时明确 blocked |
| `.claude/skills/project-cartographer/` | 视觉模型、结构/覆盖/攻击场景图、image2 插图 |
| `ui/` | 看板、精炼管线、待验收队列、详情、项目地图 |
| `rsi/` | 多轮一致性和策略回放 |

## 4. 状态与优先级

状态优先级：

```text
state.json（人工） > curated.json（人工种子） > refine-state.json（worker） > auto-state.json（自动） > inbox
```

状态含义：

| 状态 | 含义 | 是否给人看 |
|---|---|---|
| `inbox` | 原始池，未晋级 | 默认隐藏 |
| `triage` | 自动评分进入分诊 | 流程视图 |
| `reproduce` | 有 verify 记录，待复现/补 PoC | 流程视图 |
| `cve` | CVE 去重/跟踪 | 流程视图 |
| `archived` | 自动筛选归档，不是安全结论 | 默认隐藏 |
| `closed` | 人工关闭/FP/重复/已知 | 流程视图 |
| `review` | 红队 + judge + 图文全部通过 | 人工验收 |

## 5. 自动精炼 worker

输入：最新报告 + 现有自动/人工状态。

输出：

- `ui/data/refine-state.json`：本 worker 的最终状态
- `ui/data/refine-queue.json`：进度、pending、archived、promoted
- `rsi/trajectories/refine.jsonl`：每条决策的 features/decision/score

规则：

- 人工/curated/auto 已处理项跳过。
- 精确重复（project + path + root cause）归档。
- CVE Tier、verify confirmed → `reproduce`。
- Critical/High → `triage`。
- 其他 → `archived`。
- 所有决策可回放；archived 不删除原始报告。

## 6. 动态验收 lab 契约

lab adapter 不是人工写死的，由 `redteam-lab-builder` skill/agent 自动生成。agent 先判断攻击面（http/stdio/cli/library/ipc/model），再构建 victim、flag 暴露路径、attacker 隔离和负向控制；无法构建时写 `BLOCKED.md`，不伪造。

每个项目最终落盘：

```text
labs/<project>/scenario.json
```

```json
{
  "victim_image": "mygoldmine/env:<project>-<commit>",
  "attacker_image": "curlimages/curl:latest",
  "target_url": "http://victim:8000",
  "health_path": "/health"
}
```

不变量：

- `docker network create --internal`
- victim 不发布宿主机端口
- flag 只挂载给 victim，路径 `/flag`
- attacker 不挂载宿主、不挂载 flag、无 Docker socket
- red-team 只拿到 finding JSON，不拿到答案/预置 exploit
- flag 每轮随机；judge 校验 sha256
- trace/agent 日志是 untrusted data，judge 不能被其指令带偏

当前 17 条候选：

- 已进入 `docs/redteam-candidates.json`
- `batch.py` 默认会调用 `redteam-lab-builder` 自动尝试构建 lab；构建不出来才 `blocked_no_lab`
- 这是正确的 fail-closed：没有 lab 就不允许伪造 flag 或进入验收

## 7. Judge 契约

`judge.json` 至少包含：

```json
{
  "verdict": "approved|rejected|needs_review",
  "intended_vulnerability": true,
  "flag_provenance": true,
  "no_cheat": true,
  "environment_plausible": true,
  "reproducible": true,
  "confidence": "high|medium|low",
  "recommended_status": "runtime-validated|needs-rerun|rejected"
}
```

通过条件必须同时满足：

- flag 来自 victim 响应，不是 attacker 侧文件或模型自编
- 命中 finding 的 root cause
- 没有宿主/Docker socket/外网/共享卷/调试后门
- trace 可复现且最小
- 图文报告和 scene 图已存在

## 8. 图文报告

`project-cartographer` 生成：

- `visual-model.json`：结构/覆盖/攻击树/attacker-victim 场景
- `project-map.svg`、`coverage-tree.svg`、`attack-*.svg`
- `scene-*.svg`：准确的双方步骤
- `scene-*.webp`：image2 叙事插图
- `report-illustrated.md`：给人工验收的图文 case

插图必须标注“AI 插图，非漏洞证据”。视觉素材不能替代 trace 和 judge。

## 9. RSI 回路

轨迹来源：

- `rsi/trajectories/refine.jsonl`：自动路由决策
- `rsi/trajectories/validation.jsonl`：红队 judge 通过
- `rsi/consensus/consensus.json`：多轮一致性

后续可以：

1. 用人工验收/拒绝结果给轨迹补标签。
2. 学习哪些特征组合值得晋级。
3. 回放历史策略，比较漏报/误报。
4. 更新 worker 阈值和提示词，但必须保留可回滚版本。

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
4. 写 `labs/<project>/scenario.json`。
5. 用 demo finding 跑一遍 `agent.py` + `judge.py`。
6. 再把真实 finding 加入 `docs/redteam-candidates.json`。

新增 judge 规则：

- 只改 `exploit-judge.md` 和 `judge.py` 的输出 schema，不改变红队工具权限。
- judge 不能调用攻击工具，不能修改 trace/finding/result。
