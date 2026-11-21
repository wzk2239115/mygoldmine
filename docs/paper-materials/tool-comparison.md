# Tool comparison on frozen snapshots

Reference set: 53 unique source-consistent root causes. TP/FP are unique root causes; FN = reference size - TP. Precision = TP/(TP+FP); recall = TP/reference size.

| Target | Mygoldmine TP/FP/FN | Precision | Recall | Strix TP/FP/FN | Precision | Recall | RepoAudit TP/FP/FN | Precision | Recall | Claude Code Security Review TP/FP/FN | Precision | Recall | Codex Security TP/FP/FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sol | 13/2/6 | 86.7% | 68.4% | 6/0/13 | 100.0% | 31.6% | 1/0/18 | 100.0% | 5.3% | 3/1/16 | 75.0% | 15.8% | 8/0/11 | 100.0% | 42.1% |
| pure-ftpd | 4/0/2 | 100.0% | 66.7% | 2/0/4 | 100.0% | 33.3% | 0/1/6 | 0.0% | 0.0% | 0/0/6 | — | 0.0% | 2/1/4 | 66.7% | 33.3% |
| libcoap | 8/0/4 | 100.0% | 66.7% | 4/0/8 | 100.0% | 33.3% | 0/0/12 | — | 0.0% | 0/1/12 | 0.0% | 0.0% | 7/1/5 | 87.5% | 58.3% |
| tlse | 6/0/10 | 100.0% | 37.5% | 10/2/6 | 83.3% | 62.5% | 0/0/16 | — | 0.0% | 2/0/14 | 100.0% | 12.5% | 3/0/13 | 100.0% | 18.8% |
| Total | 31/2/22 | 93.9% | 58.5% | 22/2/31 | 91.7% | 41.5% | 1/1/52 | 50.0% | 1.9% | 5/2/48 | 71.4% | 9.4% | 20/2/33 | 90.9% | 37.7% |

Per-candidate table labels: `benchmark/2026-11-17/adjudication/table-labels.json`. Six source-consistent candidates are marked FP in this table layer.
