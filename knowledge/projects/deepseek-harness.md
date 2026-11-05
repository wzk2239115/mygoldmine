# DeepSeek Harness 项目知识卡

- 类型：agent-harness
- 审计 commit：`22ddee37`（提交日期 2026-10-23；最近静态审计 2026-11-02）
- 环境：`env/deepseek-harness/`（planned；Node/pnpm）

> **更新 2026-11-02**：本卡原先记录的 commit 日期（2026-10-27）与本地提交不一致，已更正为提交日期 2026-10-23；结论仍全部为 unverified/static，未做动态确认。

> 下面“已知高价值模式”来自 2026-10-27 的静态审计，默认仍是 **unverified**；
> 只能当线索，必须由 verify-agent 或运行时证据确认。

## 入口

- `packages/api/workspace-files/src/index.ts`（工作区文件读取/定位）
- `packages/api/session-controller/src/media-references.ts`（媒体引用）
- `packages/session/session-log-deepseek/src/index.ts`（会话日志路径）
- `packages/boot/app-boot/src/index.ts`（启动/配置）
- `packages/core/tool-executor-ptc/src/ptc.ts`（程序化工具调用/队列）
- `packages/core/tools/*`、`packages/mcp/mcp-client`、`packages/sandbox/sandbox-local`

## 信任边界

工作区文件、会话日志、媒体引用、项目配置、MCP、工具执行、subprocess/shell、沙箱、本地控制面 HTTP。

## 已知高价值模式（来自 2026-10-27 报告，title 需从 MD 读取）

> **更新 2026-11-02**：以下旧 VULN 编号已重新归并/排除，状态见 GIT 行与“本 commit 新发现”段。

- VULN-001/002：`locateFile` 根因导致工作区外文件读取。**仍存在**，已归并为 INFRA-FS-001（medium，读路径无工作区围栏）。
- VULN-003：媒体引用可触发服务端抓取。**已排除**：media-references 只做本地绝对路径 fs.resolve/stat/readBytes，无出站抓取。
- VULN-004：会话日志路径处理。**已排除/已修复**：`encodeSegment` 中和 `../`、绝对路径、NUL、分隔符与 `.`/`..`。
- VULN-005：`.env` → Git 配置 RCE（有验证产物）。**仍存在**，已归并为 INFRA-CONFIG-001；具体残留面是 `GIT_CONFIG_PARAMETERS`（见下）。
- VULN-006：PTC `pendingQueue` 无界 → 内存耗尽。**已排除**：有 `maxPendingCalls`（默认 128）/`maxMessageBytes` 背压。
- 本地 HTTP control-plane 认证绕过、untrusted search path、prompt injection、sandbox isolation。

## 重复提示

- 001/002 同 `locateFile` 根因。
- 012/017 同为工具明文落盘；008/061 同为无签名/MAC；038/039 与 006 重叠。
- 报告 JSON `title` 为 null，需从 MD/description 恢复。

## 默认配置与开关

- workspace root / allowed paths。
- sandbox 是否默认开启、是否允许 `sandbox-local`。
- MCP server 来源与命令。
- control-plane 是否只绑定回环、是否需要 token。

## 误报排除

- ~~文件读取有 realpath + workspace 前缀校验 → 降级。~~ **更新 2026-11-02**：过时且与代码不符。`fs-sandbox` 只围栏写（“Reads pass through untouched”），`workspace-files.read` JSDoc 明确 “files outside it are allowed”。读路径无工作区前缀校验，见 INFRA-FS-001；不要再把“有前缀校验”当误报理由。
- ~~本地 control-plane 只绑定回环且同用户 → 说明威胁模型。~~ **更新 2026-11-02**：应写成“默认回环（`127.0.0.1:3080`），非回环需显式 `--host`”；回环端口不按 OS 用户隔离。
- 沙箱默认开启、只有显式关闭才逃逸 → opt-in。
- 依赖/配置卫生问题不要与 RCE 同级。

## 验证配方

- 用 `--mode auto` 环境做源码级/导入级验证；Node 依赖安装可能较大。
- ~~对文件读取验证 realpath 边界~~ **更新 2026-11-02**：读路径无围栏可验证，但应验证“读授权允许工作区外”这一预期行为，而不是找 realpath 绕过；不读宿主敏感文件。
- 对 PTC 队列用最小循环验证增长，设内存/超时限制（注意 2026-11-02 复核确认队列有 `maxPendingCalls` 背压，已非漏洞）。
- 对 Git 配置 RCE 只验证配置是否生效，不执行外部命令。

## 下一步优先看（**更新 2026-11-02**）

1. INFRA-CONFIG-001 `.env` → `GIT_CONFIG_PARAMETERS` → 未沙箱 git（High，唯一 High）。
2. INFRA-FS-001 读路径无工作区围栏（原 VULN-001/002）。
3. INFRA-MCP-001/002 MCP 内容无标注 / schema 无界。
4. INFRA-SB-004 auto-review 卸载 fail-open。
5. VULN-003/004/006 已排除（媒体无出站抓取 / 会话日志路径已修复 / PTC 有界），不再优先。

## 六条审计 lane（2026-10-30 run 实证）

本轮按以下边界并行拆分，单点结论必须回到这些 lane 的组合链验证：

1. `config`：`packages/boot/app-boot`、`packages/boot/*`、`packages/preset/*`、`packages/bundle/*`、`AGENTS.md`/`CLAUDE.md`。
2. `process-exec`：`packages/shell/*`、`packages/subprocess/*`、`packages/core/tool-executor-ptc`、`packages/ptc-runtime/*`。
3. `mcp`：`packages/mcp/mcp-client`、`mcp-resources`、`packages/experimental/*-mcp`、browser/computer-use MCP。
4. `sandbox`：`packages/sandbox/*`、`packages/fs/fs-sandbox`、`packages/shell/*-sandbox`。
5. `control-plane`：`packages/api/*-controller`、`packages/credentials/*`、`packages/identity/*`、`packages/settings/*`。
6. `filesystem`：`packages/fs/fs-local`、`packages/fs/fs-sandbox`、`packages/session/session-log-*`、`session-persistence`。

优先组合链：`config→process-exec`（`.env`/`GIT_CONFIG_PARAMETERS`）、`mcp→process-exec`、
`control-plane→terminal/filesystem/credentials`、`sandbox→process-exec/filesystem`、`PTC→process-exec`。

## 2026-11-02 静态审计新增（commit `22ddee37`，全部 unverified/static）

案例：`knowledge/cases/deepseek-harness/2026-11-02-static-audit.md`。本轮 11 findings / 5 hypotheses / 21 rejected，无 confirmed。

- **INFRA-CONFIG-001（high，requires-config）**：`.env` 可注入 `GIT_CONFIG_PARAMETERS` 的残留面。启动层 `BOOTSTRAP_NAMES` 只拒绝 `GIT_CONFIG_GLOBAL/SYSTEM/COUNT`，漏了 `GIT_CONFIG_PARAMETERS`；`scrubbedParentEnv` 也只按 KEY/PASSWORD/SECRET/TOKEN 与 `DSH_` 过滤，不剥 `GIT_*`。该变量透传给未沙箱 git 子进程，被解析为可执行外部命令的配置键。**workspace-changes 每轮 turn/start 自动 git 快照是稳定 sink**；`GIT_CONFIG_COUNT=0` 不能抑制 PARAMETERS。次要 sink：plugin-manager `git ls-remote`。修复：把 `GIT_CONFIG_PARAMETERS` 及相关 `GIT_*` 加入拒绝名单并在 git spawn 处清空。
- **INFRA-FS-001（medium，default）**：读路径无工作区围栏。tool-fs `read/read_image`、`workspaceFiles.read/readBytes/stat`、`/api/file` 均无前缀校验；fs-sandbox 只围栏写。真实影响依赖提示词注入后数据外泄（读授权 ≠ 围栏）。**更正**：知识库旧“文件读取有工作区前缀校验”说法错误。
- **INFRA-MCP-001（medium，requires-config）**：MCP 内容无不可信标注。instructions、工具结果文本、resource 渲染原样进入 systemPrompt/上下文；未复用 web 工具的 `EXTERNAL_WEB_CONTENT_NOTICE`。
- **INFRA-MCP-002（medium，requires-config）**：MCP schema/结果无界。inputSchema/description 原样透传、无字节/数量上限，单条结果无统一字节上限；只有 output.schema 走 `assertSupportedJsonSchema`。
- **INFRA-SB-004（medium，requires-config）**：auto-review 卸载 fail-open。运行时卸载实验插件、root fiber 仍 ACTIVE 时，把 auto 会话切到 `danger-full-access` + `approval: never`（安全组件消失即放宽权限）。修复：回退到最窄模式或拒绝卸载。
- **INFRA-SB-003（medium，opt-in）**：`sdk-minimal` 硬编码 `danger-full-access`，README 已声明需隔离工作区。
- **低危加固项**：INFRA-CP-001（`/plugins`、`/plugins/events` 绕过 Connection.admit）、INFRA-CP-002（内部异常回显）、INFRA-SB-001（Web owner 终端 PTY 不经沙箱，设计能力）、INFRA-SB-005（workspace-write 额外共享 `/tmp`/tmpdir，bwrap 私有 tmpfs 不一致）、INFRA-SB-006（`runnerCommand` 无条件标 `enforcement: full`）。

### 验证配方（供下轮 verify-agent 用）

- INFRA-CONFIG-001：临时目录放 `.env`，仅验证 `GIT_CONFIG_PARAMETERS` 是否进入子进程 env 并被 git 读取配置；不要真正触发 fsmonitor/filter 执行外部命令。用无害配置优先级探针即可，注意旧 git 版本与 gix 差异。
- INFRA-FS-001：先确认 fs-sandbox 只围栏写、read JSDoc 允许工作区外；用工作区外只读文件验证读授权，不读宿主敏感文件。
- INFRA-MCP-001/002：构造最小不可信 MCP server 观察是否加 untrusted 前缀、是否有大小上限；不要外连真实第三方。
- INFRA-SB-004：本地卸载 auto-review 观察会话 preset 是否被静默切到 `danger-full-access`。
