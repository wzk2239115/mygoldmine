# 持续监控与更新溯源

`scripts/watch` 把仓库连接、提交轮询和 diff 风险审查做成一个常驻层。它不替代
`run.sh` 的深度审计，而是回答：**这次更新是否把仓库变得危险，值不值得触发审计。**

## 连接仓库

```bash
python3 scripts/watch/watch.py add --project codex --path targets/codex
python3 scripts/watch/watch.py add --project vllm --path targets/vllm --deep
```

`add` 默认把当前 `HEAD` 设为基线，不把历史提交重新扫一遍。`--deep` 会写一份
`runs/watch/queue/<project>-deep-scan.md`，提示用现有挖掘流水线做首次深度扫描：

```bash
bash run.sh targets/codex --project codex
```

## 轮询

```bash
python3 scripts/watch/watch.py poll            # 只读本地仓库
python3 scripts/watch/watch.py poll --fetch    # 先 git fetch
python3 scripts/watch/watch.py watch --interval 300 --fetch
```

每次轮询：

1. 比较 `last_sha..HEAD`。
2. 对每个新提交生成 `runs/watch/<project>/<sha>.json` 和 `.md`。
3. 静态规则评分：critical / high / review / low。
4. critical/high 写入 `runs/watch/queue/`，等待人工或自动触发深度审计。
5. 更新 `ui/data/watch-state.json`，看板“自动狩猎”页读取它。

历史被重写（`last_sha` 不是 HEAD 的祖先）会生成 `history-rewrite` 事件，不会
把重写当成普通 diff 混过去。

## 规则覆盖

- 安装/构建入口新增 `curl|sh`、`wget|sh`、`eval`、base64 解码、可执行位
- 依赖源改成 HTTP/git/file 或非官方 registry
- CI 新增 `pull_request_target`、`write-all`、secret 直接进 shell
- 新增二进制、`.node`/`.so`/`.wasm` 或无法审查的二进制变更
- 外联 + 凭据/环境变量读取同现
- 密钥/私钥材料写入、环境注入（`LD_PRELOAD`、`PATH`、代理）
- 大范围删除、超大 diff、安装面变更

静态命中只是 triage 信号，不是漏洞结论。

## LLM 复核

对高风险提交可以让 `diff-auditor` 再读一遍：

```bash
python3 scripts/watch/watch.py llm-audit \
  --project codex \
  --sha <commit> \
  --timeout 600
```

输出 `runs/watch/<project>/<sha>.llm-audit.json`，verdict 为
`malicious | suspicious | benign | inconclusive`。失败或超时会写
`.llm.log`，不会悄悄把提交标成安全。

## 常驻

```bash
scripts/watch/heartbeat.sh
```

开发机可直接跑；生产建议用 systemd：

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
watch poll -> 高风险提交 -> queue -> run.sh 深度审计
                                   -> verify -> redteam lab -> judge
                                   -> 图文报告 -> 人工验收
```

`watch` 负责“发现变化并排序”，`run.sh` 负责“深挖”，`verify/redteam/judge`
负责“高质量验证”。三者不混用结论。
