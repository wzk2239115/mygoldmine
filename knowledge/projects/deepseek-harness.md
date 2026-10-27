# DeepSeek Harness 项目知识卡

- 类型：agent-harness
- 审计 commit：`22ddee37`（2026-10-27）
- 环境：`env/deepseek-harness/`（planned；Node/pnpm）

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

- VULN-001/002：`locateFile` 根因导致工作区外文件读取。
- VULN-003：媒体引用可触发服务端抓取。
- VULN-004：会话日志路径处理。
- VULN-005：`.env` → Git 配置 RCE（有验证产物）。
- VULN-006：PTC `pendingQueue` 无界 → 内存耗尽。
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

- 文件读取有 realpath + workspace 前缀校验 → 降级。
- 沙箱默认开启、只有显式关闭才逃逸 → opt-in。
- 本地 control-plane 只绑定回环且同用户 → 说明威胁模型。
- 依赖/配置卫生问题不要与 RCE 同级。

## 验证配方

- 用 `--mode auto` 环境做源码级/导入级验证；Node 依赖安装可能较大。
- 对文件读取验证 realpath 边界，不读宿主敏感文件。
- 对 PTC 队列用最小循环验证增长，设内存/超时限制。
- 对 Git 配置 RCE 只验证配置是否生效，不执行外部命令。

## 下一步优先看

1. VULN-005 `.env` → Git 配置 RCE。
2. VULN-001/002 工作区外读取。
3. VULN-003 媒体抓取边界。
4. 本地 control-plane 认证与 sandbox 默认。
