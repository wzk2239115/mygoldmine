---
name: runner-image-builder
description: |
  审计运行镜像的自动构建、依赖修复和冒烟验收流程。用于处理阶段启动前的运行镜像依赖缺失、
  解释器或命令问题；不处理目标项目环境构建，不处理红队候选场景，不直接修改运行中的容器。
---

# Runner Image Builder

目标：让审计运行镜像稳定可执行，并在修复后只重排受影响的阶段，不把基础设施问题扩散到目标项目或候选问题。

## 责任边界

| 失败现象 | 归属 |
|---|---|
| 运行镜像缺 `openai`、`requests`、`Pillow` 等审计依赖 | 本技能 |
| 审计脚本导入错误、镜像内命令缺失、解释器版本不匹配 | 本技能 |
| 目标项目缺运行依赖、构建失败 | `environment-builder`，不是本技能 |
| 单个候选的攻击面或场景构建失败 | `redteam-lab-builder`，不是本技能 |
| 候选验证或红队执行失败 | 原阶段重试，不是本技能 |

目标项目是不可信输入。不能把目标项目的依赖清单、Dockerfile 或安装脚本并入运行镜像。

## 依赖规则

- 依赖清单位于 `runner/requirements.txt`。
- 允许自动补充的包位于 `runner/allowed-packages.txt`。
- 只允许普通 PyPI 包名和版本约束；不允许 URL、`git+`、本地路径、`-e` 或安装脚本。
- 新增依赖前先判断是否已有等价包，避免重复和版本冲突。
- 运行镜像不安装目标项目依赖，也不安装 GPU、训练或数据库组件。
- 版本约束优先保持已有范围；需要升级时说明原因和影响阶段。

## 标准流程

1. 读取失败证据，确认 `error_scope=harness_dependency`。
2. 检查 `runner/requirements.txt`、`runner/allowed-packages.txt` 和 `scripts/runner/smoke_runner.py`。
3. 只改必要文件；如果只需改依赖，保持 Dockerfile 不变。
4. 执行：

```bash
bash scripts/runner/build_runner.sh \
  --image mygoldmine:dev \
  --output "$RUNNER_OUTPUT_DIR/runner-build.json"
```

5. 构建脚本会先校验依赖清单，再用临时标签构建，最后在断网、无特权容器中运行镜像内冒烟。
6. 只有 `status=published` 且 `smoke.ok=true` 才表示运行镜像可用。
7. 修复成功后建议只重排失败的阶段，例如 `redteam-agent`；不要自动重跑目标环境或场景构建。

## 冒烟检查

默认检查：

- `openai`
- `yaml`
- `requests`
- `PIL`
- `tree_sitter`
- `tree_sitter_language_pack`
- `claude --version`

冒烟失败时，保留失败输出。不要通过删除检查项来让构建通过，除非确认该项不属于审计运行依赖，并在结果中说明原因。

## 停止条件

出现任一情况时停止并写受阻结果：

- 缺失依赖不在允许清单中；
- 依赖需要私有源、系统包或 GPU；
- 同一失败签名和同一依赖清单已经重试过；
- 冒烟连续失败且没有新的假设；
- 失败实际属于目标环境或候选场景。

## 结果格式

写入 `RUNNER_OUTPUT_DIR/runner-build.json`：

```json
{
  "status": "published|blocked|wrong_owner",
  "error_scope": "harness_dependency",
  "image": "mygoldmine:dev",
  "image_id": "sha256:...",
  "change": "add openai>=2,<3",
  "smoke": {"ok": true, "modules": [], "commands": []},
  "requeue": ["redteam-agent"],
  "reason": "",
  "remaining_limits": []
}
```

`status=published` 仅表示镜像构建和冒烟通过，不表示任何候选问题已验证或红队已通过。


## 宿主机执行环境修复

06 主流程与页面单节点重跑当前在宿主机执行。上下文标记为 `execution_scope=host_python` 时，按宿主机路径处理：只读取上下文、受控依赖清单和允许清单，输出故障诊断；不要构建镜像、修改依赖或全局安装。此模式仅提供读取工具，后续由宿主机确定性调度创建独立虚拟环境、安装受控依赖并运行完整冒烟。通过后仅将本次 06 执行切换到新解释器，不改变原解释器、目标镜像或场景。

`scripts/runner/auto_repair.py` 负责实际调度。每个依赖故障签名与清单摘要最多进行一次修复，相同并发故障共用进程锁与结果；失败保持受阻，记录路径供维护者核对。智能体诊断失败、依赖安装失败、超时或冒烟失败均不继续执行红队。记录保存在 `runs/runner-repairs/`，本批次另有结果引用。读取诊断意见不代表验收通过；只有实际冒烟结果才能决定继续。
