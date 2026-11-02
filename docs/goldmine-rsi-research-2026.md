# 2026 年 RSI 研究调研与 Goldmine 映射

调研时间：2026-11-02。以下结论均来自论文原文或作者官方页面，聚焦 recursive self-improvement / self-improving agents，而不是把普通多轮反思都包装成 RSI。

## 1. 总体判断

2026 年较有工程价值的路线不是无约束地让模型重写自己，而是：**固定安全边界，围绕轨迹、验证器、harness、候选版本和发布门禁形成可审计闭环**。Goldmine 最适合走这条路线。

| 论文 | 核心机制 | 对 Goldmine 的直接启示 |
|---|---|---|
| [Self-Harness: Harnesses That Improve Themselves](https://arxiv.org/abs/2606.09498) | Weakness Mining → 最小 harness 修改 → held-in/held-out 非回归验收 | 从红队/verify 失败轨迹聚类可复用弱点；每轮只修改声明过的策略表面，候选不过门禁就不发布 |
| [AgentDevel: Reframing Self-Evolving LLM Agents as Release Engineering](https://arxiv.org/abs/2601.04620) | 单一版本线、可执行诊断、P→F/F→P flip 门禁 | 不只看平均效用；必须记录每个 finding/项目从通过到失败的回归，保留不可变候选和回滚 |
| [Recursive Self-Improvement through Multi-Agent Self-Supervision](https://arxiv.org/abs/2610.12176) | 多智能体工作流搜索与自评估交替，优质团队轨迹回流训练 | 红队 attacker、victim harness、judge 的轨迹应按角色保留；可研究团队轨迹，但自评不能替代独立证据 |
| [Model–Harness Co-evolution for Recursive Self-Improvement](https://arxiv.org/abs/2608.13951) | build–update–rebuild、verified sibling trajectories、证据平面 | 同一 finding 的候选 harness 应保留成对成功/回归/近失样本；未来模型更新后要重建匹配的 harness |
| [DiscoveryRSI: Recursively Learning to Discover Valuable Hypotheses](https://arxiv.org/abs/2610.23839) | 假设树、credit attribution、harness replay、rediscovery | finding 不只是标签，还应有根因、调查决策、替代解释和可证伪性；可研究假设级信用分配 |
| [Recursive Self-Improvement in AI: From Bounded Self-Refinement to Autonomous Research Loops](https://arxiv.org/abs/2607.07663) | 1,250 篇论文 taxonomy、验证层级、闭环程度与崩溃风险 | 验证器强度决定 RSI 上限；形式/运行时验证强于自评，且“决定什么值得验证”仍是上游人类问题 |

## 2. 关键证据

### Self-Harness

- 固定基座模型和评估器，仅从执行轨迹挖掘模型特定弱点。
- 候选修改必须最小、针对具体失败机制，并通过 held-in 与 held-out 非回归规则。
- Terminal-Bench-2.0 上，三个模型 held-out pass rate 分别由 40.5%→61.9%、23.8%→38.1%、42.9%→57.1%。这些是论文设定内的结果，不能直接外推到 Goldmine。

### AgentDevel

- 把 agent 当作可发布制品，每轮只产生一个 RC，保留规范版本线。
- 强调 P→F 回归和 F→P 修复，而不是只看平均分。
- WebArena 消融中，完整方案 P→F 为 3.1%，移除 flip gate 后为 14.8%，并出现 4 次 bad release。这支持 Goldmine 采用逐 finding/逐项目回归门禁。

### MASS

- 同一基座模型扮演多个角色，搜索工作流，再把优质团队轨迹蒸馏回模型。
- 两轮后，四个开放研究 benchmark 上每输出 token 得分为基座的 1.2–1.6 倍。
- 论文同时提醒：模型自评可能强化共同盲点。Goldmine 的 judge 与 flag provenance 必须保持独立。

### HELIX / Model–Harness Co-evolution

- harness 不仅决定今天如何执行，也决定明天能学到什么轨迹。
- 证据平面保留 trace、测试、策略决定和 provenance；verified siblings 包含成功、回归、近失和替代方案。
- 论文报告的 200-slot sibling slice 产出 438 条 SFT/critic/filter/preference 记录，说明丰富轨迹比单一 success bit 更有学习价值。

### DiscoveryRSI

- 将假设信用、工作流 replay 和再发现连接起来。
- 两轮后假设质量从 4.86 提升到 5.39，并有初步专家评估；但其生命科学领域结果不能直接视为安全漏洞发现效果。

### 2026 综述

- 验证层级从形式验证器到内在自评，实证 improvement 强度与验证层级相关。
- 主要风险包括 self-confirming loops、模型/多样性崩溃与计算预算。
- “选择什么值得评估”不能仅靠提高 judge 分数解决，需要人类研究方向与安全先验。

## 3. Goldmine 当前差距

截至本轮代码与数据检查：

- 经验池有 986 条 occurrence，真实 actionable verify 支持从 0 修复为 6 条 static 样本。
- `trusted_support=0`，生产发布仍被拒绝；不能声称生产 RSI 或因果 uplift。
- `verify-report.json` 和 `auto-state.json` 原先未完整进入经验池，已在本轮修复。
- 新增 `redteam-experience` 适配：run 级结果与 step 级 attacker 工具事件分层，只有可重算 provenance 的 runtime/judge 才自动获得可信标签；`not_captured` 保持 unknown。
- 新增 `redteam-weakness`：按项目类型、攻击模型、失败类别和严重度形成确定性证据签名，输出支持度、成本和候选 editable surface；只做 Weakness Mining，不自动修改 harness。
- 自动路由可以提供确定性动作与 propensity，但不等于探索数据；matched-action replay 不能证明替代动作会更好。
- 红队 HTTP lab、flag provenance 和独立 judge 是强证据来源，但当前覆盖和协议范围仍有限。

## 4. 建议的短期与中期路线

短期：

1. 持续增加真实 verify / runtime / judge 标签，按 occurrence/semantic 防泄漏。
2. 为每个动作保留 pre-action context、成本、结果和证据等级。
3. 增加逐 finding P→F/F→P 与跨项目 holdout，不只汇报平均 utility。
4. 保持 shadow-only，直到 trusted support、holdout 与统计门禁真实满足。

中期：

1. 在声明过的 harness 表面做 Weakness Mining 和最小候选修改。
2. 建立 attacker / scenario / judge 多角色轨迹库与 verified siblings。
3. 用基线对照和项目级 bootstrap 评估真实提升，失败候选保留回滚。
4. 最后再研究模型参数更新；不要把开放式自我修改当作起点。
