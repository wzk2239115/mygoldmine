# 二次审计：可疑 finding 误报判定

- 时间：2026-10-27
- 方法：5 个 agent 并行，只读源码 + 报告 + 知识卡，按 `TP / FP / DUP / RUNTIME / UNCLEAR` 判定。
- 范围：每个项目 5 条最高优先级可疑项，共 25 条。
- 注意：`TP` 是**代码级**确认，不等于运行时已复现；没有做动态利用。

## 总览

| 项目 | 抽审 | TP | FP | DUP | UNCLEAR |
|---|---:|---:|---:|---:|---:|
| codex | 5 | 3 | 0 | 2 | 0 |
| deepseek-harness | 5 | 2 | 2 | 1 | 0 |
| sglang | 5 | 4 | 0 | 0 | 1 |
| verl | 5 | 1 | 2 | 2 | 0 |
| vllm | 5 | 5 | 0 | 0 | 0 |
| **合计** | **25** | **15** | **4** | **5** | **1** |

抽审样本误报率：4/25 = 16%；重复率：5/25 = 20%。`TP` 中多条是 conditional/opt-in，不能直接当默认可利用。

## codex

| id | verdict | confidence | 证据 | 结论 |
|---|---|---|---|---|
| F-01 | DUP | high | `exec-server/src/server/transport.rs:178-215,246`；`websocket-auth/src/lib.rs:288-295`；默认 `ws://127.0.0.1:0` | 与 F-36 同根因；默认回环，仅显式 `--listen 0.0.0.0` 且无 auth 时成立，降为 opt-in |
| F-02 | DUP | high | `app-server/message_processor.rs:983-992`、`:180` | 与 F-25 同根因；本地/已认证 WS 信任模型，不是未授权远程 |
| F-32 | TP | high | `account_processor.rs:1080-1127` | `includeToken` 返回 OAuth token；已 initialize 连接可读；Critical 偏高，建议 High |
| F-06 | TP | high | `sdk/python/client.py:220-223,833-839`；`api.py:85-92,316-320` | Python SDK 默认审批 accept，fail-open；低层 CodexClient 可达 |
| F-33 | TP | high | `rmcp-client/http_headers.rs:431-447`；`runtime.rs:914-939`；`loader/mod.rs:89-105` | `sh -c` 属实；需受信/自动受信配置或配置写权限 |

## deepseek-harness

| id | verdict | confidence | 证据 | 结论 |
|---|---|---|---|---|
| VULN-005 | TP | high | `app-boot/src/index.ts:144`；`subprocess/src/index.ts:47`；`git.ts:69`；`recorder.ts:139` | `.env → process.env → git 子进程` 链成立；默认触发 |
| VULN-003 | TP | medium | `media-references.ts:31-34`；`fs-local/fsio.ts:175` | 缺 workspace `confine` 属实；但默认回环+owner Cookie，High 偏高 |
| VULN-004 | FP | medium | `session-log-deepseek/src/index.ts:86,197` | 日志发往同一模型提供方，属既定功能/隐私设计；无攻击者通道 |
| VULN-001 | DUP | high | `workspace-files/src/index.ts:416-434` vs `403-409` | 与 VULN-002 同 `locateFile` 根因 |
| VULN-006 | FP | medium | `agent-loop/src/agent.ts:337`；`agent-loop/README.md:220` | 无硬 turn budget 是设计限制，可取消/扩展；重试有限，不是漏洞 |

## sglang

| id | verdict | confidence | 证据 | 结论 |
|---|---|---|---|---|
| VULN-002 | TP | high | `http_server.py:861`；`common.py:3582`；`server_args.py:316`；`watermark/core.py:25`；`auth.py:148-151` | `/server_info` 泄露 key；admin-only 时匿名读 admin_key，双 key 时普通 key 读 admin_key |
| VULN-004 | TP | high | `http_server.py:1298`；`io_struct.py:1970`；`weight_updater.py:193`；`loader.py:512`；`weight_utils.py:1398-1415` | 任意 model_path 可替换权重；RCE 需可写 .pt + legacy tar，条件 RCE |
| VULN-006 | TP | high | `http_server.py:2876-2888`；`auth.py:133-143` | 默认无密钥即全开放；默认 host 127.0.0.1，网络利用需 `--host 0.0.0.0` |
| VULN-008 | TP | medium | `server.rs:607-655`；`middleware.rs:114-148`；`worker_service.rs:225`；`detect_connection.rs:20-31` | 默认无认证可注册 worker + SSRF；配置 key 后受保护 |
| VULN-025 | UNCLEAR | low | `http_server.py:2083-2098`；`serving_responses.py:1804-1851` | 标题指 update_weights/torch.load，描述却是 `/v1/responses` IDOR；evidence 空、line 0；需重写 |

另：VULN-001 与 VULN-002 重复（同一 `/server_info`），不应独立计数。

## verl

| id | verdict | confidence | 证据 | 结论 |
|---|---|---|---|---|
| FIND-001 | TP | high | `testing_util.py:47`；`utils.py:31`；`reward/__init__.py:80-88` | 模型输出→`exec(compile)` 成立；仅 code reward 且 `sandbox_fusion.url=null` 时触发，需降级描述 |
| AC-001 | DUP | high | `naive_router.py:112,55` | 与 ROUTE-01/WEB-01 同根因 |
| AC-002 | DUP | high | `vllm_async_server.py:194`；`async_sglang_server.py:197` | 与 ROUTE-02/WEB-03 同根因 |
| CI-01 | FP | medium-high | `import_utils.py:178-189`；配置默认 null | opt-in、操作者 Hydra 配置；默认不可达，无跨信任边界 |
| CI-02 | FP | medium | `import_utils.py:283-290`；`rollout.yaml:182` | 受信配置插件机制，默认关闭 |

## vllm

| id | verdict | confidence | 证据 | 结论 |
|---|---|---|---|---|
| F-01 | TP | medium | `ipc_engine.py:80-92`；`routers.py:46-53` | 需 dev/RL + 不安全序列化 + ipc + 先 start；默认不可达，降为 conditional/dev-only |
| F-02 | TP | high | `sagemaker/api_router.py:99,110`；`authenticate.py:11,59`；`routers.py:39-42` | `/invocations` 恒注册，api-key 前缀不覆盖；可绕过认证 |
| F-04 | TP | high | `connector.py:207-209,370-379,411`；`connections.py:396-402` | 默认空 allowlist = 跳过域名校验；无私网/元数据过滤 |
| F-05 | TP | high | `envs.py:79,993-994`；`connector.py:411`；`connections.py:414-426` | 默认允许重定向；只校验首跳，可 302 到内网 |
| F-09 | TP | medium | `lora/utils.py:359-368`；`worker_manager.py:119`；`serving.py:178` | 需 `VLLM_ALLOW_RUNTIME_LORA_UPDATING=1`；`/v1` 受 auth；降为 Medium |

## 需要修正的报告问题

1. **codex**：F-01/F-36、F-02/F-25 合并；F-01/F-02 改 opt-in/local-trust；F-32 降 High。
2. **deepseek**：VULN-004/VULN-006 标 FP 或设计限制；VULN-001 合并到 002；VULN-003 降 Medium。
3. **sglang**：VULN-001 合并到 002；VULN-025 重写或删除；`server_info` 语义簇去重。
4. **verl**：AC-001/AC-002 合并到 ROUTE/WEB 别名；CI-01/CI-02 标 FP（默认 opt-in）；FIND-001 限定触发模式。
5. **vllm**：F-01 标 dev-only/conditional；F-09 标 opt-in runtime LoRA；F-04/F-05 保留。

## 结论

- 这批报告**不是全误报**：抽审 25 条中 15 条代码级成立。
- 主要问题是**重复、条件性、严重度偏高、验证状态缺失**，不是“结论全错”。
- 下一步：把 15 条 TP 中默认可达/High 的（vllm F-02/F-04/F-05，sglang VULN-002/006/008，deepseek VULN-005，codex F-32/F-06）送 `verify-agent` 做运行时确认。
