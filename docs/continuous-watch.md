# 持续监控与更新溯源

`scripts/watch` 把仓库连接、提交轮询和变更风险审查做成一个常驻层。它不替代
`run.sh` 的深度审计，而是回答：**这次更新是否把仓库变得危险，值不值得触发审计。**

## 连接仓库

```bash
python3 scripts/watch/watch.py add --project codex --path targets/codex
python3 scripts/watch/watch.py add --project vllm --path targets/vllm --deep
```

`add` 默认把当前 `HEAD` 设为基线，不把历史提交重新扫一遍。`--deep` 会写一份
`runs/watch/queue/<project>-deep-scan.md`，提示用现有批量审计流水线做首次深度扫描：

```bash
bash run.sh targets/codex --project codex
```

## 轮询

```bash
python3 scripts/watch/watch.py poll            # 只读本地仓库
python3 scripts/watch/watch.py poll --fetch    # 先 git fetch
python3 scripts/watch/watch.py watch --interval 300 --fetch
```

`poll --fetch` 和 `watch --fetch` 用远端跟踪引用（`origin/<分支>`）而不是本地分支指针判断
是否有新提交：`git fetch` 只推进远端跟踪引用，不会推进本地 `HEAD`。目标仓库通常是浅克隆，
有界抓取用 `--depth=50`（可用 `--fetch-depth` 调整），避免把整个历史都搬下来。

每次轮询：

1. 比较 `last_sha..<远端跟踪引用>`。
2. 对每个新提交生成 `runs/watch/<project>/<sha>.json` 和 `.md`。
3. 静态规则评分：`critical`、`high`、`review`、`low`。
4. `critical` 和 `high` 写入 `runs/watch/queue/`，等待人工或自动触发深度审计。
5. 更新 `ui/data/watch-state.json`，看板“自动狩猎”页读取它。

历史被重写（`last_sha` 不是 `HEAD` 的祖先）会生成 `history-rewrite` 事件，不会
把重写当成普通变更混过去。

启动时默认回看最近 24 小时（`--window-hours` / `WATCH_WINDOW_HOURS`）内的新提交，
因此刚启动就能覆盖前一天到当前时刻的更新。

## 规则覆盖

- 安装与构建入口新增 `curl|sh`、`wget|sh`、`eval`、Base64 解码和可执行位
- 依赖源改成 HTTP、Git、文件路径或非官方软件包仓库
- 持续集成新增 `pull_request_target`、`write-all`，或把密钥直接传入 Shell
- 新增二进制、`.node`、`.so`、`.wasm` 或无法审查的二进制变更
- 同时出现外联与凭据或环境变量读取
- 写入密钥或私钥材料，以及环境注入（`LD_PRELOAD`、`PATH`、代理）
- 大范围删除、超大变更和安装面变更

静态命中只是初筛信号，不是漏洞结论。

## 大语言模型复核

对高风险提交可以让 `diff-auditor` 再读一遍：

```bash
python3 scripts/watch/watch.py llm-audit \
  --project codex \
  --sha <commit> \
  --timeout 600
```

输出 `runs/watch/<project>/<sha>.llm-audit.json`，判定为
`malicious`、`suspicious`、`benign` 或 `inconclusive`。失败或超时会写
`.llm.log`，不会悄悄把提交标成安全。

## 自动派发

```bash
# 手动派发一次并查看状态
python3 scripts/watch/watch.py dispatch --once
python3 scripts/watch/watch.py dispatch --status

# 以常驻方式轮询并派发
WATCH_AUTO_RUN=1 scripts/watch/daemon.sh start
WATCH_AUTO_RUN=0 scripts/watch/daemon.sh start  # 只监控，不自动挖掘
```

派发记录在 `runs/watch/dispatch-state.json`，日志在 `runs/watch/dispatch/`。同一 commit
已有成功或运行中的报告时会标记为 `reused`，不会重复开挖。

## 常驻

```bash
scripts/watch/heartbeat.sh
```

开发机可直接运行；生产环境建议使用 systemd：

```ini
[Service]
WorkingDirectory=/home/wzk/mygoldmine
Environment=WATCH_INTERVAL=300
Environment=WATCH_FETCH=1
ExecStart=/home/wzk/mygoldmine/scripts/watch/heartbeat.sh
Restart=always
```

## 与其他层的关系

```text
watch poll -> 高风险提交 -> queue -> dispatch -> run.sh 深度审计
                                               -> verify -> redteam lab -> judge
                                               -> 图文报告 -> 人工验收
```

派发器默认启用（`WATCH_AUTO_RUN=1`）：只派发 `critical/high`，同一项目同一 commit 不重复开挖，
一次只运行一个派发任务。它会把目标 commit 检出到 `runs/watch/worktrees/<project>/<sha>/`，
不移动用户现有分支；分支名通过 `TARGET_BRANCH` 写入 `run-meta.json`。没有新提交时只轮询，
不会因为队列为空而退出。

`watch` 负责发现变化并排序，`run.sh` 负责深度审计，候选验证、红队和独立审核
负责核实证据。三者不混用结论。
