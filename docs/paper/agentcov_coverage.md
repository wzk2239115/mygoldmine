# AgentCov: Measuring Observed Audit Coverage

## Scope

GoldMine uses a vendored AgentCov adapter to record source-code exposure during stage II (security auditing). The integration observes successful tool results and associates observations with declared audit tasks. It measures what code was exposed to an agent, not whether the agent understood that code or proved it secure. The vendored revision is `d9b1f7abcfbe9262dc9abab988d6b3bc92dd944a`.

## Collection and attribution

1. Before an `Agent` or `Task` dispatch, the collector expects five separately declared fields: `AUDIT_INTENT_ID`, `AUDIT_INTENT`, `COVERAGE_ID`, `HYPOTHESIS`, and `AUDIT_SCOPE`. This provides task-level attribution, rather than an inferred rationale for every tool call.
2. Successful `Read`, `Grep`, and supported `Bash` outputs are processed through the AgentCov Claude adapter. The collector uses returned evidence to infer file and line ranges; requested ranges alone are insufficient.
3. At subagent completion, the collector can recover observations by matching successful tool results to tool-use identifiers in the subagent transcript.
4. Source paths are normalized against the target, and observations carry source-version and file-hash information. Failed tools are recorded as collection errors. A `Read` response without parseable bounds produces an `unknown` observation with no credited line range.
5. The summary deduplicates events using session, transcript, tool-use identifier, file, observation kind, file hash, and serialized ranges. It groups observations by file, hash, intent, and kind. It preserves missing attribution instead of inventing an intent.

The event count is not a count of distinct lines. Search observations are not automatically equivalent to a full source read. Downstream line-based calculations explicitly use `kind == "read"` with valid file and range information.

## Distinct lines and incremental coverage

For a file f, let R_f be the union of valid inclusive read intervals. The distinct observed line count is:

```text
L = sum_f |R_f|
|[a,b]| = b - a + 1
```

The reward implementation merges overlapping and adjacent intervals, then subtracts previously credited intervals. Previously seen state is keyed by source version, relative file path, and file hash. Re-reading unchanged lines under that identity does not earn additional coverage credit. This is identity-based accounting, not semantic equivalence across revisions.

Example: reading lines 10–20 and 15–25 exposes 16 distinct lines, not 22. If lines 10–18 were already credited, only lines 19–25 contribute seven new lines.

The collector's summary retains grouped ranges; it does not itself turn all observations into a repository-wide percentage.

## Percentages in the stage-learning scorecard

GoldMine computes several separate indicators in `rsi_scorecard.py`. They have different denominators and must be labeled accordingly.

### Risk-anchor hit coverage

The coverage ledger supplies parseable `file:start-end` evidence anchors. Risk weights are critical=4, high=3, medium=2, low=1, and informational=0.5; an unknown risk label defaults to 0.5. An anchor is counted as hit when any valid read interval overlaps it in the same file:

```text
C_anchor = 100 * sum_a w_a * I(any read overlaps a) / sum_a w_a
```

This is weighted anchor-hit coverage. A one-line overlap credits the whole anchor's weight; it is not the fraction of every line in the anchor read. Anchors are deduplicated within each ledger entry, not globally across all entries. With no parseable anchors, the score is unavailable rather than zero.

### Intent-attribution rate

```text
C_intent = 100 * max(0, observations - unattributed) / observations
```

The denominator is the number of deduplicated observations, including observation kinds that may not qualify for line credit. This measures attribution completeness, not source coverage. With no observations or missing counters, it is unavailable.

### JEV-priority unit hit coverage

For each valid JEV unit u, the scorecard clamps its priority p_u to [0,1] and checks whether any read range overlaps the unit:

```text
C_JEV = 100 * sum_u p_u * I(any read overlaps u) / sum_u p_u
```

This is weighted unit-hit coverage, not line-weighted coverage. Units remain separate contributions even when their ranges overlap. A missing or zero-weight denominator yields an unavailable score.

## Risk-weighted exploration reward

The incremental reward uses a different, line-based calculation. For each previously uncredited read line, let p be the maximum overlapping JEV priority, or zero when no priority exists:

```text
Delta C_risk = sum_(new read lines) [1 + max(overlapping JEV priorities, default 0)]
R = 0.01 * Delta C_risk + 10 * N_new_verified
```

Priorities are clamped to [0,1], so a new line contributes between one and two weighted units. For example, seven new lines with priority 0.8 contribute 12.6 weighted units and 0.126 coverage reward. The verified-report term is separately derived from strict report feedback; it is not a count of static candidates. Missing report feedback leaves the reward partial. Missing source version prevents new coverage credit; absent JEV priorities use the base weight of one.

## Reporting guidance

A defensible description is: “We measured observed source reads, task-level attribution, and risk-prioritized exploration using tool-result-derived intervals.” Do not describe these indicators as executed-code coverage, complete security review, or proof of understanding. A repository-wide percentage requires an explicitly defined, versioned denominator of eligible source lines; this integration's summary does not establish that denominator. Collection errors and unattributed or unknown observations must be reported alongside any metric.

## Implementation references

- [Collector and summary](../../scripts/audit/read_coverage.py): `observe`, `summarize`.
- [Read-only scorecard](../../scripts/stages/rsi_scorecard.py): `_intervals`, `_anchors`, `_overlap`, `_score`.
- [Incremental reward](../../scripts/stages/rsi_reward.py): `merge`, `subtract`, `calculate`.
- [Vendored dependency provenance](../../scripts/vendor/README-agentcov.md).

## Source snapshot

This document describes the restored NAS implementation inspected on 16 November 2026. Repository links are navigation aids; the hashes below identify the exact inspected files, which may differ from another checkout. No benchmark measurements are inferred from these files.

| Source file | SHA-256 |
| --- | --- |
| `scripts/audit/read_coverage.py` | `c9c70d78fb5f6cc8f1be05c58950254b892c84e3aad5753df21ff176553d3c3f` |
| `scripts/stages/rsi_scorecard.py` | `7b8dfa99c309f3fb30ff910ade64458abf4b37ed5a0bddf0a73a7ed0167923fb` |
| `scripts/stages/rsi_reward.py` | `0bc0c5e58b55e66a0c9771c0f37f2ee2b1e5de89f4cacae1123372c751052bd4` |
| `scripts/vendor/README-agentcov.md` | `6c910c4fa186694a26af36f8964b5f02de1dcce7c78d468256608c3562b3f12e` |
