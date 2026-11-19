# Candidate, TP/FP, and independent-confirmation policy

## Current status

There is no human TP/FP adjudication table and no reference vulnerability list for the four frozen targets in this benchmark:

- `codepr/sol` at `373d84877d22031b45a7f3599297f691eab09230`
- `jedisct1/pure-ftpd` at `b64c56dc81bc4a7fa5d09d76afa59012ca5509a6`
- `obgm/libcoap` at `a4de0faea54d3d548924c8b9f6e67b72a36cbac3`
- `eduardsui/tlse` at `25be48a4f0176b7242d8c5955fc325e92b487838`

The target commits are default-branch snapshots, not historical vulnerable versions paired with a known-bug list. Therefore this benchmark cannot compute recall against a known-bug reference set. An AI subagent adjudication table now exists and records `TP`/`FP`/`UNKNOWN` labels with `label_source=subagent`, `human_confirmed=false`, and `independently_confirmed=false`. These labels are AI adjudications, not human confirmation or independent dynamic confirmation.

Existing files that define the current scope:

- `benchmark/2026-11-17/comparison-summary.json`: statuses, candidate counts, and limitations.
- `benchmark/2026-11-17/comparison-summary.md`: human-readable status and count tables.
- `benchmark/2026-11-17/adjudication/`: subagent rubric, candidate inventory, per-target labels, merged labels, CSV, and counts.
- `benchmark/2026-11-17/full-results/`: per-tool, per-target reports and metadata.
- `benchmark/2026-11-17/revisions.json`: frozen target and tool commits.
- `benchmark/2026-11-17/experiment.json`: model, provider, time limits, and modes.

The historical `data/verified_reports.csv` and `data/projects.csv` snapshot in the Mygoldmine repository is not a reference list for these four targets. It contains no rows for `sol`, `pure-ftpd`, `libcoap`, or `tlse`, and its reports come from Mygoldmine's own strict-verification pipeline rather than a benchmark ground truth.

## How the RepoAudit paper defines TP/FP

Reference: Jinyao Guo, Chengpeng Wang, Xiangzhe Xu, Zian Su, Xiangyu Zhang. "RepoAudit: An Autonomous LLM-Agent for Repository-Level Code Auditing." ICML 2025. https://arxiv.org/abs/2501.18160

The paper's evaluation protocol is:

1. Build the evaluation set from bug reports previously published by existing works, plus new bugs found in the versions used by those works (Section 4.1).
2. Label previously reported bugs as `Old` TPs. `New` bugs are reported as pairs `(m, n)`, where `m` is the number of new bugs found in the historical versions and `n` is the number still present in the latest versions (Table 2).
3. Manually inspect the reports and label them TP or FP. For the industrial-tool comparison, the paper explicitly states: "we manually check the bug reports, label the TPs and FPs" (Appendix B).
4. Compute precision as `TP / (TP + FP)` and report recall as the proportion of previously reported bugs that were reproduced (Appendix E).
5. Report developer confirmation and fixes separately from TP/FP. In the real-world impact table, `TP`/`FP` are distinct from `Con`/`Fix` (Table 4).

In the main experiment, RepoAudit reports 21 `Old` TPs plus 19 `New` TPs, for 40 TPs and 11 FPs, giving 78.43% precision. Fourteen of the 19 new bugs were fixed in the latest commit.

RepoAudit's internal validator is not a human TP/FP label. The tool's Web UI allows a user to classify a report as TP/FP/Unknown and stores the labels locally (`tools/RepoAudit/docs/guide.md:81`). The output field `is_human_confirmed_true` is `false` by default and does not mean that a report has been adjudicated as a false positive.

## What this means for the current benchmark

The current benchmark cannot reproduce the RepoAudit paper's TP/FP protocol without additional work:

- No reference bug list exists for the four frozen snapshots.
- The snapshots are current default-branch revisions, not the historical versions used by prior bug reports.
- No independent human or dynamic adjudication has been performed.
- Rows with timeouts, interrupted runs, missing reports, or JSON parse failures cannot be treated as true negatives or false positives.

The current label layers are:

- `candidate`: a reported item from a tool.
- `tool_internal_validation`: a tool's own filtering, confidence, path-validator, or static-review result.
- `subagent_label`: an AI subagent's `TP`/`FP`/`UNKNOWN` verdict, with `label_source=subagent` and `human_confirmed=false`.
- `independently_confirmed`: a separately reproduced or human-adjudicated result. This field remains `false` for every row.

The subagent table supports source-consistent TP/FP counts and cross-tool root-cause deduplication. It does not support recall, because no reference bug list exists, and it does not establish human confirmation.

## If a human or dynamic TP/FP table is added later

A defensible adjudication table should record at least:

- target and frozen commit;
- tool, target, and report identifier;
- root-cause deduplication key;
- reference bug identifier, if the item reproduces a previously reported bug;
- label: `TP_old`, `TP_new_confirmed`, `FP`, or `unknown`;
- evidence: dynamic reproduction, developer confirmation/fix, or source-level contradiction;
- reviewer identity and review date;
- whether the evidence is independent of the tool that produced the report.

Only after such a table exists can precision be computed as `TP / (TP + FP)`. Recall can be computed only against a defined reference list of known bugs. Candidate counts and subagent labels must remain separate from human confirmation.
