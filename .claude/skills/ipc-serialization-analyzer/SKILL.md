---
name: ipc-serialization-analyzer
description: |
  IPC/反序列化审阅技能（agentic）。追踪 pickle/torch.load/yaml.load/msgpack/bincode，
  以及 ZMQ/Ray/NCCL/共享内存消息来源，判断是否可被不可信输入触达。
---

# IPC / Serialization Analyzer

> 知识与审阅流程，不含检测脚本。重点是输入来源到危险操作的路径与默认可达性，不是 grep 命中数量。

## 输入

- 项目源码、`knowledge/projects/<project>.md`
- 重点目录：模型加载、检查点、IPC、分布式处理、权重更新、插件

## 审阅步骤

1. **反序列化危险操作**：
   - Python：`pickle.load(s)`、`torch.load`、`dill.load`、`joblib.load`、`yaml.load`、`msgpack.unpackb`
   - Rust：`bincode::deserialize`、`rmp_serde::from_slice`、`postcard::from_bytes`
   - Go：`gob.NewDecoder`、自定义二进制解析
2. **数据来源**：
   - 网络请求体、权重更新端点、ZMQ/ROUTER socket、Ray/NCCL、共享内存、上传文件、checkpoint。
   - 是否来自不可信用户/节点？是否有签名/HMAC/长度/类型校验？
3. **安全模式**：
   - `torch.load(..., weights_only=True)`？
   - `yaml.safe_load`/`SafeLoader`？
   - `SafeUnpickler` allowlist？allowlist 是否可绕过？
4. **代码执行**：
   - `exec`/`eval` 的输入是否来自模型输出/配置/网络？
   - `from_pretrained(..., trust_remote_code=True)`、动态模块加载。
5. **IPC 边界**：
   - ZMQ 是否绑定 `tcp://*`/`0.0.0.0`？是否无认证？
   - Ray/NCCL 是否跨信任边界？消息是否可被同集群恶意节点伪造？
6. **可达性**：默认配置是否可达？需要 dev/RL/特定后端？

## 输出

每条候选问题写清：输入来源、危险操作、序列化格式、安全模式缺失、前置条件、`reachability`、证据。

## 误报排除

- `weights_only=True` + 受信检查点 → 不报 RCE。
- `yaml.safe_load`/SafeLoader → 不报。
- 只处理本地受信文件的 `pickle` → 降级。
- 纯 JSON/Protobuf 不等于安全，但需要具体解析器漏洞证据。
- 同一危险操作的多个调用点合并为一条。

## 验证

- 只确认危险操作和输入来源；不加载不可信 pickle/权重。
- 可用无害标记证明 exec 路径，不执行外部载荷。
- IPC 只连接容器内回环地址或测试套接字。
