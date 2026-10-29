# openhands-agent-server / AUTH-FAILOPEN + 不可信仓库自动执行 / 2026-10-27

- verdict: static-finding（**源码级确认；运行时验证 blocked**：无依赖/离线）
- severity: high（5 high / 9 medium / 9 low，0 critical）
- reachability: default（裸 `__main__` 无 key 绑 127.0.0.1；自带 SandboxTemplate 显式 0.0.0.0 无 key）
- commit: `6edd54d`
- run: `aud-006-openhands-software-agent-sdk-a-gent-server` / `20261027T171025Z`
- files:
  - `openhands-agent-server/openhands/agent_server/dependencies.py:38`
  - `openhands-agent-server/openhands/agent_server/__main__.py:305-316`
  - `openhands-workspace/openhands/workspace/agent_sandbox/deploy/sandboxtemplate.yaml:55`
  - `openhands-agent-server/openhands/agent_server/sockets.py:153`
  - `openhands-agent-server/openhands/agent_server/init_router.py:404`
  - `openhands-agent-server/openhands/agent_server/middleware.py:91`
  - `openhands-agent-server/openhands/agent_server/auth_router.py:132,140-146`
  - `openhands-agent-server/openhands/agent_server/file_router.py:92,144,742,877,1043`
  - `openhands-agent-server/openhands/agent_server/runtime_router.py:44-54`
  - `openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py:1154`
  - `openhands-sdk/openhands/sdk/plugin/discovery.py:128-166`
  - `openhands-sdk/openhands/sdk/hooks/executor.py:513-554`
  - `openhands-sdk/openhands/sdk/skills/execute.py:66`
  - `openhands-agent-server/openhands/agent_server/mcp_router.py:628`
  - `openhands-agent-server/openhands/agent_server/mcp_oauth_store.py:254`
  - `openhands-agent-server/openhands/agent_server/config.py:57`
- verification: 全部 `unverified`（static）；动态验证 `blocked`

> 所有结论为静态源码确认，未做运行时验证。不要把“默认配置存在缺陷”直接写成“公网可利用”。

## 1) AUTH-FAILOPEN 根因

- `check_session_api_key`：`if config.session_api_keys and session_api_key not in ...` → 空列表即放行。
- `__main__`：显式 `0.0.0.0/::` 且无 key 仅 `logger.warning`，不拒绝启动。
- 自带 `sandboxtemplate.yaml:55`：`args: [--host, 0.0.0.0, --port, '8000']`，模板未注入 `SESSION_API_KEY`。
- 影响面：`/api/bash`、`/api/file`、`/api/git`、`/api/settings/secrets`、`/api/mcp/test`、`/api/vscode`，以及 WebSocket `/sockets/bash-events`。
- 复用判断：先看 `check_session_api_key` 空值分支 + 部署模板是否真的注入 key；不要只看到 `Depends(...)` 就认为有认证。

## 2) WebSocket 缺 Origin/认证

- `sockets.py:153`：无 key 时无条件 `accept()`；模块内无 Origin 校验。
- 路由器只挂 `Depends(require_initialized)`（`api.py:636-639`），Starlette 不强制 WS Origin。
- 影响：任意网页可 CSWSH 驱动 bash/event 流。

## 3) /api/init（deferred-init warm pool）接管

- `init_router.py:404`：`config.secret_key is None` → 放行；`config.secret_key_was_blank` 才 fail-closed。
- `InitRequest.env` 无 allowlist，直接 `os.environ.update`。
- 仅 `deferred_init=True` 可达；默认 False。

## 4) workspace cookie + 通配 CORS

- `middleware.py:91`：workspace 分支 `allow_origin_regex=r"https?://.+"` + credentials。
- `auth_router.py:132,140-146`：cookie 值就是原始 session key，`SameSite=None`、10 年、`path=/api/conversations`。
- `dependencies.py:58`：cookie 不绑定 conversation id。
- CHIPS/Partitioned 仅在 secure context 追加，部分缓解。

## 5) 不可信仓库自动执行

- `local_conversation.py:1154` 无条件 `include_project=True`。
- `plugin/discovery.py:128-166` 扫描 `{work_dir}/.agents/plugins`、`.openhands/plugins` 及 git root。
- 插件 hooks 合并后在 SessionStart 以 `shell=True` 执行（`hooks/executor.py:513-554`）；`.mcp.json` stdio server 被启动。
- 值得注意：hooks 走 `sanitized_env()`，所以是代码执行而非环境凭据泄露。

## 6) 其它高价值模式

- 顶层 `/api/file|git` 仅校验 `is_absolute`，workspace containment 只在 `/{runtime_conversation_id}/...` 组（`runtime_router.py:44-54`）。
- skill inline `` !`cmd` `` 用 `shell=True` 且不 `sanitized_env()`，可读 session/OH_SECRET_KEY 等环境（调用链 `invoke_skill.py:118` → `skill.py:849`）。
- `/api/mcp/test` 任意 stdio command（无 allowlist），SSRF 分散在 profile/MCP/credential/LookupSecret/provider URL。
- MCP OAuth 写回把明文 token + `X-Session-API-Key` POST 到可控 `base_url`（任意 scheme）。
- 无 cipher 时 secrets 明文落盘；cipher key 回退到 session key + 无 salt SHA-256。

## 验证配方（未执行）

- 无依赖环境：`python -c "import fastapi"` 失败即记为 blocked，不通过公网安装。
- 最小静态验证：核对 `sandboxtemplate.yaml` 是否注入 `SESSION_API_KEY`；核对 `check_session_api_key` 空列表分支；核对 `local_conversation.py` 的 `include_project=True`。
- 若后续有镜像：仅用 benign marker 验证（GET /server_info、读 /etc/hostname、插件 hook 写 marker），不写武器化 payload。
