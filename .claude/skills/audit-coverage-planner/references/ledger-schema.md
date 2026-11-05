# 覆盖记录格式

```json
{
  "schema_version": 1,
  "project": "verl",
  "source_version": "174888f",
  "generated_at": "ISO 8601",
  "limitations": ["只审计了已识别入口，没有全仓库分母"],
  "entries": [
    {
      "id": "COV-001",
      "area": "verl/trainer/ppo/ray_trainer.py:120",
      "view": "permission",
      "risk": "high",
      "hypothesis": "未校验的配置可以控制本地执行入口",
      "status": "unchecked",
      "evidence": [],
      "missing_evidence": ["调用方", "认证条件", "实际入口"],
      "next_action": "使用 audit-hypothesis-tracer 追踪到真实入口",
      "history": [],
      "review_conditions": ["新技能版本", "新增调用方"],
      "skill_versions": [
        {"name": "audit-coverage-planner", "sha256": "64 位十六进制摘要"}
      ],
      "conclusion": "",
      "limitations": ["尚未读取调用方"]
    }
  ]
}
```

字段约束：

- `view`：`coverage`、`entry`、`dataflow`、`reachability`、`guard`、`permission`、`config`、`review`、`validation` 之一。
- `status`：只允许六种状态；`analyzed` 以上必须有证据。
- `needs_evidence` 必须写 `missing_evidence`。
- `blocked` 必须写 `limitations`。
- `runtime_confirmed` 必须有运行证据和来源；没有可信证据时不要使用。
- `review_conditions` 记录新源码、新调用方、新视角、新假设、新技能版本、新验证条件或独立复查安排。
- `history` 保留旧尝试，不覆盖。

优先级由 `scripts/audit/coverage_ledger.py` 计算，只用于安排检查顺序，不是漏洞结论。
