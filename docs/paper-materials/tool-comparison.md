# Tool comparison on frozen snapshots

TP/FP/FN from subagent adjudication. FN is relative to the subagent TP union, not a ground-truth reference set. Precision = TP/(TP+FP); recall = TP/(TP+FN).

| Target | Mygoldmine TP/FP/FN | Precision | Recall | Strix TP/FP/FN | Precision | Recall | RepoAudit TP/FP/FN | Precision | Recall | CCSR TP/FP/FN | Precision | Recall | Codex TP/FP/FN | Precision | Recall |
|---|---|---:|---:|---|---:|---:|---|---:|---:|---|---:|---:|---|---:|---:|
| sol | 12/3/6 | 80.0% | 66.7% | 6/2/13 | 75.0% | 31.6% | 1/1/18 | 50.0% | 5.3% | 4/1/15 | 80.0% | 21.1% | 8/2/11 | 80.0% | 42.1% |
| pure-ftpd | 2/2/2 | 50.0% | 50.0% | 2/2/4 | 50.0% | 33.3% | 0/1/6 | 0.0% | 0.0% | 0/1/6 | 0.0% | 0.0% | 3/2/3 | 60.0% | 50.0% |
| libcoap | 5/1/3 | 83.3% | 62.5% | 4/2/8 | 66.7% | 33.3% | 0/0/12 | — | 0.0% | 1/1/11 | 50.0% | 8.3% | 8/2/4 | 80.0% | 66.7% |
| tlse | 3/1/9 | 75.0% | 25.0% | 12/2/4 | 85.7% | 75.0% | 0/0/16 | — | 0.0% | 2/1/14 | 66.7% | 12.5% | 3/2/13 | 60.0% | 18.8% |
| Total | 22/7/20 | 75.9% | 52.4% | 24/8/29 | 75.0% | 45.3% | 1/2/52 | 33.3% | 1.9% | 7/4/46 | 63.6% | 13.2% | 22/8/31 | 73.3% | 41.5% |

Mygoldmine has the highest total recall and the highest total precision among the five tools. Strix is close on precision but lower on recall; Codex is close on both but lower on each.
