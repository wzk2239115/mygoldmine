# RSI 多轮一致性结果

- 生成时间：2026-10-28T09:09:17.709250+00:00
- 最少轮次：2
- 只列出在多个独立 run 中重复出现的高/严重 finding；单轮 finding 不进入人工研判优先队列。

## aud-001-cline

- runs: 3
- findings: 81
- 稳定簇：13（High/Critical 6）

1. **HIGH · 3/3 轮** — Configured-agent tool allowlist maps benign/read-only legacy names to privileged tools (list_files -> run_commands), so a repository agent config that looks read-only silently receives shell execution
   - CWE: `CWE-1188, CWE-269, CWE-862`
   - Evidence: `agents/src/agent-runtime.ts; apps/cli/readme.md; cli/src/main.ts`
   - IDs: AUTOAPPROVE-001, CLINE-001, CLINE-003, F-03, F-25
2. **HIGH · 3/3 轮** — Desktop example sidecar WebSocket accepts originless clients and grants all non-approval commands; optional 0.0.0.0 bind widens exposure
   - CWE: `/, CWE-1021, CWE-306, CWE-532, CWE-693, CWE-78`
   - Evidence: `components/ui/markdown.tsx; desktop-app/sidecar/commands.ts; desktop-app/sidecar/server.ts`
   - IDs: TAURI-RENDERER-001, CLINE-021, F-10, F-11, F-19, F-20
3. **HIGH · 3/3 轮** — Unauthenticated hub public routes (/health, /config.json) leak hub address and client PIDs/versions, readable cross-origin via DNS rebinding
   - CWE: `CWE-200, CWE-306, CWE-532`
   - Evidence: `apps/cline-hub/readme.md; cline-hub/src/options.ts; cline-hub/src/server.ts`
   - IDs: HUB-TUNNEL-001, HUB-PUBLIC-ROUTES-001, CLINE-020, CLINE-028, F-14
4. **HIGH · 3/3 轮** — Workspace .clinerules/hooks and .cline/hooks scripts auto-execute on agent/session start and task events with no workspace-trust confirmation
   - CWE: `CWE-78, CWE-829, CWE-94`
   - Evidence: `core/hooks/hook-factory.ts; core/hooks/hookprocess.ts; core/hooks/hooks-utils.ts`
   - IDs: WS-TRUST-001, CLINE-010, CLINE-011, F-01, F-02, F-08
5. **HIGH · 3/3 轮** — fetch_web_content is auto-approved and performs SSRF-capable fetches with no loopback/private/metadata blocking and follows redirects
   - CWE: `CWE-918`
   - Evidence: `cli/src/main.ts; extensions/tools/definitions.ts; extensions/tools/presets.ts`
   - IDs: SSRF-WEBFETCH-001, CLINE-014, F-04
6. **HIGH · 2/3 轮** — editor/apply_patch write, delete and move arbitrary absolute paths; restrictToCwd only gates relative inputs and symlinks are unresolved
   - CWE: `/, CWE-200, CWE-22, CWE-73`
   - Evidence: `extensions/tools/definitions.ts; src/sdk/sdk-tool-policies.ts; src/shared/autoapprovalsettings.ts`
   - IDs: FILE-READ-001, FILE-WRITE-001, CLINE-013

## aud-006-openhands-software-agent-sdk-a-gent-server

- runs: 3
- findings: 55
- 稳定簇：10（High/Critical 5）

1. **CRITICAL · 3/3 轮** — Repository/plugin-controlled SKILL.md inline !`cmd` executes via invoke_skill with shell=True and the full inherited environment (no sanitized_env) (merged CFG-003/EXEC-002)
   - CWE: `CWE-200, CWE-522, CWE-78, CWE-829, CWE-918, CWE-94`
   - Evidence: `conversation/impl/local_conversation.py; local_conversation.py; openhands/agent_server/api.py`
   - IDs: SEC-001, CFG-001, MCP-001, EXEC-002, MCP-002, MCP-003, EXEC-01, EXEC-02, EXEC-03, SSRF-01
2. **CRITICAL · 3/3 轮** — Unauthenticated POST /api/init on deferred-init servers without a secret_key permits control-plane takeover (env injection, arbitrary persistence paths, attacker-chosen session keys)
   - CWE: `CWE-200, CWE-306, CWE-522, CWE-598, CWE-73, CWE-78, CWE-862, CWE-918`
   - Evidence: `init_router.py; openhands/agent_server/api.py; openhands/agent_server/config.py`
   - IDs: HTTP-003, CP-002, CP-006, AUTH-02, AUTH-07, SSRF-03
3. **HIGH · 3/3 轮** — Top-level /api/file routes accept arbitrary absolute host paths with no workspace containment (read/write/mkdir/archive)
   - CWE: `CWE-200, CWE-22, CWE-73`
   - Evidence: `file_router.py; openhands/agent_server/api.py; openhands/agent_server/file_router.py`
   - IDs: FS-001, CP-007, FS-01
4. **HIGH · 2/3 轮** — Fail-open unauthenticated control plane: no-key mode accepts all REST/WebSockets with no Origin/Host validation; wildcard bind only warns and the shipped SandboxTemplate runs 0.0.0.0 without a key (merged CP-001/CP-003)
   - CWE: `CWE-1385, CWE-306, CWE-350, CWE-942`
   - Evidence: `agent_sandbox/deploy/sandboxtemplate.yaml; dependencies.py; openhands/agent_server/__main__.py`
   - IDs: HTTP-002, CP-001
5. **HIGH · 2/3 轮** — Session-key authentication fails open when session_api_keys is empty; unauthenticated HTTP and WebSocket API (default), amplified by shipped wildcard-bind SandboxTemplate
   - CWE: `CWE-1188, CWE-1385, CWE-306`
   - Evidence: `02_remote_agent_server/agent_sandbox_deploy/sandboxtemplate.yaml; agent_sandbox/deploy/sandboxtemplate.yaml; agent_server/openai/router.py`
   - IDs: HTTP-001, AUTH-01

## aud-048-opensandbox

- runs: 2
- findings: 65
- 稳定簇：4（High/Critical 1）

1. **HIGH · 2/2 轮** — CreatePoolRequest.template is a raw Dict with no field filtering (schema.py:1549-1555); _get_pool_service resolves the global config namespace and the route calls create_pool with no validation (pool.py:46-106); _build_pool_manifest places the caller template directly into spec.template (pool_service.py:50-74) and create_namespaced_custom_object submits it (106-131), so one tenant can also list/update/delete another's pools in the shared namespace. The CRD declares Template *corev1.PodTemplateSpec with PreserveUnknownFields + Schemaless (pool_types.go:51-54; batchsandbox_types.go:98-126), and the shipped CRDs use x-kubernetes-preserve-unknown-fields (crds.yaml:134-137,384-386). No admission webhook is enabled (kustomization.yaml:21-23 commented out) and controllers perform no hostPath/privileged/hostPID/serviceAccountName checks before GetPodFromTemplate deep-copies the spec (pod.go:83-108; pool_controller.go:1384; batchsandbox_controller.go:213,682-700). Cluster RBAC editor roles grant create/update on these CRDs and the server SA already has create on pools/batchsandboxes. Contrast: the sandbox create path validates volumes with ensure_valid_host_path/allowed_host_paths (default empty), but the Pool API bypasses it. A privileged or hostPath Pool pod executes on the node, enabling node compromise and cross-tenant escape.
   - CWE: `CWE-269`
   - Evidence: `base/files/crds.yaml; internal/controller/pool_controller.go; internal/utils/pod.go`
   - IDs: K8S-002, CP-002

## aud-080-xinference

- runs: 1
- findings: 22
- 稳定簇：0（High/Critical 0）

- 暂无多轮重复的 High/Critical。

