# GoldMine：从漏洞矿藏到可信证据

算法团队汇报稿 · RSI 与红队模型 · 2026-11-02

## 01 封面

**GoldMine：从漏洞矿藏到可信证据**  
RSI × 红队模型 × 可验证的算法闭环  
关键词：发现、验证、学习、非回归发布

## 02 一句话理解 GoldMine

**它不是“更会的扫描器”，而是一套把安全研究过程变成证据与经验的系统。**

目标源码 → 静态候选 → 持久沙箱验证 → 红队证明 → 经验学习 → 受控发布

已实现的基础：Finding Ledger、增量报告、持久沙箱、HTTP 红队 lab、独立 judge、Verification-RSI shadow。

## 03 为什么需要算法团队

**开发团队让系统“能运行”，安全团队让判断“够专业”，算法团队让系统“能从证据中变得更好”。**

- 算法团队：轨迹建模、策略与奖励、验证器、效用学习、跨项目泛化、RSI 发布门禁。
- 开发团队：容器、API、UI、任务调度、可靠性、工程交付。
- 安全团队：威胁情报、漏洞先验、规则、人工裁决、披露规范。

这是协作分工，不是能力高低；缺少算法闭环，Goldmine 就只能重复执行固定规则。

## 04 挖掘：先得到可追溯候选

- 每个项目独立 run，原始源码只读，工作副本可写。
- 持久沙箱复用依赖、工作区和产物，挖掘后可继续 shell 与 verify。
- Jev 只做召回，security-orchestrator 组织攻击面审计。
- 报告必须增量落盘，并通过 schema、证据字段、语言与完整性质量门。

**静态 finding 是研究假设，不是已成立漏洞。**

## 05 红队模型：不是单个“攻击模型”

红队能力 = 模型策略 + 执行 harness + 隔离 lab + 独立 judge + 可回放轨迹。

- Attacker：在受限容器中探索允许的攻击路径。
- Victim：运行真实服务，flag 随机且只存在 victim 侧。
- Judge：独立审核目标漏洞、证据、作弊风险与可复现性。
- Scenario：按 finding 与源码 hash 绑定，当前 HTTP 之外明确 blocked。

## 06 红队证据链：为什么可信度更高

- 内部网络，attacker 无宿主、无 Docker socket、无 flag 直读路径。
- flag 只能来自真实工具输出，最终回答本身不是证据。
- judge schema 与确定性 flag provenance 双重校验。
- flag + judge approved + 图文报告，三者齐全才进入人工验收。

**核心不是“模型说攻破了”，而是“系统能证明它确实发生了”。**

## 07 从轨迹到经验：RSI 的数据基础

每次决策保留：occurrence / semantic 身份、动作前上下文、策略与 propensity、成本、结果、证据等级和来源哈希。

验证层级：static < runtime < judge < manual。

本轮修复：`verify-report.json` 与 `auto-state.json` 现在能进入经验池；有结果但无动作的样本不再被静默丢弃。新增 `redteam-experience`：run 级结果与 step 级 attacker 工具事件分层，provenance 通过后才赋予 runtime/judge 标签。

## 08 Goldmine 的 RSI 闭环

轨迹 → 标签与效用 → 训练 → 跨项目 holdout → matched-action replay + outcome flips → 统计门禁 → shadow / 不可变候选 → 受控发布

- 学习 verify / deep_read / human_review 等动作效用，而不是模仿报告文本。
- refine worker 在空队列时保持常驻扫描，新 finding 和新证据能持续进入经验链。
- 自动路由的确定性 propensity 不代表探索，回放不宣称因果 uplift。
- `verify-flips` 按 semantic 观测 F→P 修复与 P→F 回归，不冒充反事实评估；默认候选门禁要求覆盖率 ≥0.8、至少一个修复、零回归。
- 版本可审计、可回滚，失败候选不进入生产。

## 09 真实现状：闭环已通，可信数据仍是瓶颈

- 986 条 occurrence 经验记录。
- 本轮前：可训练 verify 支持为 0；本轮后：6 条真实 static 动作样本。
- `trusted_support = 0`：生产发布继续拒绝。
- 红队 lab 覆盖与协议范围仍需扩大，runtime/judge 标签是下一阶段重点。

**这不是失败，而是门禁在正确工作。当前只能叫 shadow RSI，不能宣称生产自我进化。**

## 10 2026 年研究地图

- Self-Harness（2606.09498）：弱点聚类、最小 harness 修改、held-out 非回归。
- AgentDevel（2601.04620）：单版本线、可执行诊断、P→F/F→P 发布门禁。
- MASS（2610.12176）：多智能体工作流与团队轨迹回流。
- HELIX（2608.13951）：模型–harness 共进化、verified siblings、证据平面。
- DiscoveryRSI（2610.23839）：假设信用、replay 与再发现。
- RSI 综述（2607.07663）：1,250 篇论文，验证层级决定闭环上限。

## 11 对 Goldmine 的技术选择

**走“有边界的 harness RSI”，不做无约束自我修改。**

短期：真实标签、动作覆盖、逐 finding 非回归、跨项目 holdout。

中期：用 `redteam-weakness` 做确定性失败聚类，通过 `harness-propose` 生成有稳定身份的最小候选，再以 outcome flip gate 验证；同步积累 verified siblings 和多角色轨迹。

长期：在证据充分后研究模型更新，并为新模型重建匹配的 harness。

## 12 算法团队的五个工作包

1. 数据与身份：轨迹、标签、成本、血缘、语义防泄漏。
2. 策略与奖励：动作效用、成本约束、探索与基线。
3. 红队环境：场景生成、执行协议、真实 flag 与失败分类。
4. 评估器：judge、provenance、验证层级、人类复核接口。
5. 发布科学：holdout、flip gate、bootstrap、版本与回滚。

开发团队与安全团队是这些工作包的共同交付伙伴。

## 13 建议的 90 天验收指标

- trusted 标签覆盖至少 3 个独立项目，runtime/judge 样本持续增长。
- 动作标签超过 100 条，并覆盖 verify / deep_read / human_review 多类动作。
- 每次候选都有跨项目 holdout、逐 finding P→F/F→P 与基线对照。
- 红队从 HTTP 扩展到真实新协议执行器，不用包装冒充支持。
- 不满足门禁时保持 shadow，不为了展示指标放松标准。

这些是建议目标，不是当前完成度。

## 14 为什么这件事值得做

GoldMine 把一次性的“跑扫描、看报告”变成持续积累的安全研究资产：

- 对分析人员：更少重复环境搭建，更清晰的证据和漫画式解释。
- 对算法团队：可学习、可评估、可比较的策略改进闭环。
- 对组织：每一次挖掘、验证和失败，都能成为下一次更好的依据。

**让每一次挖掘，都成为下一次更好的证据。**

## 15 论文与实现依据

- https://arxiv.org/abs/2606.09498
- https://arxiv.org/abs/2601.04620
- https://arxiv.org/abs/2610.12176
- https://arxiv.org/abs/2608.13951
- https://arxiv.org/abs/2610.23839
- https://arxiv.org/abs/2607.07663

实现依据：`audit_rsi/`、`scripts/redteam/`、`scripts/mine/`、`scripts/env/sandbox.sh`、`docs/system-architecture.md`。
