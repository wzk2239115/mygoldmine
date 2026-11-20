# Subagent adjudication: strict and low-impact layers

AI subagent labels only; not human confirmation and not independent dynamic reproduction.

## Headline: source-consistent findings

| Tool | Source-consistent total | TP_security | TP_low | FP | Exclusive root causes |
|---|---:|---:|---:|---:|---:|
| Mygoldmine | 31 | 22 | 9 | 2 | 18 |
| Strix | 24 | 23 | 1 | 0 | 9 |
| Codex Security | 22 | 21 | 1 | 0 | 1 |
| Claude Code Security Review | 7 | 6 | 1 | 0 | 1 |
| RepoAudit | 2 | 2 | 0 | 1 | 0 |

## By target

| Target | Source-consistent total | TP_security | TP_low | FP | UNKNOWN |
|---|---:|---:|---:|---:|---:|
| sol | 33 | 32 | 1 | 2 | 0 |
| pure-ftpd | 9 | 7 | 2 | 1 | 0 |
| libcoap | 21 | 16 | 5 | 0 | 0 |
| tlse | 23 | 19 | 4 | 0 | 0 |

## By tool and target

| Tool | Target | Source-consistent | TP_security | TP_low | FP | Exclusive |
|---|---|---:|---:|---:|---:|---:|
| Mygoldmine | sol | 13 | 12 | 1 | 2 | 7 |
| Mygoldmine | pure-ftpd | 4 | 2 | 2 | 0 | 3 |
| Mygoldmine | libcoap | 8 | 5 | 3 | 0 | 4 |
| Mygoldmine | tlse | 6 | 3 | 3 | 0 | 4 |
| Strix | sol | 6 | 6 | 0 | 0 | 1 |
| Strix | pure-ftpd | 2 | 2 | 0 | 0 | 0 |
| Strix | libcoap | 4 | 4 | 0 | 0 | 0 |
| Strix | tlse | 12 | 11 | 1 | 0 | 8 |
| RepoAudit | sol | 2 | 2 | 0 | 0 | 0 |
| RepoAudit | pure-ftpd | 0 | 0 | 0 | 1 | 0 |
| Claude Code Security Review | sol | 4 | 4 | 0 | 0 | 1 |
| Claude Code Security Review | libcoap | 1 | 0 | 1 | 0 | 0 |
| Claude Code Security Review | tlse | 2 | 2 | 0 | 0 | 0 |
| Codex Security | sol | 8 | 8 | 0 | 0 | 1 |
| Codex Security | pure-ftpd | 3 | 3 | 0 | 0 | 0 |
| Codex Security | libcoap | 8 | 7 | 1 | 0 | 0 |
| Codex Security | tlse | 3 | 3 | 0 | 0 | 0 |

## Caveats

- TP_security is the strict first-pass label. TP_low is a second-pass source-consistent low-impact label.
- Source-consistent total = TP_security + TP_low. It is broader than a security-vulnerability count.
- Labels are AI subagent adjudications, not human confirmation or independent dynamic reproduction.
- Timeout and missing-coverage results are not counted as false negatives.
- Exclusive root causes are issues found only by that tool within the subagent union.
