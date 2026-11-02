# 表达规范

适用于所有用户可见文案：`README.md`、`docs/`、`ui/src/`、CLI 帮助与日志、报告模板、演示稿。

## 1. 三条硬规则

1. **先讲动作和产物，再给术语名。** 读者应先知道“这一步做什么、产出什么”，再看到 `finding`、`verify`、`provenance` 这类词。
2. **只描述已实现的行为。** 计划、只读建议、未接入的能力必须显式标注“计划中”“只读”“尚未接入”，不能写成已完成、已发布或已自动执行。
3. **同一概念全文只用一个词。** 代码标识符、JSON 字段、文件名可以保留英文；用户文案必须统一，并在首次出现时给出一句中文定义。

## 2. 禁用词与替换

| 禁用说法 | 统一说法 | 说明 |
|---|---|---|
| 原矿、原始池、收件箱 | **未处理候选** | 指 `status=inbox`；需要技术对应时写“未处理候选（inbox）” |
| 精炼、精炼漏斗 | **自动分类** | 指打分、去重、分流、归档；代码名 `refine` 保留 |
| 唤醒 | **重新评估** / **重新进入队列** | 由输入变化触发，不是拟人化动作 |
| 血缘 | **证据来源链** | 技术对应 `provenance` |
| 影子链路、影子模式 | **只读建议模式** | 英文 `shadow` 仅作字段名或首次括号说明 |
| 飞轮 | **学习循环** / **流程步骤** | 不使用比喻 |
| 回流 | **结果回写** | 未接入时必须写“结果回写尚未接入” |
| 闭环已通 | **只读建议已跑通；尚未完成验证、发布和结果回写** | 不得声称完整闭环 |
| 复现（作为阶段名） | **待验证** | 只有 verify 结论为 `confirmed/reproduced` 时才说“已复现” |
| 晋级、门槛、门禁 | **进入下一阶段的通过条件** / **发布检查** | 按语境拆开，不混用 |
| 台账 | **发现记录表** | 首次出现可写“发现记录表（ledger）” |
| 挖矿、矿场、挖掘工厂 | **批量审计** | 品牌名 `GoldMine` 除外 |
| 攻击切面、切面 | **检查维度** / **攻击面维度** | 不使用“切面” |

## 3. 保留术语与首次写法

以下术语有精确含义，保留原词，但首次出现必须给中文定义。

| 术语 | 首次写法 | 含义 |
|---|---|---|
| finding | 候选问题（finding） | 一条待核实的候选，不等于已确认漏洞 |
| run | 一次审计运行（run） | 一次执行及其产物目录 |
| triage | 初筛（triage） | 按严重度和可达性决定先看哪些 |
| verify | 验证（verify） | 静态检查、环境验证或最小复现，结果分 confirmed/rejected/inconclusive/blocked |
| judge | 独立审核（judge） | 独立模型按固定 schema 判断证据是否成立 |
| provenance | 证据来源链（provenance） | 能重新计算的证据来源，例如 flag 的哈希链 |
| holdout | 留出验证集（holdout） | 训练时不看、用于检验跨项目效果的项目集 |
| flip | 结果翻转（flip） | 同一问题前后结果变化；F→P 为修复，P→F 为回归 |
| utility | 动作收益（utility） | 动作带来的收益减去成本 |
| propensity | 选择概率（propensity） | 某动作被选中的概率，用于加权 |
| trusted | 可信样本（trusted） | 证据来源为 runtime、judge 或 manual；static 不算 |
| occurrence | 单次观测身份（occurrence） | `project/run_id/local_id`，定位一次具体观测 |
| semantic | 同源聚合身份（semantic） | 由证据路径、根因和 CWE 计算，合并多轮审计中的同一问题 |
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
- 发布与结果回写尚未接入 `audit_rsi` CLI，只有库函数和测试覆盖。

### 不可以说

- “闭环已通”“完整闭环已跑通”。
- “已实现生产 RSI”“已自动发布策略”“已自动改变审计流程”。
- “五种动作都已学习”“已证明因果提升”。
- “影子链路”“飞轮”“回流”作为现状描述。

### 标准句式

> 目前只读建议模式已跑通：真实轨迹 → 标签 → 动作收益打分 → 只读建议。可信样本为 0，回放不足，发布和结果回写尚未接入，因此还不能称为完整闭环。

## 6. 提交前检查

```bash
# 1. 禁用词残留
grep -rnE '原矿|原始池|收件箱|精炼|唤醒|血缘|影子链路|影子模式|飞轮|回流|闭环已通' \
  README.md docs ui/src ui/README.md ui/scripts tests \
  | grep -vE 'node_modules|expression-guide|返回流程'

# 2. 行为与文案
bash scripts/ci/fast.sh
cd ui && npm run test:system
```

发现禁用词时，先判断它是不是代码标识符、JSON 字段或历史产物；只改用户可见文案，不改契约字段。
