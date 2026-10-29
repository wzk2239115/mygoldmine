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

`scripts/redteam/lab.py` 创建：

- 独立 Docker network，`--internal`，攻击者不能出公网
- 受害者容器：目标镜像，不发布宿主机端口；flag 以只读文件挂载到 `/flag`
- 攻击者容器：只有 shell/curl，不挂载宿主机、不挂载 flag、没有 docker socket
- 每轮随机 `FLAG{...}`，不写入攻击者可见路径
- `runs/redteam/<project>/<run>/trace.jsonl` 记录工具调用和输出

flag 必须由受害者的真实服务响应返回；攻击者侧没有 flag 文件。

## 红队 agent

`scripts/redteam/agent.py`：

- 读取 finding JSON，不读取预置 exploit
- 通过 OpenAI-compatible 模型做 agentic loop
- 每步只允许输出一个 JSON：`shell` 或 `done`
- 工具只在攻击者容器执行
- 成功条件：工具输出或最终回答中精确出现本轮随机 flag
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

`scripts/redteam/judge.py` 使用独立的 `exploit-judge` agent 审核：

- 是否利用 finding 描述的目标漏洞
- flag 是否来自受害者，而不是攻击者侧文件/伪造输出
- 是否访问宿主、Docker socket、共享卷、外网或调试后门
- 轨迹是否可复现、是否最小
- 证据是否足以支持 `runtime-validated`

```bash
python3 scripts/redteam/judge.py \
  --run-dir runs/redteam/demo/<run-id>
```

红队和 judge 不使用同一模型实例；judge 只看证据，不做攻击。

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
