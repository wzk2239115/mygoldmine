# Full per-tool result artifacts

This directory contains the per-tool, per-target result artifacts for the 2026-11-17 comparison. It supplements `comparison-summary.md` and `comparison-summary.json`.

## Included

- `mygoldmine/` and `mygoldmine-clean/`: reports, run metadata, status, triage artifacts, and rendered reports.
- `claude-security-review/`: raw and filtered findings, prompts, execution logs, and session traces excluded.
- `codex-security/`: findings, reports, threat model, scan manifests, SARIF exports, and evidence files.
- `strix/`: run metadata, vulnerability JSON/CSV/SARIF, coverage, execution logs, and per-vulnerability Markdown.
- `repoaudit/`: per-target execution logs.
- `repoaudit-tool-result/`: persisted RepoAudit `detect_info.json` and related tool output.
- `config/`: experiment scripts, protocol, revisions, runtime requirements, and adaptation patches.

## Excluded

Provider credentials, `provider.env`, private Codex state directories (`.aws`, `.codex`, `.git`, `.scratch`), Claude `session-home`, Strix source snapshots and `.state`, raw JSONL traces, rendered/stderr model logs, setup-attempt and permission-attempt records, PID/stop control files, and other private runtime state.

## Caveat

Raw candidate counts remain candidate counts, not independently confirmed vulnerabilities. Timeout, interrupted, and parse-failure results are retained as such.
