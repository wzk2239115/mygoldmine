# Docker + Claude Code 挖掘设计（T06）

本文提炼 `/home/wzk/projects/exploitgym` 的可复用设计，并给出 mygoldmine 在 Docker 中
用 Claude Code 做源码安全审计的落地方案。它是 T07（镜像/入口）、T08（单项目脚本）、
T09（日志渲染）、T10（冒烟）的实现依据。

## 1. exploitgym 设计提炼

| 关注点 | exploitgym 做法 | 可复用点 | 证据 |
| --- | --- | --- | --- |
| Agent 启动 | `docker exec` 进入长驻容器，`bash -c` + `timeout` + `tee` | 超时与原始日志必须由外层统一兜底 | `src/cybergym/evaluation/agents/claude_code.py:294-303` |
| CLI 参数 | `--verbose --output-format=stream-json --permission-mode=bypassPermissions` | 非交互、机器可读事件流 | 同上 `:298-299` |
| 会话恢复 | 首轮 `--resume`，后续 `--continue`，失败回退 fresh | 只恢复可验证的会话，失败不硬撑 | `:275-283`, `:360-371` |
| 配置目录 | `CLAUDE_CONFIG_DIR=/logs`，工作目录 `/workspace` | 配置与会话必须落到可收集目录 | `:211`, `:320` |
| 模型/代理 | `ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`，并把 Sonnet/Opus/Haiku 别名统一 | 第三方代理必须同步所有模型别名 | `:203-225` |
| 日志渲染 | `render_stream()` 将每行 JSON 转人读文本，单行解析失败不中断 | 渲染器必须容错、流式 | `claude_stream_renderer.py:50-151` |
| 事件协议 | `system/init`、`rate_limit_event`、`assistant.thinking/tool_use/text`、`user.tool_result` | 渲染字段以事件 `type` + `message.content[].type` 为准 | `claude_stream_renderer.py:63-132` |
| 容器限制 | `mem_limit=64g`、`nano_cpus=4e9`、`pids_limit=65536`、`agent_timeout_seconds=3600` | 资源与时间都要显式限制 | `types.py:105,164-177` |
| 挂载 | 运行时目录只读挂载；任务工作区由容器内可写目录承载 | 配置只读、产物可写、目标不改 | `base.py:516-537` |
| 网络 | 安装阶段 allow-all 代理；运行阶段仅放行 LLM API 的 Squid 内网 | 运行期最小出网；不使用 docker socket | `docs/firewall.md` |
| 凭据 | `ANTHROPIC_API_KEY` 走环境变量，或把凭据文件软链进容器后删除 | 密钥不进仓库、不进元数据 | `claude_code.py:185-195`, `:377-379` |
| 镜像准备 | `pull_images.py` 按 `user:`/`kernel:`/`v8:` 前缀解析镜像，去重、并发拉取、默认跳过本地已有 | 目标清单要能被机器解析，拉取要幂等可续 | `scripts/setup/pull_images.py:60-133`, `:203-232` |
| 日志收集 | `collect_rendered_logs.sh` 按 `<task>/logs/claude_code.rendered.log` 扁平导出，按 `result.json` 分数过滤，重名加槽位后缀 | 产物命名稳定，状态过滤与冲突处理不能丢日志 | `scripts/collect_rendered_logs.sh:40-81` |

镜像与日志的取舍：mygoldmine 不为每个目标构建/拉取镜像（单 `Dockerfile` + 构建缓存即可），
因此不照搬 `pull_images.py` 的任务前缀分发；日志也不扁平化复制，而是保留
`runs/<project>/<ts>/` 结构，由 `run-meta.json` 和 T15 的 `verify.sh` 做状态汇总与完整性校验。

不可直接照搬的部分：exploitgym 是「靶场容器 + Agent 容器」双容器、以 `/workspace/flag.txt`
和 `result.json` 判分；mygoldmine 是「源码只读挂载 + 单 Agent 容器」、以
`audit-report.md/json` 为产物。以下方案按后者重塑。

## 2. 总体拓扑

```
host                                   container (非 root)
targets/<project>/  ──ro──────────────> /target
.claude/            ──ro──────────────> /opt/mygoldmine/.claude
runs/<project>/<ts>/──rw──────────────> /runs
（镜像内预装 claude/python/jq/git）     /workspace/repo  <- 从 /target 复制的可写副本
```

- **单容器**：审计不需要靶场进程，不为每个目标构建镜像。
- **目标只读 + 工作副本可写**：`/target` 只读保证原仓库不被改动；入口脚本把源码复制到
  `/workspace/repo`，在副本里链接 `.claude`、允许 Agent 写笔记。复制时排除 `.git` 以外的
  大对象可用 `COPY_EXCLUDES` 控制，默认保留 `.git` 以便 `git log/blame`。
- **报告走绝对路径**：提示词要求把报告写到 `/runs/<project>/<ts>/`，不写进目标副本，
  避免污染与遗漏。

## 3. 镜像设计（T07 落地）

- 基础镜像：`python:3.12-slim`（Debian），固定 `WORKDIR /opt/mygoldmine`。
- 预装：`git jq ripgrep curl ca-certificates nodejs npm`、Python `tree-sitter`、
  `tree-sitter-language-pack`；安装 Claude Code CLI（版本固定，构建参数可覆盖）。
- 非 root：创建 `miner` 用户，构建参数 `UID/GID` 默认 1000；运行时可 `--user $(id -u):$(id -g)`
  以匹配宿主挂载权限。`HOME=/home/miner`，并预建 `/runs`、`/workspace`。
- 不安装 Docker CLI，不挂载 `/var/run/docker.sock`；容器内不能启动兄弟容器。
- 入口：`scripts/mine/entrypoint.sh`，支持 `--dry-run`，只打印配置与将执行的命令。

镜像内需要两份代码：mygoldmine 骨架（`.claude/`、`scripts/`）放到 `/opt/mygoldmine`。
目标源码在运行时挂载，不进入镜像。

## 4. 挂载与用户

| 容器路径 | 宿主来源 | 模式 | 用途 |
| --- | --- | --- | --- |
| `/target` | `targets/<project>` | `ro` | 原始目标源码，Agent 只读 |
| `/opt/mygoldmine/.claude` | 仓库 `.claude` | `ro` | skills/agents，容器启动时软链到工作副本 |
| `/runs` | `runs/` | `rw` | `audit-report.*`、`raw.jsonl`、`claude.rendered.log`、`run-meta.json` |
| `/workspace` | 匿名卷或 tmpfs | `rw` | 目标可写副本、临时文件 |
| `/tmp` | tmpfs | `rw` | 提示词/中间文件，`noexec` 可选 |

`.claude` 链接方式（与 mygoldmine 现有手工流程一致）：

```bash
# entrypoint 在可写副本中执行
cp -a /target/. /workspace/repo/
# 目标自带的 .claude 不覆盖审计配置，改名保留供参考
[ -e /workspace/repo/.claude ] && mv /workspace/repo/.claude /workspace/repo/.claude.upstream
ln -s /opt/mygoldmine/.claude /workspace/repo/.claude
```

不采用「在只读 `/target` 上直接建软链」：`ro` 挂载不可写，且 Docker 嵌套 bind mount
依赖目标里已存在 `.claude` 目录，失败模式不直观。复制一份可写副本更稳定，代价是磁盘
（建议编排层预留 ≥ 目标体积 × 并发数 × 1.5）。

用户与权限：
- 容器默认 `miner`（UID/GID 可构建期指定），禁止 root。
- 宿主 `runs/` 需对运行 UID 可写；若 UID 不一致，用 `--user "$(id -u):$(id -g)"` 并在
  镜像中保证该 UID 对 `/home/miner`、`/workspace` 可写（或改用命名卷）。
- 凭据只通过 `-e ANTHROPIC_API_KEY`（值来自宿主环境变量）注入，不写文件、不进命令行参数。

## 5. 网络策略

| 场景 | 网络 | 出网 |
| --- | --- | --- |
| `--dry-run` / 小样本离线 | `--network none` | 无 |
| 真实挖掘 | 专用 bridge `mygoldmine-run` | 仅经 Squid 代理放行模型 API 域名 |
| 克隆目标 | 宿主执行（T11） | 容器不负责 clone |

- 真实运行设置 `HTTPS_PROXY/HTTP_PROXY=http://mygoldmine-proxy:3128`，Squid
  `dstdomain` 白名单只含 360 代理域名（按实际 `ANTHROPIC_BASE_URL` 主机配置）。
- 容器无默认路由时，即使程序忽略 `HTTP_PROXY` 也出不去；与 exploitgym 的 run proxy 同思路，
  但 mygoldmine 不做「安装阶段」，依赖全部预装，因此只需一个代理网络。
- 禁止 `WebSearch`/`WebFetch`（`--disallowed-tools WebSearch,WebFetch`），避免绕过代理做
  外部检索。

## 6. 超时、预算与并发

- 单项目墙钟：`TIMEOUT=21600`（6h），入口 `timeout --signal=TERM --kill-after=60`；
  `timeout` 返回 124 时标记 `timed_out=true`，保留已产生的全部日志。
- 资源上限：`--memory 16g --cpus 4 --pids-limit 4096`；低于 exploitgym 的 64g/4CPU，
  因为源码审计不需要靶场/内核构建。
- 并发：编排层（T12）默认 5 个容器；单实例锁 `flock` 防止重复启动；启动前检查
  `runs/` 所在磁盘剩余空间。
- 模型：默认 `360-proxy/deepseek/deepseek-v4.1-flash`，通过 `MODEL` 覆盖；同时设置
  `ANTHROPIC_MODEL` 与 Sonnet/Opus/Haiku/子代理别名，避免子任务回落到默认模型。
- 不在实现阶段运行真实 6h 挖掘；T07/T10 只允许 `--dry-run` 或小仓库冒烟。

## 7. 执行命令与 stream-json 协议

入口最终命令（`T08` 实现，示意）：

```bash
set -o pipefail
cd /workspace/repo
cat /tmp/prompt.txt \
  | timeout --signal=TERM --kill-after=60 "$TIMEOUT" \
      claude --verbose --output-format=stream-json \
             --permission-mode=bypassPermissions \
             --disallowed-tools WebSearch,WebFetch \
             --agent "$AGENT" \
  | tee -a "$RUN_DIR/raw.jsonl"
```

提示词要点：
1. 目标目录 `/workspace/repo`，只读原件 `/target`；
2. 用 `security-orchestrator` 做全流程，产物写到 `$RUN_DIR/audit-report.md` 与
   `$RUN_DIR/audit-report.json`；
3. 只做定位、根因、最小复现思路、修复建议，不写武器化 exploit；
4. 不访问公网，不读取 `/target` 之外的宿主路径。

stream-json 是「每行一个 JSON 事件」，渲染器按事件类型处理（与 exploitgym
`claude_stream_renderer.py:50-134` 对齐）：

| 事件 | 关键字段 | 渲染为 |
| --- | --- | --- |
| `system` + `subtype=init` | `model`, `cwd` | `[init] model=... cwd=...` |
| `rate_limit_event` | `rate_limit_info.status` | `[rate-limit] status=...` |
| `assistant` + `thinking` | `message.content[0].thinking` | `[thinking] ...` |
| `assistant` + `tool_use` | `content[0].name/input.description/input.command` | `[tool:<name>] ...` + `$ command` |
| `user` + `tool_result` | `content`, `is_error` | `[tool-result]` / `[tool-error]` |
| `assistant` + `text` | `message.content[].text` | 原样文本 |

渲染规则：非 JSON 行原样输出；字段缺失用 `?`/空串；单行异常输出
`[render-error] <类型>: <消息>` 并继续，不终止整份日志。

## 8. 产物与日志字段

每次运行目录 `runs/<project>/<ts>/`：

| 文件 | 内容 |
| --- | --- |
| `raw.jsonl` | 原始 stream-json，含续跑分隔行，用于复盘与重渲染 |
| `claude.rendered.log` | 人读过程日志（工具调用、命令、改动、结果、错误、耗时） |
| `audit-report.md` | 面向人的审计报告 |
| `audit-report.json` | 机器可读报告，供 T14/T15 校验 |
| `run-meta.json` | 运行元信息，不含任何密钥 |

`run-meta.json` 建议字段：

```json
{
  "schema_version": 1,
  "project": "vllm",
  "target_url": "https://github.com/vllm-project/vllm",
  "commit": "<git rev-parse HEAD>",
  "started_at": "2026-10-27T22:00:00Z",
  "ended_at": "2026-10-28T03:12:34Z",
  "duration_seconds": 18754,
  "model": "360-proxy/deepseek/deepseek-v4.1-flash",
  "agent": "security-orchestrator",
  "attempts": 1,
  "exit_code": 0,
  "timed_out": false,
  "renderer_exit_code": 0,
  "artifacts": {
    "raw": "raw.jsonl",
    "rendered": "claude.rendered.log",
    "report_md": "audit-report.md",
    "report_json": "audit-report.json"
  }
}
```

禁止字段：`api_key`、`token`、`authorization`、完整环境变量转储。渲染器与入口在写
`run-meta.json` 前对值做 `sk-`/`Bearer` 模式扫描，命中则拒绝写入并报错。

## 9. 失败分类与重试

| 情况 | 判定 | 处理 |
| --- | --- | --- |
| 正常结束 | `exit_code=0` 且报告文件非空 | 成功，不再重试 |
| Agent 提前退出 | `exit_code=0` 但无报告 | 视为失败，最多补跑 1 次 |
| 超时 | `exit_code=124` | 不原地重试；保留日志，交编排层决定是否新起 run |
| 模型/代理瞬时错误 | 非 0，stderr 含 429/5xx/timeout | 退避 60s 后原地重试，最多 `MAX_ATTEMPTS=2` |
| 认证/参数错误 | 401/403/400/invalid model | 不重试，立即失败并记录 |
| 渲染失败 | 渲染器非 0 | 保留 `raw.jsonl`，`run-meta` 记 `renderer_exit_code`，报告仍可判成功 |

入口用 `trap` 在 `EXIT`/`TERM` 时先刷新并渲染已写入的 `raw.jsonl`，再写 `run-meta.json`，
确保超时被杀也有可读日志。续跑以项目为单位：T12/T13 读取 `run-meta.json`，只补
`exit_code!=0` 或 `timed_out=true` 且没有有效报告的项目，不复用半截会话。

## 10. 与 exploitgym 的差异

| 维度 | exploitgym | mygoldmine |
| --- | --- | --- |
| 目标 | 靶场二进制/内核/V8，运行在独立 target 容器 | 本地克隆的开源源码，只读挂载到 Agent 容器 |
| 容器拓扑 | agent 容器 + target 容器 | 单 Agent 容器 + 工作副本 |
| 镜像 | 每任务拉取 registry 镜像 + 预装 CLI 的 agent 运行时 | 一个 `docker/Dockerfile`，目标源码不打进镜像 |
| 成功信号 | `/workspace/flag.txt`、`result.json` 分数 | `audit-report.md/json` 存在且非空，T14 `verify.sh` |
| `.claude` | 把 `CLAUDE.md` 注入 `/workspace`，CLI 在 `/data/node` | 可写副本内 `ln -s /opt/mygoldmine/.claude`，沿用现有 skill/agent |
| 网络 | install allow-all 代理 + run API-only 代理，双网络切换 | 无安装阶段；单 API-only 代理；dry-run 可 `none` |
| 超时 | 默认 3600s，多轮 `--continue` 直到 flag 或轮次上限 | 默认 21600s，单轮；项目级续跑 |
| 会话恢复 | 容器内 `--resume/--continue` + session jsonl | 不依赖会话文件；按 `run-meta.json` 重跑未完成项目 |
| 日志 | `/logs/claude_code.log` + `claude_code.rendered.log` | `raw.jsonl` + `claude.rendered.log` + `run-meta.json` |
| 渲染器 | `claude_stream_renderer.py` + 中间用量统计回调 | `render_claude_log.py`（T09），带 `--self-test`、坏行降级 |
| 凭据 | API key 或凭据文件软链，运行后删除 | 仅宿主环境变量注入，元数据强制脱敏 |
| 资源 | 64g / 4 CPU / 64k pids / 可选 core dump | 16g / 4 CPU / 4k pids，面向源码审计 |
| 并发 | 评测槽位 + `run_as.sh` 清理 | 5 并发 + `flock` 单实例锁 + 磁盘余量检查 |

## 11. 命令示例

构建（UID/GID 与宿主一致，避免挂载权限问题）：

```bash
docker build -f docker/Dockerfile \
  --build-arg UID="$(id -u)" --build-arg GID="$(id -g)" \
  -t mygoldmine:dev .
```

dry-run（不联网、不调用模型，只打印命令与配置）：

```bash
docker run --rm --network none \
  -e TARGET_DIR=/target \
  -e RUN_DIR=/runs/demo/20261027-220000 \
  -e TIMEOUT=21600 \
  -e MODEL=360-proxy/deepseek/deepseek-v4.1-flash \
  -e AGENT=security-orchestrator \
  -v "$PWD/targets/demo:/target:ro" \
  -v "$PWD/runs:/runs" \
  mygoldmine:dev --dry-run
```

真实单项目（密钥只从宿主环境读取；网络走 allowlist 代理）：

```bash
export ANTHROPIC_API_KEY   # 由调用者预先 export，不落盘
docker run --rm \
  --network mygoldmine-run \
  --memory 16g --cpus 4 --pids-limit 4096 \
  --user "$(id -u):$(id -g)" \
  -e ANTHROPIC_API_KEY \
  -e ANTHROPIC_BASE_URL \
  -e TARGET_DIR=/target \
  -e RUN_DIR=/runs/vllm/20261027-220000 \
  -e TIMEOUT=21600 \
  -e MODEL=360-proxy/deepseek/deepseek-v4.1-flash \
  -e AGENT=security-orchestrator \
  -v "$PWD/targets/vllm:/target:ro" \
  -v "$PWD/.claude:/opt/mygoldmine/.claude:ro" \
  -v "$PWD/runs:/runs" \
  mygoldmine:dev
```

渲染（T09，可对已有 raw 日志重跑）：

```bash
python3 scripts/mine/render_claude_log.py \
  --input runs/vllm/20261027-220000/raw.jsonl \
  --output runs/vllm/20261027-220000/claude.rendered.log \
  --verbose
```

## 12. 待验证项（交给 T07/T10）

1. 非 root 用户 + 宿主 UID 不一致时，`/runs` 与 `/workspace` 的写权限。
2. 目标体积较大（vLLM）时复制副本的耗时与磁盘占用；必要时改为 `rsync --exclude=.git`。
3. Squid 白名单对 360 代理域名/端口的实际放行与 `ANTHROPIC_BASE_URL` 是否完全一致。
4. `--agent security-orchestrator` 与提示词 `@.claude/agents/...` 两种调用方式在
   stream-json 下都能正确初始化。
5. `timeout` 发 TERM 后 Claude Code 是否能在 60s 内退出，否则 `--kill-after` 兜底并
   依赖已落盘的 `raw.jsonl` 渲染。
