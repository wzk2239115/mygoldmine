# 整夜并行挖掘：overnight.sh（T13）

`scripts/mine/overnight.sh` 是 `parallel_mine.sh` 的运行入口，固定整夜场景的默认值：

| 参数 | 默认值 |
|------|--------|
| `MODEL` | `360-proxy/deepseek/deepseek-v4.1-flash`（容器内自动转成 `deepseek/deepseek-v4.1-flash`） |
| `MAX_PARALLEL` | `5` |
| `TIMEOUT` | `21600` 秒（6 小时/项目） |
| `RETRIES` | `1` 次（超时不重试） |
| 目标清单 | `targets/manifest.json`（先跑 `clone_targets.sh`） |
| 状态目录 | `runs/.orchestrator/` |
| 报告目录 | `runs/<project>/<timestamp>/` |

## 今晚：一条启动命令

先确认 360 鉴权可用（三选一，推荐写进 `~/.config/opencode/opencode.json` 让它自动读取）：

```bash
export ANTHROPIC_BASE_URL=https://api.360.cn
export ANTHROPIC_AUTH_TOKEN='你的360 key'
```

```bash
bash scripts/mine/overnight.sh start
```

执行链：`overnight.sh` → `parallel_mine.sh` → `mine_one_docker.sh` → `docker run mygoldmine:dev`
→ 容器内 `entrypoint.sh` → `mine_one.sh` → Claude Code（`deepseek/deepseek-v4.1-flash`）。
目标源码只读挂载，容器内复制到 `/workspace/repo` 后再审计。

启动前会检查：目标目录/清单、执行器可执行、磁盘余量（默认 ≥20G）、是否已有实例（`flock` + PID）。
确认无误后以 `setsid + nohup` 后台运行，命令立即返回并打印 PID 与日志路径。

只预览计划、不创建目录、不调用模型：

```bash
bash scripts/mine/overnight.sh start --dry-run
```

只想跑部分项目：

```bash
bash scripts/mine/overnight.sh start --projects vllm,sglang
```

## 看进度：status

```bash
bash scripts/mine/overnight.sh status
```

输出包含：

- `state=running|finished|stopped` 与 `orchestrator_alive`
- 每个项目的 `STATUS`（`running / success / failed / timeout / stopped / pending`）
- `summary: total=5 running=2 completed=3 failed=0 stopped=0 pending=0`
- 每个项目最近一次 `run_dir` 与日志位置

示例（测试用假执行器，非真实模型）：

```text
state=finished orchestrator_alive=no pid=1159602
PROJECT            STATUS     RC   DUR(s)   RUN_DIR                                    NOTE
vllm               success    0    0        .../runs/vllm/20261026T175310Z             报告齐全
codex              success    0    0        .../runs/codex/20261026T175306Z            报告齐全
summary: total=5 running=0 completed=5 failed=0 stopped=0 pending=0
```

单项目实时日志：

```bash
tail -f runs/.orchestrator/logs/<project>.log
```

编排器日志：

```bash
tail -f runs/.orchestrator/logs/orchestrator.log
```

## 止损：stop

```bash
bash scripts/mine/overnight.sh stop
```

行为：写入 `STOP` 标记，向编排器与 worker 进程组发 `TERM`，等待最多 30 秒后必要时 `KILL`。
已产出的报告、`raw.jsonl`、`claude.rendered.log` 都会保留；未完成项目状态记为 `stopped`。

## 断点续跑：resume

```bash
bash scripts/mine/overnight.sh resume
```

- 从状态目录与 `run-meta.json` 计算未完成项目（`success` / `skipped` 视为完成）
- 只把未完成项目通过 `--projects a,b` 传给 `parallel_mine.sh`
- 已完成项目不会产生新 run 目录；全部完成时直接输出“无需 resume”
- 同样支持 `--dry-run` 预览，例如：

```bash
bash scripts/mine/overnight.sh resume --dry-run
```

## 明早：收报告

```bash
# 总览
bash scripts/mine/overnight.sh status

# 每个项目的报告（按时间取最新）
for p in targets/*/; do
  name="$(basename "$p")"
  latest="$(find "runs/$name" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"
  [ -n "$latest" ] && echo "== $name: $latest" && ls "$latest"
done
```

每个 run 目录应包含：

```text
audit-report.md
audit-report.json
raw.jsonl
claude.rendered.log
claude.stderr.log
run-meta.json
```

报告路径：`runs/<project>/<timestamp>/audit-report.md`。

## 常见状态与处理

| 状态 | 含义 | 建议 |
|------|------|------|
| `running` + `orchestrator_alive=yes` | 正常执行中 | 继续等待，看项目日志 |
| `running` + `orchestrator_alive=no` | 进程被 kill -9 等异常退出 | `resume` 续跑 |
| `finished`，`failed=0` | 全部成功或已完成跳过 | 收报告 |
| `failed>0` / `timeout>0` | 失败或超时（超时不原地重试） | 看 `logs/<project>.log` 后 `resume` |
| `stopped>0` | 人工止损 | `resume` 只补这些项目 |
| `state=not-started` | 尚未启动 | `start` |

## 本次验证记录（2026-10-27，假执行器，未调用真实模型）

使用 `tests/fixtures/fake-mine-executor/fake_mine.sh` 与临时 manifest，验证：

1. **默认值**：`start --dry-run` 输出 `MODEL=360-proxy/deepseek/deepseek-v4.1-flash`、`MAX_PARALLEL=5`、`PROJECT_TIMEOUT=21600`，且未创建状态目录。
2. **完成状态**：5 个项目在 `--max-parallel 2` 下后台完成，`status` 输出 `completed=5 failed=0`，每个项目均有 `audit-report.md/json` 与 `run-meta.json`。
3. **运行状态**：`FAKE_MINE_SLEEP=30` 启动 2 个项目后，`status` 输出 `state=running orchestrator_alive=yes`、`running=2`。
4. **止损**：`stop` 后编排器退出，`status` 输出 `state=stopped`、`stopped=2`，项目状态为 `stopped`，日志保留。
5. **resume 只补未完成**：首轮故意让 `vllm` 失败、其余 4 个成功；`resume` 输出“未完成项目（1）: vllm”，仅新增 `vllm` 的 run 目录，其余项目 run 目录数量不变。再次 `resume` 时输出“所有项目均已完成，无需 resume”。
6. **安全边界**：`--dry-run` 不创建目录、不调用模型；测试全程使用假执行器，未启动真实 6h 挖掘，产物中不含密钥。

复现时只需把 `--executor` 指向假执行器，并传入临时 `--targets-dir/--runs-root`；真实整夜运行不要传 `--executor`，使用默认的 `mine_one.sh`。
