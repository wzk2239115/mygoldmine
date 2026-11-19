# Subagent TP/FP adjudication

Labels are AI subagent adjudications, not human confirmation and not independent dynamic confirmation. `independently_confirmed` remains false.

## Totals

- Assessed candidates: 89
- TP entries: 74
- FP entries: 8
- UNKNOWN entries: 7
- Duplicate entries: 13
- Unique TP root causes across targets: 42

## By tool

| Tool | Candidates | TP entries | FP entries | UNKNOWN | Duplicates | Unique TP root causes |
|---|---:|---:|---:|---:|---:|---:|
| Mygoldmine | 33 | 22 | 7 | 4 | 0 | 22 |
| Strix | 24 | 23 | 0 | 1 | 1 | 22 |
| RepoAudit | 3 | 2 | 1 | 0 | 1 | 1 |
| Claude Code Security Review | 7 | 6 | 0 | 1 | 0 | 6 |
| Codex Security | 22 | 21 | 0 | 1 | 11 | 11 |

## By target

| Target | Candidates | TP entries | FP entries | UNKNOWN | Duplicates | Unique TP root causes |
|---|---:|---:|---:|---:|---:|---:|
| sol | 35 | 32 | 3 | 0 | 1 | 18 |
| pure-ftpd | 10 | 7 | 3 | 0 | 3 | 4 |
| libcoap | 21 | 16 | 1 | 4 | 9 | 8 |
| tlse | 23 | 19 | 1 | 3 | 0 | 12 |

## By tool and target

| Tool | Target | Candidates | TP | FP | UNKNOWN | Duplicates | Unique TP root causes |
|---|---|---:|---:|---:|---:|---:|---:|
| Mygoldmine | sol | 15 | 12 | 3 | 0 | 0 | 12 |
| Mygoldmine | pure-ftpd | 4 | 2 | 2 | 0 | 0 | 2 |
| Mygoldmine | libcoap | 8 | 5 | 1 | 2 | 0 | 5 |
| Mygoldmine | tlse | 6 | 3 | 1 | 2 | 0 | 3 |
| Strix | sol | 6 | 6 | 0 | 0 | 0 | 6 |
| Strix | pure-ftpd | 2 | 2 | 0 | 0 | 0 | 2 |
| Strix | libcoap | 4 | 4 | 0 | 0 | 1 | 3 |
| Strix | tlse | 12 | 11 | 0 | 1 | 0 | 11 |
| RepoAudit | sol | 2 | 2 | 0 | 0 | 1 | 1 |
| RepoAudit | pure-ftpd | 1 | 0 | 1 | 0 | 0 | 0 |
| Claude Code Security Review | sol | 4 | 4 | 0 | 0 | 0 | 4 |
| Claude Code Security Review | libcoap | 1 | 0 | 0 | 1 | 0 | 0 |
| Claude Code Security Review | tlse | 2 | 2 | 0 | 0 | 0 | 2 |
| Codex Security | sol | 8 | 8 | 0 | 0 | 0 | 8 |
| Codex Security | pure-ftpd | 3 | 3 | 0 | 0 | 3 | 0 |
| Codex Security | libcoap | 8 | 7 | 0 | 1 | 8 | 0 |
| Codex Security | tlse | 3 | 3 | 0 | 0 | 0 | 3 |

## Caveats

- Labels are AI subagent adjudications, not human confirmation and not independent dynamic confirmation.
- A TP label is a source-consistent defect assessment. A FP label requires source-level contradiction.
- UNKNOWN includes feature-gated, runtime-dependent, or report-insufficient cases.
- Timeout and missing-coverage results are not counted as false negatives.
- Unique TP root causes are deduplicated by subagent root_cause_key; they are not a CVE count.
- Claude tlse has two assessed candidates from an unparsed execution log; its structured report remains invalid.
