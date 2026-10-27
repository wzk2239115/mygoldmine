# Training Framework 审计知识卡

## 适用项目

verl、DeepSpeed、Megatron-LM、Ray RLlib、FSDP/GRPO/PPO 训练框架。

## 核心信任边界

1. **模型输出执行**：`exec`/`eval` 模型生成代码、reward/grader、代码沙箱。
2. **数据/配置**：dataset 路径、YAML/JSON 配置、Hydra、环境变量、HDFS/S3 路径。
3. **Checkpoint**：`torch.load`、`pickle`、merge/split 脚本、resume。
4. **分布式**：Ray、NCCL、ZeroMQ、worker/router、driver 信任。
5. **训练服务**：reward loop 反向代理、worker HTTP、OpenAI-compatible 端点。
6. **依赖/脚本**：`requirements*.txt` 未固定版本、`curl | sh`、shell 脚本、CI。

## 高价值问题

- 模型生成代码/答案是否进入 `exec`/`eval`，默认是否有沙箱？
- `load_module`/`exec_module`/`load_class_from_fqn` 是否接受任意路径/类名？
- checkpoint/模型合并是否 `torch.load(weights_only=False)` 或 `pickle.load`？
- reward router / worker 是否绑定可路由 IP 且无 api_key？
- Ray/NCCL/ZMQ 消息是否来自不可信节点？是否有认证/序列化校验？
- dataset/model 路径是否可穿越到受信根之外？HDFS/S3 命令是否拼接用户输入？
- 训练脚本/文档是否引导 `curl | sh` 或未固定版本依赖？

## 常见 CWE

CWE-95（eval 注入）、CWE-78、CWE-502、CWE-306、CWE-22、CWE-400、CWE-362、CWE-829。

## 误报排除

- `exec`/`eval` 只在明确的可信本地脚本中使用，且不接收模型/用户输入 → 不报。
- `torch.load(weights_only=True)` + 受信 checkpoint → 不报 RCE。
- 训练集群完全受信、无跨租户边界 → 需说明威胁模型，降级。
- 供应链卫生问题（未 pin 版本）不要和 RCE 同级；通常 Medium/Low。

## 验证配方

- 用环境镜像运行最小 Python 导入/单测，确认 sink 可达。
- 对 exec/eval 只用 benign marker，不执行外部载荷。
- 对 reward router/worker 起本地服务，`curl 127.0.0.1` 检查认证。
- 对路径问题只验证 realpath 边界，不读写宿主敏感文件。

## 输出要求

必须区分“训练节点内部信任”与“跨租户/网络可达”。默认配置、需要哪些启动参数、是否只在特定 dataset/reward 模式下触发，都要写清。
