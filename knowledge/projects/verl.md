# verl 项目知识卡

- 类型：training-framework
- 审计 commit：`174888fc`（2026-10-27）
- 环境：`mygoldmine/env:verl-test`（partial；`pip install -e . --no-deps`）

> 下面“已知高价值模式”来自 2026-10-27 的静态审计，默认仍是 **unverified**；
> 只能当线索，必须由 verify-agent 或运行时证据确认。

## 入口

- `verl/experimental/reward_loop/router/naive_router.py`（未认证反向代理）
- worker HTTP / reward loop / OpenAI-compatible 端点
- `verl/utils/reward_score/prime_code/testing_util.py`（模型代码 exec）
- `verl/utils/reward_score/prime_math/`（模型答案 eval）
- `verl/utils/import_utils.py`（`load_module`/`exec_module`）
- `scripts/model_merger.py`、`verl/model_merger/`（checkpoint/权重）
- Ray / NCCL / 分布式 trainer

## 信任边界

模型输出、reward/grader、dataset、配置/Hydra、checkpoint、Ray/NCCL、reward router/worker、HDFS/S3、依赖脚本。

## 已知高价值模式（来自 2026-10-27 报告）

- FIND-001：`prime_code` 对模型生成代码 `exec(compile(...))`，非安全沙箱。
- FIND-002：`prime_math` 对模型答案 `eval`。
- CI-01：`load_module` 文件路径分支 `exec_module` 任意 Python 文件。
- CI-02：`load_class_from_fqn` 按配置加载任意类。
- AC-001/ROUTE-01/WEB-01：未认证 catch-all 反向代理绑定可路由 IP（同一根因）。
- AC-002/ROUTE-02：worker HTTP 绑定可路由 IP 且无 api_key。
- DEP-01/02：文档引导 `curl | sh`、requirements 未固定版本（供应链卫生，通常 Medium/Low）。

## 默认配置与开关

- reward router / worker 的绑定地址与 api_key 配置。
- 训练是否使用本地 exec/eval、是否启用远程沙箱。
- checkpoint 合并脚本的 `torch.load` 参数。
- Ray/NCCL 集群是否跨信任边界。

## 误报排除

- `exec/eval` 只在受信本地脚本、输入不可控 → 不报。
- `torch.load(weights_only=True)` + 受信 checkpoint → 不报。
- 训练集群完全受信、无跨租户边界 → 说明威胁模型后降级。
- `curl | sh` 属于供应链卫生，不要与 RCE 同级。

## 验证配方

- 环境镜像 `mygoldmine/env:verl-test` 可做源码级/导入级验证。
- 对 exec/eval 只用 benign marker，不执行外部载荷。
- 起 reward router/worker，`curl 127.0.0.1` 检查认证与绑定。
- 对路径问题只验证 realpath 边界，不读宿主敏感文件。

## 下一步优先看

1. FIND-001/FIND-002 的默认可达性（是否所有 reward 模式都触发）。
2. AC-001/AC-002 的默认绑定与 api_key。
3. CI-01/CI-02 的配置来源是否可控。
4. checkpoint/merge 的 `torch.load` 参数。
