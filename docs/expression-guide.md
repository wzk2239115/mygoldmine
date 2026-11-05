# 表达规范

适用于所有用户可见文案和项目说明：`AGENTS.md`、`README.md`、`docs/`、`knowledge/`、`ui/src/`、CLI 帮助与日志、报告模板、演示稿、agent 指令与提示模板。

## 1. 四条硬规则

1. **中文正文优先使用中文。** 不得把英文内部词直接当作中文句子的主语、谓语或宾语。先让读者看懂“谁做什么、产生什么”，再提供必要的技术对应。
2. **先讲动作和产物，再给术语名。** 读者应先知道“这一步做什么、产出什么”，再看到 `finding`、`verify`、`provenance` 这类词。
3. **只描述已实现的行为。** 计划、只读建议、未接入的能力必须显式标注“计划中”“只读”“尚未接入”，不能写成已完成、已发布或已自动执行。
4. **同一概念全文只用一个中文词。** 需要技术对应时，首次写“中文说明（`标识符`）”，后文只用中文，不在同一段落反复切换中英文。

### 中英混写边界

以下内容可以保留英文：代码标识符、JSON 字段、枚举值、文件名、命令、协议名，以及整体采用英文的 CLI 或文档。保留英文不等于可以把它们直接拼进中文正文；技术引用应放在行内代码或首次括号说明中。

| 不通过 | 应改为 |
|---|---|
| 每个 run 一个沙箱，verify 前 isolate 网络 | 每次审计运行使用独立沙箱；验证前断开网络 |
| worker 消费 finding | 后台处理任务读取候选问题 |
| 不生产 promote | 不发布为生产策略 |
| 白名单 editable surface | 白名单允许修改的范围 |
| agentic 失败后回退 baseline | 智能体辅助失败后恢复基线方案 |
| judge approved 后进入 review 门禁 | 独立审核通过后，检查待人工验收条件 |

新增或修改文案时必须遵守本节。发现同段旧文案存在上述问题时，应在同一轮修改中一并纠正；不得只在旧句子上继续追加新的英文术语。

## 2. 禁用词与替换

| 禁用说法 | 统一说法 | 说明 |
|---|---|---|
| 原矿、原始池、收件箱 | **未处理候选** | 指 `status=inbox`；需要技术对应时写“未处理候选（inbox）” |
| 精炼、精炼漏斗 | **自动分类** | 指打分、去重、分流、归档；代码名 `refine` 保留 |
| 唤醒 | **重新评估** / **重新进入队列** | 由输入变化触发，不是拟人化动作 |
| 血缘 | **证据来源链** | 技术对应 `provenance` |
| 效用学习 | **成本与收益评估** | 面向用户说明比较各处理方式的成本与收益；`utility` 字段保留 |
| 弱点聚类 | **找出反复出现的执行失败** | 先说明统计哪些真实失败、得到什么统计结果，再说明用于安排优先检查；代码名 `redteam-weakness` 保留 |
| Holdout + Flips 评估 | **跨项目验证与前后结果对比** | 技术字段与产物名保留；正文说明验证项目未参与训练 |
| 影子链路、影子模式 | **只读建议模式** | 英文 `shadow` 仅作字段名或首次括号说明 |
| 飞轮 | **学习循环** / **流程步骤** | 不使用比喻 |
| 回流 | **结果回写** | 未接入时必须写“结果回写尚未接入” |
| 闭环已通 | **只读建议已跑通；尚未完成验证、发布和结果回写** | 不得声称完整闭环 |
| 复现（作为阶段名） | **待验证** | 只有 verify 结论为 `confirmed/reproduced` 时才说“已复现” |
| 晋级、门槛、门禁、质量门 | **进入下一阶段的通过条件** / **发布检查** / **完整性检查** | 按实际检查内容命名，不混用 |
| 断点续跑 | **恢复未完成项目** / **从中断处继续** | 直接说明恢复时会处理哪些项目 |
| 失败语义 | **失败时如何处理** | 直接说明失败后保留什么、是否重试 |
| 红队 lab | **隔离环境验证** | 说明攻击端能访问什么、不能访问什么，以及哪些场景不会执行 |
| 台账、Finding Ledger | **发现记录表** | 首次出现可写“发现记录表（ledger）”；正文先说明如何编号和归并问题 |
| 挖矿、矿场、挖掘工厂 | **批量审计** | 品牌名 `GoldMine` 除外 |
| 攻击切面、切面 | **检查维度** / **攻击面维度** | 不使用“切面” |

## 3. 保留术语与首次写法

以下术语有精确含义，保留原词，但首次出现必须给中文定义。

| 术语 | 首次写法 | 含义 |
|---|---|---|
| finding | 候选问题（finding） | 一条待核实的候选，不等于已确认漏洞 |
| run | 一次审计运行（run） | 一次执行及其产物目录 |
| triage | 初筛（triage） | 按严重度和可达性决定先看哪些 |
| priority | 优先检查分数（priority） | Jev 为代码块生成的 0 到 1 分数，用于安排检查顺序 |
| flags | 风险信号（flags） | 达到阈值的风险类型及分数，例如认证边界或危险反序列化 |
| mitigations | 已有防护措施（mitigations） | 路径白名单等已有防护及分数，会降低优先检查分数 |
| verify | 验证（verify） | 静态检查、环境验证或最小复现，结果分 confirmed/rejected/inconclusive/blocked |
| judge | 独立审核（judge） | 独立模型按固定 schema 判断证据是否成立 |
| provenance | 证据来源链（provenance） | 能重新计算的证据来源，例如 flag 的哈希链 |
| holdout | 留出验证集（holdout） | 训练时不看、用于检验跨项目效果的项目集 |
| flip | 前后结果变化（flip） | 同一问题前后结果变化；F→P 为修复，P→F 为回归 |
| utility | 动作收益（utility） | 动作带来的收益减去成本 |
| propensity | 历史动作被选中的概率（propensity） | 历史流程当时选中某动作的概率，用于加权 |
| trusted | 可信样本（trusted） | 证据来源为 runtime、judge 或 manual；static 不算 |
| occurrence | 单次观测身份（occurrence） | `project/run_id/local_id`，定位一次具体观测 |
| semantic | 同一问题编号（semantic） | 由证据路径、根因和 CWE 计算，合并多轮审计中的同一问题 |
| reviewReady | 待人工验收条件（reviewReady） | 派生条件，不是可保存的 status |

## 4. 状态词规范

- 流程状态只有六个：`inbox`、`triage`、`reproduce`、`cve`、`closed`、`archived`。
- `review` 不是 status。用户界面可显示“待人工验收”，技术对应 `reviewReady`，成立条件是：红队拿到 flag、judge 审核通过、证据来源链可重算、图文报告和场景图齐全。
- `verdict` 分三层，必须带限定语：
  - 候选判定：`untriaged` / `tp` / `fp` / `duplicate` / `unclear`
  - 验证结论：`confirmed` / `rejected` / `inconclusive` / `blocked`
  - 审核结论：`approved` / `rejected` / `needs_review`
- `tp` 只表示“源码级成立”，不等于运行时已验证；`confirmed` 才表示动态复现。
- `status=cve` 只表示“CVE 候选/跟踪中”，不代表已有 CVE 编号。

## 5. RSI 专章

### 可以说

- 当前固定五动作词表：`verify`、`deep_read`、`human_review`、`duplicate_candidate`、`defer`。
- 训练支持 91 条，全部为 `static`；按动作仅 `deep_read` 25 条、`defer` 66 条有样本，其余三种为 0。
- 可用于动作训练的 `trusted` 样本为 0；现有 20 条人工结论因缺动作记录未进入训练。
- 回放状态为 `insufficient`，当前没有 `flips` 产物。
- 只读建议模式输出 `recommendation_only=true`、`state_change=none`。
- 挖掘修复已进入单项目与批量主流程：`Claude Code` 学习节点组合多个技能生成修复 `Markdown`，候选实际参与隔离重跑和红蓝验证，接受项按共享或仓库专属作用域发布，下一轮加载并可回滚；未评估或评估失败的候选不发布。

### 不可以说

- “闭环已通”“完整闭环已跑通”。
- “已实现生产 RSI”“已证明误报持续下降”“未经评估的候选已自动发布”。
- “五种动作都已学习”“已证明因果提升”。
- “影子链路”“飞轮”“回流”作为现状描述。

### 标准句式

> 验证资源学习目前只生成只读建议：可信样本为 0，回放不足，验证动作策略不发布。挖掘修复已在主流程执行“`Claude Code` 学习节点组合多个技能生成修复 `Markdown` → 候选实际参与隔离重跑与红蓝验证 → 分作用域发布 → 下一轮加载 → 版本回滚”；只有接受项会发布，证据不足或执行失败时保持候选，不宣称生产效果已经得到证明。

## 6. 提交前检查

```bash
# 1. 全量覆盖率，以及相对基线是否新增问题
python3 scripts/ci/check_expression.py \
  --baseline scripts/ci/expression-baseline.json \
  --allow-unreadable .claude/skills/integer-overflow-analyzer/general.md \
  --allow-unreadable .claude/skills/numeric-conversion-error-analyzer/general.md

# 2. 保存完整候选清单，供人工判断和清理
python3 scripts/ci/check_expression.py \
  --json-output .workspace/expression-audit.json \
  --limit 0

# 3. 行为与文案
bash scripts/ci/fast.sh
cd ui && npm run test:system
```

扫描结果是候选，不代表所有英文都要删除。先判断它是不是代码标识符、JSON 字段、历史证据、产品名、协议名或漏洞标准名称；只改不必要的中文正文混写，不改机器契约。

基线用于防止新增问题，行号变化不会误报。清理存量并人工复查后，才能用 `--write-baseline scripts/ci/expression-baseline.json` 重建基线；不得为了隐藏本轮新增问题而直接更新基线。两个文件目前无法按文本解码，扫描报告会单独列为“无法读取、未纳入扫描”，不计入已读覆盖率。
