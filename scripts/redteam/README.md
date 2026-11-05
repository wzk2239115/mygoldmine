# Red-team validation

```bash
# demo
docker build -t mygoldmine/lab-demo-victim labs/demo
python3 scripts/redteam/agent.py --finding labs/demo/finding.json --victim-image mygoldmine/lab-demo-victim
python3 scripts/redteam/judge.py --run-dir runs/redteam/demo/<run-id>
```

# 由智能体自动生成隔离验证环境
python3 scripts/redteam/build_lab.py --project <project> --finding <finding.json>

# 17 条候选，默认先尝试自动建立隔离验证环境
python3 scripts/redteam/batch.py

场景支持三种执行原语：HTTP 常驻服务（`mode=http`）、固定命令行（`mode=cli`）和进程内库调用（`mode=library`）。红队执行和独立审核默认各最多 10 条候选并行，批处理可用 `--agent-jobs` 与 `--judge-jobs` 调整。红队执行单候选默认总超时 7200 秒、最多 1000 步，可用 `--agent-timeout` 或 `REDTEAM_AGENT_TIMEOUT` 调整。命令行和库调用场景通过 `/input` 接收攻击者文件，受害端只执行场景固定命令或固定驱动入口；攻击者容器不能向受害端直接传命令。红队模型通过 `--model` / `REDTEAM_MODEL` 和 `--base-url` / `REDTEAM_BASE_URL` 指定。

无法构建时构建器提交 `blocked.json`，其中记录真实攻击面、已核对入口、缺少能力和重试条件；不再用“未生成 scenario.json”覆盖原因。

安全边界：HTTP 场景使用内部网络；命令行和库调用场景的受害端不依赖网络。攻击者容器按宿主机 uid/gid 运行，不挂载随机标记、没有 Docker 套接字，只能写 `/input`；输入执行前复制为快照，符号链接和设备文件会被拒绝，符号链接只拒绝本次输入并提示智能体清理；随机标记每轮随机。
