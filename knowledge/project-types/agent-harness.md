# 智能体执行框架（Agent Harness）审计知识卡

## 适用项目

codex、deepseek-harness、Claude Code 类智能体、MCP 客户端与服务端，以及带工具调用的编程助手。

## 核心信任边界

1. **项目级配置**：`.mcp.json`、`.codex/config.toml`、`.claude/settings.json`、`AGENTS.md`、`CLAUDE.md`。
2. **工具与命令执行**：Shell、子进程、MCP `command/args/env`、Git 钩子、文件系统监视和清理过滤器。
3. **审批与沙箱**：审批策略、允许与拒绝的命令前缀、沙箱模式、网络与文件系统限制。
4. **本地控制面**：应用服务、执行服务、WebSocket、本地 HTTP 和 IDE 集成。
5. **会话与凭据**：OAuth 令牌、API 密钥、登录状态、会话日志和上下文压缩。
6. **模型输出**：提示词注入、工具参数注入，以及计划或代码生成后的自动执行。

## 高价值问题

- 项目配置是否在**无确认**的情况下生效？`mcp_servers.command/args/env` 是否会执行任意程序？
- 审批是否只匹配命令的首个词或前缀？别名、参数、管道、`sh -c` 能否绕过？
- 沙箱默认是否关闭？`bypassPermissions`、`--no-sandbox`、`approval_policy=never` 是否可达？
- 执行服务或应用服务是否绑定非回环地址？WebSocket 是否有认证和方法级授权？
- Git 相关功能是否会执行仓库内可控的钩子、过滤器或文件系统监视命令？
- 本地控制面是否允许任意本地进程调用高危方法？是否有来源校验？
- 登录或会话令牌是否可能通过工具输出、日志、错误信息泄露？
- 模型输出进入工具参数时，是否有类型、长度、路径和命令校验？

## 常见 CWE

CWE-78（命令注入）、CWE-94（代码注入）、CWE-306（缺少认证）、CWE-862（缺少授权）、
CWE-693（保护机制失效）、CWE-22（路径遍历）、CWE-200（信息泄露）、CWE-522（凭据保护不足）。

## 误报排除

- 配置只在显式 `--dangerously` 或用户确认后生效：可达性为 `opt-in`，应降级。
- 沙箱和审批默认开启，只有文档示例关闭：不算默认漏洞。
- 本地回环且采用同用户信任模型的控制面：需要说明威胁模型，不能直接定为严重。
- 令牌只在内存或受保护文件中，且没有跨边界输出：不报泄露。

## 验证配方

- 启动本地应用服务或执行服务，检查绑定地址与认证。
- 构造最小项目配置，包括 MCP 命令和审批前缀，观察是否生成无害标记。
- 用 `curl 127.0.0.1` 检查本地控制面是否需要认证。
- 对沙箱和审批只做配置级验证，不写武器化绕过。

## 输出要求

每条候选问题（finding）必须包含：入口、可控输入、危险数据终点、前置条件、可达性、证据 `file:line`、
最小无害验证思路和修复建议。没有执行链的只写成假设。

## 默认六条边界检查路径

`security-orchestrator` 对智能体执行框架不应只启动一个 `infra-analyst`，而应并行拆成六条检查路径，
每条都产出独立的 `infra-<boundary>.json`，最后由 `hypothesis-critic` 合并：

| 检查路径 | 主要问题 | 常见入口 |
|---|---|---|
| `config` | 项目配置、`.env` 和插件是否无确认生效 | `boot`、`plugin-manager`、`AGENTS.md`、`CLAUDE.md`、`.mcp.json` |
| `process-exec` | 模型或配置输入是否进入 Shell、子进程或 PTC | `shell`、`subprocess`、`tool-executor-ptc` |
| `mcp` | MCP 服务端的 `command/args/env` 来源，以及工具结果是否送回模型 | `mcp-client`、`mcp-resources`、内置 MCP |
| `sandbox` | 默认值、失败时默认放行、`workspaceRoot`、网络与文件系统限制 | `sandbox-*`、`fs-sandbox`、`bash-sandbox` |
| `control-plane` | 本地 HTTP 和 WebSocket 是否缺少方法级授权，能否启动终端、修改配置或获取凭据 | `api/*-controller`、`credentials`、`identity` |
| `filesystem` | 真实路径、符号链接、大小写和 Windows 路径是否越出工作区 | `fs-local`、`fs-sandbox`、`session-log-*` |

## 跨边界组合链（优先于单点）

智能体执行框架的真实风险通常不在单个文件，而在跨边界组合：

1. `config → process-exec`：`.env`、项目配置或插件加载进入 Git 配置或命令执行。
2. `mcp → process-exec`：项目级 MCP `command/args/env` 自动执行；MCP 结果再送回模型，形成提示词注入。
3. `control-plane → terminal/filesystem/credentials`：本地控制面方法缺少授权，直接启动终端、读取工作区外文件或导出令牌。
4. `sandbox → process-exec/filesystem`：沙箱默认关闭或失败时默认放行，导致工具执行或路径校验失效。
5. `PTC → process-exec`：模型生成代码进入 Python 运行时，队列无界或分发前未校验。

证据复核智能体合并时必须优先找这些链；只有单点危险数据终点、没有可达输入来源的，降低为假设。
