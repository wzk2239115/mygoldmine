# Batch 1 — RCE 候选短名单

- 生成时间：2026-10-28
- 结论：**有 RCE 候选，但还没有“运行时实测 RCE”证据。**
- 最强的是 `OpenSandbox EXECD-001`：源码链 + 默认网络暴露都成立，当前为源码级 confirmed。

## 第一梯队：源码链确认，优先验证

### 1. OpenSandbox EXECD-001（Critical）

- 入口：未认证 `POST /internal/init`
- 链：`/internal/init` 在 `preInitPaths`，`accessTokenMiddleware` 提前放行 → `InitController.Init` → `RuntimeInitManager.Apply` → `runPreStart` → `RunHook` → `exec.Command(hook.Command[0], hook.Command[1:]...)`
- 默认可达：`execd` 监听 `:44772`（所有 IPv4），Docker 默认 `publish_host=0.0.0.0`
- 影响：未认证调用者可让 execd 执行请求指定的 hook 命令，并可写入新的 binding/token
- 状态：verify `confirmed`，method `static`；未实际执行 marker
- 限制：部署可能改成只绑 `127.0.0.1`；hook 以 execd 进程身份运行
- 报告：`runs/aud-048-opensandbox/20261028T080748Z/verify/execd-001/verify-report.md`

### 2. AgentScope Runtime INFRA-LCP-003（High）

- 入口：训练 box `env_service` 的 `/step` 等接口
- 默认：`--portal 0.0.0.0`，无认证中间件
- 链：`/step` 将 action 交给环境执行，可达代码执行
- 状态：source-level confirmed；缺运行时验证
- 报告：`runs/aud-046-agentscope-runtime/20261027T171026Z/verify/INFRA-LCP-003/verify-report.md`

### 3. Xinference MODEL-001（High）

- 入口：`POST /v1/models` 的 `model_path`
- 链：内置 family 保留 `is_builtin=True` → `allow_trust_remote_code()` 返回 True → dots.ocr `trust_remote_code=True` → 加载调用者目录里的 `scripts/qwen3_vl_embedding.py`
- 前置：`models:write` 或认证关闭；攻击者能在 worker 文件系统放置目录
- 状态：source-level confirmed；未运行时验证
- 报告：`runs/aud-080-xinference/20261028T070634Z/verify/ML-001/verify-report.md`

### 4. Xinference MODEL-003（High）

- 入口：`POST /v1/models` 的 `model_code_path`
- 链：`_ensure_source_checkout` 只检查 `is_dir()` → 作为 cwd → `runpy.run_path('generate.py')`
- 前置：`models:write` 或认证关闭；攻击者控制目录
- 状态：source-level confirmed
- 报告：`runs/aud-080-xinference/20261028T070634Z/verify/ML-003/verify-report.md`

## 第二梯队：源码链成立，运行时 blocked

### 5. OpenHands SEC-001 / CFG-001（High，2/2 轮）

- 仓库内插件/`.mcp.json`/SessionStart hooks 自动加载，`shell=True` 执行仓库控制内容
- 影响：克隆恶意仓库并在其中启动会话即可在宿主执行命令
- 状态：2/2 轮一致，源码链成立；未运行时执行
- 备注：默认 MANUAL/HITL 只覆盖部分 tool，不覆盖插件启动 hooks

### 6. Cline WS-TRUST-001 / CLINE-010 / CLINE-011（High，2/2 轮）

- `.clinerules/hooks`、`.cline/hooks` 在 session/task 事件自动执行，无 workspace trust 确认
- 影响：恶意仓库 → hooks → 宿主命令执行
- 状态：2/2 轮一致，源码链成立；未运行时执行

### 7. OpenCode OC-001 / OC-003（High）

- OC-001：well-known/remote config 被解析为完整 Config.Info，可注入 plugin/local MCP/skill
- OC-003：`worktree_create` 的 `..` 逃逸，项目 setup 命令在逃逸目录运行
- 状态：源码链成立，运行时 blocked；需要相应配置/操作路径

### 8. Deep Agents EXEC-001（High）

- 模型可控 tool 参数到 `LocalShellBackend.execute(shell=True)`，继承完整环境
- 状态：源码链成立，运行时 blocked
- 限制：默认 MANUAL/HITL 会拦截 `execute`；需要 auto_approve/YOLO/allow-list 或 context-forced path

## 明确是条件性/opt-in，不建议直接当默认真实 RCE

- `llama.cpp VULN-002`：`--tools/--agent/MCP` 开启后未认证 `/tools` 执行 shell；运行时 blocked
- `llama.cpp VULN-012`：未认证 RPC `GGML_OP_CUSTOM`；缺运行环境
- `llama.cpp VULN-021/022`：模型转换脚本 RCE，取决于转换工作流/模型仓库
- `TEI-05`：`TRUST_REMOTE_CODE=true`，默认 false
- `LiteLLM LITELLM-002`：LocalSandbox 执行模型生成 shell；需确认默认模式与部署边界
- `OpenSandbox CP-001`：已动态确认的 proxy 认证绕过，但不是 RCE；需确认是否能接到 execd/控制面

## 下一步

1. 对 `OpenSandbox EXECD-001` 做 benign marker 运行时验证（当前最强 RCE）。
2. 对 `AgentScope INFRA-LCP-003`、`Xinference MODEL-001/MODEL-003` 做最小运行时 harness。
3. 对 `OpenHands SEC-001`、`Cline WS-TRUST` 用临时恶意仓库 + marker 验证默认启动链。
