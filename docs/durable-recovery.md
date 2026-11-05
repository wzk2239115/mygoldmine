# 批量审计异常恢复

## 行为

默认批量审计将 `.workspace/findings`、`.workspace/tasks` 持久化到运行目录的 `task-artifacts`、`task-state`。容器退出后产物仍保留。原始轨迹不会被覆盖。

`progress_guard.py` 根据原始轨迹中的实际事件判断进展，不把界面刷新或监督进程心跳视为进展。原始轨迹尚未产生事件的环境准备阶段默认允许 900 秒，模型等待阶段默认连续 180 秒无事件触发退出码 125；存在未完成的 `tool_use` 时不因暂时无事件而误终止，但总时限仍触发 124。它是进程级监视，不是 HTTP 请求级超时；仍有输出的重复循环需要后续另加检测。

默认 `run.sh` 在批量审计异常退出且原始轨迹能解析出基础设施检查任务计划时，自动进入同级的 `-recovery` 目录。其他类型的任务尚不支持自动拆分恢复。`AUTO_RECOVER=0` 可关闭此回退。

恢复器复用已有合法产物，只重新执行缺失或失败的边界；每个任务使用独立容器，不再通过模型内部 Task 调度嵌套分派。检查点记录目标提交、产物 SHA256、尝试次数及状态。重启时校验这些信息，并保留被中断的尝试目录；文件锁防止同一目录重复运行。

默认单任务 600 秒、最多 2 次尝试、本次恢复进程总预算 1800 秒。显式重新启动恢复进程会重新计算总预算，但不会清空已记录的尝试次数。配置项为 `AUDIT_IDLE_TIMEOUT`、`AUDIT_SETUP_IDLE_TIMEOUT`、`RECOVERY_TASK_TIMEOUT`、`RECOVERY_BUDGET`、`RECOVERY_MAX_ATTEMPTS`。

失败边界不阻止汇总已有成果。边界全部完成且最终报告通过 `check_report.py` 质量检查时标记为 `success`；报告有效但存在失败边界时标记为 `partial`，并列出缺失边界。最终报告不能通过时标记为 `failed` 并保存 `partial-report.json`，不能把候选问题列表为空解释为无漏洞。恢复返回监督进程后，质量合格的报告继续进入第 4 阶段；质量失败时不自动验证。

## 手动恢复

在仓库根执行：

```sh
python3 scripts/mine/durable_recovery.py \
  --target /absolute/target \
  --recover-from /absolute/old-run \
  --run-dir /absolute/new-run \
  --idle-timeout 180 --task-timeout 600 --budget 1800 --max-attempts 2
```

再次使用相同 `--run-dir` 即可从检查点继续。运行中不要手工改写检查点或产物。

## 2026-10-30 诊断证据

原 deepseek-harness 运行 20261030T085517Z 的六个边界有五个完成，文件系统边界停滞。没有明确 context_length_exceeded 错误，不能确认硬性上下文超限。其最后请求用量字段之和约 131793 输入 token，而正常完成的配置边界约 145136；代理用量字段存在统计口径不确定性。

恢复运行 20261030T100530Z 复用五个边界，文件系统边界首次尝试约九分钟完成，最后输入用量约 28789 token。恢复同时改变上下文规模和并发，因此不能据此独立归因。明确的流程缺陷是缺少基于进展的超时和分支恢复。本补丁解决成果持久化、有限重试、失败隔离及汇总收尾；请求级遥测和上下文主动压缩仍待实现。

## 验证

本轮 30 项 scoped 测试覆盖恢复、重试 deadline、旧 429 隔离、setup/model/tool idle、无效报告、125、recovery Phase 4 和 batch 质量拒绝；全部使用 fake clock/runner，不启动真实模型或容器。
