# TODOLIST — mygoldmine 漏洞挖掘自动化

> 本文件是 ralph loop 的需求来源。规则：每轮只做**一个**未完成任务；完成后勾选，并把
> `.agent/tasks.json` 中对应任务的 `status` 改为 `done`；每个任务单独 commit。
> 机器可读任务列表以 `.agent/tasks.json` 为准，本文件用于人读与验收。

## 总目标

把 mygoldmine 从「Web / 智能合约审计框架」扩展成「可对 AI 基础设施源码做持续漏洞挖掘」的流水线：

1. 汇总 codex、deepseek harness、vLLM、SGLang、verl 等项目的公开漏洞，找出 mygoldmine 的能力缺口并补齐 skill / agent。
2. 参考 `/home/wzk/projects/exploitgym`，让 Claude Code 在 Docker 中运行 mygoldmine 做漏洞挖掘，并产出 `claude.rendered.log` 过程日志。
3. 克隆目标源码，5 个项目并行，每个项目单次挖掘 ≤ 6h，用 360 平台的 `deepseek/deepseek-v4.1-flash`，可断点续跑，支持整夜无人值守。

## 安全与成本约束（所有任务都必须遵守）

- 只分析**本地克隆的开源仓库副本**，不扫描公网、生产环境或未授权目标。
- 只做漏洞定位、根因分析、最小复现与修复建议；**不编写可直接武器化的 exploit**。
- 容器默认非 root、默认断网，只挂载目标目录与只读配置；克隆/装依赖时显式放行网络。
- API key、token 只从环境变量读取，禁止写入仓库、日志或 `run-meta.json`。
- 不在实现阶段启动真实 6h 挖矿；只允许 `--dry-run` / 小样本冒烟。
- 每个任务单独 commit，不删除或大改已有 skill，采用增量新增。

## 目录约定

```
.agent/                     ralph 状态与提示词
.claude/skills/             现有 84 个 skill，新增 skill 放这里
research/                   漏洞汇总与差距分析
docker/                     Dockerfile、entrypoint
scripts/mine/               克隆、单项目挖掘、并行编排、日志渲染
runs/<project>/<ts>/        每次挖掘产物
  claude.rendered.log       人读过程日志
  raw.jsonl                 原始事件流
  audit-report.md/json      mygoldmine 报告
  run-meta.json             项目/提交/耗时/模型/退出码（不含密钥）
targets/                    克隆的目标源码（gitignore）
logs/                       编排器与 ralph 日志（gitignore）
```

---

## Phase 1 — 公开漏洞汇总与能力差距

### T01 公开漏洞汇总

- [x] 已完成（2026-10-27）：产出 `research/disclosed-vulns.md` 与 `research/disclosed-vulns.json`，共 38 条，5 个项目均 ≥3 条。
- 目标：调研 codex、deepseek harness（DeepSeek 官方仓库/推理 harness）、vLLM、SGLang、verl 的公开漏洞与安全公告。
- 来源优先级：GitHub Security Advisory、NVD/CVE、项目 SECURITY.md、release notes、已修复的 security PR、可信 writeup。
- 产物：
  - `research/disclosed-vulns.md`（按项目分组，人读）
  - `research/disclosed-vulns.json`（字段：project, id, type, component, affected, severity, summary, source_url, fix_ref）
- 验收：5 个项目每个至少 3 条可核实条目；每条都有 URL；无法核实的标注 `unverified`，不得编造 CVE 编号。
- 注意：只记录公开信息，不下载/运行 exploit。

### T02 现有能力盘点

- [x] 已完成（2026-10-27）：产出 `research/capability-matrix.md`，覆盖 T01 全部 29 个 type；记录 82 个含 `SKILL.md` 的 skill、3 个可执行 agent、7 个 quick-scan（4 个 tree-sitter）及本机依赖缺失情况。
- 目标：盘点 mygoldmine 现有 84 个 skill、4 个 agent、tree-sitter quick-scan 的实际检测范围。
- 产出 `research/capability-matrix.md`：漏洞类型 × skill/scanner × 检测方式（tree-sitter/规则/LLM）× 覆盖度（强/弱/无）× 证据路径。
- 验收：至少覆盖 T01 中出现的全部漏洞类型；每个「强/弱」结论都有具体文件路径或代码行佐证。

### T03 差距分析

- [x] 已完成（2026-10-27）：产出 `research/gap-analysis.md`，归并 15 个缺口、覆盖 26/38 条 T01 条目（P0 5 个 / P1 7 个 / P2 3 个），并给出编排差距 O01-O04、误报排除规则与 T04 落地顺序。
- 目标：对比 T01 与 T02，输出 `research/gap-analysis.md`。
- 内容：缺失类型、弱覆盖类型、误报风险、优先级（P0/P1/P2）、建议实现方式（新 skill / 扩展现有 skill / tree-sitter 规则 / agent 编排）。
- 验收：每个缺口都对应到 T01 的具体条目；给出可执行的下一步，而不是泛泛而谈。

### T04 新增高优先级 skill（至少 2 个）

- [x] 已完成（2026-10-27）：新增 `model-loading-analyzer`、`agent-config-analyzer`，各含 `SKILL.md`、`quick-scan.py`、`patterns/*.json`；真实位置引用 vLLM `20bf65ad`、SGLang `3a62cdfb`、verl `174888fc`、codex `970111f6`、deepseek-harness `22ddee37`。
- 目标：按 T03 的 P0/P1，新增至少 2 个 skill，优先考虑：
  - 推理框架：权重加载/反序列化（pickle、torch.load、safetensors）、路径遍历、SSRF（模型下载）、HTTP/gRPC 解析、调度器并发/竞态、资源耗尽。
  - Agent/训练框架：工具调用权限、提示注入、沙箱逃逸、分布式通信（Ray/NCCL/ZeroMQ）、配置注入。
- 每个 skill 目录必须包含：`SKILL.md`（适用场景、检测步骤、sink/source、误报排除、输出格式）、必要的模式文件；可选 `quick-scan.py`。
- 验收：`SKILL.md` 结构完整；至少给出 2 个**目标仓库内真实存在的代码位置**作为示例（可用 grep 定位）；不产生明显误报规则。
- 约束：新增，不修改无关 skill。

### T05 接入编排与文档

- [x] 已完成（2026-10-27）：`security-orchestrator.md` 新增 AI 基础设施条件任务，`project-profiler` 支持按特征追加新 skill；`skills/README.md` 与根 `README.md` 已更新并拆分显式调用/自动调度；产出 `research/phase1-summary.md`。命名过滤 `-scanner`/`-analyzer` 保持不变。
- 目标：更新 `.claude/agents/security-orchestrator.md`、`.claude/skills/README.md`、根 `README.md`，把新 skill 接入工作流、白名单与命名规则。
- 产物：更新后的 agent/skill 文档 + `research/phase1-summary.md`（一页结论）。
- 验收：orchestrator 的 skill 过滤规则（`-scanner`/`-analyzer`）仍成立；新 skill 能在工作流中被引用；文档无死链。

---

## Phase 2 — Docker + Claude Code + rendered log

### T06 设计文档

- [x] 已完成（2026-10-27）：产出 `docs/docker-claude-mining.md`，覆盖镜像/挂载/用户/网络/超时/stream-json/日志字段/重试，并给出 12 项与 exploitgym 的差异及 dry-run、真实运行、渲染命令示例。
- 目标：阅读 `/home/wzk/projects/exploitgym` 的 `src/cybergym/evaluation/agents/claude_code.py`、`scripts/collect_rendered_logs.sh`、`scripts/setup/pull_images.py`，提炼可复用设计。
- 产物 `docs/docker-claude-mining.md`：镜像基础、挂载、用户、网络策略、超时/预算、stream-json 协议、日志字段、失败重试。
- 验收：明确列出与 exploitgym 的差异（mygoldmine 的 `.claude` 链接方式、报告路径）；给出命令示例。

### T07 Docker 镜像与入口

- [x] 已完成（2026-10-27）：产出 `docker/Dockerfile`、`.dockerignore`、`scripts/mine/entrypoint.sh`。镜像基于 `python:3.12-slim`，非 root（miner UID/GID 可构建期覆盖），预装 git/jq/rg/python/tree-sitter/Claude Code 2.1.138，未安装 Docker CLI。`docker build` 成功；`docker run --rm --network none ... --dry-run` 退出 0 并打印配置、提示词与审计命令；挂载 `/var/run/docker.sock` 时真实运行退出 7（可用 `ALLOW_DOCKER_SOCKET=1` 覆盖）；缺少 T08 脚本时真实运行退出 5 且不创建 RUN_DIR。
- 目标：实现 `docker/Dockerfile` 与 `scripts/mine/entrypoint.sh`。
- 要求：非 root 用户、固定工作目录、预装 python3/jq/git/tree-sitter 依赖、支持 `TARGET_DIR`、`RUN_DIR`、`TIMEOUT`、`MODEL`、`AGENT` 环境变量；默认不挂载 docker socket。
- 验收：`docker build` 成功；`docker run --rm ... --dry-run` 能打印将执行的审计命令与配置。

### T08 单项目挖掘脚本

- [x] 已完成（2026-10-27）：产出 `scripts/mine/mine_one.sh`。支持 `--dry-run`、`--run-dir/--target/--prompt/--timeout/--model/--agent/--project/--target-url`；运行前链接 `.claude`，以 stream-json 调用 Claude 并写 `raw.jsonl`，优先调用 T09 渲染器、缺失时用 jq fallback 生成 `claude.rendered.log`，写出 `audit-report.md/json` 与不含密钥的 `run-meta.json`。用 stub CLI 验证：正常样本退出 0 且 5 类文件齐全；`TIMEOUT=2` 的阻塞样本退出 124、`timed_out=true` 且保留日志；TERM 中止退出 143、`interrupted=true` 且无残留子进程；无报告时退出 2；RUN_DIR 非空时退出 6；URL userinfo 已剥离。
- 目标：实现 `scripts/mine/mine_one.sh`，在容器内运行 Claude Code + mygoldmine。
- 行为：在目标目录链接 `.claude`，执行 security-orchestrator 审计，写出 `audit-report.md/json`，原始 stream 写 `raw.jsonl`，渲染后写 `claude.rendered.log`，元信息写 `run-meta.json`（不含密钥）。
- 验收：`--dry-run` 可运行；真实小样本能产出上述 4 类文件；超时后能优雅退出并保留日志。

### T09 日志渲染器

- 目标：实现 `scripts/mine/render_claude_log.py`，把 stream-json 渲染成人读 `claude.rendered.log`（工具调用、文件改动、命令、耗时、错误）。
- 验收：用 T08 的 `raw.jsonl` 生成日志；字段缺失/乱码时降级不崩溃；附单元测试或 `--self-test`。
- 参考：exploitgym `scripts/analyze_logs.py`、`tests/evaluation/test_claude_stream_renderer.py`。

### T10 容器冒烟

- 目标：选一个**小仓库**（可用 mygoldmine 自身或 tests/fixtures）跑通 T07-T09。
- 产物 `docs/docker-smoke-test.md`：命令、耗时、产物截图/摘录、已知限制。
- 验收：`claude.rendered.log` 非空且可读；退出码与 `run-meta.json` 一致；无密钥泄漏。

---

## Phase 3 — 并行整夜挖掘

### T11 目标克隆

- 目标：实现 `scripts/mine/clone_targets.sh`，克隆/更新：
  - `openai/codex`（或实际可访问的 codex 源码仓）
  - DeepSeek 官方推理 harness 仓库（以 T01 确认的 URL 为准）
  - `vllm-project/vllm`
  - `sgl-project/sglang`
  - `volcengine/verl`
- 要求：浅克隆可配置、支持 `--update`、超时、失败不阻塞其他项目、写入 `targets/manifest.json`（url/commit/clone_time）。
- 验收：`--dry-run` 打印计划；至少 1 个真实浅克隆成功；manifest 记录 commit。

### T12 并行编排器

- 目标：实现 `scripts/mine/parallel_mine.sh`：最多 5 个并发、每项目 `TIMEOUT=6h`、失败重试 1 次、断点续跑（已完成项目跳过）、独立日志、单实例锁、`--stop`、`--status`。
- 要求：用 `setsid/nohup` 脱离终端；记录 PID；磁盘余量 < 20G 时拒绝启动；`--dry-run` 展示计划。
- 验收：`--dry-run`、`--status` 可用；用假目标（`sleep`）验证超时与并发上限。

### T13 整夜启动/恢复

- 目标：实现 `scripts/mine/overnight.sh`：`start|stop|status|resume`，默认 `MODEL=360-proxy/deepseek/deepseek-v4.1-flash`、`MAX_PARALLEL=5`、`TIMEOUT=21600`。
- 产物 `docs/overnight-run.md`：一条启动命令、如何看进度、如何止损、次日如何收报告。
- 验收：`overnight.sh status` 能读出运行中/完成/失败；`resume` 只补未完成项目。

### T14 验证脚本

- 目标：实现 `scripts/mine/verify.sh`：检查目录结构、报告完整性、日志非空、JSON 可解析、无密钥模式（如 `sk-`、`api_key`）。
- 验收：对 T10 冒烟产物通过；对故意缺文件/含假 key 的样本能报错。

### T15 总验收与收尾

- 目标：跑完整 `verify.sh`，更新 `TODOLIST.md` 勾选状态、`README.md` 快速开始、`research/phase1-summary.md`。
- 验收：`scripts/mine/verify.sh` 退出 0；文档给出「今晚怎么跑、明早看哪里」；`.gitignore` 覆盖 `targets/`、`runs/`、`logs/`、`.agent/history/`。

---

## 初判差距假设（待 T01-T03 用证据确认，不得直接当结论）

现有 84 个 skill 偏 Web 漏洞与智能合约，对 AI 基础设施可能弱覆盖：

- C/C++/CUDA 内存安全：越界读写、整数溢出、use-after-free（推理 kernel、KV cache、张量并行）。
- Python 反序列化与权重加载：`pickle`、`torch.load`、`safetensors`、`transformers` 自定义代码。
- 服务端解析：HTTP/gRPC/Protobuf 边界、请求 smuggling、分块编码、超大 header。
- 并发与分布式：调度器竞态、Ray/NCCL/ZeroMQ 通信、共享状态、死锁/资源耗尽。
- 路径与下载：模型/配置下载 SSRF、权重路径遍历、缓存投毒。
- Agent 框架：工具调用越权、提示注入、命令执行、沙箱逃逸、MCP 权限。
- 供应链：依赖混淆、构建脚本、CI 注入。

## 完成定义（DoD）

- Phase 1：有可核实的漏洞清单、能力矩阵、差距报告，且至少 2 个新 skill 落地并接入。
- Phase 2：Docker 内可跑通 mygoldmine，产出 `claude.rendered.log` 和报告。
- Phase 3：一条命令并行 5 个项目、每项 6h 上限、可断点续跑、可查状态、次日可收报告。
