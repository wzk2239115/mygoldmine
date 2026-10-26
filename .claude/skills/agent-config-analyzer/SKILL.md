---
name: agent-config-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 AI Agent 项目级配置信任与审批绕过漏洞；重点关注仓库内 .codex/config.toml、.mcp.json、.env、AGENTS.md、.claude/settings.json、本地 Git 配置在无用户确认时被自动加载，MCP server 的 command/args 可执行任意程序，审批规则按前缀匹配且可被参数/别名绕过，以及 core.hooksPath、core.fsmonitor、clean/process filter 等仓库信任链触发点；覆盖 codex、deepseek-harness 等 Agent/训练框架。
---

# Agent 项目级配置信任与审批绕过分析器

分析“打开一个不可信仓库 → Agent 读取仓库内配置 → 启动 MCP/命令或放宽审批”这条链。适用缺口：G04（Agent 项目级配置信任）、G07（命令审批绕过）、G08 的 Agent 打开仓库触发链。

## 适用场景

- 项目是编码 Agent、CLI Agent、MCP 客户端/服务端、代码沙箱或自动化执行器。
- 代码或文档中出现 `.codex/config.toml`、`.mcp.json`、`mcpServers`、`AGENTS.md`、`CLAUDE.md`、`.claude/settings.json`、`.env`。
- 存在 `approval_policy`、`allow_prefix`、`PrefixRule`、`auto_approve`、`dangerously-skip-permissions`、`bypassPermissions`。
- Agent 会自动打开/索引用户克隆的 Git 仓库，或从仓库读取 project-level config。

**Early exit**：项目不读取项目目录配置、没有 MCP/工具执行、也没有命令审批逻辑时，只审查 Git 配置章节即可退出。

## Source / Sink

| 类别 | 具体位置 |
|------|----------|
| Source | 仓库内 `.codex/config.toml`、`.mcp.json`、`.env`、`.vscode/settings.json`、`.claude/settings.json`、`AGENTS.md`、`.git/config`、`.gitattributes`、`.gitmodules` |
| Sink | 配置层加载器（`load_config_layers_state`、profile layer merge）、MCP stdio `command`/`args`/`env`、`spawn`/`exec`、审批规则 `PrefixRule`、`allow_prefix`、`approval_policy`、Git `core.hooksPath` / `core.fsmonitor` / `filter.*.clean` / `filter.*.process` / `attr.tree` / `core.sshCommand` |
| 信任边界 | 项目级配置是否在用户确认前生效；`--ignore-project-config` 是否为默认；trusted/untrusted 判定是否可被仓库内容改写 |

## 检测步骤

1. **列出配置发现顺序**：用户目录、系统目录、项目目录、仓库根、父目录、CLI override 谁覆盖谁；确认项目级配置是否“加载但未信任”还是直接生效。
2. **确认信任门槛**：打开仓库时是否要求用户显式标记 trusted；`projects.<path>.trust_level` 是否可被仓库内文件影响；是否默认信任当前工作目录。
3. **检查 MCP 启动配置**：`mcp_servers.*.command` / `args` / `env` 是否来自仓库；是否会 shell 展开；是否允许相对路径、`sh -c`、下载后执行；是否有命令白名单或签名。
4. **检查审批规则**：审批是按完整 argv 匹配还是按命令名前缀；`rg`、`git`、`find`、`curl`、`python` 等命令是否存在可改变行为的参数（如 `--pre`、`-c`、`--upload-pack`）；别名/函数/环境变量是否绕过前缀。
5. **检查 Git 自动执行链**：不可信仓库是否设置 `core.hooksPath`、`core.fsmonitor`、`filter.*.clean`、`filter.*.process`、`attr.tree`、`core.sshCommand`；Agent 是否在打开仓库时自动执行 `git status` / `git diff` / `git add`。
6. **检查环境变量注入**：项目 `.env` 是否覆盖 `PATH`、`LD_PRELOAD`、`LD_LIBRARY_PATH`、`NODE_OPTIONS`、`PYTHONPATH`、`GIT_CONFIG*`、`BASH_ENV`。
7. **结合沙箱**：配置是否放宽文件系统/网络/子进程边界；与 `agent-sandbox-analyzer` 交叉引用，不在此重复判定沙箱 profile 细节。

## 判定矩阵

| 条件 | 结论 |
|------|------|
| 仓库内 `.codex/config.toml` / `.mcp.json` 在无确认时自动加载，且含 `command` | High |
| MCP `command` 为 `sh`/`bash`/`cmd`/`powershell` 或参数含 `-c` | High |
| 审批仅按首 token 前缀允许，命令存在危险参数 | High/Medium |
| `approval_policy="never"` 且自动批准危险工具 | Medium |
| `core.hooksPath` / clean/process filter 指向仓库内文件，且 Agent 自动执行 Git 命令 | High |
| `core.fsmonitor` 指向仓库内可执行文件 | High/Medium |
| 项目 `.env` 覆盖 `LD_PRELOAD` / `NODE_OPTIONS` / `GIT_CONFIG*` | Medium |
| 仅出现 `.env` 普通业务变量，或配置位于用户主目录且需手动启用 | 不报告/降级 |

## 真实代码位置（已核对，2026-10-27）

| 项目 / commit | 位置 | 关键代码 | 用途 |
|---------------|------|----------|------|
| codex `970111f6cb62` | `codex-rs/config/src/loader/mod.rs:132-134` | `cwd ${PWD}/config.toml`、`.codex/config.toml` “loaded but disabled when the directory is untrusted” | 项目级配置发现顺序与信任门槛 |
| codex `970111f6cb62` | `codex-rs/config/src/loader/mod.rs:146-155` | `pub async fn load_config_layers_state(...)` | 配置层合并入口 |
| codex `970111f6cb62` | `codex-rs/config/src/loader/mod.rs:342-421` | `if !ignore_project_config && let Some(cwd) = cwd` → `load_project_layers(...)` → `layers.extend(...)` | 项目配置实际注入点 |
| codex `970111f6cb62` | `codex-rs/config/src/loader/mod.rs:1075-1141` | `fn is_trusted()`、`project-local config, hooks, and exec policies` 仅在 trusted 时加载 | 信任判定与降级提示 |
| codex `970111f6cb62` | `codex-rs/config/src/mcp_types.rs:388-397` | `RawMcpServerConfig { command, args, env, env_vars, ... }` | 仓库配置可指定 MCP 可执行文件与参数 |
| codex `970111f6cb62` | `codex-rs/execpolicy/src/rule.rs:44-63` | `matches_prefix()` 只比较 `cmd[0]` 与固定前缀 token | 审批前缀匹配语义，参数绕过审计点 |
| codex `970111f6cb62` | `codex-rs/core/src/exec_policy.rs:358-390` | `exec_policy.check_multiple_with_options(...)`、`derive_requested_execpolicy_amendment_from_prefix_rule(...)` | 审批决策与自动新增前缀规则 |
| deepseek-harness `22ddee379240` | `packages/mcp/mcp-client/src/index.ts:51-66` | `StdioConfig { transport: 'stdio', command, args, env, cwd }` | MCP 子进程启动配置 |
| deepseek-harness `22ddee379240` | `packages/interaction/user-approval/src/index.ts:56-75` | `ApprovalOutcome`、`ApprovalPolicy = 'ask' | 'never'` | 审批结果与策略 |
| deepseek-harness `22ddee379240` | `packages/interaction/user-approval/src/index.ts:150-157` | `Config.policy?: ApprovalPolicy` | 部署级审批默认值审计点 |
| deepseek-harness `22ddee379240` | `packages/boot/app-boot/src/config-schema/index.ts:9-16` | `Imports, Config getters, and lazy builders execute trusted code`；layers 按顺序应用 | 配置层与“可信代码”边界 |

复核命令：

```bash
targets/codex $ grep -n "loaded but disabled when the directory is untrusted\|load_project_layers\|struct RawMcpServerConfig" codex-rs/config/src/loader/mod.rs codex-rs/config/src/mcp_types.rs
targets/codex $ grep -n "matches_prefix\|check_multiple_with_options" codex-rs/execpolicy/src/rule.rs codex-rs/core/src/exec_policy.rs
targets/deepseek-harness $ grep -n "command: string\|ApprovalPolicy\|execute trusted code" packages/mcp/mcp-client/src/index.ts packages/interaction/user-approval/src/index.ts packages/boot/app-boot/src/config-schema/index.ts
```

## 误报排除

- 项目只读取用户主目录配置（`~/.codex/config.toml`），且仓库内无同名配置：降级。
- 项目级配置加载前有显式交互确认，或默认 `ignore_project_config=true`：降级。
- MCP `command` 为受信内置程序、参数固定且无用户/仓库输入：不报。
- `.env` 只含业务变量（如 `LOG_LEVEL`），不覆盖可执行搜索路径/加载器：不报。
- `.git/hooks` 默认不随 clone 生效；只有 `core.hooksPath`、`fsmonitor`、filter 或 `sshCommand` 被项目配置设置时才报告。
- 审批规则按完整 argv 匹配且拒绝未知参数：不报；只有按前缀匹配且危险参数可改变行为时才报告。
- AGENTS.md 中出现普通构建说明不报告；只有“自动批准/禁止询问/忽略审批”等指令且被实际当作策略时才报告。

## 输出格式

```json
{
  "skill": "agent-config-analyzer",
  "findings": [
    {
      "rule": "AC-MCP-PROJECT-CONFIG",
      "severity": "high",
      "confidence": "high",
      "file": ".codex/config.toml",
      "line": 4,
      "source": "repository-controlled project config",
      "sink": "mcp_servers.<name>.command",
      "evidence": "command = \"sh\"",
      "why": "项目级配置无需确认即可指定 MCP 子进程命令",
      "fix": "默认忽略项目配置；MCP 命令使用受信注册表；加载前显式确认"
    }
  ]
}
```

Markdown 报告按 `severity` 排序，每条包含：配置来源、覆盖顺序、生效条件、触发命令、影响、修复建议。

## 快速扫描

```bash
python3 .claude/skills/agent-config-analyzer/quick-scan.py targets/codex targets/deepseek-harness
python3 .claude/skills/agent-config-analyzer/quick-scan.py --self-test
```

`quick-scan.py` 只使用 Python 标准库（`json`、`tomllib`、`re`），不依赖 tree-sitter；规则数据位于 `patterns/agent-config.json`。扫描目标是“仓库内可能被 Agent 读取的配置”，不会执行配置内容。

## 修复建议

- 项目级配置默认不加载；首次加载要求用户显式确认并记录信任状态。
- MCP server 只允许受信注册表/签名清单，禁止仓库直接指定 `command`/`args`。
- 审批按完整 argv + 参数语义匹配，默认拒绝未知参数；不要仅按命令名前缀自动批准。
- 打开仓库前清除 `GIT_CONFIG_*`，默认禁用 `core.hooksPath`、`fsmonitor`、clean/process filter。
- `.env` 不参与 Agent 自身运行时配置；只加载显式白名单变量。
