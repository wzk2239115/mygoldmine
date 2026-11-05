# 推理引擎（Inference Engine）审计知识卡

## 适用项目

vLLM、SGLang、TensorRT-LLM、llama.cpp、TGI，以及兼容 OpenAI 接口的模型服务。

## 核心信任边界

1. **HTTP 与 OpenAI API**：`/v1/*`、`/invocations`、`/tokenize`、`/pooling`、`/score`、`/rerank` 和管理端点。
2. **认证中间件**：路径前缀白名单、`api_key`、`admin_api_key`、失败时默认放行，以及分词器工作进程分支。
3. **模型与权重**：`from_pretrained`、`trust_remote_code`、`torch.load`、`safetensors`、LoRA 路径和 `/update_weights*`。
4. **多模态抓取**：`image_url`、`audio_url`、`video_url`、媒体下载、重定向、私网和云元数据。
5. **进程间通信与分布式执行**：ZMQ、msgpack、Ray、NCCL、共享内存和分离式部署。
6. **调度与缓存**：KV 缓存、请求队列、动态批处理、工作进程管理和横向扩容。
7. **本地代码与 CUDA**：C++ 和 CUDA 扩展、索引计算、内存拷贝。

## 高价值问题

- 默认是否绑定 `0.0.0.0` 且无认证？认证是否只覆盖部分路径前缀？
- `/invocations`、`/tokenize`、`/pooling`、`/classify`、`/score`、`/rerank` 是否与 `/v1` 等价但绕过认证？
- 多模态 URL 是否允许访问回环地址、私网或云元数据？重定向能否绕过白名单？
- `/update_weights`、`/update_weights_from_disk`、`/workers` 和横向扩容是否未认证？是否触发 pickle 反序列化或远程代码执行？
- `torch.load` 是否设置 `weights_only=True`？LoRA 和 `model_path` 是否有受信根目录限制？
- gRPC 和 ZMQ 是否监听所有网卡且无认证？反序列化是否发生在 `0.0.0.0` 套接字上？
- 管理端点是否泄露 `api_key`、`admin_api_key` 或启动配置？
- 调度器和队列是否存在无界增长、竞态或资源耗尽？

## 常见 CWE

CWE-306、CWE-862、CWE-502（反序列化）、CWE-918（SSRF）、CWE-22、CWE-200、
CWE-400（资源耗尽）、CWE-362（竞态）、CWE-787/125（内存安全）。

## 误报排除

- `torch.load(..., weights_only=True)` 且来源受信：不报远程代码执行。
- 多模态抓取具备出站白名单、私网过滤和重定向校验：降级或排除。
- 认证缺失但端点只在 `--dev` 或强化学习模式启用：可达性为 `dev-only`。
- 默认绑定回环地址或仅使用 Unix 套接字：不作为网络可达的严重问题。
- 同一根因的多个端点或语言实现应合并，不按端点数量重复计数。

## 验证配方

- 用环境镜像分别按默认配置和安全配置启动服务，`curl 127.0.0.1` 检查认证与响应。
- 对 SSRF 只访问容器内回环测试监听器，不访问云元数据或公网。
- 对反序列化只确认危险数据终点与数据来源，不在生产环境或宿主机执行不可信载荷。
- 对竞态和拒绝服务使用最小并发与长度验证，设置超时和资源限制。

## 输出要求

必须标注：默认配置是否可达、需要哪些启动参数、认证是否覆盖、是否有网络暴露，以及是否只在开发或强化学习模式启用。
同一根因合并为一条，列出别名。
