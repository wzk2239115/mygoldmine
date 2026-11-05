---
name: audit-hypothesis-tracer
description: 围绕一条审计假设补调用链、输入控制、可达性、防护条件和影响证据，并更新覆盖记录。用于从“看到了可疑代码”推进到可核实结论或明确证据缺口；不把静态命中当漏洞。
---

# 审计假设追踪

## 何时使用

- 覆盖记录中的条目状态为 `unchecked`、`analyzed`、`needs_evidence`、`blocked` 或 `counterevidence`，需要继续补证据。
- 编排器要求围绕一个入口、危险操作、信任边界、权限或配置条件深入追踪。
- 复审计划选中了旧区域，需要换视角或按新条件重新检查。

## 提前退出

- 找不到真实入口、调用方或输入来源时，把状态写为 `needs_evidence`，列出缺失证据，不要猜 `default` 可达。
- 只有关键词、注释、测试代码或文档示例，没有执行路径时，写 `analyzed` 或 `counterevidence` 并说明限制。
- 环境、权限或依赖导致无法继续时，写 `blocked` 和具体原因；不要写成误报。
- 预算或时间用完时，保存当前结论和下一步动作，不继续无限追踪。

## 输入

- 覆盖条目：`.workspace/findings/coverage-ledger.json` 中的 `COVERAGE_ID`
- 已有假设文件：`.workspace/findings/hypotheses/<COVERAGE_ID>.md`
- 项目知识卡、误报排除条件、已发布技能规则
- 可选的验证报告、红队结果、历史复审记录

## 步骤

1. 读取覆盖条目和已有假设，确认本次要验证的具体问题，不要扩大成整个仓库扫描。
2. 沿“输入来源 → 处理过程 → 危险操作”补齐：
   - 输入是否由用户、配置、模型文件、IPC 或环境变量控制；
   - 是否到达真实生产入口，还是只到测试、示例或未调用函数；
   - 认证、白名单、路径规范化、安全加载、沙箱或权限检查是否阻止利用；
   - 影响需要哪些前置条件，是否需要特定配置、版本或调用顺序。
3. 每条结论必须附可核实的 `path:line` 或运行证据。没有证据的推断保留为假设。
4. 记录已有反证；反证不是“没发现漏洞”，而是能排除路径的具体条件。
5. 更新覆盖条目的 `status`、`evidence`、`missing_evidence`、`history`、`next_action`、`conclusion`、`limitations` 和 `skill_versions`。历史尝试追加，不覆盖。
6. 运行校验：
   ```bash
   python3 "$MYGOLDMINE_HOME/scripts/audit/coverage_ledger.py" validate \
     --ledger .workspace/findings/coverage-ledger.json
   ```
7. 写入 `.workspace/findings/hypotheses/<COVERAGE_ID>.md`，并在返回给编排器的任务列表中说明：
   - 新确认或新排除的路径；
   - 还缺什么证据；
   - 下一步应交给 `hypothesis-critic`、验证智能体还是复审计划。

## 输出

- 更新后的 `.workspace/findings/coverage-ledger.json`
- `.workspace/findings/hypotheses/<COVERAGE_ID>.md`
- 一个简短结果：`status`、证据、缺口、下一步动作

## 证据要求

- 代码证据：文件路径、行号、关键片段和调用关系。
- 运行证据：命令、返回码、输出摘要和可重算的来源。
- 配置证据：配置键、默认值、覆盖位置和生效条件。
- 没有证据时不得把 `analyzed` 写成 `runtime_confirmed`。
- 不能把 `blocked` 写成 `counterevidence`，也不能把 `counterevidence` 写成“安全”。

详细证据清单见 [references/evidence-checklist.md](references/evidence-checklist.md)。

## 交接

- 需要合并、去重、校准严重度：交给 `hypothesis-critic`。
- 需要动态确认：交给 `verify-agent` 或红队流程；技能本身不执行验证。
- 复审：把新条件写入 `review_conditions`，交给 `audit-review-planner`。
- 经验：把可复用判断和证据交给 `stage-skill-learning`，只提交候选。
