# Batch 1 复核筛选：先看有源码证据的，不把 unverified 当真实漏洞

- 生成时间：2026-10-27
- 总 findings：354

## 高/严重分类

- Critical/High：54
- 源码级已确认：5
- 源码链成立但运行时 blocked：6
- 阻塞/不确定：7
- 尚无验证：36

## A. 源码级已确认（仍需运行时/条件复核）

- **HIGH · aud-046-agentscope-runtime · INFRA-001** — Unauthenticated /shutdown and /admin/shutdown let any network client kill the agent service
  -  confirmed   
- **HIGH · aud-046-agentscope-runtime · INFRA-LCP-001** — Sandbox manager control-plane authentication fails open when BEARER_TOKEN is unset (default), exposing create/call_tool/get_info
  -  confirmed   
- **HIGH · aud-046-agentscope-runtime · INFRA-LCP-003** — Training-box env_service exposes /create /step /evaluate /release on 0.0.0.0 with no authentication, and /step reaches code execution
  -  confirmed   
- **HIGH · aud-097-vllm-ascend · HA-003** — Example load-balance proxy exposes unauthenticated /instances/add, allowing SSRF and exfiltration of OPENAI_API_KEY to arbitrary backends
  - In-repo chain confirmed statically: unauthenticated /instances/add adopts arbitrary host:port, NodeListener probes it with Authorization: Bearer $OPENAI_API_KEY. Example-only script.    ['Example-only script; not package code. Dynamic HTTP/SSRF not executed (no docker).', 'Impact requires the proxy to be reachable and OPENAI_API_KEY to be set.']
- **HIGH · aud-097-vllm-ascend · IPC-001** — Unauthenticated netloader ElasticServer streams full model weights to any reachable JOIN peer and discloses server identity
  - In-repo chain confirmed statically (no runtime): unauthenticated bind/listen, key-presence-only JOIN validation, NACK descriptor leak, and P2PSend to peer-derived host + attacker port streaming the model. Reachability opt-in.    ['Dynamic end-to-end weight transfer not executed: no Ascend NPU / HCCL runtime and docker unavailable.', 'Reachability is opt-in (
- **MEDIUM · aud-097-vllm-ascend · CFG-003** — rl_config.enabled silently sets VLLM_SERVER_DEV_MODE=1, enabling upstream vLLM developer endpoints as a side effect
  - In-repo fact confirmed statically: RlConfig.apply sets VLLM_SERVER_DEV_MODE=1 unconditionally when rl_config.enabled, with no separate dev-mode opt-in. Upstream dev-route mapping is out of repo/unverified.    ['Static code fact confirmed; upstream vLLM mapping of VLLM_SERVER_DEV_MODE to unauthenticated developer routes is out of repo and unverified.', 'Requi
- **MEDIUM · aud-097-vllm-ascend · HA-001** — RFork seed HTTP service binds 0.0.0.0 by default and authenticates with a deterministic (non-secret) seed_key used as an identifier, disclosing TransferEngine session_id and weight pointer manifest
  - In-repo chain confirmed statically: seed service defaults to 0.0.0.0 bind, seed_key is deterministic SHA-256 over public descriptor, matching key returns TransferEngine session_id + weight manifest, key logged at INFO. Data-plane RDMA read is out of repo/unverified.    ['Dynamic HTTP request not executed; no docker/NPU runtime available.', 'Data-plane arbitr
- **MEDIUM · aud-097-vllm-ascend · IPC-003** — KV-transfer ZMQ ROUTER side channels bind a routable host IP with no authentication; peer frames drive metadata disclosure and unbounded allocation
  - In-repo chain confirmed statically: side channel binds get_ip() ROUTER, recv_multipart with no size cap, unauthenticated GET_META_MSG returns metadata, port_send_num grows unbounded. Requires KV-transfer connector enabled.    ['Dynamic ZMQ interaction not executed; no docker/NPU runtime available.', 'Requires a KV-transfer connector enabled (PD disaggregatio
- **MEDIUM · aud-097-vllm-ascend · IPC-004** — Unauthenticated netloader JOIN kills the sole handler thread (uncaught int() ValueError) and untimed recv stalls the accept loop
  - In-repo chain confirmed statically: single daemon handler thread with no try/except around register_handler; numeric casts can raise ValueError and kill the sole accept/handle thread; accepted conn has no timeout. Reachability opt-in.    ['Dynamic DoS not executed (would require running the out-of-repo netloader server with torch/NPU).', 'Opt-in netloader su

## B. 源码链成立、运行时 blocked（优先人工复核）

- **HIGH · aud-005-opencode · OC-001** — Well-known remote config is parsed as full Config.Info, allowing plugin/local-MCP/skill/instruction injection outside the ConfigIntegration.Remote allowlist
  - Static chain holds: the well-known/remote config body is substituted then decoded with the full Config.Info (config.ts:174,190,197), whose schema includes plugins/mcp/instructions/skills; the ConfigIntegration.Remote allowlist is used only for connection documents (provider/opencode.ts), not well-known documents; plugin dynamic import and local MCP child spa
- **HIGH · aud-005-opencode · OC-002** — Well-known/remote config resolves {env:} and {file:} substitutions from the local process, sending secrets and file contents to remote origins via MCP/remote_config URLs and headers
  - Static chain holds: {env:} in the manifest remote_config.url/headers is substituted from process.env and sent to the attacker-chosen URL (wellknown.ts:87-95); the origin-returned config body is passed through ConfigVariable.substitute, which also expands {file:} with arbitrary absolute-path reads (config.ts:190; variable.ts:29,61-65); values placed in mcp ur
- **HIGH · aud-005-opencode · OC-003** — worktree_create accepts an unvalidated name; path.join lets '..' escape the configured worktree base and the project setup command runs in the escaped directory
  - Static chain holds: worktree_create name is only Trim+isNonEmpty (opencode.ts:31-33) and Worktree.CreateInput.name is unvalidated (schema/worktree.ts:19); path.join(directory, name) at worktree.ts:213 collapses '..' and escapes the base; git worktree add accepts out-of-repo targets (git.ts:1326; benign local reproduction with node 20/git 2.47 succeeded); can
- **HIGH · aud-024-deep-agents · EXEC-001** — Model-controlled tool arguments reach an unrestricted host shell (LocalShellBackend.execute shell=True) with the full active environment
  -  Source-level chain is present and matches the finding: model-controlled `command` reaches subprocess.run(shell=True, env=shell_env) with a full copy of the active environment. However, runtime verification is impossible in this snapshot, so status is blocked, not confirmed. Note: default MANUAL mode gates `execute` via interrupt_map; unapproved execution re
- **HIGH · aud-024-deep-agents · INFRA-CFG-001** — Default project .env auto-load lets a cloned repository redirect model endpoints, HTTP proxies/TLS trust roots, and LangSmith trace uploads
  -  Source-level behavior matches the finding: the project .env is discovered upward and loaded by default, and the denylists do not enumerate proxy/TLS/base-URL/LangSmith endpoint keys, while model_config resolves base URLs from the active environment. Runtime verification is impossible because the implementing modules do not parse and dependencies are absent,
- **HIGH · aud-024-deep-agents · SBX-001** — Local mode disables virtual path containment and does not HITL-gate read/ls/grep/glob, enabling arbitrary host file read via prompt injection
  -  Source-level chain matches the finding: with virtual_mode=False, _resolve_path returns absolute keys verbatim, read_file/ls/grep/glob are absent from interrupt_map, and default permissions are empty, so an injected absolute path would be read from the host. Runtime verification is impossible in this snapshot, so status is blocked. Exfiltration still require
- **MEDIUM · aud-079-text-embeddings-inference · TEI-04** — Legacy pytorch_model.bin fallback can deserialize repo-supplied pickle (Python-backend images only)
  - Code chain is statically present (pytorch_model.bin fallback -> Python child spawn -> transformers from_pretrained), but runtime reproduction is impossible: no cargo, docker, torch or transformers in the verify environment. Final exploitability also depends on unverified external torch/transformers semantics, and the shipped Python images use torch >= 2.6 / 

## C. 阻塞/不确定

- **HIGH · aud-005-opencode · OC-004** — Desktop FilesOpenPath/FilesOpenLocalFile pass a caller-supplied path and application to shell.openPath/execFile/spawn with no allowlist or caller validation
  - The sink chain is real: FilesOpenPath allows a free-form path + optional application with no allowlist, and the file handlers perform no caller-window/origin check (unlike PluginRpcs), so openPath reaches shell.openPath or execFile(application,[target]) and openLocalFileURL opens any file: URL via shell.openPath. However, attacker control is not established:
- **HIGH · aud-060-llama-cpp · VULN-002** — When --tools/--agent/MCP is enabled, unauthenticated POST /tools executes arbitrary shell commands and reads/writes arbitrary files
  - no build toolchain / container runtime / network in audit container    ['audit container: cmake/gcc/g++/clang++/make/docker/podman all MISSING', 'no network access', 'scripts/verify/run_verify.sh and env manifest not present in workspace']
- **HIGH · aud-060-llama-cpp · VULN-008** — Unauthenticated GET /props (and router /props) discloses model path, chat templates, build info and, with --connect, the tunnel connect_code
  - no build toolchain / container runtime / network in audit container    ['audit container: cmake/gcc/g++/clang++/make/docker/podman all MISSING', 'no network access', 'no real connect tunnel may be exercised; only placeholder code against a loopback dummy']
- **HIGH · aud-060-llama-cpp · VULN-012** — Unauthenticated RPC server trusts client-supplied op/op_params, exposing GGML_OP_CUSTOM function-pointer calls -> remote code execution
  - no build toolchain / container runtime / network in audit container    ['audit container: cmake/gcc/g++/clang++/make/docker/podman all MISSING', 'no network access', 'GGML_OP_CUSTOM struct layout depends on a real compiled binary; cannot be emulated in pure Python']
- **HIGH · aud-060-llama-cpp · VULN-021** — Conversion scripts use AutoTokenizer(trust_remote_code=True) for several architectures, executing arbitrary Python from a model repo
  - no build toolchain / container runtime / network in audit container    ['python3 present but transformers/torch/numpy MISSING', 'no network access to install dependencies', 'audit container: cmake/gcc/g++/clang++/make/docker/podman all MISSING']
- **HIGH · aud-060-llama-cpp · VULN-022** — convert_legacy_llama.py LazyUnpickler allows unrelated globals for non-torch modules, giving pickle RCE on untrusted legacy checkpoints
  - no build toolchain / container runtime / network in audit container    ['python3 present but torch/numpy MISSING', 'no network access to install dependencies', 'no isolated container runtime available to safely deserialize fixtures']
- **HIGH · aud-079-text-embeddings-inference · TEI-05** — TRUST_REMOTE_CODE=true executes arbitrary Python code from the model repository
  - Static verification confirms the vulnerable code path exists: TRUST_REMOTE_CODE (default false) flows into transformers AutoConfig/AutoModel*.from_pretrained(trust_remote_code=...), which executes model-provided Python. Runtime reproduction is impossible in this environment (no cargo, docker, torch or transformers), so the verdict is blocked on runtime; the 

## D. 尚未验证的高/严重

这些不能当真实漏洞，也不能直接进人工研判优先队列；需要第 2/3 轮一致性或 verify-agent。

- CRITICAL · aud-048-opensandbox · EXECD-001 — preInitPaths contains /internal/init (router.go:37-41) and accessTokenMiddleware returns early for preInit paths (router.go:198-201); runtimeInitGate is a no-op unless --runtime-init is set (router.go:271-273), so the en
- HIGH · aud-001-cline · DEEPLINK-001 — Unauthenticated vscode:// LG-task deep link reads arbitrary local files, installs executable hooks, and overwrites the webhook config; /auth lacks state validation
- HIGH · aud-001-cline · FILE-READ-001 — read_files/read_file accept arbitrary absolute paths with no workspace containment
- HIGH · aud-001-cline · FILE-WRITE-001 — editor/apply_patch write, delete and move arbitrary absolute paths; restrictToCwd only gates relative inputs and symlinks are unresolved
- HIGH · aud-001-cline · HUB-TUNNEL-001 — ROOM_SECRET enforced only for non-loopback HOST, so a loopback bind published through a public tunnel can be unauthenticated
- HIGH · aud-001-cline · SIDECAR-AUTH-001 — Desktop sidecar treats Origin-less clients as trusted and leaves powerful commands ungated (chat, MCP upsert, git/editor, shutdown)
- HIGH · aud-001-cline · TAURI-RENDERER-001 — Tauri webview has no CSP and exposes an unrestricted interactive PTY shell (renderer script execution -> native RCE)
- HIGH · aud-001-cline · WS-TRUST-001 — No workspace-trust gate: repo-controlled hooks and plugins execute code by default when a task runs
- HIGH · aud-003-gemini-cli · MCP-AGENT-TRUST-BYPASS — Extension agents can declare MCP servers that bypass extension MCP trust-stripping and are not disclosed in install consent
- HIGH · aud-003-gemini-cli · MCP-OAUTH-NAME-CONFUSION — Stored MCP OAuth tokens are selected by server name only, not by endpoint URL
- HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · FS-001 — Top-level /api/file and /api/git endpoints accept arbitrary absolute host paths with no workspace confinement
- HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · HTTP-001 — WebSocket handlers validate neither Origin nor any credential when no session key is configured, enabling cross-site WebSocket hijacking to bash execution
- HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · HTTP-002 — Session-key auth is fail-open when no keys are configured and a wildcard bind without a key is only a warning; the shipped SandboxTemplate uses exactly that shape
- HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · HTTP-003 — POST /api/init is unauthenticated when a deferred-init (warm-pool) server has no secret_key, allowing unauthenticated takeover and process-environment injection
- HIGH · aud-006-openhands-software-agent-sdk-a-gent-server · SEC-001 — Workspace project plugins auto-load and execute hooks (shell=True) and MCP stdio commands at conversation start with no opt-in
- HIGH · aud-047-anthropic-sandbox-runtime · VULN-001 — Masked-credential sentinel is injectable at every allowed host (default injectHosts)
- HIGH · aud-048-opensandbox · EXECD-002 — accessTokenMiddleware checks the binding first, then the legacy token; when no binding hash and legacyToken=='' it calls ctx.Next() unconditionally (router.go:224-227). parser.go defaults ServerAccessToken to '' and only
- HIGH · aud-048-opensandbox · INGRESS-001 — Secure access is opt-in: the annotation is written only when request.secure_access is true (create_helpers.py:76-79), and CheckIngressSecureAccess returns nil immediately when the resolved endpoint advertises no token (i
- HIGH · aud-048-opensandbox · K8S-001 — NewRouter registers POST /setTasks, POST /tasks, GET/DELETE /tasks/{id} and GET /health with no auth middleware (router.go:21-32). createTask/syncTasks decode an attacker-controlled JSON body requiring only a non-empty N
- HIGH · aud-048-opensandbox · K8S-002 — CreatePoolRequest.template is a raw Dict with no field filtering (schema.py:1549-1555); _get_pool_service resolves the global config namespace and the route calls create_pool with no validation (pool.py:46-106); _build_p
- HIGH · aud-048-opensandbox · SERVER-001 — AuthMiddleware.dispatch returns call_next() for any path matching _PROXY_PATH_RE whenever the app is not multi-tenant, before the valid_api_keys check (auth.py:82-87); configuring server.api_key therefore does not protec
- HIGH · aud-048-opensandbox · SERVER-002 — extensions is an arbitrary user-controlled dict; validate_extensions only validates the deprecated access.renew key and has no allowlist (validation.py:127-141), so bootstrap.execd.isolation reaches sandbox creation. doc
- HIGH · aud-078-ollama · OLLAMA-001 — No inbound authentication on the HTTP control plane; OLLAMA_AUTH is client-side only and Host validation is skipped on non-loopback binds
- HIGH · aud-078-ollama · OLLAMA-003 — Unauthenticated /api/pull and /api/push dial an attacker-chosen registry host with no egress/IP filter
- HIGH · aud-080-xinference · CTRL-001 — Unauthenticated xoscar actor transport in distributed mode exposes actor RPC and a cloudpickle deserialization sink
- HIGH · aud-080-xinference · CTRL-002 — Client-supplied absolute python_executable is spawned without an allowlist (relaunch and model reload)
- HIGH · aud-080-xinference · MODEL-001 — dots.ocr loader hardcodes trust_remote_code=True, bypassing the operational trust gate
- HIGH · aud-080-xinference · MODEL-002 — Trust gate keys on model-family provenance, not model_path provenance: built-in family + caller model_path executes model-repository code
- HIGH · aud-080-xinference · MODEL-003 — Caller-supplied virtual_env_packages and envs reach package installation and the model subprocess environment without an allowlist
- HIGH · aud-080-xinference · MODEL-005 — Audio/TTS loaders torch.load model-supplied checkpoints with weights_only disabled
- HIGH · aud-080-xinference · SSRF-001 — Embeddings and rerank endpoints fetch client-supplied media URLs/paths without the media guard (SSRF + local file read)
- HIGH · aud-099-litellm · LITELLM-001 — allow_requests_on_db_unavailable fails open: any non-empty bearer is authenticated as INTERNAL_USER with all-model access during a DB connection error
- HIGH · aud-099-litellm · LITELLM-002 — Harness LocalSandbox executes model-generated shell as an unisolated host subprocess, and SessionContext defaults permissions='full' (no approval)
- HIGH · aud-099-litellm · LITELLM-003 — /customer/info has no inline tenant check; an ORG_ADMIN can read any organization's end-user record via a caller-supplied organization_id
- HIGH · aud-099-litellm · LITELLM-004 — /audit and /audit/{id} are unscoped global reads reachable by an ORG_ADMIN through its own organization_id
- HIGH · aud-119-tensorizer · TENS-001 — Unsafe path/URI dispatch in open_stream enables SSRF, arbitrary local file read and arbitrary file write

## 结论

- 先人工研判 A/B；C 需要环境；D 先等一致性/验证，不直接送人。
- source-confirmed 仍是静态语义证据，不等于运行时确认；source-supported 是“代码链成立但没跑起来”。
