# Red-team labs

每个目标需要自己的 lab 适配，不能拿源码目录直接当“受害者服务”。

```text
labs/<project>/scenario.json
```

```json
{
  "victim_image": "mygoldmine/lab-demo-victim",
  "attacker_image": "curlimages/curl:latest",
  "target_url": "http://victim:8000",
  "health_path": "/health"
}
```

要求：

- victim 容器必须在 `--internal` lab network 内启动真实服务
- 不发布宿主机端口
- `/flag` 只挂载给 victim，不挂载给 attacker
- attacker 只有 shell/curl，不挂载宿主或 flag
- `victim_image` 必须来自环境构建或专用 fixture，不能只复制源码就假装是服务

没有 `scenario.json` 的 finding 会被 batch 标为 `blocked_no_lab`，不会伪造 flag。
