# Subagent adjudication artifacts

This directory contains a TP/FP/UNKNOWN adjudication of every reported candidate in the 2026-11-17 comparison.

## Label source

Labels were produced by four AI subagents, one per target, using `adjudication-rubric.md`. They are **AI subagent adjudications**:

- `label_source = subagent`
- `human_confirmed = false`
- `independently_confirmed = false`

They are not human confirmation and not independent dynamic reproduction. The user requested that subagent verdicts be used directly as TP/FP labels; this directory records that provenance explicitly.

## Files

- `candidates.json`: candidate inventory extracted from the tool reports.
- `sol.json`, `pure-ftpd.json`, `libcoap.json`, `tlse.json`: per-target subagent verdicts.
- `all.json`: merged 89 candidate verdicts.
- `labels.csv`: compact label table.
- `summary.json`: counts by tool, target, and tool-target pair.
- `summary.md`: human-readable summary tables.

## Coverage

- 89 candidates were assessed: 87 structured or partial report entries plus 2 Claude/tlse sections recovered from an unparsed execution log.
- 13 entries are marked as duplicates of another candidate.
- RepoAudit libcoap/tlse had no persisted candidates for adjudication because their completed categories reported zero and other categories timed out; those missing categories remain unknown, not false negatives.
- Timeout, interrupted, and parse-failure coverage is preserved in the original result status. No false-negative count is produced.

## Totals

- TP entries: 74
- FP entries: 8
- UNKNOWN entries: 7
- Unique TP root causes across targets: 42
