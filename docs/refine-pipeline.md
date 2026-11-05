# 自动分类与自动处理队列

目标不是把 956 条候选问题（finding）全部送入验证，而是先用低成本策略把明显不值得人工看的条目筛掉，只把少数候选送进待验证、CVE 去重和人工验收。

```text
未处理候选
  -> 自动评分 / 去重 / 证据检查
  -> 未达通过条件：archived（归档，不占主视图）
  -> 达标：triage（分诊）
  -> 验证结论为 confirmed 或属于 CVE 分级候选：reproduce（待验证）
  -> CVE 候选：cve（去重/跟踪）
  -> 通过全部自动条件：待人工验收
  -> 人工最终验收（CVE 去重之后、披露之前）
```

自动分类只负责把 `inbox` 分成 `triage` 和 `archived`；后续 `triage -> verify -> reproduce/closed` 和
`reproduce -> red-team -> review` 由 `flow_worker.py` 处理。它不会越过候选验证或独立审核的通过条件。

## 后台处理任务

```bash
bash scripts/workflow/refine_worker.sh start
bash scripts/workflow/refine_worker.sh status
bash scripts/workflow/refine_worker.sh pause
bash scripts/workflow/refine_worker.sh resume
bash scripts/workflow/refine_worker.sh stop
bash scripts/workflow/refine_worker.sh once
```

- 默认每批 20 条，间隔 5 秒；`REFINE_BATCH`、`REFINE_INTERVAL` 可调。`--loop` 在空队列时等待并继续扫描，不会退出；新候选问题到达后可自动进入处理。
- 运行状态写入 `ui/data/refine-queue.json`，决策写入 `ui/data/refine-state.json`。
- `scripts/ui/start.sh` 默认启动后台处理任务；`REFINE_WORKER=0` 可关闭。
- `mine_one_docker.sh` 每次审计结束会补跑一个批次。
- 归档条目没有删除；它们仍在原始报告中，只是默认不进入看板主视图。

## 自动决策

- `archived`：低优先级、证据不足、重复项；不是“已确认漏洞”。
- `triage`：严重或高危，或者评分达到阈值。
- `reproduce`（待验证）：存在 `confirmed` 验证结论或属于 CVE 分级候选；不表示已经复现。
- 待人工验收：必须经过红队捕获随机标记、独立审核（judge）通过，并且图文报告已生成，才进入人工验收。
- `flow-state.json` 记录自动流转的验证和红队结果；人工状态仍然优先于自动状态，自动流转高于自动分类。
- `cve`：仍由人工或 CVE 裁定产物推进，不由自动流转创建。

## RSI 轨迹

后台处理任务会把每条决策追加为一条 JSONL 记录：

```text
rsi/trajectories/refine.jsonl
rsi/trajectories/flow.jsonl
```

字段包括 `features`（`severity`、`verified`、`confidence`、`cve_tier`、`verify_verdict`、`evidence_count`）、`decision`、`reason`、`score`、`run_id`。后续 RSI 可以：

1. 用人工验收结果和候选验证结果给轨迹补标签。
2. 学习哪些特征组合容易达到待人工验收条件。
3. 调整阈值和排序策略，减少漏报和无效验证。
4. 把新策略回放到历史轨迹，再更新后台处理任务。

轨迹是自动化的经验记录；不是漏洞证据，也不会直接改写候选问题的严重度。
