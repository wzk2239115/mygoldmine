# Second-pass low-impact classification

## Purpose

The first pass used a strict security-TP standard. This second pass reviews only entries labeled `FP` or `UNKNOWN` and asks whether they are still source-consistent defects with limited or indirect security impact.

This produces a secondary label without changing the strict `TP` labels.

## Labels

- `TP_low`: the defect is consistent with the frozen source, but impact is limited or indirect. Examples: hardening gap, bounded resource leak, fail-closed availability issue, protocol correctness affecting integrity, latent OOB requiring non-default configuration, or a crypto weakness with constrained exposure.
- `FP`: the frozen source contradicts the report, or there is no source-consistent defect at all.
- `UNKNOWN`: the source evidence is insufficient to decide.

Do not use `TP_low` for a report that merely restates intended default behavior with no defect. Do not use `FP` merely because dynamic proof is absent.

## Evidence

Cite exact frozen-source `path:line` facts. Read-only review; do not build or execute.

## Output

Write a JSON array to `adjudication/low-impact.json`. Each element:

```json
{
  "candidate_id": "...",
  "original_label": "FP|UNKNOWN",
  "secondary_label": "TP_low|FP|UNKNOWN",
  "reason": "short source-specific reason",
  "evidence": ["path:line", "source fact"],
  "reviewer": "subagent:low-impact",
  "reviewed_at_utc": "..."
}
```

Review every entry whose current label is `FP` or `UNKNOWN` exactly once.
