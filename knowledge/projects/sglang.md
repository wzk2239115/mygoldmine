# SGLang 项目知识卡

- 类型：inference-engine
- 审计 commit：`3a62cdfb`（2026-10-27）
- 环境：`env/sglang/`（planned；Python + Rust）

> 下面“已知高价值模式”来自 2026-10-27 的静态审计，默认仍是 **unverified**；
> 只能当线索，必须由 verify-agent 或运行时证据确认。

## 入口

- `python/sglang/srt/entrypoints/http_server.py`（主 HTTP 服务）
- `python/sglang/srt/entrypoints/grpc_server.py` / native gRPC
- `sgl-model-gateway/`、`sgl-router/`（Rust 网关/路由）
- 多模态生成、ZMQ broker、disaggregation、tokenizer worker
- 管理端点：`/server_info`、`/get_server_info`、`/update_weights_from_disk`、`/workers`、`/flush_cache`

## 信任边界

HTTP/gRPC、认证中间件、模型权重、LoRA、多模态/媒体抓取、ZMQ/IPC、tokenizer worker、Rust 网关/路由、调度器。

## 已知高价值模式（来自 2026-10-27 报告，需去重后使用）

- VULN-002：`/server_info` 明文返回 `api_key`/`admin_api_key`/launch config。
- VULN-006：未配置密钥时认证 fail-open，43 个管理端点匿名可达。
- VULN-004：`/update_weights_from_disk` 接受任意 `model_path`，`load_format=pt` 触发 `torch.load(weights_only=False)`。
- VULN-008：未认证 `POST /workers`，可 SSRF/流量劫持。
- ZMQ/多模态调度器反序列化不可信 pickle；native gRPC 无认证；tokenizer worker 模式不装认证中间件。

## 去重提示

报告有 342 条，但语义簇严重重复：

- `server_info` 17 条
- `torch.load` 18 条
- `flush_cache` 13 条
- `/workers` 5 条
- `source_id` 复用混乱

分析时按 **root cause + 文件/函数** 合并，不要按端点/语言重复计数。

## 误报排除

- `--api-key`/`--admin-api-key` 已配置且中间件覆盖 → 降级。
- `torch.load(weights_only=True)` / SafeUnpickler allowlist → 不报 RCE。
- 管理端点只绑定回环或仅内部网络 → 降级。
- 某些端点只在特定后端/多模态/RL 模式启用 → 标 reachability。

## 验证配方

- 起 HTTP 服务，`curl 127.0.0.1/server_info` 检查是否泄露密钥。
- 对 `/update_weights_from_disk` 只验证路径/格式校验，不加载未知权重。
- gRPC/ZMQ 检查绑定地址与认证；只连容器内回环。
- 用 `--mode auto` 环境做源码级导入/配置验证；完整运行可能需 GPU。

## 下一步优先看

1. `server_info` 脱敏与认证覆盖。
2. fail-open 默认与 tokenizer worker 分支。
3. `update_weights_from_disk` + `load_format=pt` 的 pickle 链。
4. `/workers`、gRPC、ZMQ 的未认证入口。
