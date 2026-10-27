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

## 构建命令

```bash
# 检测（不构建）
bash scripts/env/build_env.sh targets/codex --dry-run

# 构建 auto（静态/导入级）
bash scripts/env/build_env.sh targets/codex --mode auto

# 构建失败时：读日志，改 env/<project>/Dockerfile，再复用
bash scripts/env/build_env.sh targets/codex --no-generate

# 完整安装/编译（慢，慎用）
bash scripts/env/build_env.sh targets/verl --mode full --timeout 7200
```

退出码：`0 ready`、`10 partial`、`20 blocked`。

## 已知限制

- 自动检测会忽略 `examples/`、`tests/`、`sdk/`、`scripts/`、`tools/`、`.github/` 等目录，避免把辅助包当成主工程；需要时改 `env/<project>/Dockerfile`。
- 默认不启用 GPU；vLLM/SGLang/verl 的 CUDA/分布式路径无法在 auto 环境验证。
- Node 默认 `--ignore-scripts`，Rust/Go 默认只 fetch/download，Python 默认 `--no-deps`；这些都是 `partial` 的明确原因。
- 未提供数据库、Ray 集群、对象存储等外部服务；verify-agent 必须把这类 finding 标为 `blocked` 或 `inconclusive`。

## 下一步

1. 对 5 个 target 逐个执行 `--mode auto` 构建，记录 ready/partial/blocked。
2. 对每个项目报告中的 Critical/High 生成 harness，用 `run_verify.sh` 批量验证。
3. 最终报告区分 `static finding` 与 `confirmed/rejected/inconclusive/blocked`。
