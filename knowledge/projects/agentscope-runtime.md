# AgentScope Runtime 项目知识卡

- 类型：`backend-http` + `agent-harness` + `training-framework`（FastAPI / Python）
- 审计 commit：`22072fd`（2026-10-27）
- 环境：离线静态审计；无预构建镜像，运行时验证统一 `blocked`
- 关联 case：`cases/agentscope-runtime/2026-10-27-infra-control-plane.md`

> 下面的“已知模式”为 **源码级静态确认（static confirmed）**，未做运行时验证；
> 只当前置条件成立时有效。不要把“默认配置存在”直接等同于“公网可利用”。

## 入口

- 沙箱管理器控制面：`src/agentscope_runtime/sandbox/manager/server/app.py`
  - `verify_token`（`app.py:116-124`）、动态路由注册（`app.py:159-213`）。
  - `register_routes` 把所有 `@remote_wrapper` 方法自动注册为 HTTP 路由（create / call_tool / get_info / release / add_mcp_servers）。
- 沙箱管理器实现：`sandbox/manager/sandbox_manager.py`（`create` 合并 `environment`、`get_info` 序列化 `ContainerModel`）。
- 引擎 HTTP 面：`src/agentscope_runtime/engine/app/agent_app.py`
  - CORS（`:362-368`）、进程控制端点（`:610-635`）、默认绑定（`:56-57,890`）。
- 训练沙箱：`sandbox/box/training_box/env_service.py`（FastAPI 应用 `:472`，路由 `/create /step /evaluate /release`），启动脚本 `appworld.sh:18`、`bfcl.sh:19`。
- 沙箱内共享 API：`sandbox/box/shared/app.py`、`sandbox/box/shared/routers/*`（generic/workspace/mcp/runtime_watcher）。
- 沙箱容器客户端：`common/container_clients/docker_client.py`（端口发布、`host_ip` 缺省）。
- 工具注册：`tools/mcp_wrapper.py`、`tools/cli/modelstudio_mcp_server.py`。

## 信任边界

1. 引擎 HTTP/SSE/A2A：默认无认证。
2. 沙箱管理器控制面：Bearer 可选，空值 fail-open。
3. 沙箱容器 API：`SECRET_TOKEN` Bearer（`box/shared/dependencies/deps.py`）。
4. training_box env_service：独立 FastAPI，无认证。
5. 容器网络发布：Docker `ports=` 未指定 `host_ip`。
6. MCP 工具/进程执行、workspace 文件 API、tracing/日志。

## 默认配置与开关（逐项核对）

- Manager：`HOST="127.0.0.1"`（`config.py:15`），`BEARER_TOKEN=None`（`config.py:19`），`.env.example` 中 BEARER_TOKEN 为空；外部访问需显式 `HOST=0.0.0.0`（cookbook）。
- AgentApp：`HOST=os.getenv("HOST","0.0.0.0")`（`agent_app.py:56`），`PORT=8080`；CLI run、standalone 模板、`package.py`、生成的 Dockerfile 全为 `0.0.0.0`。
- LocalDeployManager：默认 `127.0.0.1`，是唯一默认回环的引擎部署路径。
- training_box：`--portal 0.0.0.0 --port 80`（appworld/bfcl 脚本），镜像 CMD 直接跑脚本，无 nginx/auth 前置。
- Docker 端口发布：`port_mapping[container_port]=host_port`，`containers.run(ports=...)` 无 `host_ip` → 绑定所有接口。
- 沙箱 token：manager 正常路径生成 `secrets.token_hex(16)` 注入；直接 `docker run` / build health-check / mobile `start.sh` 会回落到 `deps.py:7` 的硬编码默认值。

## 已知高价值模式（2026-10-27 静态确认）

- **LCP-001（high）**：`verify_token` 在 `BEARER_TOKEN` 为空时直接放行；默认即空。所有动态 RPC 路由无鉴权 → 创建/销毁容器、`call_tool`、`get_info` 读 `runtime_token`。
- **LCP-003（high）**：training_box `env_service` 无任何认证，容器 `0.0.0.0:80` 发布；`/step` 把调用方 action 送入 AppWorld `world.execute` / BFCL 工具调用。
- **INFRA-001（high）**：AgentApp 无条件注册 `/shutdown`、`/admin/shutdown`，无认证，默认 `0.0.0.0`；远程可终止进程（DAEMON_THREAD 下是宿主进程）。
- **SEC-001（medium）**：沙箱默认 Bearer token 硬编码，出现在 `deps.py:7`、`build.py`、多个 Dockerfile、mobile `start.sh`；仅影响非 manager 注入路径。
- **INFRA-003（medium）**：`allow_origins=["*"]` + `allow_credentials=True` 同时出现在 AgentApp、manager、legacy factory、SSE header；无 DNS rebinding 即可跨站驱动本地无鉴权服务。
- 关联：**LCP-002** `/desktop` HTTP 代理与 WebSocket 从不调用 `verify_token`（即使配了 token 也开放）；**SEC-003** `get_info` 返回容器 `runtime_token`；**SEC-005** `create(environment=...)` 可覆盖 `SECRET_TOKEN`。

## 误报排除（重要）

- 沙箱内 `run_shell_command` / `run_ipython_cell` 是**设计能力**，不是独立漏洞；只有在拿到沙箱 token、绕过 manager 或容器逃逸时才升级。generic 路由编译进 FILESYSTEM 镜像只算加固提示。
- `mcp_wrapper exec(code)` 的 code 由**受信静态工具元数据**（类名/方法名/参数名）生成，不是模型/用户可控；除非存在不可信插件注册工具元数据的入口，否则不报 RCE。
- Manager 默认 `HOST=127.0.0.1`：默认配置下的“认证缺失”不等于公网可利用；远程需 `HOST=0.0.0.0`，或借助浏览器跨站（CORS `*` + credentials）访问回环。
- 模型工具参数可达 shell/IPython 属于沙箱既定执行面，不单独计漏洞；要看是否有跨边界入口。
- `/admin/status` 信息泄露、SSE 错误回显、日志记录属低危；与 high 的认证缺失合并评估影响，不重复计数。

## 验证配方（下次可直接复用）

- Manager fail-open：不设 `BEARER_TOKEN` 启动，`curl` POST `/create`（benign body），观察是否 200；再设 token 重试应 401。静态可先核对 `verify_token` 分支与 `register_routes`。
- training env_service：创建 APPWORLD/BFCL 沙箱，从另一网络命名空间 POST 无 Authorization 的 `/step`；同时检查 `docker ps` / port mapping 是否 `0.0.0.0`。
- AgentApp：最小 AgentApp 默认启动，远端 POST `/shutdown`；再设 `HOST=127.0.0.1` 确认不可达。
- CORS：带 `Origin: https://evil.example` 请求，检查是否回显该 Origin 且 `Access-Control-Allow-Credentials: true`。
- 默认 token：只核对位置与回退逻辑，**不要在报告/知识库复述 token 值**。

## 下一步优先看

1. manager `/desktop` HTTP + WebSocket 的认证/Origin（LCP-002）。
2. `get_info` token 脱敏、`create(environment=...)` 保留键覆盖（SEC-003/005）。
3. workspace 路径校验 `abspath+startswith`（SBX-001）与 `.git` clean filter（SBX-005）。
4. MCP `add_servers` command/env 注入与远程 URL SSRF（MCP-001/003）。
5. tracing/日志中的 api_key/token 泄露面（SEC-004/006/008）。
