# Red-team labs

lab 适配由 `redteam-lab-builder` skill/agent 自动生成，不是人工为每个项目写死。agent 先判断攻击面（http/stdio/cli/library/ipc/model），再构建 victim、flag 和 attacker。

没有自动化生成成功时，才需要人工提供下面的 `scenario.json`。默认路径按 finding 隔离：

```text
labs/<project>/<finding-id>/scenario.json
```

```json
{
  "schema_version": 1,
  "finding_id": "F-06",
  "finding_sha256": "<finding JSON 原始字节的 sha256>",
  "source": {"commit": "<source revision>"},
  "mode": "http",
  "victim_image": "mygoldmine/lab-codex-f06:latest",
  "attacker_image": "curlimages/curl:latest",
  "launch": {"command": []},
  "target_url": "http://victim:8000",
  "health": {
    "path": "/health",
    "attempts": 30,
    "interval_seconds": 0.5,
    "timeout_seconds": 2
  }
}
```

`source` 必须且只能包含 `commit` 或 `content_sha256` 之一。builder 会把当前 finding/source 绑定写进 `lab-task.json`；构建器退出为 0 且 scenario 通过结构化校验，`build_lab.py` 才返回成功。

要求：

- victim 容器必须在 `--internal` lab network 内启动真实服务，并设置 cap-drop、no-new-privileges、PID、内存和 CPU 限制
- 不发布宿主机端口；scenario 不允许声明 mounts/volumes，`/flag` 只由 harness 只读挂载给 victim
- attacker 只有 shell/curl，不挂载宿主或 flag
- `victim_image` 必须来自环境构建或专用 fixture，不能只复制源码就假装是服务
- `finding_id` 和 `finding_sha256` 必须与候选 finding 一致；source 绑定必须匹配构建输入
- 当前可执行适配器只支持 `mode: http`；其他攻击面必须保持 blocked，不能伪装成 HTTP
- flag 只能由 harness 从真实工具输出捕获，并记录工具事件、输出 sha256 和 flag sha256；最终回答不能凭空捕获
- judge 只有通过完整 schema、必要布尔值和确定性 provenance 校验的 `approved` 才写 validation 轨迹

旧路径 `labs/<project>/scenario.json` 只在 `legacy_compatible: true` 且完整绑定仍匹配时兼容；否则为 `blocked_legacy_scenario`。没有可用场景的 finding 会被 batch 标为 `blocked_no_lab`，不会伪造 flag。
