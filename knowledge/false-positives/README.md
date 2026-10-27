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
