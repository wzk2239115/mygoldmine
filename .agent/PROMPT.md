# mygoldmine 项目说明（ralph loop 每轮必读）

本仓库原名 Vul-AI-V2，是基于 Claude Code 的自动化安全审计框架。不要把本仓库当作目标；
目标源码会被克隆到 `targets/`，审计产物写到 `runs/`。

## 现有结构

- `.claude/agents/`：`security-orchestrator.md`、`skill-runner.md`、`report-generator.md`
- `.claude/skills/`：84 个 skill，命名以 `-analyzer` / `-scanner` 结尾
- `.claude/skills/task-manage/scripts/setup.sh`：内置任务管理命令
- `smartbugs-curated/`：智能合约样例
- `docs/`、`README.md`：框架文档

## 需求来源

- `TODOLIST.md`：人读需求与验收标准
- `.agent/tasks.json`：机器可读任务（以它为准选择任务）
- `.agent/STEERING.md`：运行时人工指令，有内容时优先处理

## 工作规则

1. 本轮只做一个任务：按 `priority` 选第一个 `status != done` 的任务。
2. 开始前先读 `TODOLIST.md` 里对应任务的「目标 / 产物 / 验收」。
3. 用证据说话：引用具体文件路径、行号、命令输出；不要编造 CVE 编号或未核实的漏洞。
4. 新增 skill 必须放 `.claude/skills/<name>/SKILL.md`，命名遵循 `-analyzer` / `-scanner`。
5. 不删除、不重写无关的现有 skill；改动尽量小且可回滚。
6. 每个任务完成后：
   - 更新 `TODOLIST.md` 中对应复选框；
   - 把 `.agent/tasks.json` 里该任务 `status` 改为 `done`；
   - `git add` 本任务相关文件并单独 commit（不要提交 `targets/`、`runs/`、`logs/`、密钥）。
7. 全部任务完成时，最后一条消息只输出 `<promise>DONE</promise>`。

## 验证命令

```bash
bash ./check-dependencies.sh          # 依赖检查（可能提示缺失，不要自动装系统包）
python3 -m py_compile <改动的 .py>     # Python 语法
bash -n <改动的 .sh>                  # Shell 语法
jq empty <改动的 .json>               # JSON 合法性
git status --porcelain                # 确认没有把 targets/runs/logs 加入暂存区
```

## 安全边界

- 只分析本地克隆的开源仓库；不扫描公网/生产系统。
- 不编写可直接武器化的 exploit；只做定位、根因、最小复现思路、修复建议。
- 密钥只从环境变量读取；日志与 JSON 中不得出现 `sk-`、`api_key`、`Bearer` 等秘密。
- 实现阶段不要启动真实 6h 挖矿，只允许 `--dry-run` 或小样本冒烟。
