# verl 项目知识卡

- 类型：training-framework
- 审计 commit：`174888fc`（2026-10-27）
- 环境：`mygoldmine/env:verl-test`（partial；`pip install -e . --no-deps`）

> 下面“已知高价值模式”来自 2026-10-27 的静态审计，默认仍是 **unverified**；
> 只能当线索，必须由验证智能体（`verify-agent`）或运行时证据确认。

## 入口

- `verl/experimental/reward_loop/router/naive_router.py`（未认证反向代理）
- 工作进程 HTTP、奖励循环和兼容 OpenAI 接口的端点
- `verl/utils/reward_score/prime_code/testing_util.py`（模型代码 `exec`）
- `verl/utils/reward_score/prime_math/`（模型答案 `eval`）
- `verl/utils/import_utils.py`（`load_module`/`exec_module`）
- `scripts/model_merger.py`、`verl/model_merger/`（检查点/权重）
- Ray / NCCL / 分布式训练进程

## 信任边界

模型输出、奖励与评分、数据集、配置（Hydra）、检查点、Ray/NCCL、奖励路由进程与工作进程、HDFS/S3、依赖脚本。

## 已知高价值模式（来自 2026-10-27 报告）

- FIND-001：`prime_code` 对模型生成代码 `exec(compile(...))`，非安全沙箱。
- FIND-002：`prime_math` 对模型答案 `eval`。
- CI-01：`load_module` 文件路径分支 `exec_module` 任意 Python 文件。
- CI-02：`load_class_from_fqn` 按配置加载任意类。
- AC-001/ROUTE-01/WEB-01：未认证 catch-all 反向代理绑定可路由 IP（同一根因）。
- AC-002/ROUTE-02：工作进程 HTTP 绑定可路由 IP 且无 `api_key`。
- DEP-01/02：文档引导直接执行远程脚本（`curl | sh`）、`requirements` 未固定版本（供应链卫生，通常为中危或低危）。

## 默认配置与开关

- 奖励路由进程和工作进程的绑定地址与 `api_key` 配置。
- 训练是否使用本地 `exec`/`eval`、是否启用远程沙箱。
- 检查点合并脚本的 `torch.load` 参数。
- Ray/NCCL 集群是否跨信任边界。

## 误报排除

- `exec`/`eval` 只在受信本地脚本、输入不可控时不报。
- `torch.load(weights_only=True)` 且检查点受信时不报远程代码执行。
- 训练集群完全受信、无跨租户边界时，说明威胁模型后降级。
- 直接执行远程脚本属于供应链卫生问题，不要与远程代码执行同级。

## 验证配方

- 环境镜像 `mygoldmine/env:verl-test` 可做源码级或导入级验证。
- 对 `exec`/`eval` 只生成无害标记，不执行外部载荷。
- 启动奖励路由进程或工作进程，用 `curl 127.0.0.1` 检查认证与绑定。
- 对路径问题只验证真实路径（`realpath`）边界，不读宿主机敏感文件。

## 下一步优先看

1. FIND-001/FIND-002 的默认可达性（是否所有奖励模式都触发）。
2. AC-001/AC-002 的默认绑定与 `api_key`。
3. CI-01/CI-02 的配置来源是否可控。
4. 检查点合并（`checkpoint/merge`）的 `torch.load` 参数。

## 后续波次优先技能

首波由基础设施分析智能体（`infra-analyst`）处理上文入口中的 `exec`/`eval`、检查点、反向代理和分布式边界。后续波次按项目画像的推荐技能和覆盖缺口选择：

- `web-auth-analyzer`：进入奖励循环反向代理、工作进程 HTTP、兼容 OpenAI 接口的端点或管理接口时，检查认证和绑定。
- `unauth-route-scanner`：认证分析完成后，枚举无需认证即可访问的路径。
- `path-traversal-analyzer`：数据集、模型、检查点或日志路径来自配置、请求、HDFS 或 S3 时，检查路径边界。
- `sensitive-info-scanner`：配置模板、启动脚本、日志或接口响应中出现令牌、`api_key` 或凭据时，检查泄露。
- `dependency-analyzer`：检查 `requirements*.txt`、锁文件、安装脚本和持续集成配置中的未固定版本或远程执行。
- `race-conditions-analyzer`：异步奖励评分、工作队列、共享检查点目录或并发写入出现时，检查共享状态和写入顺序。
- `command-injection-analyzer`：训练命令、启动脚本、HDFS/S3 命令或 `subprocess` 拼接可控参数时，检查 shell 使用和参数拼接。

只有入口存在且尚未覆盖时才创建任务；同一“区域 + 视角 + 假设 + 技能版本”不重复安排。

上文的 FIND、CI 和 AC 条目继续保持 `unverified` 线索；复审或技能推荐不会把它们升级为 `confirmed`，也没有新增未核实 CVE。
