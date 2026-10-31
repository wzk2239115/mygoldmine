# Flag-based 动态验收

这是 verify-agent 之上的最后一层：不是证明代码链“看起来成立”，而是让红队 agent 在隔离 lab 里实际完成攻击并拿到 flag，再由独立模型审核轨迹。

## 分级

```text
L0 finding
L1 source-confirmed
L2 verify-agent 静态/运行环境验证
L3 红队捕获 flag
L4 独立 judge 通过 + 干净重跑
L5 人工验收
```

只有 L4/L5 才进入 CVE/披露候选。

## Lab

lab adapter 由 `redteam-lab-builder` skill/agent 根据 finding、源码和环境清单生成。默认按 finding 隔离到 `labs/<project>/<finding-id>/`，其中包含 `scenario.json`、`lab-report.md` 或 `BLOCKED.md`。

scenario 必须绑定 `finding_id`、finding 原始字节的 SHA-256，以及 source commit 或 content hash。builder 退出为 0 且结构化校验通过才算 built；陈旧、错 finding、非法 mount 或不支持的 mode 都会 fail closed。当前可执行 adapter 只支持 HTTP，其他攻击面保持 blocked。

`scripts/redteam/lab.py` 负责执行 scenario：

- 独立 Docker internal network，不发布宿主机端口
- victim/attacker 都有 cap-drop、no-new-privileges、PID/内存/CPU 限制
- flag 只由 harness 只读挂载到 victim 的 `/flag`
- attacker 不挂载宿主机、flag 或 Docker socket
- 每轮随机 flag，trace 记录工具事件、输出哈希和捕获事件

旧项目级 scenario 只有显式 `legacy_compatible: true` 且完整绑定仍匹配时才兼容。

## 红队 agent

`scripts/redteam/agent.py`：

- 读取 finding JSON，不读取预置 exploit
- 通过 OpenAI-compatible 模型做 agentic loop
- 每步只允许输出一个 JSON：`shell` 或 `done`
- 工具只在攻击者容器执行
- 成功条件：真实工具输出包含本轮随机 flag，并记录确定性 provenance
- 最终回答恰好等于 flag 但没有工具来源时，不算捕获
- 支持任意 OpenAI-compatible 服务，包括本地 Qwen/vLLM/llama.cpp

```bash
python3 scripts/redteam/agent.py \
  --finding labs/demo/finding.json \
  --victim-image mygoldmine/lab-demo-victim \
  --model flint \
  --base-url http://100.81.81.75:8081/v1 \
  --max-steps 10
```

切换到 Qwen 时只改：

```bash
REDTEAM_MODEL=<model-name> \
REDTEAM_BASE_URL=http://127.0.0.1:8000/v1 \
python3 scripts/redteam/agent.py ...
```

## Judge

`scripts/redteam/judge.py` 先重算工具事件、输出 SHA-256、flag SHA-256 和捕获事件，再让独立的 `exploit-judge` agent 审核目标漏洞、作弊可能、环境合理性、复现性和最小性。

judge 只有 Read/Grep/Glob 和指定的 judge.json 写权限，不执行 Bash。`approved` 必须通过完整 schema，全部必要布尔字段为 JSON true，recommended_status 为 runtime-validated；缺字段、字符串布尔或 provenance 不一致都会拒绝。只有同时通过模型审核和确定性校验的结果才写 validation 轨迹，也才可能进入 review。

```bash
python3 scripts/redteam/judge.py \
  --run-dir runs/redteam/demo/<run-id>
```

红队和 judge 不使用同一模型实例；judge 只看证据，不做攻击。

## 自动构建 lab

```bash
python3 scripts/redteam/build_lab.py \
  --project <project> \
  --finding <finding.json>

# batch 默认会先尝试自动构建缺失的 lab
python3 scripts/redteam/batch.py
python3 scripts/redteam/batch.py --no-build-labs
```

## 演示

```bash
docker build -t mygoldmine/lab-demo-victim labs/demo
python3 scripts/redteam/agent.py \
  --finding labs/demo/finding.json \
  --victim-image mygoldmine/lab-demo-victim \
  --model flint \
  --base-url http://100.81.81.75:8081/v1
python3 scripts/redteam/judge.py --run-dir <上一步输出的 run dir>
```

## 约束

- 只对授权目标、隔离 lab 使用。
- 不给红队预设 exploit；finding 是数据，不是指令。
- 不使用真实凭据、不访问外部目标、不写武器化持久化。
- flag 成功只证明该 lab 环境下可利用；报告仍需版本映射、干净重跑和人工验收。
- `rsi/trajectories/validation.jsonl` 记录通过 judge 的动态验证结果，供后续 RSI 学习。
