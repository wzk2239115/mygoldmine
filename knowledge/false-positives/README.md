# 误报模式库

按项目/类型积累“看起来像、实际不是”的模式。

## 通用

- `torch.load(..., weights_only=True)` + 受信 checkpoint → 不是 RCE。
- `yaml.load(..., Loader=SafeLoader)` → 不是反序列化 RCE。
- 只绑定 `127.0.0.1`/unix socket 的管理端点 → 网络不可达，降级。
- 危险 flag 只在显式 `--dangerously-*`/用户确认后生效 → `opt-in`，不是默认漏洞。
- allowlist + realpath + 重定向校验都存在的下载/文件路径 → 需要具体绕过证据。
- 测试/示例/文档中的不安全写法 → 不算产品默认行为。

## vLLM

- `torch.load` 全部 `weights_only=True`。
- 媒体抓取有 egress allowlist + 私网过滤。
- dev/RL 端点需要显式 flag。

## SGLang

- 配置了 `--api-key`/`--admin-api-key` 且中间件覆盖。
- SafeUnpickler allowlist。
- 管理端点只绑定回环。

## verl

- `exec/eval` 只处理受信本地脚本。
- 训练集群完全受信、无跨租户边界。
- `torch.load(weights_only=True)`。

## codex

- 控制面只绑定回环且同用户。
- 危险配置需显式确认。
- 沙箱/审批默认开启。

## deepseek-harness

- 文件读取有 workspace 前缀校验。
- 沙箱默认开启。
- control-plane 只绑定回环。

## 维护

每次 `hypothesis-critic` 或 `verify-agent` 判定 `rejected`，由 `knowledge-scribe` 把模式追加到这里。

## 2026-10-27 二次审计新增

- codex F-01 / F-36：exec-server 默认 `ws://127.0.0.1:0`；只有显式 `--listen 0.0.0.0` 且无 ws-auth 才成立 → opt-in。
- codex F-02 / F-25：app-server 默认 stdio/回环或已认证 WS，本地信任模型；不是未授权远程 → opt-in。
- deepseek VULN-004：session log 发往同一模型提供方，属既定功能/隐私设计；`.env` 禁止改 baseURL，无攻击者通道。
- deepseek VULN-006：无 turn budget 是设计限制，可取消/扩展；重试有上限，不是漏洞。
- deepseek VULN-001：与 VULN-002 同 `locateFile` 根因，合并。
- sglang VULN-001：与 VULN-002 同 `/server_info` 根因，合并。
- sglang VULN-025：标题/描述不一致，evidence 空、line 0 → UNCLEAR，重写或删除。
- verl CI-01 / CI-02：`custom_cls.path`/`router_config_path` 默认 null，来源是操作者 Hydra 配置；
  默认不可达、无跨信任边界 → FP（只有多租户/配置注入场景才重新评估）。
- verl AC-001 / AC-002：与 ROUTE-01/WEB-01、ROUTE-02/WEB-03 同根因，合并别名。

## agentscope-runtime（2026-10-27，静态审计）

- 沙箱内 `run_shell_command` / `run_ipython_cell`（`box/shared/routers/generic.py:121-138`）是**设计能力**，不是独立漏洞；
  只有在拿到沙箱 token、绕过 manager 或容器逃逸（MOBILE `privileged=True`）时才升级。generic 路由编译进 FILESYSTEM 镜像只算加固提示。
- `tools/mcp_wrapper.py` 的 `exec(code, namespace)`（`:137-184`）由**受信静态工具元数据**（类名/方法名/参数名/类型名）生成，
  非模型/用户可控；除非存在不可信插件或外部 FQN 注册工具元数据的入口，否则不报代码注入。
- Manager 默认 `HOST=127.0.0.1`（`sandbox/manager/server/config.py:15`）：默认配置类 finding 要写清
  “loopback 默认；远程需 `HOST=0.0.0.0` 或浏览器跨站”，不要直接按公网 Critical。
- 训练沙箱 `env_service` 与共享 box 的 `verify_secret_token` 是两套入口，不能因为共享 box 有 token 就认为训练面已认证。
- 同一根因的端点/脚本/Dockerfile 变体要合并（本次 8 条源 finding → 5 个 cluster），不要按出现次数重复计数。
- `/admin/status` 信息泄露、SSE 错误回显、完整请求体日志属低危，与 high 认证缺失合并评估，不重复计漏洞。


## 工具层误报（2026-10-28，batch 1）

这些不是目标仓库的漏洞模式，而是 mygoldmine 自身验证流程的误报来源：

- `auto_verify.sh` 把 `exec_module` 关键词命中判成 confirmed → verl CI-01 实际是默认 null、操作者 Hydra 配置的 FP。**关键词命中不是漏洞证明。**
- `auto_verify.sh` 把“关键词没搜到”判成 rejected → 关键词缺失同样不是反证。现在只允许 `inconclusive`。
- 源码链存在、但环境缺失/无法启动时，应标 `blocked` 或 `source-supported`，不能写 confirmed。
- 默认 HITL / 人工审批 / 回环绑定 / opt-in flag / 测试与示例代码，必须先在 `false_positive_checks` 里排除。
- `confirmed` 必须有 `evidence/` 文件；没有证据的 confirmed 由 `run_verify.sh` 自动降级。
- 只做单行 grep 的 harness 必须标 `evidence_class=static-pattern`，只能产出 `inconclusive`。

这些模式用于反向优化：
1. 先问“默认配置是否可达”；
2. 再问“有没有反向对照”；
3. 最后才问“sink 是否存在”。
缺少前两项时，不进入人工研判优先队列。
