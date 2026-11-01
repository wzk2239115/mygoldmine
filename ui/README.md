# VUL/AI Findings Board

漏洞挖掘 Kanban UI，读取 `runs/<project>/<timestamp>/audit-report.json`，把二次审计结论、CVE 候选和运行日志放在同一个工作台里。

## 启动

```bash
# 生产模式：构建前端 + 启动本地 API/静态服务
bash scripts/ui/start.sh
# 打开 http://127.0.0.1:8787
```

首次运行会自动 `npm install` 和 `npm run build`。也可以手动：

```bash
cd ui
npm install
npm run build
npm start
```

开发模式（Vite HMR + API server）：

```bash
cd ui
node server/index.mjs
# 另一个终端
npm run dev
# http://127.0.0.1:5173
```

环境变量：

```bash
PORT=8787 HOST=127.0.0.1 bash scripts/ui/start.sh
```

`HOST=0.0.0.0` 会把 API 暴露到网络；默认只监听回环，因为报告里可能包含未修复漏洞细节。

## 验证

```bash
# 服务启动后
cd ui
npm run smoke
```

`smoke` 会检查 `/api/board` 结构、统计一致性、至少 25 条人工复核、至少 8 个 CVE 候选，以及 `/api/live` 和日志/轨迹接口。

## 数据来源

- `ui/data/finding-ledger.json` 扫描所有完整有效 run，以 occurrence/semantic 双层身份保留历史独有 finding；运行中、失败或不完整草稿不会替代最新完整报告。没有台账时 UI 回退到旧最新报告路径。
- 默认排除 `smoke`、`smoke-real`、`smoke-target`；报告里的 `findings` 或 `vulnerabilities` 统一归一化。
- `run.sh` 的 `.meta/status.json` 优先；没有 status 的运行按日志更新时间识别 LIVE。
- `ui/data/curated.json` 保存人工复核种子；旧 `project:finding-id` 只有语义唯一时才继承，歧义状态不会套到不同 finding。
- `ui/data/auto-state.json` 合并台账、verify 和 CVE 产物，生成自动路由及 review 资格；红队 review 会重算确定性 flag provenance。
- `ui/data/state.json` 保存手工改动，优先使用 occurrence_id，旧 API 仍可回退到 project:id。
- `scripts/workflow/refine_worker.py` 按 source hash 重算原始池，新证据可唤醒归档；轨迹写入 `rsi/trajectories/refine.jsonl`。
- 优先级：`state.json` > `curated.json` > `refine-state.json` > `auto-state.json` > 默认 inbox。手工变更不修改原始报告。

## 列与判定

| 列 | 含义 |
|---|---|
| 收件箱 | 未进入流程 |
| 分诊 | Critical / High 自动入队；人工判断可达性、重复、设计意图 |
| 复现 | 已有 verify 记录；补版本映射、环境验证、最小 PoC |
| CVE 跟踪 | 先查 NVD/GHSA/项目公告去重，再披露/CNA |
| 已关闭 | 误报、重复、已知 CVE、设计限制 |

自动分诊只代表“值得先看”，不等于漏洞成立；`auto` 徽标表示该状态来自产物而不是人工。`原始池` 是自动评分后未达到晋级门槛的 finding，默认隐藏，不是待办。

`verdict`：`TP` 代码级成立、`FP` 误报、`DUP` 重复、`UNCLEAR` 待定。

## 视图

- **Board**：六阶段流程视图；卡片显示严重度、判定、CVE Tier、证据数，点击或键盘打开详情后修改状态。
- **Live mining**：运行中的 run 在看板顶部显示 LIVE 条（状态、耗时、最后一行日志）；点开进入实时日志抽屉，运行状态每 4 秒轮询，报告生成后看板自动重载。
- **Table**：按严重度/目标排序，适合批量分诊。
- **系统架构**：左侧轨道书图标进入可钻取的架构浏览器，包含目标调度、隔离挖掘、增量报告、质量门、Finding Ledger、端到端流水线、恢复机制、状态优先级、红队隔离边界和 Verification-RSI 门禁。点击任意阶段或组件可查看输入输出、设计契约、实现入口、失败语义和优化检查点，再返回总览。同步维护要求见根目录 `AGENTS.md`。
- **Detail drawer**：Brief / Evidence / Agent stream。
  - Brief：改状态、判定、CVE Tier、CVE 状态、关联 CVE、审计备注。
  - Evidence：复制证据路径、打开 `audit-report.md` / `.json`、查看原始 finding JSON。
  - Agent stream：读取 `claude.rendered.log` 尾部，可自动刷新、复制 `run.sh --verify-only` 命令。
- **Filter**：目标、严重度、判定、CVE-only、待验收、搜索；默认隐藏原始池，只显示已精炼流程。
- **待验收**：只显示通过红队 flag 验证、judge 审核和图文报告门槛的 case；人工在这里做最终验收。
- 深色/浅色主题；状态与筛选保存在浏览器 localStorage。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/board` | 聚合后的项目、findings、统计、liveRuns |
| GET | `/api/live` | 轻量轮询：运行中的 run + 目标状态 |
| GET | `/api/runs` | 所有可读运行摘要 |
| GET | `/api/runs/:project/:runId/log?lines=400` | 渲染日志尾部 |
| GET | `/api/runs/:project/:runId/log.txt` | 完整日志纯文本（去掉 ANSI） |
| GET | `/api/runs/:project/:runId/report.md` | 原始 Markdown 报告 |
| GET | `/api/runs/:project/:runId/report.json` | 原始 JSON 报告 |
| GET | `/api/findings/:project/:id/raw` | 单条原始 finding |
| PATCH | `/api/findings/:project/:id` | 更新状态/判定/备注/CVE 字段 |

## 设计说明

- 交互参考 `siteboon/claudecodeui` 的 workspace shell、侧栏、详情面板和 agent session 组织方式；**没有 vendoring 它的代码**（其许可证为 AGPL-3.0-or-later）。
- 视觉采用中性浅色工作区：白色内容面、浅灰侧栏、细边框和柔和圆角；颜色主要用于严重度、判定、错误和运行状态，深色主题使用中性炭灰。左侧品牌图标为混元 3D 生成的黄金铲子；首页精炼管线保留 3D 工厂主视觉，进入具体流程后切换为轻量计数面板。
- 报告是静态分析结果，UI 会明确标注“未运行时验证”。CVE 结论以人工复核和 `docs/cve-handoff.json` 为准。

## 重置

```bash
printf '{}\n' > ui/data/state.json
python3 scripts/workflow/build_state.py
```

只重置某条：

```bash
jq 'del(."vllm:F-02")' ui/data/state.json > /tmp/state.json && mv /tmp/state.json ui/data/state.json
```
