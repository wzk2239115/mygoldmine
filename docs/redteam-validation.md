# 基于随机标记的动态验收

这是候选问题验证（`verify-agent`）之上的最后一层：不是证明代码链“看起来成立”，而是让红队智能体在隔离环境中实际完成攻击并拿到随机标记（flag），再由独立模型审核轨迹。

## 分级

```text
L0 候选问题
L1 源码级确认
L2 verify-agent 静态/运行环境验证
L3 红队捕获随机标记
L4 独立审核通过 + 干净重跑
L5 人工验收
```

只有 L4 和 L5 才进入 CVE 与披露候选。

## 隔离环境

隔离环境适配器由 `redteam-lab-builder` 技能和智能体根据候选问题（finding）、源码和环境清单生成。默认按候选问题隔离到 `labs/<project>/<finding-id>/`，其中包含 `scenario.json`、`lab-report.md` 或 `BLOCKED.md`。

场景必须绑定 `finding_id`、候选问题原始字节的 SHA-256，以及源码提交或内容哈希。构建器退出码为 0 且结构化校验通过才算构建完成；场景过期、候选问题不匹配、挂载配置非法或现有原语无法表达时都不会执行。执行器支持 HTTP 常驻服务、固定命令行和进程内库调用三种原语；命令行和库调用场景中攻击者只能写 `/input` 快照，攻击者容器按宿主机 uid/gid 运行，受害端只执行场景固定入口；输入含符号链接时只拒绝本次输入并提示清理，不判场景无效；无法表达时提交结构化 `blocked.json`。

`scripts/redteam/lab.py` 负责执行场景：

- 使用独立的 Docker 内部网络，不发布宿主机端口
- 目标端和攻击端都有 `cap-drop`、`no-new-privileges`、进程数、内存和 CPU 限制
- 随机标记只由验证程序（harness）以只读方式挂载到目标端的 `/flag`
- 攻击端不挂载宿主机目录、随机标记或 Docker 套接字
- 每轮使用随机标记，轨迹记录工具事件、输出哈希和捕获事件

旧项目级场景只有显式设置 `legacy_compatible: true` 且完整绑定仍匹配时才兼容。

## 红队智能体

`scripts/redteam/agent.py`：

- 读取候选问题 JSON，不读取预置利用代码
- 通过兼容 OpenAI 接口的模型进行多轮智能体交互
- 每步只允许输出一个 JSON：`shell` 或 `done`
- 工具只在攻击者容器执行
- 成功条件：真实工具输出包含本轮随机标记，并记录可重新计算的确定性证据来源链（provenance）
- 单候选默认总超时 7200 秒（2 小时），最多执行 1000 步；批处理和节点重跑可用 `REDTEAM_AGENT_TIMEOUT` 或 `--agent-timeout` 调整总超时
- 最终回答恰好等于随机标记但没有工具来源时，不算捕获
- 支持任意兼容 OpenAI 接口的服务，包括本地 Qwen、vLLM 和 llama.cpp

```bash
python3 scripts/redteam/agent.py \
  --finding labs/demo/finding.json \
  --victim-image mygoldmine/lab-demo-victim \
  --model flint \
  --base-url http://100.81.81.75:8081/v1 \
  --max-steps 1000
```

切换到 Qwen 时只改：

```bash
REDTEAM_MODEL=<model-name> \
REDTEAM_BASE_URL=http://127.0.0.1:8000/v1 \
python3 scripts/redteam/agent.py ...
```

## 独立审核

`scripts/redteam/judge.py` 先重算工具事件、输出 SHA-256、随机标记 SHA-256 和捕获事件，再让独立的 `exploit-judge` 智能体审核目标漏洞、作弊可能、环境合理性、复现性和最小性。

独立审核（judge）只有 Read、Grep、Glob 和指定 `judge.json` 的写权限，不执行 Bash。审核结论为 `approved` 时必须提供完整固定结构，全部必要布尔字段为 JSON `true`，且 `recommended_status` 为 `runtime-validated`；缺字段、字符串布尔或证据来源链不一致都会拒绝。只有同时通过模型审核和确定性校验的结果才写入验证轨迹，也才可能进入待人工验收状态。

```bash
python3 scripts/redteam/judge.py \
  --run-dir runs/redteam/demo/<run-id>
```

红队和独立审核不使用同一模型实例；独立审核只看证据，不做攻击。

## 自动构建隔离环境

```bash
python3 scripts/redteam/build_lab.py \
  --project <project> \
  --finding <finding.json>

# 批量执行默认会先尝试自动构建缺失的隔离环境
python3 scripts/redteam/batch.py
python3 scripts/redteam/batch.py --no-build-labs

# run.sh 主流程：当前审计运行中的严重或高危候选问题自动进入批量执行与独立审核
bash scripts/redteam/phase5_redteam.sh \
  --project <project> --run-dir <run> --max 5 \
  --model flint --judge-claude claude
```

## 演示

```bash
docker build -t mygoldmine/lab-demo-victim labs/demo
python3 scripts/redteam/agent.py \
  --finding labs/demo/finding.json \
  --victim-image mygoldmine/lab-demo-victim \
  --model flint \
  --base-url http://100.81.81.75:8081/v1
python3 scripts/redteam/judge.py --run-dir <上一步输出的运行目录>
```

## 约束

- 只对授权目标和隔离环境使用。
- 不给红队预设利用代码；候选问题是数据，不是指令。
- 不使用真实凭据、不访问外部目标、不编写武器化持久化内容。
- 成功捕获随机标记只证明该隔离环境下可利用；报告仍需版本映射、干净重跑和人工验收。
- `rsi/trajectories/validation.jsonl` 记录通过独立审核的动态验证结果；第 6 阶段同时构建红队运行与步骤经验。挖掘修复候选必须在独立目录实际重跑红队审核后才可发布，候选审核轨迹通过 `RSI_VALIDATION_TRAJECTORY` 与正式历史隔离；未捕获或审核未通过不能自动成为误报规则。
