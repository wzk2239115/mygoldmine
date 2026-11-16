# JEV: Fast Risk Triage Before Deep Auditing

## Role in GoldMine

GoldMine uses JEV through the SystemOne API as a structured decision service for initial source-code triage. It asks bounded questions about a file or code block, converts the returned answers into an inspection priority, and directs subsequent deep auditing toward promising regions. A high priority means “inspect this region first,” not “this region contains a confirmed vulnerability.”

The integration defaults to the model alias `typesafe/jev-latest` and the `/v1/systemone` endpoint. The requested alias and returned model should be recorded for reproducibility. The repository demonstrates the client workflow; it does not expose JEV's training procedure, parameter count, internal architecture, or inference implementation.

## Processing pipeline

### 1. Select and bound the input

The client selects eligible source paths using path lists, glob filters, and exclusions. It filters sensitive paths and applies its implemented redaction before constructing units. These controls reduce exposure but are not a guarantee that arbitrary source code is free of secrets; review inputs before external transmission.

A unit contains a relative path, source text, and a line range. The default character budget is 12,000. Files can be split by a configured line-block size or character budget. These bounds reduce per-request context, but may hide relationships across units. The chosen splitting mode and truncation budget therefore belong in the experimental configuration.

### 2. Ask structured questions

Profiles specify questions about security-relevant behavior, such as authentication boundaries, control-plane operations, model loading, outbound requests, or configuration trust. The API receives source text as `state` and a map of typed `questions`.

Supported answer forms in this client include:

- `noul`: a scalar decision value, used directly by the scoring function.
- `score`: an ordinal value normalized by `max(1, number_of_criteria - 1)` and clamped to [0,1].
- `choice`: a categorical answer whose returned confidence is used by the generic priority scorer.

All questions for the same input are included in one request rather than issued as a sequence of follow-up calls. This reduces client-side request overhead. The API skill describes parallel question evaluation, but the client code does not establish how the provider schedules model inference internally.

### 3. Compute a transparent inspection priority

Each question is marked as a positive risk signal or a mitigation signal. Let v_q be its normalized answer value:

```text
risk_base = max(v_q for positive questions, default 0)
mitigation = max(v_q for mitigation questions, default 0)
priority = max(0, risk_base - 0.5 * mitigation)
```

The function also records individual risk flags and mitigations when their values meet the configured threshold (default 0.5). That threshold controls the recorded flags; it is not a vulnerability-confirmation threshold. The generic scoring function does not interpret the selected category's security meaning beyond its configured polarity and returned confidence, so profile design matters.

Illustrative calculation: risk values of 0.9 and 0.6, together with a mitigation value of 0.4, produce a priority of 0.7. This is a numerical example, not an observed benchmark or a calibrated probability of exploitation.

### 4. Rank and hand off

Units are sorted by descending priority for subsequent inspection. The default top-k setting is 50. Deep-audit agents then use source reading and cross-file reasoning to assess reachability, trust boundaries, preconditions, and alternative explanations. Dynamic verification and independent review remain separate requirements. A low triage score must not be treated as evidence that a region is safe.

## Why this workflow can be faster

The implemented mechanisms reduce the amount of expensive deep analysis or repeated work:

1. **Bounded decision tasks:** structured classification and ranking replace an open-ended audit narrative during initial triage.
2. **Multiple questions per request:** the same source context serves several decisions without repeated round trips.
3. **Concurrent requests:** a thread pool processes independent requests. The default is eight workers; the implementation bounds concurrency between one and 32.
4. **Optional batching:** more than one unit can share a request, with questions namespaced per unit. The default batch size is one, so batching should not be claimed as active unless configured.
5. **Response caching:** unchanged request groups can reuse stored responses instead of calling the model again.
6. **Ranked deep inspection:** expensive audit reasoning is focused on prioritized regions rather than applied uniformly at the triage step.

These mechanisms explain the intended efficiency; they do not establish a measured speedup, recall advantage, or superiority over another model. Such claims require an experiment with comparable workloads, budgets, model versions, and end-to-end timings.

## Cache and failure semantics

The implemented cache key hashes the requested model identifier, profile name, and each grouped unit's identifier and redacted text. It does not hash the entire question configuration. When changing a profile's instructions or criteria under the same name, disable or invalidate the cache to avoid reusing obsolete decisions. A mutable model alias can also change provider behavior without changing the local cache key.

Requests have timeout/retry handling, and results record cache use, usage, errors, and returned model information. Failed or missing decisions are unavailable evidence, not safe-code classifications. Completion statistics should be checked before interpreting a ranked list as a complete scan.

## Connection to coverage and learning

JEV priorities can guide which code to read next. GoldMine later compares observed AgentCov reads with JEV unit ranges and uses the maximum overlapping priority to weight newly read lines. These are prioritization and process-feedback signals. They do not independently establish a vulnerability, prove that an agent understood the code, or show that skill evolution caused a later discovery.

## Suggested paper wording

“We use JEV as a structured semantic triage service before deep auditing. Source units are evaluated against security-oriented questions, and a deterministic aggregation of risk and mitigation signals produces an inspection priority. Concurrent requests, bounded contexts, and caching reduce repeated triage work, while subsequent agents perform contextual analysis and verification. The triage priority is not interpreted as a vulnerability probability.”

## Implementation references

- [JEV client](../../.claude/skills/jev-triage/jev_triage.py): `collect_paths`, `iter_units`, `split_blocks`, `build_requests`, `score_answers`, `Cache`, `process_request`, `run`.
- [JEV integration skill](../../.claude/skills/jev-triage/SKILL.md).
- [Coverage-aware reward](../../scripts/stages/rsi_reward.py): `calculate`.
- [Priority-hit scorecard](../../scripts/stages/rsi_scorecard.py): `_score`.

## Source snapshot

This document describes the restored NAS implementation inspected on 16 November 2026. Repository links are navigation aids; the hashes below identify the exact inspected files, which may differ from another checkout. No benchmark measurements are inferred from these files.

| Source file | SHA-256 |
| --- | --- |
| `.claude/skills/jev-triage/jev_triage.py` | `5cd2c154c9dd1cdee36b04194b09eba6ff376f174ba27bb0c293dbf9b6dd3344` |
| `.claude/skills/jev-triage/SKILL.md` | `dc1e2b22cee2205041295c3a218063ca33d757c0a2083e71143bc7c47a58dc2e` |
| `scripts/stages/rsi_reward.py` | `0bc0c5e58b55e66a0c9771c0f37f2ee2b1e5de89f4cacae1123372c751052bd4` |
| `scripts/stages/rsi_scorecard.py` | `7b8dfa99c309f3fb30ff910ade64458abf4b37ed5a0bddf0a73a7ed0167923fb` |
