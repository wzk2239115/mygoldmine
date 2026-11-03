# 环境构建状态（Phase 0）

生成时间：2026-10-27

## 已完成的闭环

| 目标 | 语言 | 模式 | env_status | 镜像 | 说明 |
|---|---|---|---|---|---|
| `tests/fixtures/smoke-target` | generic | auto | ready | `mygoldmine/env:smoke-target-test` | 通用审计/验证闭环冒烟 |
| `targets/verl` | python | auto | partial | `mygoldmine/env:verl-test` | `pip install -e . --no-deps` 成功；运行时依赖未装 |

验证冒烟：

| finding | 项目 | verdict | 报告 |
|---|---|---|---|
| SMOKE-001 | smoke-target | confirmed | `runs/smoke-target/verify/SMOKE-001/verify-report.md` |
| FIND-001 | verl | confirmed（源码级） | `runs/verl/verify/FIND-001/verify-report.md` |

## 五个目标的检测结果（仅 dry-run，未构建）

| 项目 | 检测语言 | 计划安装 | env_status | 建议 |
|---|---|---|---|---|
| codex | node, rust | pnpm install；cargo fetch | planned | 先 `--mode auto` 构建；Rust 完整编译用 `--mode full` |
| deepseek-harness | node | pnpm install --ignore-scripts | planned | `--mode auto` 即可 |
| vllm | python, rust, native | pip editable --no-deps；cargo fetch | planned | 运行时依赖需 `--mode full`，但体积大/可能需 GPU |
| sglang | python, rust | pip editable --no-deps；cargo fetch | planned | 同上；`python/` 与 `rust/` 是主工程 |
| verl | python | pip editable --no-deps | partial（已构建测试镜像） | 已可用；完整依赖用 `--mode full` |

对应 `env/<project>/env-manifest.json` 均已生成（`env_status=planned` 表示尚未构建）。

## 第 0 阶段主流程：智能体主导与确定性备用

`run.sh` 现在调用 `scripts/env/phase0_env.sh`：

1. 默认直接启动 `environment-builder`（`build_env_agent.sh`），由智能体检查源码、选择构建方式、诊断失败并验收环境；
2. 智能体把 `build_env.sh` 作为确定性构建工具调用，可以修改 Dockerfile 后重新构建；
3. 智能体没有产出可用环境时才执行确定性备用方案；`--agent off` 表示明确关闭智能体，只执行备用方案。

```bash
bash run.sh targets/deepseek-harness --env-mode auto
bash run.sh targets/deepseek-harness --env-agent on --env-agent-rounds 2
bash run.sh targets/deepseek-harness --env-agent off
```

查看：`<run>.meta/env-phase.json`、`<run>.meta/env-build-agent-1.log`。
报告完整性检查通过后，`run.sh` 默认继续生成 `visual-rendered/report-illustrated.md` 与场景图，执行真实 `verify-agent`（`verify/agent/summary.json`），再运行红队批量执行与独立审核（`redteam/summary.json`）。可用 `--skip-visual`、`--skip-verify`、`--skip-redteam` 分别关闭。
`env-phase.json` 记录运行时检测结果：Claude、技能和脚本是否可用，以及缺失项、智能体状态、备用方案状态和最终状态；智能体直接成功时备用方案状态为 `not_run`。`run.sh --status` 会显示 `env_agent_status` 和 `env_agent_reason`。

## 构建命令

```bash
# 检测（不构建）
bash scripts/env/build_env.sh targets/codex --dry-run

# 自动构建（静态检查与导入级验证）
bash scripts/env/build_env.sh targets/codex --mode auto

# 构建失败时：读日志，改 env/<project>/Dockerfile，再复用
bash scripts/env/build_env.sh targets/codex --no-generate

# 完整安装/编译（慢，慎用）
bash scripts/env/build_env.sh targets/verl --mode full --timeout 7200
```

退出码：`0` 表示 `ready`，`10` 表示 `partial`，`20` 表示 `blocked`。

## 已知限制

- 自动检测会忽略 `examples/`、`tests/`、`sdk/`、`scripts/`、`tools/`、`.github/` 等目录，避免把辅助包当成主工程；需要时改 `env/<project>/Dockerfile`。
- 默认不启用 GPU；vLLM、SGLang 和 verl 的 CUDA 与分布式路径无法在自动构建环境中验证。
- Node 默认使用 `--ignore-scripts`，Rust 和 Go 默认只下载依赖，Python 默认使用 `--no-deps`；这些都是 `partial` 的明确原因。
- 未提供数据库、Ray 集群、对象存储等外部服务；`verify-agent` 必须把这类候选问题标为 `blocked` 或 `inconclusive`。

## 下一步

1. 对 5 个目标逐个执行 `--mode auto` 构建，记录 `ready`、`partial` 或 `blocked`。
2. 用 `run.sh` 主流程让 `verify-agent` 生成验证程序、`run_verify.sh` 执行，再检查红队批量执行与独立审核是否满足待人工验收条件。
3. 最终报告区分静态候选问题与 `confirmed`、`rejected`、`inconclusive`、`blocked` 验证结论。
