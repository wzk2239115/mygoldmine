# Codex 项目知识卡

- 类型：agent-harness
- 审计 commit：`970111f6`（2026-10-27）
- 环境：`env/codex/`（planned；Rust + Node）

> 下面“已知高价值模式”来自 2026-10-27 的静态审计，默认仍是 **unverified**；
> 只能当线索，必须由 verify-agent 或运行时证据确认。

## 入口

- `codex-rs/app-server`：IDE/客户端控制面，initialize 后方法级授权。
- `codex-rs/exec-server`：WebSocket/命令执行/文件系统。
- `codex-rs/cli`：CLI、审批、sandbox、配置加载。
- `codex-rs/core/src/config`、`exec_policy`、`mcp`、`tools`。
- `codex-cli`、`sdk/python`、`sdk/typescript`。

## 信任边界

项目配置、MCP、工具/命令执行、审批策略、沙箱、git hooks/fsmonitor、本地控制面、OAuth/会话 token、模型输出。

## 已知高价值模式（来自 2026-10-27 报告）

- F-01：exec-server 网络 WebSocket 可无认证绑定 → 远程命令/文件系统执行。
- F-02/F-25：app-server initialize 后无方法级/来源级授权。
- F-32：`includeToken` 直接返回 OAuth token。
- F-06：Python 审批默认 accept。
- F-33：`http_headers_helper` 经 `sh -c` 执行。
- 项目级 `mcp_servers.command/args/env` 直接执行，未在项目配置 denylist。
- 审批按首 token 前缀匹配，危险参数/别名可绕过；git hooks/fsmonitor/filter 可执行仓库内代码。

## 默认配置与开关

- 审批策略、sandbox mode、`--dangerously-bypass-approvals-and-sandbox`、`approval_policy`。
- 项目配置是否需要在首次打开时确认。
- exec-server 是否默认监听本地/网络、是否有 auth token。
- MCP server 的 command/args/env 来源。

## 误报排除

- 控制面只绑定回环且同用户信任 → 说明威胁模型，降级。
- 危险配置只在显式 `--dangerously`/用户确认后生效 → reachability=`opt-in`。
- 沙箱/审批默认开启，只有文档示例关闭 → 不算默认漏洞。
- 同一根因的 F-01/F-36、F-02/F-25 合并。

## 验证配方

- 起 app-server/exec-server，检查绑定地址与认证。
- 构造最小项目配置（MCP command/approval prefix），观察是否执行 benign marker。
- 用 `curl 127.0.0.1` 检查本地控制面认证。
- 只做配置级 sandbox/approval 验证，不写武器化绕过。

## 下一步优先看

1. exec-server WebSocket 默认绑定与认证。
2. app-server 方法级授权。
3. 项目配置/MCP 的信任与 denylist。
4. 审批前缀绕过与 git hooks/fsmonitor。
