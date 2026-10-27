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

`smoke` 会检查 `/api/board` 的 5 个目标、601 条原始 finding、25 条精选、8 个 CVE 候选、`/api/live` 结构，并读取一次日志尾部。

## 数据来源

- 每个目标取 `runs/<project>/` 下时间最新、且存在 `audit-report.json` 的一次运行。
- 默认排除 `smoke`、`smoke-real`、`smoke-target`。
- 报告里的 `findings` 或 `vulnerabilities` 会统一归一化；`evidence` / `files` / `location` 合并为可复制证据。
- `run.sh` 的 `.meta/status.json` 优先；没有 status 的 `overnight.sh` / `mine_one.sh` 运行，只要 `claude.rendered.log` 在 30 分钟内有更新，也会识别为 LIVE。
- `ui/data/curated.json` 是二次审计的 25 条精选 finding，按 `project:finding-id` 建立初始分诊状态。
- `ui/data/state.json` 保存手工改动（状态、判定、CVE Tier、备注、关联 CVE）。默认不提交。
- 所有状态变更都只写 `ui/data/state.json`，**不修改原始报告**。

## 列与判定

| 列 | 含义 |
|---|---|
| 收件箱 | 未分诊 |
| 分诊 | 判断可达性、重复、设计意图 |
| 复现 | 版本映射、环境验证、最小 PoC |
| CVE 跟踪 | 去重、披露、CNA 申请 |
| 已关闭 | 误报、重复、已知 CVE、设计限制 |

`verdict`：`TP` 代码级成立、`FP` 误报、`DUP` 重复、`UNCLEAR` 待定。

## 视图

- **Board**：5 列 Kanban，原生拖拽移动状态；卡片显示严重度、判定、CVE Tier、证据数。
- **Live mining**：运行中的 run 在看板顶部显示 LIVE 条（状态、耗时、最后一行日志）；点开进入实时日志抽屉，2 秒刷新，可跳到最新。报告生成后看板自动重载。
- **Table**：按严重度/目标排序，适合批量分诊。
- **Detail drawer**：Brief / Evidence / Agent stream。
  - Brief：改状态、判定、CVE Tier、CVE 状态、关联 CVE、审计备注。
  - Evidence：复制证据路径、打开 `audit-report.md` / `.json`、查看原始 finding JSON。
  - Agent stream：读取 `claude.rendered.log` 尾部，可自动刷新、复制 `run.sh --verify-only` 命令。
- **Filter**：目标、严重度、判定、CVE-only、搜索；范围可切精选 / CVE 候选 / 全部。
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
- 视觉方向按 `oil-oil/oil-ui` 的方法执行：证据档案/现场工作台，不是通用深色 dashboard；压缩展示字 + 等宽证据 + 纸面卡片；一个红色强调，严重度用编码色；避免为每个指标加卡片底板。
- 报告是静态分析结果，UI 会明确标注“未运行时验证”。CVE 结论以人工复核和 `docs/cve-handoff.json` 为准。

## 重置

```bash
printf '{}\n' > ui/data/state.json
```

只重置某条：

```bash
jq 'del(."vllm:F-02")' ui/data/state.json > /tmp/state.json && mv /tmp/state.json ui/data/state.json
```
