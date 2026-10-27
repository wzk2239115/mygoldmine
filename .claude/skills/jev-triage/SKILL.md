---
name: jev-triage
description: Jev/SystemOne 决策模型快速初筛技能：对大型仓库的文件或代码块并行做 yes/no/choice/score 判断，快速定位与认证、控制面、模型加载、SSRF、配置信任、敏感信息等相关的候选，减少 Claude Code 深读范围；只做召回初筛，不作为漏洞结论。
---

# Jev 决策模型文件初筛

## 适用场景

- 目标仓库文件数多（>500 文件）或 Claude Code 无法一次读完。
- 需要回答“哪些文件/代码块与 xxx 功能有关”，但正则难以表达（例如“是否有认证边界”“是否会从客户端输入加载模型/adapter”“是否默认暴露控制面”）。
- 深度审计前，需要把 Read/Grep 预算集中到高概率文件。
- 已有 ripgrep 候选文件，但需要语义二次排序。

**不适用**：需要生成文本、解释、多步推理、精确计数/日期比较；需要最终漏洞定级；仓库包含大量真实密钥且无法脱敏。

## 模型与端点

- 默认模型：`typesafe/jev-latest`（360 返回 `typesafe/jev-1.14-20261014`）。
- 备选：`alibaba/decision-model-preview`。
- 端点：`POST https://api.360.cn/v1/systemone`。
- 请求形态：

```json
{
  "model": "typesafe/jev-latest",
  "state": "FILE: path\n\n<code>",
  "questions": {
    "auth_check": {"type": "noul", "instructions": "..."},
    "area": {"type": "choice", "instructions": "...", "criteria": {"auth": "...", "other": "..."}},
    "risk": {"type": "score", "instructions": "...", "criteria": ["Low", "Medium", "High"]}
  }
}
```

- 响应：`answers.<key>`，noul 返回 `noul` 概率，choice 返回 `choice/probabilities/confidence`，score 返回 `score/probabilities/confidence`。
- 同一 state 的所有 question 并行评估；**一次调用问完所有可能需要的判断**，不要串行追问。

## 凭据

按顺序读取：

1. `--api-key`
2. `JEV_API_KEY` / `THREE60_API_KEY` / `OPENCODE_360_KEY`
3. `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` / `GLM_API_KEY`（`mine_one.sh` / `mine_one_docker.sh` 已把 360 key 放进这些变量）
4. `~/.config/opencode/opencode.json` 的 `provider["360-proxy"].options.apiKey`
5. `OPENCODE_CONFIG` 指向的配置文件

不要打印、写入报告或日志。

## 快速开始

在目标仓库根目录执行：

```bash
python3 .claude/skills/jev-triage/jev_triage.py \
  --root . --profile infra \
  --top-k 80 --workers 8
```

输出位置：

- `RUN_DIR` 已设置（`mine_one.sh` / `mine_one_docker.sh` 的审计流程）：写到 `$RUN_DIR/triage/jev-<profile>.json|md`，容器退出后仍保留。
- `RUN_DIR` 未设置：写到 `<root>/.workspace/triage/jev-<profile>.json|md`。

只看计划、不调用模型：

```bash
python3 .claude/skills/jev-triage/jev_triage.py --root . --profile infra --dry-run
```

对 ripgrep 候选二次排序：

```bash
rg -l 'trust_remote_code|auto_map|torch\.load|from_pretrained' > /tmp/jev-candidates.txt
python3 .claude/skills/jev-triage/jev_triage.py \
  --root . --paths-from /tmp/jev-candidates.txt \
  --profile lora-model --top-k 50 --workers 8
```

按代码块初筛：

```bash
python3 .claude/skills/jev-triage/jev_triage.py \
  --root . --profile auth --block-lines 80 --max-chars 6000 \
  --glob '*.py' --glob '*.ts' --top-k 100
```

自定义判断：

```bash
python3 .claude/skills/jev-triage/jev_triage.py \
  --root . --profile custom \
  --question 'handles_upload=This code handles a file upload from an HTTP request' \
  --question 'writes_disk=This code writes attacker-controlled data to disk' \
  --top-k 40
```

## Profiles

| profile | 主要判断 |
|---|---|
| `infra` | 控制面、认证边界、不可信模型/路径输入、路径白名单、子进程、反序列化、出站 URL、默认暴露 |
| `auth` | 认证实现、未认证路由、客户端身份信任、fail-open、推理能力暴露 |
| `input-sink` | 攻击者输入、危险 sink、校验/白名单（反向计分）、外部可达性、风险评分 |
| `config-trust` | 项目级配置加载、自动加载、子进程/Git hook、无确认生效 |
| `lora-model` | 客户端控制路径、路径白名单（反向计分）、权重反序列化、adapter resolver |
| `secrets` | 硬编码凭据、日志/响应泄露、凭据入 URL |
| `custom` | `--question` / `--choice` / `--score` |

`positive: false` 的问题（如 `path_allowlist`、`validation`）表示“命中是缓解项”，会降低优先级，并写入 `mitigations`。

## 输出怎么用

脚本写两个文件：

- `$RUN_DIR/triage/jev-*.json`（或 `<root>/.workspace/triage/jev-*.json`）：机器可读，包含每个 unit 的 `priority/flags/mitigations/answers`。
- 同目录 `jev-*.md`：人读 top-k 表。

读取策略：

- `priority >= 0.70`：优先 Read/Grep 深读。
- `0.40 <= priority < 0.70`：人工/LLM 复核，尤其看 `flags` 命中但 `mitigations` 未命中的单元。
- `< 0.40`：通常可跳过；但 ripgrep 已命中的 sink 关键词仍以确定性证据为准。
- `confidence` 低或答案接近 0.5：要求 Claude 读代码确认，不要直接下结论。
- Jev 的 `noul` 概率是**校准置信度**，不是正确性保证；可被代码注释、字符串等 state 内容影响（prompt injection / adversarial content）。

## 与 Claude Code 的结合方式

推荐顺序：

1. `workspace-scanner` / `project-profiler` 得到项目类型与入口。
2. `ripgrep` 做确定性候选（路由、sink、配置文件名）。
3. 对候选跑 `jev-triage`（`infra` + `auth` + `input-sink`）。
4. Claude 只读 top-k + 低置信度 + `flags` 与 `mitigations` 冲突的单元。
5. 深读后用 `infra-analyst` / 具体 analyzer 形成 finding；Jev 结果只作为 `triage` 证据，不进入最终 severity。

在 Agentic Infra Track 中可直接把 `$RUN_DIR/triage/jev-infra.json`（或 `.workspace/triage/jev-infra.json`）作为 `infra-analyst` 的输入之一。`mine_one.sh` 已导出 `RUN_DIR`，Docker 也按相同绝对路径挂载，因此容器内写出的 triage 文件会落到宿主 run 目录。

## 性能与成本

- 单请求 1–3 秒（360 代理实测），输入约 1–3k tokens/文件。
- 价格约 $0.042 / M input tokens，output 免费；2000 个文件、每文件 1.5k tokens 约 $0.13。
- `--workers 8` 约 4–8 req/s；不要超过 16，360 限制约 1200 req/min。
- `--batch-size 4` 可把多个文件放进一个 state、为每个文件生成独立 question，减少请求数；但 state 过大会降低准确率，建议只在 top-k 二次排序时用，并抽检。
- `--cache-dir` 默认缓存答案；同一文件内容不变时重复运行几乎零成本。

## 安全边界

- 默认跳过 `.env`、`*.pem`、`*.key`、`id_rsa*`、`credentials*`、`secrets*`、`auth.json` 等敏感文件（`.env.example` 除外）。
- 发送前做基础脱敏（`sk-*`、`AKIA*`、`Bearer *`、`password=...`）。
- 不要把含真实密钥的目录传给 `--root`；不要把 `--allow-sensitive` 当成默认。
- Jev 只做召回初筛；不得用它单独确认漏洞、定级或授权任何操作。
- 代码注释/字符串可能影响判断；把 Jev 输出当作“需要读哪里的信号”，不是“结论”。

## 失败处理

- `HTTP 400`：检查 `model` 是否带 provider 前缀（必须 `typesafe/jev-latest`），以及 `questions` 是否合法。
- `HTTP 429/5xx`：脚本自动退避重试；仍失败时降低 `--workers`。
- 大文件超时：降低 `--max-chars`，或 `--block-lines` 切块。
- 批处理失败：`--fallback-single`（默认开启）会逐文件重试。
