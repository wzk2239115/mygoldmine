---
name: audit-review-planner
description: 为已有代码区域安排有理由的复审。用于源码、调用方、检查视角、假设、技能版本或验证条件变化后，或按小预算做独立复查；保留历史尝试，不把重复报告算成新增收益。
---

# 审计复审规划

## 何时使用

- 首轮覆盖和假设追踪完成后，需要选择旧区域重新检查。
- 源码版本、调用方、检查视角、假设、技能版本或验证条件发生变化。
- 需要安排独立复查，或需要用少量预算做随机复查来减少长期盲区。
- `hypothesis-critic` 发现旧结论缺少证据，但还没有新验证条件。

## 提前退出

- 覆盖记录为空或没有可复审条目时，说明原因并结束。
- 本轮复审预算已用完，或已有暂停标记时，不新增任务。
- 同一尝试内已经用相同区域、视角、假设和技能版本检查过，且没有新条件时，跳过并记录原因。
- 不因为“想再确认一次”而无限重复；每轮复审必须有预算和停止条件。

## 输入

- `.workspace/findings/coverage-ledger.json`
- `.workspace/findings/hypotheses/`
- `.workspace/reports/findings.normalized.json`（如果已生成）
- 当前技能版本：各技能 `SKILL.md` 的 SHA-256
- 可选验证报告、红队结果、本轮新知识卡或误报排除条件

## 复审条件

满足任一条件才允许创建新的审计尝试：

- 源码版本或关键文件内容变化；
- 新增调用方、入口或部署配置；
- 换检查视角，例如从覆盖改为数据流、权限或可达性；
- 出现新的待验证假设或新的反证；
- 技能版本变化，旧结论需要按新规则复核；
- 验证条件变化，例如有新的环境镜像、运行入口或独立验证记录；
- 明确安排独立复查。

没有上述条件时，允许在预算内随机选择少量条目做复查，但必须记录“随机复查”原因，不能把重复发现算成新增收益。

## 波次与预算

- 复审属于第 3 波，前两波完成后再执行。第 3 波未完成时可在后续有界波次继续，但总波次最多 3 波，每波最多 6 个任务，本次审计运行的分析任务总数最多 18 个。
- 每波只处理上一波新增的源码、调用方、检查视角、假设、技能版本或验证条件；没有新条件时，只在预算内随机复查。
- 同一“区域 + 视角 + 假设 + 技能版本”已经执行过的复审不再创建任务，除非出现新的 `review_conditions`。
- 每波达到 6 个任务或预算上限时停止，记录未安排条目和原因。

## 步骤

1. 读取覆盖记录，排除已经 `runtime_confirmed` 的条目。
2. 优先选择带 `review_conditions` 的条目，再按覆盖计划中的优先检查分数选择。
3. 若仍有预算，按稳定随机种子选择少量其他条目；记录种子和选择理由。
4. 同一尝试内按“区域 + 视角 + 假设 + 技能版本”去重；历史尝试只追加，不覆盖。每个任务写出去重键（`dedup_key`）。
5. 生成复审任务：
   ```bash
   python3 "$MYGOLDMINE_HOME/scripts/audit/coverage_ledger.py" review \
     --ledger .workspace/findings/coverage-ledger.json \
     --out .workspace/findings/review-plan.json \
     --budget "${AUDIT_REVIEW_BUDGET:-3}" \
     --seed "${PROJECT:-audit}"
   ```
6. 把任务交给编排器写入 `security-orchestrator-tasks.json`；每项写清复审原因、波次、预算、去重键、技能版本和期望补齐的证据。
7. 传统分析技能任务交给传统分析任务执行者（`audit-skill-worker`）；需要补调用链、可达性或证据的条目交给 `audit-hypothesis-tracer`。按任务类型选择执行者，不把两种任务混在一起。
8. 复审完成后更新对应条目的 `history`、`review_conditions` 和结论。没有新证据时，不要声称复审提高了覆盖或召回。

## 输出

- `.workspace/findings/review-plan.json` 和 `.md`
- 复审任务清单：`wave`、`coverage_id`、`reason`、`priority`、`skill`、`artifact`、`dedup_key`、`skill_versions`、`expected_evidence`
- 复审后更新后的覆盖记录和假设文件

`skill_versions` 写实际加载技能的名称与对应 `SKILL.md` 的 SHA-256；技能未加载时记录原因，不写完成。

复审条件和去重规则见 [references/review-conditions.md](references/review-conditions.md)。

## 限制

- 同根因的候选问题仍由 `hypothesis-critic` 合并，不能把重复报告算成新增收益。
- 没有完整分母时只报告已识别范围，不声称全仓库覆盖。
- 没有可信标签或独立对照时，不声称真实召回率提高。
- 复审预算是上限，不是必须用完的配额。
- 波次和任务数量上限用于控制预算，不代表剩余区域已经安全。

## 交接

- 传统分析技能任务交给传统分析任务执行者（`audit-skill-worker`），由它按任务描述加载对应技能。
- 需要深入追踪调用链或补齐证据的条目交给 `audit-hypothesis-tracer`。
- 需要合并和校准的候选交给 `hypothesis-critic`。
- 复审带来的新经验交给 `stage-skill-learning`，通过既有候选和独立评估机制处理。
