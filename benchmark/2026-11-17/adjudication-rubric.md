# Subagent TP/FP adjudication rubric

## Purpose

This rubric is for an AI subagent to review each reported candidate against the frozen source snapshot and the tool report. The resulting label is an **AI adjudication label**, not human confirmation and not independent dynamic confirmation. The label must not be written as `independently_confirmed=true`.

## Inputs

- Frozen source: `/vol1/1000/mygoldmine-benchmark/2026-11-17/targets/<target>/`
- Tool reports: paths in `adjudication/candidates.json`
- Candidate inventory: `benchmark/2026-11-17/adjudication/candidates.json`
- Scope and limitation policy: `benchmark/2026-11-17/labeling-policy.md`

## Label definitions

- `TP`: The report identifies a concrete defect that is consistent with the frozen source. A security-relevant path must be identifiable from attacker-controlled or application-reachable input to the reported sink, and no visible guard, validation, lifetime rule, or configuration invariant in the frozen source defeats the report. Static-only source verification is allowed; record that evidence level.
- `FP`: The frozen source contradicts the report. Examples: the reported code is absent at the frozen commit; a required guard or bounds check is present; the sink is unreachable because of type, lifetime, or control-flow constraints; the report misidentifies the root cause; the described impact requires an impossible state; or the report is only a style/robustness concern with no security-relevant path.
- `UNKNOWN`: The available evidence is insufficient to decide. Examples: the trigger depends on a runtime configuration, allocator behavior, compiler behavior, or external application callback that cannot be resolved from the frozen source and reports; the report is too vague to map to a concrete path; the relevant functions or callers are missing from the snapshot; or only a partial report exists.

Do not use `FP` for a candidate that was not reviewed, was not reported, was cut off by a timeout, or has no structured report. Those are `UNKNOWN`/not assessed. Do not use `FN`; false negatives require a reference list that this benchmark does not have.

## Required evidence

For every label, cite at least one of:

- exact `path:line` locations in the frozen source;
- a quoted guard, validation, or lifetime rule that defeats the report;
- a source-verified call path from entrypoint to sink;
- a statement that the reported location does not exist at the frozen commit.

Do not execute the target, compile it, run scanners, send network traffic, or build exploit payloads. This is a read-only source and report review.

## Duplicate handling

- Deduplicate within a tool by root cause, not merely by title or call-chain length.
- For RepoAudit `sol`, the two NPD records share the same `buggy_value`; label the root cause once and mark the other record as a duplicate.
- Cross-tool duplicates may each receive a TP label because each tool independently reported the bug, but the merged table must carry a shared `root_cause_key` so the final true-bug count can be deduplicated across tools.
- A duplicate is not an FP.

## Output schema

Return a JSON array. Each element must contain:

```json
{
  "candidate_id": "tool:target:report-id",
  "tool": "...",
  "target": "sol|pure-ftpd|libcoap|tlse",
  "title": "...",
  "report_path": "...",
  "label": "TP|FP|UNKNOWN",
  "confidence": "high|medium|low",
  "root_cause_key": "short stable key",
  "duplicate_of": "candidate_id or null",
  "evidence": ["path:line", "guard or source fact"],
  "reason": "short, specific explanation",
  "evidence_level": "static_source|static_plus_runtime_claim|report_only",
  "requires_dynamic_check": true,
  "reviewer": "subagent:<target>",
  "reviewed_at_utc": "..."
}
```

Keep `reason` concise and do not include weaponized payloads. Report-only claims must not be accepted as source-verified evidence.
