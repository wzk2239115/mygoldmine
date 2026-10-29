# agentscope-runtime / INFRA control-plane cluster / 2026-10-27

- verdict: confirmed（**static / source-level only**；运行时验证 blocked）
- severity: high（cluster 内 3 条 high + 2 条 medium）
- reachability: default（manager 侧受默认 127.0.0.1 约束，见下）
- commit: `22072fd`
- run: `aud-046-agentscope-runtime` / `20261027T171026Z`
- files:
  - `src/agentscope_runtime/sandbox/manager/server/app.py:116-124,159-213`
  - `src/agentscope_runtime/sandbox/manager/server/config.py:15,19`
  - `src/agentscope_runtime/sandbox/manager/sandbox_manager.py:857-866,1234-1236`
  - `src/agentscope_runtime/sandbox/box/training_box/env_service.py:202-209,472,491-683,733-752`
  - `src/agentscope_runtime/sandbox/box/training_box/appworld.sh:18`、`bfcl.sh:19`
  - `src/agentscope_runtime/common/container_clients/docker_client.py:79-90,117-126`
  - `src/agentscope_runtime/engine/app/agent_app.py:56-57,215,359-380,424,607-635,890`
  - `src/agentscope_runtime/cli/commands/run.py:25-32`
  - `src/agentscope_runtime/engine/deployers/utils/templates/standalone_main.py.j2:155`
  - `src/agentscope_runtime/engine/deployers/utils/package.py:104`
  - `src/agentscope_runtime/engine/deployers/utils/docker_image_utils/dockerfile_generator.py:135`
  - `src/agentscope_runtime/sandbox/box/shared/dependencies/deps.py:7,12-22`
  - `src/agentscope_runtime/sandbox/build.py:227,278-285`
  - `src/agentscope_runtime/sandbox/box/mobile/box/scripts/start.sh:122`
  - `src/agentscope_runtime/sandbox/box/shared/app.py:33-39`
  - `src/agentscope_runtime/sandbox/box/shared/routers/generic.py:121-138`
- verification: `verify/INFRA-LCP-001`、`verify/INFRA-LCP-003`、`verify/INFRA-001` 均为 `conclusion=confirmed`、`verification_mode=static`、`runtime=blocked`（无镜像/离线）。其余两条为 static-finding，本次由 scribe 逐行复核源码。

> 所有结论均为**静态源码确认，未做运行时验证**。不要把“默认配置存在缺陷”直接写成“公网可利用”。

## 1) Sandbox Manager BEARER_TOKEN 空值 fail-open

- 位置：`sandbox/manager/server/app.py:116-124`（分支 122-124）；`config.py:19`。
- root cause：`verify_token` 在 `BEARER_TOKEN` 缺失/空时 `logger.warning(...); return credentials`，而不是抛 401；默认配置即 `BEARER_TOKEN=None`。
- trigger：manager 不配置 token 启动 → 任意能访问 manager 的客户端调用自动注册的 `/create`、`/call_tool`、`/get_info`、`/release` 等；JSON body 直接作为方法 kwargs。
- evidence：`register_routes` 在启动时遍历所有 `@remote_wrapper` 方法；除 CORS 外无全局认证中间件（`app.py:37-44`）。
- 影响链：`/create(environment=...)` 可覆盖 `SECRET_TOKEN`（`sandbox_manager.py:857-866`，`**environment` 最后展开）→ 固定已知容器 token；`/get_info` 返回 `ContainerModel` 含 `runtime_token`（`:1234-1236`）→ 直连容器 API。
- reachability 校正：shipped `HOST="127.0.0.1"`（`config.py:15`），远程未授权利用需 `HOST=0.0.0.0`（cookbook 外部访问配置）或本机进程/浏览器跨站。
- 复用判断：先看 `verify_token` 的空值分支，再看 `register_routes` 是否无条件注册；不要只 grep `Depends(security)` 就认为有认证。

## 2) training_box env_service 无鉴权 + 0.0.0.0:80

- 位置：`env_service.py:472`（`FastAPI(lifespan=lifespan)` 无 `dependencies=`）、路由 `:491,524,568,606,644,683`；`appworld.sh:18`、`bfcl.sh:19`（`--portal 0.0.0.0 --port 80`）；默认参数 `:733-737`。
- root cause：独立 FastAPI 服务，既无 Bearer 也无中间件，且启动即绑 0.0.0.0；镜像 CMD 直接执行脚本，无 nginx/auth 前置。
- trigger：容器端口 80 被发布后，任意可达客户端 POST `/create`、`/step`、`/evaluate`、`/release`。
- 端口发布证据：`docker_client.py:79-90,117-126` 的 `containers.run(ports=port_mapping)` 未传 `host_ip` → Docker 默认绑所有接口。
- sink：`/create` 的 `env_type` 参与 `importlib.import_module(f"training_box.environments.{env_type}.{env_type}_env")`（`:202-209`）；`/step` → AppWorld `world.execute(action)`（`appworld_env.py:969-973`）/ BFCL `execute_multi_turn_func_call`（`env_handler.py:179-186`）。
- 残留：`world.execute` 的“任意代码”能力属第三方实现，已在调用边界确认，但未证明对所有环境都是 OS 级 RCE。
- 复用判断：训练类沙箱要单独看 `env_service`，不要以为共享 box 的 `verify_secret_token` 覆盖了它。

## 3) AgentApp `/shutdown`、`/admin/shutdown` 无认证

- 位置：`engine/app/agent_app.py:607-635`（本次复核 `/shutdown` 在 607 起）、`_add_process_control_endpoints` 于 `:424` 无条件调用、`_setup_builtin_routes` 于 `:215` 无条件执行。
- root cause：两个路由直接 `asyncio.create_task(delayed_shutdown())` → `os.kill(os.getpid(), SIGTERM)`，无任何鉴权依赖；引擎栈只有 CORS/header 中间件。
- 绑定默认：`agent_app.py:56-57,890` → `0.0.0.0:8080`；CLI、standalone 模板、`package.py`、生成 Dockerfile 同为 0.0.0.0；仅 `LocalDeployManager` 回环。
- 影响：远程 DoS；DAEMON_THREAD 下杀的是宿主进程；配合 CORS `*` 可被任意页面跨站触发。
- 复用判断：看到 `os.kill(os.getpid(), SIGTERM)` / `process_control`，先确认路由注册是否无条件、是否有认证依赖、默认绑定地址。

## 4) 沙箱默认 Bearer token 硬编码（仅记录位置，不复述值）

- 位置：`sandbox/box/shared/dependencies/deps.py:7`（`os.getenv("SECRET_TOKEN", <literal>)`）；`sandbox/build.py:227,278-285`；mobile `start.sh:122`；各 Dockerfile CMD。
- root cause：token 缺失时回落到公开默认值，`verify_secret_token`（`deps.py:12-22`，非恒定时间比较）接受该值。
- 影响面：直接 `docker run`、build health-check、mobile start.sh、自定义部署；**manager 创建的容器不受影响**（走 `secrets.token_hex(16)`）。
- 前置：`SECRET_TOKEN` 未注入 + 端口可达（Docker 默认 0.0.0.0）。
- 复用判断：核对“随机注入路径”和“回退路径”是否区分；只报回退路径，避免把正常 manager 路径误报为默认漏洞。不要在知识库/报告写 token 原文。

## 5) CORS `allow_origins=["*"]` + `allow_credentials=True`

- 位置：`engine/app/agent_app.py:362-368`；`sandbox/manager/server/app.py:38-44`；legacy `fastapi_factory.py:383-389`；SSE `response_api_protocol_adapter.py:23-30`。
- root cause：通配 Origin 与 credentials 同时启用，浏览器 SOP 保护失效；manager 的 `/desktop` WebSocket 也无 Origin 校验。
- 影响：任意网页可跨源读取响应并发起状态变更请求 → 驱动本地无鉴权 manager（`/create`、`/call_tool`）与 AgentApp（`/shutdown`），无需 DNS rebinding。
- 复用判断：CORS 配置只在“目标服务无认证”时有实际杀伤；先确认目标端点的 auth 与绑定地址，再定级。

## 误报排除经验（本次明确不报）

- 沙箱内 `run_shell_command` / `run_ipython_cell`（`generic.py:121-138`）是**设计能力**，不是独立漏洞；只有在获得沙箱 token、绕过 manager 或容器逃逸（如 MOBILE `privileged=True`）时才升级。原 `INFRA-SBX-003` 已转为 hypothesis。
- `mcp_wrapper.py` 的 `exec(code, namespace)`（`:137-184`）由**受信静态工具元数据**（类名/方法名/参数名/类型名）生成，非模型/用户可控；除非有不可信插件或外部 FQN 注册工具元数据的入口，否则不报代码注入。
- Manager 默认 `HOST=127.0.0.1`（`config.py:15`）显著缓解远程利用：默认配置类 finding 要写清 “loopback 默认 / 0.0.0.0 或浏览器跨站才远程可达”，不要直接按公网 Critical。
- `/admin/status` 信息泄露、SSE 错误回显、完整请求体日志属低危，与 high 认证缺失合并评估，不重复计数。
- 同一根因的端点/脚本/Dockerfile 变体要合并（本次 8 条源 finding 合并为 5 个 canonical cluster），不要按出现次数重复计漏洞。

## 复用下一步

1. `grep -n "verify_token\|register_routes\|BEARER_TOKEN" manager/server/` 先确认认证是否真的覆盖所有动态路由。
2. training_box 的 `env_service` 独立看认证与 `--portal`；`docker_client` 看 `host_ip`。
3. AgentApp 看 `_add_process_control_endpoints` 调用点与默认 `HOST`。
4. token 类 finding 区分“随机注入路径”与“硬编码回退路径”。
5. CORS 定级前先确认目标端点是否有认证。
