# Docker 容器冒烟测试（T10）

- 执行时间：2026-10-27（宿主时区 UTC+8）
- 宿主：Docker Engine 28.3.3
- 镜像：`mygoldmine:dev`
  - ID：`sha256:5afad73b09f2e4390bb4c4eafb976ca414fefb67f3c1f848f713445c344d4a71`
  - 构建时间：2026-10-27T01:41:39+08:00
- 运行时用户：`uid=1000(miner) gid=1000(miner)`
- 目标：`tests/fixtures/smoke-target`（小仓库，只读挂载到 `/target`）
- 模型：**fake Claude CLI**，不调用网络、不需要 API key。

## 1. 测试范围与隔离方式

T10 验证的是 Docker 链路本身，而不是模型审计质量：

```
docker run
  -> scripts/mine/entrypoint.sh        （非 root、参数校验、复制目标到 /workspace/repo）
  -> scripts/mine/mine_one.sh          （链接 .claude、调用 CLI、写 raw/meta）
  -> tests/fixtures/fake-claude/claude （模拟 stream-json 事件并写两份报告）
  -> scripts/mine/render_claude_log.py （渲染 claude.rendered.log）
```

为避免真实 API 调用与密钥依赖，容器内通过 `CLAUDE_BIN=/fakebin/claude` 指向
只读挂载的 fake CLI。fake CLI 只输出固定事件、写固定报告，不代表真实审计结论。
镜像中仍保留真实 `claude` CLI，`entrypoint.sh` 的前置检查因此仍会执行。

隔离参数：

- `--network none`：运行期完全断网。
- `--read-only`：根文件系统只读；仅 `/tmp`、`/workspace` 使用 tmpfs，`/runs` 为可写挂载。
- 未挂载 `/var/run/docker.sock`（入口脚本也会主动拒绝）。
- `PYTHONDONTWRITEBYTECODE=1`，避免只读根文件系统产生 `__pycache__` 噪音。

## 2. 复现命令

构建（本机 Docker 代理需要 host 网络时加 `--network host`）：

```bash
time docker build --network host -f docker/Dockerfile -t mygoldmine:dev .
```

冒烟：

```bash
RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="/runs/smoke/${RUN_TS}"

set +e
time docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,mode=1777 \
  --tmpfs /workspace:rw,mode=1777 \
  -v "$PWD/runs:/runs" \
  -v "$PWD/tests/fixtures/smoke-target:/target:ro" \
  -v "$PWD/tests/fixtures/fake-claude:/fakebin:ro" \
  -e CLAUDE_BIN=/fakebin/claude \
  -e RUN_DIR="${RUN_DIR}" \
  -e PROJECT=smoke-target \
  -e TIMEOUT=120 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  mygoldmine:dev
rc=$?
set -e
echo "container_rc=${rc}"
echo "host_run_dir=$PWD/runs/smoke/${RUN_TS}"
```

本次实际运行使用 `RUN_TS=20261026T174149Z`，宿主产物目录：
`runs/smoke/20261026T174149Z/`。

## 3. 运行结果

- 容器退出码：`0`
- 墙钟耗时：约 `1s`（含容器启动、目标复制、fake CLI、渲染；非真实审计耗时）
- 容器日志：

```text
[entrypoint] 复制目标源码到可写工作副本: /target -> /workspace/repo
[entrypoint] 已链接 .claude -> /opt/mygoldmine/.claude
[entrypoint] 提示词已写入 /tmp/mygoldmine-prompt.txt
[entrypoint] 委托 mine_one.sh 执行审计（timeout=120s, model=360-proxy/deepseek/deepseek-v4.1-flash, agent=security-orchestrator）
[mine_one] 已链接 /workspace/repo/.claude -> /opt/mygoldmine/.claude
[mine_one] 渲染 stream-json -> /runs/smoke/20261026T174149Z/claude.rendered.log
render_claude_log: 8 lines, 0 invalid, 2 tool calls -> /runs/smoke/20261026T174149Z/claude.rendered.log
[mine_one] 完成: exit_code=0 timed_out=0 attempts=1 run_dir=/runs/smoke/20261026T174149Z
```

产物（宿主侧）：

```text
audit-report.json      560 bytes
audit-report.md        836 bytes
claude.rendered.log    922 bytes
claude.stderr.log        0 bytes
raw.jsonl             1379 bytes
run-meta.json          614 bytes
```

## 4. `claude.rendered.log` 摘录

文件非空、可读，包含 init、工具调用、工具结果、最终 result 与 summary：

```text
[init] model=360-proxy/deepseek/deepseek-v4.1-flash cwd=/workspace/repo
[rate-limit] status=allowed
[thinking] 冒烟模式：只验证产物与日志链路。
[assistant] 开始对 smoke-target 做冒烟审计。
[tool:Read] 查看目标源码
  file: app.py
[tool-result] 8: subprocess.run(command, shell=True, check=False)
[tool:Write] 写入人读报告
  file: /runs/smoke/20261026T174149Z/audit-report.md
[tool-result] report written
[assistant] 报告已生成：audit-report.md / audit-report.json。
[result] is_error=false subtype=success duration_ms=42 num_turns=2 total_cost_usd=0.0
smoke test complete

[summary] lines=8 json_ok=8 invalid=0 blank=0 tool_calls=2 tool_errors=0 render_errors=0 result_seen=true result_errors=0 tools(Read=1 Write=1)
```

## 5. 退出码一致性

`run-meta.json` 摘录：

```json
{
  "project": "smoke-target",
  "duration_seconds": 1,
  "attempts": 1,
  "exit_code": 0,
  "timed_out": false,
  "interrupted": false,
  "renderer_exit_code": 0,
  "reports_complete": true
}
```

校验结果：

```text
container_rc=0
meta_exit_code=0   # 与容器退出码一致
meta_json=ok       # jq empty 通过
report_json=ok     # jq empty 通过
raw_lines=8
```

## 6. 密钥泄漏检查

对本次产物目录执行模式扫描：

```bash
grep -rEni 'sk-[A-Za-z0-9_-]{16,}|Bearer[[:space:]]+[A-Za-z0-9._-]{16,}|api[_-]?key|ANTHROPIC_API_KEY|password' \
  runs/smoke/20261026T174149Z/
```

结果：无匹配（`SECRET_SCAN=clean`）。

说明：本次没有向容器传入任何 API key；fake CLI 输出与报告均为固定文本。
渲染器自身的 `sk-`/`Bearer`/`api_key` 脱敏能力已由 T09 的 `--self-test` 覆盖，
不在本冒烟中重复注入假密钥，以免假密钥进入 `raw.jsonl` 干扰后续 `verify.sh`。

## 7. 已知限制

1. **不是真实模型审计**：fake CLI 返回固定事件与固定报告，只证明链路、路径、
   退出码与日志协议可用；不能据此判断审计质量或漏报率。
2. **未覆盖认证/限流/重试**：真实 `claude` 的 API 认证、429/5xx 重试、费用统计
   需要在有 API key 的环境另行验证。
3. **未覆盖 6h 超时**：本次 `TIMEOUT=120` 且 1s 完成；超时路径由 T08 的 stub
   `sleep` 测试覆盖，T12 会用假目标再验证编排层超时。
4. **镜像需在脚本变更后重建**：`scripts/` 通过 `COPY` 进入镜像，T08/T09 更新后
   必须重新 `docker build`，否则容器内仍是旧脚本。
5. **fixture 不进入镜像**：`tests/fixtures/*` 只在运行时只读挂载，避免把测试桩
   打进生产镜像。
6. **`runs/` 权限**：若宿主 `runs/` 由 root 创建，需先 `chown 1000:1000 runs`
   （或使用 `--user $(id -u):$(id -g)`），否则非 root 容器无法写入。
7. **输出只到 `claude.stderr.log` 为空**：fake CLI 不写 stderr，真实运行时应结合
   `claude.stderr.log` 与 `raw.jsonl` 排查代理/网络错误。
