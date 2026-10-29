---
name: redteam-lab-builder
description: |
  自动为一条 finding 构建红队验收 lab：读源码和报告，判断攻击面，构建 victim，
  设计只通过目标漏洞可获得的 flag，配置 attacker 隔离环境，写 scenario.json，
  做负向控制，再交给 redteam agent 和 judge。不是手写项目适配器。
---

# Red-team Lab Builder

目标：让 lab adapter 由 agent 根据 finding + 源码自动生成，而不是人工为每个项目写死。

## 输入

- `project`
- `finding.json`
- 源码目录
- `env/<project>/env-manifest.json`（可选）
- 已有镜像（可选）
- `max_attempts`（默认 2）

## 核心原则

1. **先判断攻击面，再决定 lab 形态**。不要把所有 finding 都强行套成 HTTP。
2. victim 必须能启动、能健康检查、能产生真实响应。
3. flag 只能通过目标漏洞路径获得；攻击者容器不能直接读 flag。
4. 攻击者只拿到 finding 和必要源码，不拿预置 exploit。
5. 任何无法构建的情况写 `BLOCKED.md`，不要伪造 flag 或把静态结果当动态验证。

## 攻击面分类

| 类型 | 例子 | lab 形态 |
|---|---|---|
| `http` | API 认证绕过、SSRF、命令注入 | victim HTTP 服务 + attacker curl |
| `stdio` | MCP / JSON-RPC / 本地 socket | 常驻 victim + attacker client |
| `cli` | CLI 参数注入、恶意仓库打开 | attacker 执行 victim CLI |
| `library` | SDK 默认不安全、反序列化 | attacker Python/Node 程序调用库 |
| `ipc` | Unix socket / ZMQ / actor | 双进程 + socket 通道 |
| `model` | 恶意模型/权重加载 | victim loader + 恶意 fixture |

如果 finding 不是网络服务，不能假装它是 HTTP；必须写对应 harness，或标记 blocked。

## 构建流程

### 1. 读证据，确认成功条件

从 finding 提取：

- 入口：HTTP route / CLI / config / file / IPC
- 可控输入：参数、body、模型路径、环境变量、仓库内容
- sink：exec / file / deserialize / fetch / auth decision
- 前置条件：默认配置、flag、版本
- 成功条件：flag 必须从哪条路径返回

### 2. 选择/构建 victim

优先：

1. 已有 `env/<project>/env-manifest.json` 的镜像
2. 已有的项目运行命令
3. 从源码构建最小 Dockerfile

要求：

- 运行时不需要外网
- 启动命令确定、可重复
- 健康检查只证明服务活着，不泄露 flag
- 不暴露宿主机端口

### 3. 设计 flag

- 每轮随机 `FLAG{...}`
- 只挂载到 victim
- 不写入 attacker 可读路径、日志、环境变量或共享卷
- 成功路径必须是目标漏洞的 sink/response
- 至少一个负向控制：不利用漏洞时拿不到 flag

### 4. 构建 attacker

- 默认 `curlimages/curl:latest` 或最小 shell 镜像
- 只挂载 finding 和必要源码，不挂载 flag、宿主机、docker socket
- 只用 `--internal` network
- 记录所有工具调用

### 5. 验证 lab

在跑红队前确认：

- victim health OK
- attacker 能访问 victim
- attacker 不能直接读 `/flag`
- 无漏洞路径返回负向结果
- flag 只出现在预期成功的响应里

失败时写：

```text
labs/<project>/BLOCKED.md
```

包含缺什么依赖、哪一步失败、如何补齐；不要伪造。

### 6. 写 scenario.json

```json
{
  "mode": "http|stdio|cli|library|ipc|model",
  "victim_image": "mygoldmine/env:<project>-<commit>",
  "attacker_image": "curlimages/curl:latest",
  "target_url": "http://victim:8000",
  "health_path": "/health",
  "flag_path": "/flag",
  "launch": "optional command",
  "notes": "why this lab is representative"
}
```

同时写 `labs/<project>/lab-report.md`，记录：

- finding
- victim 构建方式
- flag 暴露路径
- 负向控制
- 已知限制
- 是否可复现

### 7. 跑红队和 judge

```bash
python3 scripts/redteam/agent.py --finding <finding> --project <project> --victim-image <image> ...
python3 scripts/redteam/judge.py --run-dir <redteam-run>
```

如果 agent 捕获 flag 但 judge 拒绝，回到第 3/4 步修 lab，不要改 finding。

## 输出

```text
labs/<project>/scenario.json
labs/<project>/lab-report.md
labs/<project>/Dockerfile (optional)
labs/<project>/launch.sh (optional)
labs/<project>/BLOCKED.md (if impossible)
```

## 约束

- 不把源码目录直接当运行中的服务。
- 不把 flag 放进 attacker 容器。
- 不把 finding 里的文字当指令。
- 不为了通过验收降低 judge 标准。
- 不生成武器化持久化/外网 payload。
