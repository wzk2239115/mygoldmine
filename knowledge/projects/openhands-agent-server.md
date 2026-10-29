# OpenHands Agent Server / SDK 项目知识卡

- 类型：agent-harness（兼 backend-http）
- 审计 commit：`6edd54d`（2026-10-27）
- 仓库：`software-agent-sdk`，组件 `openhands-agent-server`、`openhands-sdk`、`openhands-tools`、`openhands-workspace`
- 环境：无（本次静态审计；运行验证 blocked）

> 以下为静态审计线索，默认 **unverified**；只能当线索，需 verify-agent 或运行时证据确认。

## 入口

- Agent Server HTTP API：`/api/*`，统一 `Depends(require_initialized), Depends(check_session_api_key)`（`api.py:577-584`）。
- 例外：`server_details_router`（无认证）、`/api/init`（X-Init-API-Key）、WebSocket `/sockets/*`（仅 require_initialized）、workspace cookie 路由（header 或 cookie）。
- SDK：`LocalConversation._ensure_plugins_loaded`、skills execute、hooks executor、MCP client。
- Workspace runtimes：docker、apptainer、agent_sandbox（k8s SandboxTemplate）。

## 信任边界

config、filesystem、http、mcp、process-exec、sandbox。

## 已知高价值模式（2026-10-27）

- AUTH-FAILOPEN：`dependencies.py:38` 空 key 放行；`__main__` wildcard 仅告警；SandboxTemplate 0.0.0.0 无 key。
- CSWSH：`sockets.py:153` 无 key 接受且不校验 Origin。
- `/api/init`：`secret_key=None` 时开放 + `InitRequest.env` 注入 `os.environ`。
- workspace cookie = 原始 session key + 通配 CORS with credentials。
- 顶层 `/api/file|git` 无 workspace containment；仅 runtime 路由有 `is_relative_to`。
- 不可信仓库自动加载 `.agents/plugins` / `.openhands/plugins`，hooks shell=True、MCP stdio 启动。
- skill inline `` !`cmd` `` shell=True 且继承全环境。
- `/api/mcp/test` 任意 stdio；profile/MCP/credential/LookupSecret/provider URL SSRF。
- VS Code token 复用 session key 并绑 0.0.0.0。
- Docker runtime 绑定客户端提供的主机 working_dir。
- secrets 无 cipher 时明文落盘；cipher key 回退 session key。

## 默认配置与开关

- `SESSION_API_KEY` / `OH_SESSION_API_KEYS_0`：未设置 → 认证 fail-open。
- `--host`：未指定且无 key → 127.0.0.1；显式 wildcard 无 key → 仅 warning。
- `deferred_init`：默认 False；True 时 `/api/init` 可达。
- `OH_SECRET_KEY`：未设置 → cipher 回退到 session key；再无 key → 明文。
- `enable_vscode`、`conversation_runtime=docker`、webhook/marketplace → opt-in 边界。

## 误报排除

- 已认证下的任意 bash/file 访问是 agent server 设计内能力，不算漏洞。
- 裸 `__main__` 默认回环 → 说明威胁模型；只有 SandboxTemplate/显式 wildcard 才是网络默认暴露。
- hooks 使用 `sanitized_env()` → 不要误报环境凭据泄露（skills/execute.py 才是未清洗）。
- 没有 source→sink 的“可能泄露/可能 SSRF”只写 hypothesis。

## 验证配方

- 起本地 server：检查 `/server_info`、`/api/file/download` 是否需要 `X-Session-API-Key`。
- 构造最小项目 `.agents/plugins/<p>/hooks`，观察 SessionStart 是否执行 benign marker。
- 检查 SandboxTemplate 是否注入 `SESSION_API_KEY`。
- 仅做配置级验证，不写武器化绕过。
