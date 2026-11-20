# Cross-tool security audit comparison: frozen snapshots

Experiment date: 2026-11-17. This directory contains aggregated results only.

## Scope

Five AI-assisted security audit tools were run against four open-source C/C++ repositories.
Each tool-target combination had a one-hour wall-clock limit. The target revisions are frozen in `revisions.json`.

| Tool | sol | pure-ftpd | libcoap | tlse |
|---|---|---|---|---|
| Mygoldmine | Completed; 15 raw | Timeout, partial; 4 raw | Timeout, partial Markdown; 8 raw | Timeout, partial; 6 raw |
| Strix | Timeout, partial; 6 raw | Timeout, partial; 2 raw | Timeout, partial; 4 raw | Timeout, partial; 12 raw |
| RepoAudit | Partial timeout; 2 raw, 1 dedup | Partial timeout; 1 raw, 1 dedup | Partial timeout; 0 persisted, NPD, MLK unknown | Partial timeout; 0 persisted, NPD unknown |
| Claude Code Security Review | Completed; 4 raw | Completed; 0 raw | Completed; 1 raw | Invalid JSON parse failure; 2 unparsed |
| Codex Security | Completed; 8 raw | Completed; 3 raw | Completed; 8 raw | Completed; 3 raw |

## Result validity

- 8 of 20 combinations completed with a valid structured report: Mygoldmine/sol, three Claude Code Security Review runs, and all four Codex Security runs.
- 11 combinations are partial because they reached the one-hour limit or because some RepoAudit categories did not finish.
- 1 combination is invalid: Claude Code Security Review/tlse exited without a parseable report. Its execution log contains two unparsed vulnerability sections, which are not counted as structured findings.
- Missing, timed-out, or unparsed results are not treated as zero-vulnerability results.

## Candidate counts

Counts are raw report entries, not true vulnerabilities. Only RepoAudit/sol was deduplicated: two persisted NPD records share the same `buggy_value` root cause and reduce to one reported issue.

| Tool | sol | pure-ftpd | libcoap | tlse |
|---|---|---|---|---|
| Mygoldmine | 15 | 4 | 8 | 6 |
| Strix | 6 | 2 | 4 | 12 |
| RepoAudit | 2 raw / 1 dedup | 1 raw / 1 dedup | 0 persisted / unknown | 0 persisted / unknown |
| Claude Code Security Review | 4 | 0 | 1 | n/a (invalid) |
| Codex Security | 8 | 3 | 8 | 3 |

## Tool configurations

- Mygoldmine: stage-II audit mode with DeepSeek V4.1 Flash and JEV triage. Full blue-team, red-team, and independent review stages were not run.
- Strix: full-source, standard mode, DeepSeek V4.1 Flash, USD 10 estimated cost cap. All four runs were interrupted by the one-hour limit and produced partial reports.
- RepoAudit: NPD, MLK, and UAF categories, up to 1200 seconds per category, four neural workers. Only the provider base URL was adapted; the detection algorithm was not modified.
- Claude Code Security Review: adapted full-source review with DeepSeek V4.1 Flash. Upstream audit and filtering prompts were retained; this is not an Anthropic default-model result.
- Codex Security: adapted custom provider using the 360 `/v1` Responses endpoint and DeepSeek V4.1 Flash. Earlier "official access required" status was superseded by actual runs.

## Limitations

- Raw candidate counts are not true-positive counts, precision, recall, vulnerability counts, CVE counts, or a tool ranking.
- Tool-internal filtering and validation are not a shared independent ground truth; independently confirmed counts remain unknown.
- Model, provider, scope, and source settings were adapted and differ from official product defaults.
- Timeout and interrupted reports are partial. Missing reports and unfinished categories must not be read as zero vulnerabilities.
- Cross-tool deduplication has not been performed. RepoAudit sol raw records are deduplicated by persisted buggy_value root-cause key.
- The targets are frozen default-branch snapshots, not historical vulnerable versions with a ground-truth set.
- Tool-internal validation is not independent confirmation. The independent confirmation count remains unknown for every row.
- This is not a historical vulnerable-version recall experiment with a ground-truth set.

## Excluded material

Raw reports, candidate descriptions, proof-of-concept payloads, execution logs, session traces, source snapshots, provider credentials, and private state are not included in this directory.

## AI subagent adjudication

AI subagent labels only; not human confirmation and not independent dynamic reproduction. `TP_security` is the strict layer. `TP_low` is a second-pass source-consistent low-impact layer. `source_consistent_total = TP_security + TP_low`.

| Tool | Source-consistent total | TP_security | TP_low | FP | Exclusive root causes |
|---|---:|---:|---:|---:|---:|
| Mygoldmine | 31 | 22 | 9 | 2 | 18 |
| Strix | 24 | 23 | 1 | 0 | 9 |
| Codex Security | 22 | 21 | 1 | 0 | 1 |
| Claude Code Security Review | 7 | 6 | 1 | 0 | 1 |
| RepoAudit | 2 | 2 | 0 | 1 | 0 |

By target:

| Target | Source-consistent total | TP_security | TP_low | FP | UNKNOWN |
|---|---:|---:|---:|---:|---:|
| sol | 33 | 32 | 1 | 2 | 0 |
| pure-ftpd | 9 | 7 | 2 | 1 | 0 |
| libcoap | 21 | 16 | 5 | 0 | 0 |
| tlse | 23 | 19 | 4 | 0 | 0 |

Exclusive root causes are issues found only by that tool within the subagent union. They are not ground-truth vulnerabilities.
