---
name: rpc-surface-scanner
description: |
  RPC 与入口面审阅技能（由智能体阅读代码，不含规则扫描）。按 HTTP/gRPC/WebSocket/ZMQ/CLI
  入口逐项检查绑定地址、认证中间件、管理端点、默认配置与可达性。
---

# RPC Surface Scanner

> 这是**知识与审阅流程**，不是代码扫描器。不要把 `scripts/experimental/` 的运行结果当结论；
> 输出由 `infra-analyst` 写成归一化候选问题。

## 输入

- 项目根目录、commit
- `knowledge/projects/<project>.md`、`knowledge/project-types/<type>.md`
- 可选：`.workspace/tasks/<TASK_ID>/project-profile.json` 的 `entrypoints.infra`

## 审阅步骤

1. **列入口**：HTTP 路由、gRPC 服务、WebSocket、ZMQ、CLI、管理端点。
   - Python：FastAPI/Flask/aiohttp/uvicorn、`add_api_route`、`@app.*`
   - Rust：axum/actix/tonic、`Server::builder`、`add_service`
   - Go：`net/http`、gin/echo/chi、`grpc.NewServer`
   - IPC：ZMQ `ROUTER/PUB/SUB`、`tcp://*`、Ray/NCCL
2. **绑定地址**：默认 `0.0.0.0`/`::`/`--host 0.0.0.0`？还是 `127.0.0.1`/Unix 套接字？
3. **认证**：
   - 是否有全局中间件或拦截器？
   - 是否只覆盖部分路径前缀？等价端点（`/invocations`、`/tokenize`、`/workers`）是否绕过？
   - 未配置密钥时默认放行还是默认拒绝？
4. **管理/敏感端点**：`/server_info`、`/config`、`/metrics`、`/update_weights`、`/workers`、
   `/debug`、`/reload`、`/shutdown`。是否有独立认证/来源限制？
5. **WebSocket/gRPC**：握手/拦截器是否有身份校验？是否允许未授权调用高危方法？
6. **可达性**：默认配置即可达？需要额外开关或模式？只绑定回环？

## 输出

每条候选问题必须包含：入口、方法/路径、绑定地址、认证状态、前置条件、`reachability`、
`file:line`、证据片段、修复建议。没有从输入来源到危险操作完整路径的，只写待核实假设。

```json
{
  "id": "RPC-001",
  "title": "...",
  "severity": "high",
  "confidence": "medium",
  "reachability": "default|opt-in|dev-only|unknown",
  "cwe": "CWE-306",
  "files": [{"path": "...", "line_start": 1, "line_end": 1}],
  "evidence": [{"type": "code", "path": "...", "line": 1, "snippet": "..."}],
  "verification": {"status": "unverified", "method": "static", "report": ""},
  "remediation": "..."
}
```

## 误报排除

- 只绑定 `127.0.0.1`/Unix 套接字且同用户信任 → 降级并说明威胁模型。
- 认证由反向代理/网关统一提供 → 需要证据，不能直接判定无认证。
- 端点只在 dev/RL 模式启用 → `dev-only`，不标 Critical。
- 公开的健康检查或指标端点不必然敏感；看是否泄露密钥、配置或内部地址。

## 验证

- 启动本地服务，`curl 127.0.0.1` 检查认证与响应。
- 只访问容器内回环，不访问外部目标。
- 对 gRPC/WebSocket 只做无害调用或握手。
