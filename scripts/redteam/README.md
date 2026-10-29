# Red-team validation

```bash
# demo
docker build -t mygoldmine/lab-demo-victim labs/demo
python3 scripts/redteam/agent.py --finding labs/demo/finding.json --victim-image mygoldmine/lab-demo-victim
python3 scripts/redteam/judge.py --run-dir runs/redteam/demo/<run-id>
```

真实目标只需替换 `--victim-image`、`--target-url`、`--health-path`。红队模型通过 `--model` / `REDTEAM_MODEL` 和 `--base-url` / `REDTEAM_BASE_URL` 指定。

安全边界：`Lab` 使用 `docker network create --internal`；攻击者容器不挂载宿主、不挂载 flag、没有 Docker socket；flag 每轮随机。
