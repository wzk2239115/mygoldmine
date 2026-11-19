# Cross-tool audit comparison: 2026-11-17

This directory contains the aggregated results of a five-tool, four-target security audit comparison on frozen source snapshots.

## Files

- `comparison-summary.md`: human-readable status and candidate-count tables.
- `comparison-summary.json`: machine-readable rows, status definitions, and limitations.
- `labeling-policy.md`: TP/FP status, the RepoAudit paper's labeling protocol, and the missing reference-list requirements.
- `adjudication/`: AI subagent TP/FP/UNKNOWN labels for every reported candidate, with rubric, merged labels, and counts.
- `experiment.json`: model, provider, time limits, modes, and revision policy.
- `revisions.json`: frozen target and tool commits.
- `target-sizes.json`: target size statistics.
- `results/<tool>.json`: per-tool status and count breakdown.
- `full-results/`: per-tool, per-target report artifacts; credentials and private runtime state are excluded.

## Reading the results

Raw candidate counts are not true vulnerability counts. Several runs reached the one-hour limit, one Claude Code Security Review run has an invalid structured report, and some RepoAudit categories did not finish. Missing or unparsed results are not treated as zero.

No reference vulnerability list exists for the four frozen targets, so precision and recall cannot be computed. An AI subagent TP/FP/UNKNOWN adjudication table now exists in `adjudication/`; its labels are not human confirmation and not independent dynamic confirmation. See `labeling-policy.md`.

## Excluded material

Credentials, `provider.env`, private tool state, source snapshots, raw session traces, and setup-attempt records are not published. `full-results/` contains report artifacts but not those private materials.
