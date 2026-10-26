# Phase 1 总结：公开漏洞 → 能力差距 → 新增 skill 接入

- 生成时间：2026-10-27
- 覆盖任务：T01-T05
- 结论：Phase 1 完成。新增 2 个 P0 skill 并接入 `project-profiler` / orchestrator / README；AI 基础设施审计从「无自动调度」变为「按项目特征条件触发」。P1/P2 缺口尚未落地，见 §4。

## 1. 输入与产出

| 任务 | 产物 | 关键数字 |
|------|------|----------|
| T01 公开漏洞汇总 | `research/disclosed-vulns.md`、`research/disclosed-vulns.json` | 38 条 / 29 个 type；codex、deepseek-harness、vLLM、SGLang、verl 均 ≥3 条 |
| T02 能力盘点 | `research/capability-matrix.md` | 82 个含 `SKILL.md` 的 skill；3 个可执行 agent；7 个 quick-scan（4 个依赖 tree-sitter）；强覆盖 8 / 弱覆盖 14 / 无覆盖 7 个 type |
| T03 差距分析 | `research/gap-analysis.md` | 15 个缺口覆盖 26/38 条；P0 5、P1 7、P2 3 |
| T04 新 skill | `.claude/skills/model-loading-analyzer/`、`.claude/skills/agent-config-analyzer/` | 各含 `SKILL.md`、`quick-scan.py`、`patterns/*.json`；真实代码位置引用 vLLM `20bf65ad`、SGLang `3a62cdfb`、verl `174888fc`、codex `970111f6`、deepseek-harness `22ddee37` |
| T05 接入 | `security-orchestrator.md`、`.claude/skills/README.md`、根 `README.md`、`project-profiler/SKILL.md`、本文件 | 条件触发 + 显式调用两条路径；命名过滤不变 |

## 2. 已补齐的 P0 缺口

| 缺口 | T01 代表条目 | 新 skill | 核心判定 |
|------|--------------|----------|----------|
| G01 模型加载信任边界 | vLLM `CVE-2026-27893`、`CVE-2025-66448` | `model-loading-analyzer` | 不可信模型源 + `trust_remote_code` / `auto_map` / `get_class_from_dynamic_module` |
| G04 Agent 项目级配置信任 | codex `CVE-2025-61260` | `agent-config-analyzer` | 仓库内 `.codex/config.toml` / `.mcp.json` 无确认生效，MCP `command`/`args` 可执行任意程序 |
| G07 命令审批绕过 | codex `CVE-2025-54558` | `agent-config-analyzer` | 审批按首 token 前缀匹配，危险参数/别名可绕过 |
| G08 Git 信任链（触发链部分） | codex `CVE-2026-19590/19593/19592` | `agent-config-analyzer` | `core.hooksPath`、`fsmonitor`、clean/process filter、`attr.tree` |
| G02 的 HF 加载链（部分） | verl `CVE-2025-50461`、SGLang `CVE-2026-15976` | `model-loading-analyzer` | `torch.load(weights_only=False)` 与 `from_pretrained` 串联；普通 `pickle.loads` 仍交 `insecure-deserialization-analyzer` |

## 3. 接入结果

1. `.claude/agents/security-orchestrator.md`：在「子任务 Skill 过滤规则」后新增「AI 基础设施条件任务」，按依赖/文件特征追加两个新 skill；条件任务仍须通过 `-scanner` / `-analyzer` 命名过滤与 `artifact + skill` 去重。
2. `.claude/skills/project-profiler/SKILL.md`：后端 HTTP 服务的基础列表保持 `web-auth-analyzer` + `sensitive-info-scanner`，新增按特征追加条件任务；输出 JSON 可直接包含新 skill。
3. `.claude/skills/README.md`：补充本仓库命名约定、内置例外，以及两个新 skill 的适用项目特征与 `quick-scan.py` 用法。
4. 根 `README.md`：核心能力、快速脚本、工作流、目录结构加入新 skill；「支持的扫描器」拆为「可被显式调用的扫描器」与「自动调度路径」，修正原先把显式调用误写成自动调度的误导。
5. `research/phase1-summary.md`：本文件。

命名过滤复核：

```bash
grep -n '以 `-scanner` 结尾\|以 `-analyzer` 结尾' .claude/agents/security-orchestrator.md
# 命中现有过滤规则，未被条件任务段落改写

for d in .claude/skills/model-loading-analyzer .claude/skills/agent-config-analyzer; do
  basename "$d"   # 均以 -analyzer 结尾
done
```

## 4. 未完成与已知限制

### P1（尚未落地）

| 缺口 | T01 代表条目 | 建议目标 |
|------|--------------|----------|
| G03 Host 头 → 路由认证绕过 | vLLM `CVE-2026-48746`、deepseek-harness `CVE-2026-82533` | 扩展 `web-auth-analyzer` + `http-header-injection-analyzer` |
| G05 模型权重/管理端点外泄 | SGLang `CVE-2026-15978`（Unverified） | 扩展 `access-control-analyzer` + `sensitive-info-scanner` |
| G06 沙箱边界与逃逸 | deepseek-harness `CVE-2026-101078` 等 | 新 skill `agent-sandbox-analyzer`（orchestrator 已预留提示，未接入） |
| G09 可执行文件搜索路径 | deepseek-harness `CVE-2026-95182` | 扩展 `command-injection-analyzer` |
| G10 SSRF 解析器差异 | vLLM `CVE-2026-25960` | 扩展 `ssrf-analyzer` |
| G11 管理端点凭据泄露 | SGLang `CVE-2026-15977`（Unverified） | 扩展 `sensitive-info-scanner` |
| G15 SafeUnpickler 允许列表绕过 | SGLang `CVE-2026-15969`（Unverified） | 扩展 `insecure-deserialization-analyzer` |

### P2（尚未落地）

- G12 可达 `assert` DoS、G13 高复杂度 `data_hash` DoS、G14 eval + 反序列化组合复核（分别扩展 `error-boundary-analyzer`、`dos-attacks-analyzer`、现有规则回归）。

### 环境与编排限制

- **O02 tree-sitter 依赖未锁定**：宿主机缺 `tree_sitter_language_pack` 时，4 个 tree-sitter quick-scan 无法启动。两个新 skill 的 `quick-scan.py` 只用标准库，不受影响；T07 Dockerfile 需显式安装。
- **O03 `case-studies-analyzer` 不可加载**：目录无 `SKILL.md`，本轮未新增依赖；新 skill 自带 `patterns/` 与真实位置表。
- **`agent-sandbox-analyzer` 未创建**：G06 仍为缺口，orchestrator 只记录提示，不会追加任务。
- **T01 的 Unverified 条目**：`CVE-2026-15969/15971/15974/15976/15977/15978` 无 CVSS，未据其写死规则；`verl-issue-5331` 为非 CVE issue。
- **本轮未运行真实挖矿**：仅做静态文档与脚本接入；`quick-scan.py --self-test` 在 T04 已验证。

## 5. 下一步（Phase 2）

按 `.agent/tasks.json` 优先级进入 T06：阅读 exploitgym 的 Claude Code 运行器与日志收集实现，产出 `docs/docker-claude-mining.md`，为容器化挖掘与 `claude.rendered.log` 协议定稿。

## 6. T15 总验收补充（2026-10-27）

Phase 2（T06-T10）与 Phase 3（T11-T14）已落地，本轮执行总验收：

- `scripts/mine/verify.sh` 默认扫描 `runs/`，对 T10 冒烟产物 `runs/smoke/20261026T174149Z` 退出 0：`通过=1 失败=0 错误项=0`。
- 根 `README.md` 新增「整夜并行挖掘（Phase 3）」，说明今晚 `clone_targets.sh` → `overnight.sh start`，明早 `overnight.sh status` → `runs/<project>/<timestamp>/` → `verify.sh` 的完整路径。
- `.gitignore` 覆盖 `targets/`（保留 `targets/manifest.json`）、`runs/`、`logs/`、`.agent/history/`。
- 本节为 Phase 1 总结的收尾记录；P1/P2 缺口仍未落地，不因总验收而视为已修复。
