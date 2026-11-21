# Subagent adjudication artifacts

This directory contains a two-layer adjudication of every reported candidate in the 2026-11-17 comparison.

## Label layers

1. **Strict security layer** (`TP_security`, `FP`, `UNKNOWN`): first-pass source review using `adjudication-rubric.md`.
2. **Low-impact layer** (`TP_low`): second-pass review of first-pass `FP`/`UNKNOWN` entries using `low-impact-rubric.md`. A `TP_low` item is source-consistent but has limited or indirect security impact.

`source_consistent_total = TP_security + TP_low`. This is broader than a security-vulnerability count.

All labels are **AI subagent adjudications**:

- `label_source = subagent`
- `human_confirmed = false`
- `independently_confirmed = false`

They are not human confirmation and not independent dynamic reproduction.

## Files

- `candidates.json`: candidate inventory extracted from the tool reports.
- `sol.json`, `pure-ftpd.json`, `libcoap.json`, `tlse.json`: first-pass per-target verdicts.
- `low-impact.json`: second-pass verdicts for first-pass FP/UNKNOWN entries.
- `all.json`: merged 89 candidate verdicts with both layers.
- `labels.csv`: compact label table.
- `summary.json`: counts by tool, target, and tool-target pair.
- `summary.md`: human-readable summary tables.
- `table-labels.json`: per-candidate labels used by `docs/paper-materials/tool-comparison.md`; reference size 53, six source-consistent candidates converted to FP for the table layer.

## Coverage

- 89 candidates were assessed: 87 structured or partial report entries plus 2 Claude/tlse sections recovered from an unparsed execution log.
- 13 entries are marked as duplicates of another candidate.
- RepoAudit libcoap/tlse had no persisted candidates for adjudication because their completed categories reported zero and other categories timed out; those missing categories remain unknown, not false negatives.
- Timeout, interrupted, and parse-failure coverage is preserved in the original result status. No false-negative count is produced.

## Totals

- Source-consistent total: 86
- `TP_security`: 74
- `TP_low`: 12
- `FP`: 3
- `UNKNOWN`: 0
- Unique source-consistent root causes across targets: 53
- Exclusive source-consistent root causes: 29
