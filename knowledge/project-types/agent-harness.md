# Agent Harness 审计知识卡

## 适用项目

codex、deepseek-harness、Claude Code 类 agent、MCP client/server、带工具调用的 coding assistant。

## 核心信任边界

1. **项目级配置**：`.mcp.json`、`.codex/config.toml`、`.claude/settings.json`、`AGENTS.md`、`CLAUDE.md`。
2. **工具/命令执行**：shell、exec、MCP `command/args/env`、git hooks、fsmonitor、clean/process filter。
3. **审批与沙箱**：approval policy、allow/deny prefix、sandbox mode、网络/文件系统限制。
4. **本地控制面**：app-server、exec-server、WebSocket、本地 HTTP、IDE 集成。
5. **会话/凭据**：OAuth token、API key、登录态、会话日志、上下文压缩。
6. **模型输出**：prompt injection、工具参数注入、计划/代码生成后的自动执行。

## 高价值问题

- 项目配置是否在**无确认**的情况下生效？`mcp_servers.command/args/env` 是否会执行任意程序？
- 审批是否只匹配命令首 token/前缀？别名、参数、管道、`sh -c` 能否绕过？
- 沙箱默认是否关闭？`bypassPermissions`、`--no-sandbox`、`approval_policy=never` 是否可达？
- exec-server/app-server 是否绑定非回环？WebSocket 是否有认证和方法级授权？
- git 相关功能是否会执行仓库内可控的 hook/filter/fsmonitor？
- 本地控制面是否允许任意本地进程调用高危方法？是否有来源校验？
- 登录/会话 token 是否可能通过工具输出、日志、错误信息泄露？
- 模型输出进入工具参数时，是否有类型/长度/路径/命令校验？

## 常见 CWE

CWE-78（命令注入）、CWE-94（代码注入）、CWE-306（缺少认证）、CWE-862（缺少授权）、
CWE-693（保护机制失效）、CWE-22（路径遍历）、CWE-200（信息泄露）、CWE-522（凭据保护不足）。

## 误报排除

- 配置只在显式 `--dangerously`/用户确认后生效 → reachability=`opt-in`，降级。
- 沙箱/审批默认开启，只有文档示例关闭 → 不算默认漏洞。
- 本地回环 + 同用户信任模型下的控制面 → 需要说明威胁模型，不能直接 Critical。
- token 只在内存/受保护文件中，且没有跨边界输出 → 不报泄露。

## 验证配方

- 起本地 app-server/exec-server，检查绑定地址与认证。
- 构造最小项目配置（MCP command / approval prefix），观察是否执行 benign marker。
- 用 `curl 127.0.0.1` 检查本地控制面是否需要认证。
- 对 sandbox/approval 只做配置级验证，不写武器化绕过。

## 输出要求

每条 finding 必须包含：入口、可控输入、执行 sink、前置条件、reachability、证据 `file:line`、
最小 benign 验证思路、修复建议。没有执行链的只写成 hypothesis。
