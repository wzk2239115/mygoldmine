# vLLM 项目知识卡

- 类型：inference-engine
- 审计 commit：`20bf65ad`（2026-10-27）
- 环境：`env/vllm/`（planned；完整运行需 `--mode full`，可能依赖 CUDA）

> 下面“已知高价值模式”来自 2026-10-27 的静态审计，默认仍是 **unverified**；
> 只能当线索，必须由 verify-agent 或运行时证据确认。

## 入口

- `vllm/entrypoints/cli/main.py`、`vllm/entrypoints/cli/serve.py`
- `vllm/entrypoints/launchers/app.py`、`vllm/entrypoints/openai/*`
- 管理/运维端点：`/invocations`、`/tokenize`、`/pooling`、`/classify`、`/score`、`/rerank`、
  `/update_weights`、`/update_weights_from_disk`、`/workers`、scale-out。
- 多模态：请求体 `image_url`/`audio_url`/`video_url` 触发服务端抓取。

## 信任边界

HTTP/OpenAI API、认证中间件、模型/权重、LoRA/适配器路径、多模态下载、IPC/Ray/NCCL、调度器/KV cache、Rust 前端。

## 已知高价值模式（来自 2026-10-27 报告）

- F-01：未认证 dev `/update_weights` + 客户端可控 pickle → 条件 RCE（需 dev/RL 开关）。
- F-02：`/invocations` 与 `/v1` 等价但绕过 api-key。
- F-04/F-05：默认多模态媒体 SSRF；allowlist 可被重定向绕过。
- F-09：LoRA 路径无白名单。
- F-06/07/08：未授权运维/管理面。
- 认证实现是路径前缀白名单（`/v1`、`/v2`、`/inference`、`/cohere`），大量等价端点不在白名单。

## 默认配置与开关

- `--host` / `--port`：默认绑定所有网卡。
- `--api-key` / `--admin-api-key`：可选；未配置时 fail-open。
- dev/RL 端点需要显式 flag 或 dev 模式。
- `--allowed-media-domains` 等 allowlist 存在，但重定向/解析差异可能绕过。

## 误报排除

- `torch.load(..., weights_only=True)` 且来源受信 → 不报 RCE。
- 多模态有 egress allowlist + 私网过滤 + 重定向校验 → 降级。
- 端点只在 `--dev`/RL 模式启用 → reachability=`dev-only`，不要默认 Critical。
- 同一根因的多个端点/语言实现合并，不要按端点数量重复计数。

## 验证配方

- 优先用 `mygoldmine/env:vllm-*` 起服务；若镜像 partial，至少做源码级 sink/配置验证。
- 默认配置：`curl 127.0.0.1` 检查 `/invocations`、`/tokenize` 是否需要 api-key。
- SSRF：只访问容器内回环监听器，不访问云元数据/公网。
- 权重更新：确认路由、认证、`load_format`/pickle sink，不执行不可信 payload。

## 下一步优先看

1. `/invocations`、`/tokenize`、`/score` 等非 `/v1` 端点的认证覆盖。
2. 多模态 URL 解析/重定向/私网过滤。
3. `update_weights*` + pickle/msgpack 的条件 RCE 链。
4. LoRA/模型路径是否限制在受信根目录。
