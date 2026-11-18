# Cross-tool audit comparison: 2026-11-17

This directory contains the aggregated results of a five-tool, four-target security audit comparison on frozen source snapshots.

## Files

- `comparison-summary.md`: human-readable status and candidate-count tables.
- `comparison-summary.json`: machine-readable rows, status definitions, and limitations.
- `experiment.json`: model, provider, time limits, modes, and revision policy.
- `revisions.json`: frozen target and tool commits.
- `target-sizes.json`: target size statistics.
- `results/<tool>.json`: per-tool status and count breakdown.

## Reading the results

Raw candidate counts are not true vulnerability counts. Several runs reached the one-hour limit, one Claude Code Security Review run has an invalid structured report, and some RepoAudit categories did not finish. Missing or unparsed results are not treated as zero.

No independent confirmation was established for any row. The independent-confirmation count remains unknown.

## Excluded material

Raw findings, candidate descriptions, proof-of-concept payloads, execution logs, session traces, source snapshots, credentials, and private state are not published here.
