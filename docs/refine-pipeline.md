# 精炼漏斗与自动处理队列

目标不是把 956 条 finding 全部送进 verify，而是先用低成本策略把明显不值得人工看的条目筛掉，只把少数候选送进复现、CVE 去重和人工验收。

```text
原始 finding
  -> 自动评分 / 去重 / 证据门槛
  -> 未达门槛：archived（归档，不占主视图）
  -> 达标：triage（分诊）
  -> 有 verify：reproduce（复现）
  -> CVE 候选：cve（去重/跟踪）
  -> 精品：review（待验收）
  -> 人工最终验收（CVE 去重之后、披露之前）
```

## 后台 worker

```bash
bash scripts/workflow/refine_worker.sh start
bash scripts/workflow/refine_worker.sh status
bash scripts/workflow/refine_worker.sh pause
bash scripts/workflow/refine_worker.sh resume
bash scripts/workflow/refine_worker.sh stop
bash scripts/workflow/refine_worker.sh once
```

- 默认每批 20 条，间隔 5 秒；`REFINE_BATCH`、`REFINE_INTERVAL` 可调。
- 运行状态写入 `ui/data/refine-queue.json`，决策写入 `ui/data/refine-state.json`。
- `scripts/ui/start.sh` 默认启动 worker；`REFINE_WORKER=0` 可关闭。
- `mine_one_docker.sh` 每次审计结束会补跑一个批次。
- 归档条目没有删除；它们仍在原始报告中，只是默认不进入看板主视图。

## 自动决策

- `archived`：低优先级、证据不足、重复项；不是“已确认漏洞”。
- `triage`：Critical、High、评分达到阈值。
- `reproduce`：已有 verify 记录或 CVE Tier 候选。
- `review`：CVE 候选或源码级已验证项，进入人工验收队列。
- 人工状态仍然优先于自动状态。

## RSI 轨迹

worker 每条决策都会追加一条 JSONL 到：

```text
rsi/trajectories/refine.jsonl
```

字段包括 `features`（severity、verified、confidence、cve_tier、verify_verdict、evidence_count）、`decision`、`reason`、`score`、`run_id`。后续 RSI 可以：

1. 用人工验收结果和 verify 结果给轨迹补标签。
2. 学习哪些特征组合容易进入 review。
3. 调整阈值和排序策略，减少漏报和无效复现。
4. 把新策略回放到历史轨迹，再更新 worker。

轨迹是自动化的“经验层”；不是漏洞证据，也不会直接改写 finding 的严重度。
