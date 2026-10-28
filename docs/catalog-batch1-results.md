# Catalog Batch 1 — 静态审计结果

- 生成时间：2026-10-27
- 范围：`agent_llm_audit_catalog.xlsx` 首批候选 22 个
- 完成：18 个新跑 + 3 个复用已有报告 = 21/22；`aud-004-openclaw` 克隆超时（仓库约 11GB）
- 新跑报告：354 findings（1 critical、53 high、147 medium、152 low、1 info）
- 性质：静态分析结论，未做运行时验证；高危项仍需人工复核

## 项目结果

| 项目 | Findings | Critical | High | Medium | Low | 耗时 | Run |
|---|---:|---:|---:|---:|---:|---:|---|
| `aud-048-opensandbox` | 30 | 1 | 6 | 8 | 15 | 41m | `runs/aud-048-opensandbox/20261027T184554Z` |
| `aud-001-cline` | 25 | 0 | 7 | 12 | 6 | 45m | `runs/aud-001-cline/20261027T181038Z` |
| `aud-080-xinference` | 22 | 0 | 7 | 8 | 7 | 32m | `runs/aud-080-xinference/20261027T192717Z` |
| `aud-060-llama-cpp` | 26 | 0 | 5 | 12 | 9 | 51m | `runs/aud-060-llama-cpp/20261027T190611Z` |
| `aud-006-openhands-software-agent-sdk-a-gent-server` | 23 | 0 | 5 | 9 | 9 | 23m | `runs/aud-006-openhands-software-agent-sdk-a-gent-server/20261027T171025Z` |
| `aud-099-litellm` | 32 | 0 | 4 | 13 | 15 | 62m | `runs/aud-099-litellm/20261027T192738Z` |
| `aud-005-opencode` | 25 | 0 | 4 | 13 | 8 | 56m | `runs/aud-005-opencode/20261027T181038Z` |
| `aud-046-agentscope-runtime` | 26 | 0 | 3 | 12 | 11 | 23m | `runs/aud-046-agentscope-runtime/20261027T171026Z` |
| `aud-024-deep-agents` | 19 | 0 | 3 | 8 | 8 | 53m | `runs/aud-024-deep-agents/20261027T181038Z` |
| `aud-003-gemini-cli` | 24 | 0 | 2 | 15 | 7 | 35m | `runs/aud-003-gemini-cli/20261027T181038Z` |
| `aud-097-vllm-ascend` | 16 | 0 | 2 | 7 | 7 | 25m | `runs/aud-097-vllm-ascend/20261027T174447Z` |
| `aud-078-ollama` | 15 | 0 | 2 | 4 | 9 | 25m | `runs/aud-078-ollama/20261027T173302Z` |
| `aud-079-text-embeddings-inference` | 15 | 0 | 1 | 6 | 8 | 20m | `runs/aud-079-text-embeddings-inference/20261027T173343Z` |
| `aud-119-tensorizer` | 10 | 0 | 1 | 4 | 4 | 7m | `runs/aud-119-tensorizer/20261027T174633Z` |
| `aud-047-anthropic-sandbox-runtime` | 5 | 0 | 1 | 3 | 1 | 34m | `runs/aud-047-anthropic-sandbox-runtime/20261027T171026Z` |
| `aud-055-fastmcp` | 18 | 0 | 0 | 4 | 14 | 38m | `runs/aud-055-fastmcp/20261027T185543Z` |
| `aud-056-ibm-contextforge` | 13 | 0 | 0 | 4 | 9 | 24m | `runs/aud-056-ibm-contextforge/20261027T190335Z` |
| `aud-007-pi` | 10 | 0 | 0 | 5 | 5 | 36m | `runs/aud-007-pi/20261027T171026Z` |

已有报告复用：`codex` / `vllm` / `sglang`（当前 commit 与 catalog 一致），未重复跑。

## 重点 Critical / High

1. **HIGH · aud-001-cline · DEEPLINK-001** — Unauthenticated vscode:// LG-task deep link reads arbitrary local files, installs executable hooks, and overwrites the webhook config; /auth lacks state validation
   - CWE: `CWE-939`
   - Evidence: `apps/vscode/src/services/uri/SharedUriHandler.ts:98; apps/vscode/src/services/uri/SharedUriHandler.ts:63`
2. **HIGH · aud-001-cline · FILE-READ-001** — read_files/read_file accept arbitrary absolute paths with no workspace containment
   - CWE: `CWE-22 / CWE-200`
   - Evidence: `sdk/packages/core/src/extensions/tools/executors/file-read.ts:231; sdk/packages/core/src/extensions/tools/executors/file-read.ts:242`
3. **HIGH · aud-001-cline · FILE-WRITE-001** — editor/apply_patch write, delete and move arbitrary absolute paths; restrictToCwd only gates relative inputs and symlinks are unresolved
   - CWE: `CWE-22 / CWE-73`
   - Evidence: `sdk/packages/core/src/extensions/tools/executors/editor.ts:55; sdk/packages/core/src/extensions/tools/executors/editor.ts:146`
4. **HIGH · aud-001-cline · HUB-TUNNEL-001** — ROOM_SECRET enforced only for non-loopback HOST, so a loopback bind published through a public tunnel can be unauthenticated
   - CWE: `CWE-306`
   - Evidence: `apps/cline-hub/src/options.ts:79; apps/cline-hub/src/options.ts:30`
5. **HIGH · aud-001-cline · SIDECAR-AUTH-001** — Desktop sidecar treats Origin-less clients as trusted and leaves powerful commands ungated (chat, MCP upsert, git/editor, shutdown)
   - CWE: `CWE-306`
   - Evidence: `apps/examples/desktop-app/sidecar/server.ts:71; apps/examples/desktop-app/sidecar/server.ts:241`
6. **HIGH · aud-001-cline · TAURI-RENDERER-001** — Tauri webview has no CSP and exposes an unrestricted interactive PTY shell (renderer script execution -> native RCE)
   - CWE: `CWE-78 / CWE-693`
   - Evidence: `apps/examples/desktop-app/src-tauri/src/terminal.rs:177; apps/examples/desktop-app/src-tauri/src/terminal.rs:71`
7. **HIGH · aud-001-cline · WS-TRUST-001** — No workspace-trust gate: repo-controlled hooks and plugins execute code by default when a task runs
   - CWE: `CWE-829`
   - Evidence: `sdk/packages/shared/src/session/runtime-config.ts:19; apps/cli/src/runtime/run-agent.ts:306`
8. **HIGH · aud-003-gemini-cli · MCP-AGENT-TRUST-BYPASS** — Extension agents can declare MCP servers that bypass extension MCP trust-stripping and are not disclosed in install consent
   - CWE: `CWE-862`
   - Evidence: `packages/cli/src/config/extension-manager.ts:868; packages/cli/src/config/extension-manager.ts:950`
9. **HIGH · aud-003-gemini-cli · MCP-OAUTH-NAME-CONFUSION** — Stored MCP OAuth tokens are selected by server name only, not by endpoint URL
   - CWE: `CWE-522`
   - Evidence: `packages/core/src/tools/mcp-client.ts:2343; packages/core/src/mcp/oauth-token-storage.ts:181`
10. **HIGH · aud-005-opencode · OC-001** — Well-known remote config is parsed as full Config.Info, allowing plugin/local-MCP/skill/instruction injection outside the ConfigIntegration.Remote allowlist
   - CWE: ``
   - Evidence: `config.ts:174-197 loads each well-known entry, substitutes the returned config body, then calls parseInfo(text, entry.origin) which decodes the full Config.Info schema. Config.Info includes plugins, mcp, instructions and skills (packages/sc`
11. **HIGH · aud-005-opencode · OC-002** — Well-known/remote config resolves {env:} and {file:} substitutions from the local process, sending secrets and file contents to remote origins via MCP/remote_config URLs and headers
   - CWE: ``
   - Evidence: `wellknown.ts:87-88 substitutes only {env:NAME} into manifest.remote_config.url/headers using variables[name] ?? process.env[name], then issues the GET with those headers (wellknown.ts:89-100). Separately, config.ts:190-197 passes the return`
12. **HIGH · aud-005-opencode · OC-003** — worktree_create accepts an unvalidated name; path.join lets '..' escape the configured worktree base and the project setup command runs in the escaped directory
   - CWE: ``
   - Evidence: `WorktreeCreateInput is Schema.Trim.check(Schema.isNonEmpty()) only (opencode.ts:31); the tool calls ctx.worktree.create({name}) at opencode.ts:162. The HTTP CreateInput accepts optional(Schema.String) for name and an optional arbitrary Abso`
13. **HIGH · aud-005-opencode · OC-004** — Desktop FilesOpenPath/FilesOpenLocalFile pass a caller-supplied path and application to shell.openPath/execFile/spawn with no allowlist or caller validation
   - CWE: ``
   - Evidence: `FilesOpenPath RPC payload is {path: String, application?: String} (shared/ipc-rpc/files.ts:66) and the handler calls files.openPath(path, application) (ipc-handlers/files.ts:31). DesktopFiles.openPath runs shell.openPath when no application`
14. **HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · FS-001** — Top-level /api/file and /api/git endpoints accept arbitrary absolute host paths with no workspace confinement
   - CWE: ``
   - Evidence: `file_router.py:84-106 _upload_file
    target_path = Path(path)
    if not target_path.is_absolute(): raise HTTPException(400)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "wb") as f: ...
file_router.`
15. **HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · HTTP-001** — WebSocket handlers validate neither Origin nor any credential when no session key is configured, enabling cross-site WebSocket hijacking to bash execution
   - CWE: ``
   - Evidence: `sockets.py:142-155 (_accept_authenticated_websocket)
    config = _get_config(websocket)
    resolved_key = _resolve_websocket_session_api_key(websocket, session_api_key)
    # No auth configured - accept unconditionally.
    if not config.`
16. **HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · HTTP-002** — Session-key auth is fail-open when no keys are configured and a wildcard bind without a key is only a warning; the shipped SandboxTemplate uses exactly that shape
   - CWE: ``
   - Evidence: `dependencies.py:38
    if config.session_api_keys and session_api_key not in config.session_api_keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

__main__.py:305-316
    auth_enabled = _auth_enabled()
    if host is None:
   `
17. **HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · HTTP-003** — POST /api/init is unauthenticated when a deferred-init (warm-pool) server has no secret_key, allowing unauthenticated takeover and process-environment injection
   - CWE: ``
   - Evidence: `init_router.py:403-413
    config: Config | None = getattr(request.app.state, "config", None)
    if config is None or config.secret_key is None:
        if config is not None and config.secret_key_was_blank:
            raise HTTPException`
18. **HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · SEC-001** — Workspace project plugins auto-load and execute hooks (shell=True) and MCP stdio commands at conversation start with no opt-in
   - CWE: ``
   - Evidence: `local_conversation.py:1152-1159
            ambient_plugins = load_available_plugins(
                work_dir=self.workspace.working_dir,
                include_user=True,
                include_project=True,
            )

local_convers`
19. **HIGH · aud-024-deep-agents · EXEC-001** — Model-controlled tool arguments reach an unrestricted host shell (LocalShellBackend.execute shell=True) with the full active environment
   - CWE: `CWE-78`
   - Evidence: `libs/deepagents/deepagents/backends/local_shell.py:304; libs/deepagents/deepagents/backends/local_shell.py:202`
20. **HIGH · aud-024-deep-agents · SBX-001** — Local mode disables virtual path containment and does not HITL-gate read/ls/grep/glob, enabling arbitrary host file read via prompt injection
   - CWE: `CWE-22`
   - Evidence: `libs/code/deepagents_code/agent.py:3173; libs/code/deepagents_code/agent.py:3179`
21. **HIGH · aud-024-deep-agents · INFRA-CFG-001** — Default project .env auto-load lets a cloned repository redirect model endpoints, HTTP proxies/TLS trust roots, and LangSmith trace uploads
   - CWE: `CWE-15`
   - Evidence: `libs/code/deepagents_code/config.py:783; libs/code/deepagents_code/config.py:735`
22. **HIGH · aud-046-agentscope-runtime · INFRA-001** — Unauthenticated /shutdown and /admin/shutdown let any network client kill the agent service
   - CWE: `['CWE-306', 'CWE-352', 'CWE-400']`
   - Evidence: `src/agentscope_runtime/engine/app/agent_app.py:610-635; src/agentscope_runtime/engine/app/agent_app.py:424`
23. **HIGH · aud-046-agentscope-runtime · INFRA-LCP-001** — Sandbox manager control-plane authentication fails open when BEARER_TOKEN is unset (default), exposing create/call_tool/get_info
   - CWE: `['CWE-306', 'CWE-1188', 'CWE-200']`
   - Evidence: `src/agentscope_runtime/sandbox/manager/server/app.py:121-124; src/agentscope_runtime/sandbox/manager/server/config.py:15,19`
24. **HIGH · aud-046-agentscope-runtime · INFRA-LCP-003** — Training-box env_service exposes /create /step /evaluate /release on 0.0.0.0 with no authentication, and /step reaches code execution
   - CWE: `['CWE-306', 'CWE-94', 'CWE-78']`
   - Evidence: `src/agentscope_runtime/sandbox/box/training_box/env_service.py:472; src/agentscope_runtime/sandbox/box/training_box/env_service.py:733-737`
25. **HIGH · aud-047-anthropic-sandbox-runtime · VULN-001** — Masked-credential sentinel is injectable at every allowed host (default injectHosts)
   - CWE: `['CWE-522']`
   - Evidence: `src/sandbox/credential-mask-env.ts:103; src/sandbox/credential-mask-files.ts:228`
26. **CRIT · aud-048-opensandbox · EXECD-001** — preInitPaths contains /internal/init (router.go:37-41) and accessTokenMiddleware returns early for preInit paths (router.go:198-201); runtimeInitGate is a no-op unless --runtime-init is set (router.go:271-273), so the endpoint is live in classic mode too. InitController.Init parses the body and calls manager.Apply with no authentication, origin, peer-IP, loopback or first-caller restriction (init_runtime.go:175-199). Apply accepts req.AccessTokenHash and installs it into the new binding (init_runtime.go:210-218, 298-316); accessTokenMiddleware then treats the binding hash as authoritative (router.go:209-216), so the attacker-chosen token becomes the only accepted credential (lockout of the control plane plus full API access for the attacker). With preserveRuntimeState=false Apply sets ready=false, resets controllers/sessions, stops user processes and can restart the entrypoint (init_runtime.go:229-292). lifecycle.preStart is executed via exec.Command(hook.Command[0], hook.Command[1:]...) (lifecycle/runner.go:43,64-79). validateInitEnvs only blocks a small case-insensitive execd env blacklist, so arbitrary env vars can be injected into subsequently spawned workloads. No server-side caller of /internal/init or EXECD token provisioning exists under server/opensandbox_server/services/*; the design relies entirely on network isolation of 44772, which the Docker runtime does not enforce by default.
   - CWE: `CWE-306`
   - Evidence: `components/execd/main.go:238-239`
27. **HIGH · aud-048-opensandbox · EXECD-002** — accessTokenMiddleware checks the binding first, then the legacy token; when no binding hash and legacyToken=='' it calls ctx.Next() unconditionally (router.go:224-227). parser.go defaults ServerAccessToken to '' and only overrides from EXECD_ACCESS_TOKEN/--access-token (parser.go:40-42,62-64). _build_labels_and_env adds EXECD_INIT and OPENSANDBOX_ID but never EXECD_ACCESS_TOKEN (container_ops.py:286-320), and no server-side init/token provisioning was found, so a normal Docker sandbox runs with the empty token. Networking publishes 44772 to (publish_host, host_execd_port) with publish_host default 0.0.0.0 (networking.py:549-553, config.py:1386-1397). Anyone reaching the published host port gets unauthenticated command execution, arbitrary sandbox file read/write and PTY access, bypassing the API-key-protected proxy entirely.
   - CWE: `CWE-306`
   - Evidence: `components/execd/pkg/flag/parser.go:40-42`
28. **HIGH · aud-048-opensandbox · SERVER-001** — AuthMiddleware.dispatch returns call_next() for any path matching _PROXY_PATH_RE whenever the app is not multi-tenant, before the valid_api_keys check (auth.py:82-87); configuring server.api_key therefore does not protect proxy routes in single-tenant mode. The only compensation, _verify_secure_access, returns immediately when the resolved endpoint carries no OpenSandbox-Secure-Access header (proxy.py:336-365). Docker rejects secureAccess=request with 400 and the default ingress mode is direct with secure_access=None; on K8s, create_helpers.py writes the secure-access token only when request.secure_access is true (create_helpers.py:76-79) - it does not additionally require ingress.mode=gateway. WebSocket proxy is doubly exposed: BaseHTTPMiddleware does not see WS, and _authenticate_websocket_tenant returns True when tenant_provider is None (proxy.py:267-269). Tests assert the HTTP bypass is intentional. CORRECTION: analyst cited proxy.py:275-276 for the WS return; actual lines are 267-269, and the 'AND ingress.mode=gateway' condition in the analyst narrative is not present in create_helpers.py.
   - CWE: `CWE-306`
   - Evidence: `server/opensandbox_server/middleware/auth.py:82-83`
29. **HIGH · aud-048-opensandbox · SERVER-002** — extensions is an arbitrary user-controlled dict; validate_extensions only validates the deprecated access.renew key and has no allowlist (validation.py:127-141), so bootstrap.execd.isolation reaches sandbox creation. docker_service.py:938-958 sets isolation_requested from the extension, adds SYS_ADMIN, strips existing apparmor/seccomp options, appends unconfined profiles, and unconfine_system_paths clears MaskedPaths/ReadonlyPaths (container_ops.py:463-465). provider_common.py:205-215 applies the equivalent SYS_ADMIN + Unconfined context on K8s. This weakens the cap_drop/no-new-privileges/seccomp/AppArmor defaults intended to contain sandbox workloads.
   - CWE: `CWE-269`
   - Evidence: `server/opensandbox_server/services/docker/docker_service.py:937-958`
30. **HIGH · aud-048-opensandbox · INGRESS-001** — Secure access is opt-in: the annotation is written only when request.secure_access is true (create_helpers.py:76-79), and CheckIngressSecureAccess returns nil immediately when the resolved endpoint advertises no token (ingress_access.go:77-80, endpoint.go:45-47). Legacy two-segment host/URI routes are accepted unconditionally (host.go:110-123, host_route_parse.go:49-74). Providers watch NamespaceAll (batchsandbox_provider.go:54) and match by name across every namespace, erroring only on duplicate names (89-131); the verifier is built only when --secure-access-keys is set (main.go:69-78). Result: any reachable caller who knows an unsecured sandbox UUID can proxy arbitrary HTTP/WebSocket traffic to it regardless of tenant boundary.
   - CWE: `CWE-306`
   - Evidence: `components/ingress/pkg/proxy/host.go:97`

## 观察

- 最高风险集中在：控制面鉴权 fail-open、绝对路径读写、MCP/OAuth 信任边界、项目配置/插件自动执行。
- `aud-048-opensandbox` 是目前唯一 Critical：`preInitPaths` 中的 `/internal/init` 被 `accessTokenMiddleware` 提前放行。
- `aud-001-cline`、`aud-080-xinference` 各 7 条 High，是本批最值得优先人工复核的两个项目。
- `aud-055-fastmcp`、`aud-056-ibm-contextforge`、`aud-007-pi` 本批无 High，但不代表无风险，需看 Medium/Low。
- UI 中总计 955 findings 包含历史 5 个项目；本批新增是 354。

## 查看

```bash
# 单项目报告
runs/aud-001-cline/20261027T181038Z/audit-report.md

# UI
bash scripts/ui/start.sh
# http://127.0.0.1:8787
```
