# Inference Engine 审计知识卡

## 适用项目

vLLM、SGLang、TensorRT-LLM、llama.cpp、TGI、OpenAI-compatible serving。

## 核心信任边界

1. **HTTP/OpenAI API**：`/v1/*`、`/invocations`、`/tokenize`、`/pooling`、`/score`、`/rerank`、管理端点。
2. **认证中间件**：路径前缀白名单、`api_key`/`admin_api_key`、fail-open 默认、tokenizer worker 分支。
3. **模型/权重**：`from_pretrained`、`trust_remote_code`、`torch.load`、`safetensors`、LoRA 路径、`/update_weights*`。
4. **多模态抓取**：`image_url`/`audio_url`/`video_url`、媒体下载、重定向、私网/云元数据。
5. **IPC/分布式**：ZMQ、msgpack、Ray、NCCL、共享内存、disaggregation。
6. **调度/缓存**：KV cache、请求队列、动态 batching、worker 管理、scale-out。
7. **Native/CUDA**：C++/CUDA 扩展、索引计算、内存拷贝。

## 高价值问题

- 默认是否绑定 `0.0.0.0` 且无认证？认证是否只覆盖部分路径前缀？
- `/invocations`、`/tokenize`、`/pooling`、`/classify`、`/score`、`/rerank` 是否与 `/v1` 等价但绕过认证？
- 多模态 URL 是否允许回环/私网/云元数据？重定向能否绕过 allowlist？
- `/update_weights`、`/update_weights_from_disk`、`/workers`、scale-out 是否未认证？是否触发 pickle/RCE？
- `torch.load` 是否 `weights_only=True`？LoRA/model_path 是否有受信根目录限制？
- gRPC/ZMQ 是否监听所有网卡、无认证？反序列化是否在 `0.0.0.0` socket 上？
- 管理端点是否泄露 `api_key`/`admin_api_key`/launch config？
- 调度器/队列是否存在无界增长、竞态、资源耗尽？

## 常见 CWE

CWE-306、CWE-862、CWE-502（反序列化）、CWE-918（SSRF）、CWE-22、CWE-200、
CWE-400（资源耗尽）、CWE-362（竞态）、CWE-787/125（内存安全）。

## 误报排除

- `torch.load(..., weights_only=True)` 且来源受信 → 不报 RCE。
- 多模态抓取有 egress allowlist + 私网过滤 + 重定向校验 → 降级/排除。
- 认证缺失但端点只在 `--dev`/RL 模式启用 → reachability=`dev-only`。
- 默认绑定回环或仅 unix socket → 不作为网络可达 Critical。
- 同一根因的多个端点/语言实现应合并，不按端点数量重复计数。

## 验证配方

- 用环境镜像启动服务（默认配置 / 安全配置两套），`curl 127.0.0.1` 检查认证与响应。
- 对 SSRF 只访问容器内回环测试监听器，不访问云元数据/公网。
- 对反序列化只确认 sink 与数据来源，不在生产/宿主执行不可信 payload。
- 对竞态/DoS 用最小并发/长度验证，设超时与资源限制。

## 输出要求

必须标注：默认配置是否可达、需要哪些 flag、认证是否覆盖、是否有网络暴露、是否只在 dev/RL 模式。
同一根因合并为一条，列出 aliases。
