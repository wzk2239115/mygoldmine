import os
import re
import json
import glob
import datetime
import pathlib

BASE = pathlib.Path(os.environ.get("BENCHMARK_BASE", "/vol1/1000/mygoldmine-benchmark/2026-11-17"))
RESULTS = BASE / "results"
TARGETS = ["sol", "pure-ftpd", "libcoap", "tlse"]
CATEGORIES = ["NPD", "MLK", "UAF"]
REPOAUDIT_ROOT = BASE / "tools/RepoAudit/result/dfbscan/deepseek/deepseek-v4.1-flash"


def read_json(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def rel(path):
    return str(pathlib.Path(path).relative_to(BASE))


def jobs_for(tool, target=None):
    jobs = read_json(RESULTS / "comparator-status.json", [])
    return [
        job for job in jobs
        if job.get("tool") == tool and (target is None or job.get("target") == target)
    ]


def unique_titles(items, key="title"):
    titles = []
    for item in items:
        value = item.get(key) if isinstance(item, dict) else None
        if value:
            titles.append(re.sub(r"\s+", " ", str(value)).strip().lower())
    return len(set(titles)) if titles else None


def mygoldmine_row(target):
    run_root = RESULTS / ("mygoldmine" if target == "pure-ftpd" else "mygoldmine-clean") / target
    meta = read_json(run_root / "run-meta.json", {})
    report = read_json(run_root / "audit-report.json")
    findings = report.get("findings", []) if isinstance(report, dict) else []
    report_path = run_root / "audit-report.json" if report is not None else None
    partial_md = run_root / "audit-report.md"
    partial_candidates = None
    if report is None and partial_md.exists():
        text = partial_md.read_text(encoding="utf-8", errors="replace")
        partial_candidates = len(re.findall(r"^### LIBCOAP-[A-Z]+-\d+", text, flags=re.M))
        report_path = partial_md
    controller = read_json(RESULTS / "mygoldmine-clean/status.json", [])
    controller_job = next((x for x in controller if x.get("target") == target), {})
    controlled_timeout = controller_job.get("status") == "timeout"
    timed_out = bool(controlled_timeout or meta.get("timed_out"))
    run_status = meta.get("status")
    if controlled_timeout and meta.get("interrupted"):
        status = "timeout_interrupted_partial_report" if report is not None else "timeout_interrupted_no_final_report"
    elif controlled_timeout or run_status == "timeout":
        status = "timeout_partial_report"
    elif run_status == "success":
        status = "completed"
    elif run_status == "partial":
        status = "partial_report"
    else:
        status = run_status or "unknown"
    verified = sum(
        1 for finding in findings
        if isinstance(finding.get("verification"), dict)
        and finding["verification"].get("status") == "verified"
    )
    raw_candidates = len(findings) if report is not None else partial_candidates
    return {
        "tool": "Mygoldmine",
        "target": target,
        "configuration": "stage-II-only; DeepSeek V4.1 Flash audit plus JEV triage; not full blue/red/independent review",
        "status": status,
        "report_complete": bool(report is not None and meta.get("reports_complete") and not timed_out),
        "raw_candidates": raw_candidates,
        "raw_candidates_basis": "audit-report.json findings" if report is not None else (
            "candidate headings in partial audit-report.md" if partial_candidates is not None else None
        ),
        "deduplicated_issues": None,
        "deduplication_status": "not_performed",
        "tool_internal_validation": {
            "verified": verified,
            "unverified": len(findings) - verified,
            "basis": "finding.verification.status",
            "independent": False,
        },
        "independently_confirmed": None,
        "report": rel(report_path) if report_path is not None and report_path.exists() else None,
        "started_at": meta.get("started_at"),
        "ended_at": meta.get("ended_at"),
        "controller_status": controller_job.get("status"),
        "timed_out": bool(controlled_timeout or meta.get("timed_out")),
        "interrupted": meta.get("interrupted"),
        "timeout_basis": "external 3600s wall-clock budget; SIGTERM/exit 143 is not a normal scan failure" if controlled_timeout else None,
    }


def claude_row(target):
    run_root = RESULTS / "claude-security-review" / target
    raw = read_json(run_root / "raw-findings.json", {})
    filtered = read_json(run_root / "filtered-findings.json", {})
    raw_results = raw.get("results", {}) if isinstance(raw, dict) else {}
    filtered_results = filtered.get("results", {}) if isinstance(filtered, dict) else {}
    raw_findings = raw_results.get("findings", []) if isinstance(raw_results, dict) else []
    filtered_findings = filtered_results.get("filtered_findings", []) if isinstance(filtered_results, dict) else []
    summary = raw_results.get("analysis_summary", {}) if isinstance(raw_results, dict) else {}
    review_completed = bool(summary.get("review_completed"))
    execution_log = run_root / "execution.log"
    log_text = execution_log.read_text(encoding="utf-8", errors="replace") if execution_log.exists() else ""
    parse_failure = "Failed to parse JSON" in log_text
    unparsed_mentions = len(re.findall(r"# Vuln \d+:", log_text)) if parse_failure else 0
    if parse_failure or not review_completed:
        status = "invalid_json_parse_failure" if parse_failure else "incomplete_review"
    else:
        status = "completed"
    job = next(iter(jobs_for("claude-security-review", target)), {})
    stats = filtered.get("stats", {}) if isinstance(filtered, dict) else {}
    return {
        "tool": "Claude Code Security Review",
        "target": target,
        "configuration": "adapted full-source review with DeepSeek V4.1 Flash; upstream audit/filter prompts retained; not Anthropic default model",
        "status": status,
        "report_complete": bool(review_completed and not parse_failure),
        "raw_candidates": len(raw_findings) if review_completed and not parse_failure else None,
        "filtered_candidates": len(filtered_findings) if review_completed and not parse_failure else None,
        "unparsed_candidate_mentions": unparsed_mentions if parse_failure else None,
        "deduplicated_issues": None,
        "deduplication_status": "not_performed",
        "tool_internal_validation": {
            "filtering_enabled": filtered.get("filtering_enabled") if isinstance(filtered, dict) else None,
            "kept": stats.get("kept_findings"),
            "excluded": stats.get("excluded_findings", stats.get("excluded")),
            "review_completed": review_completed,
            "files_reviewed": summary.get("files_reviewed"),
            "independent": False,
        },
        "independently_confirmed": None,
        "report": rel(run_root / "filtered-findings.json") if (run_root / "filtered-findings.json").exists() else None,
        "elapsed_seconds": job.get("elapsed_seconds"),
        "parse_failure": parse_failure,
        "notes": "execution.log contains two unparsed vulnerability sections" if parse_failure and unparsed_mentions else None,
    }


def repoaudit_category(target, category):
    entries = [x for x in jobs_for("repoaudit", target) if x.get("subtask") == f"-{category.lower()}"]
    job = entries[-1] if entries else {}
    files = sorted(
        (REPOAUDIT_ROOT / category / "Cpp" / target).glob("*/detect_info.json"),
        key=lambda p: p.stat().st_mtime,
    )
    records = read_json(files[-1]) if files else None
    candidates = len(records) if records is not None else None
    log_path = RESULTS / "repoaudit" / target / f"execution-{category.lower()}.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    zero_detected = "0 bug(s) was/were detected in total" in log_text
    if candidates is None and job.get("status") == "finished" and zero_detected:
        candidates = 0
    coverage = "persisted_records" if candidates is not None else (
        "timed_out_unknown" if job.get("status") == "timeout" else "not_run_unknown"
    )
    return {
        "type": category,
        "run_status": job.get("status"),
        "candidates": candidates,
        "coverage": coverage,
        "source": rel(files[-1]) if files else None,
        "records": records,
    }


def repoaudit_row(target):
    categories = [repoaudit_category(target, category) for category in CATEGORIES]
    entries = jobs_for("repoaudit", target)
    observed = [c for c in categories if c["candidates"] is not None]
    raw_candidates = sum(c["candidates"] for c in observed) if observed else None
    all_records = []
    for category in categories:
        if isinstance(category["records"], dict):
            all_records.extend(category["records"].values())
    root_causes = set()
    for record in all_records:
        key = record.get("buggy_value") if isinstance(record, dict) else None
        if key:
            root_causes.add(key)
    unknown = [c["type"] for c in categories if c["candidates"] is None]
    deduplicated = len(root_causes) if all_records else (0 if raw_candidates == 0 and not unknown else None)
    timeouts = [c["type"] for c in categories if c["run_status"] == "timeout"]
    finished = [c["type"] for c in categories if c["run_status"] == "finished"]
    if timeouts and any((c["candidates"] or 0) > 0 for c in categories):
        status = "partial_timeout_with_persisted_results"
    elif timeouts and observed:
        status = "partial_timeout_zero_in_completed_categories"
    elif timeouts:
        status = "partial_timeout_no_persisted_results"
    elif len(finished) == len(CATEGORIES):
        status = "completed"
    else:
        status = "unknown"
    return {
        "tool": "RepoAudit",
        "target": target,
        "configuration": "NPD/MLK/UAF; 1200s per category; max 4 neural workers; only provider base URL adapted",
        "status": status,
        "report_complete": not unknown,
        "raw_candidates": raw_candidates,
        "raw_candidates_complete": not unknown,
        "raw_candidates_basis": "persisted detect_info.json records only; unfinished categories are not counted as zero",
        "deduplicated_issues": deduplicated,
        "deduplication_basis": (
            "unique persisted buggy_value root-cause key among persisted records only"
            if all_records else
            "not computed because some categories are unknown" if unknown else
            "no persisted records; all categories completed with zero"
        ),
        "tool_internal_validation": {
            "path_validator": "internal LLM path validator only",
            "human_confirmed_true": sum(
                1 for record in all_records
                if isinstance(record, dict) and record.get("is_human_confirmed_true") is True
            ),
            "independent": False,
        },
        "independently_confirmed": None,
        "unknown_categories": unknown,
        "timed_out_categories": timeouts,
        "completed_zero_categories": [c["type"] for c in categories if c["candidates"] == 0],
        "categories": [
            {k: v for k, v in c.items() if k != "records"} for c in categories
        ],
        "subtasks": entries,
    }


def strix_row(target):
    run_dirs = sorted((RESULTS / "strix" / target).glob("strix_runs/*"))
    run_dir = run_dirs[-1] if run_dirs else None
    run_meta = read_json(run_dir / "run.json", {}) if run_dir else {}
    vulnerabilities = read_json(run_dir / "vulnerabilities.json", []) if run_dir else []
    if not isinstance(vulnerabilities, list):
        vulnerabilities = []
    titles = unique_titles(vulnerabilities)
    job = next(iter(jobs_for("strix", target)), {})
    interrupted = run_meta.get("status") == "interrupted" or job.get("status") == "timeout"
    return {
        "tool": "Strix",
        "target": target,
        "configuration": "full-source; standard mode; DeepSeek V4.1 Flash; USD 10 estimated cost cap",
        "status": "timeout_partial_report" if interrupted else (run_meta.get("status") or job.get("status") or "unknown"),
        "report_complete": False if interrupted else run_meta.get("status") == "completed",
        "raw_candidates": len(vulnerabilities),
        "unique_titles": titles,
        "deduplicated_issues": None,
        "deduplication_status": "title-count only; root causes not independently verified",
        "tool_internal_validation": {
            "separate_validation_stage": False,
            "confidence_field_present": all(isinstance(v, dict) and v.get("confidence") for v in vulnerabilities),
            "independent": False,
        },
        "independently_confirmed": None,
        "report": rel(run_dir / "vulnerabilities.json") if run_dir and (run_dir / "vulnerabilities.json").exists() else None,
        "run_status": run_meta.get("status"),
        "controller_status": job.get("status"),
        "started_at": run_meta.get("start_time"),
        "ended_at": run_meta.get("end_time"),
        "limitations": "partial findings from an interrupted one-hour run" if interrupted else None,
    }


def codex_row(target):
    run_root = RESULTS / "codex-security" / target
    findings_doc = read_json(run_root / "findings.json", {})
    findings = findings_doc.get("findings", []) if isinstance(findings_doc, dict) else []
    manifest = read_json(run_root / "scan-manifest.json", {}).get("scan", {})
    status_job = next((x for x in read_json(RESULTS / "codex-security/status.json", []) if x.get("target") == target), {})
    completed = status_job.get("status") == "finished" and manifest.get("status") == "completed"
    validated = sum(
        1 for finding in findings
        if isinstance(finding.get("validation"), dict)
        and finding["validation"].get("status") == "validated"
    )
    validation_present = sum(
        1 for finding in findings
        if isinstance(finding.get("validation"), dict)
        and (finding["validation"].get("status") or finding["validation"].get("method"))
    )
    return {
        "tool": "Codex Security",
        "target": target,
        "configuration": "adapted custom provider; 360 /v1 Responses endpoint; DeepSeek V4.1 Flash; not official-hosted default",
        "status": "completed" if completed else (status_job.get("status") or "unknown"),
        "report_complete": completed,
        "raw_candidates": len(findings),
        "unique_titles": unique_titles(findings),
        "deduplicated_issues": None,
        "deduplication_status": "title-count only; root causes not independently verified",
        "tool_internal_validation": {
            "validation_present": validation_present,
            "validated": validated,
            "basis": "finding.validation.status or finding.validation.method",
            "independent": False,
        },
        "independently_confirmed": None,
        "report": rel(run_root / "findings.json") if (run_root / "findings.json").exists() else None,
        "markdown_report": rel(run_root / "report.md") if (run_root / "report.md").exists() else None,
        "scan_manifest_status": manifest.get("status"),
        "started_at": status_job.get("started_at"),
        "ended_at": status_job.get("ended_at"),
    }


rows = []
for target in TARGETS:
    rows.extend([
        mygoldmine_row(target),
        strix_row(target),
        repoaudit_row(target),
        claude_row(target),
        codex_row(target),
    ])

LIMITATIONS = [
    "Raw candidate counts are not true-positive counts, precision, recall, vulnerability counts, CVE counts, or a tool ranking.",
    "Tool-internal filtering and validation are not a shared independent ground truth; independently confirmed counts remain unknown.",
    "Model, provider, scope, and source settings were adapted and differ from official product defaults.",
    "Timeout and interrupted reports are partial. Missing reports and unfinished categories must not be read as zero vulnerabilities.",
    "Cross-tool deduplication has not been performed. RepoAudit sol raw records are deduplicated by persisted buggy_value root-cause key.",
    "The targets are frozen default-branch snapshots, not historical vulnerable versions with a ground-truth set.",
]

out = {
    "updated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "base": str(BASE),
    "targets": TARGETS,
    "limitations": LIMITATIONS,
    "rows": rows,
    "status_definitions": {
        "completed": "Run and report completed; zero findings can be a valid result.",
        "timeout_partial_report": "Hit the one-hour wall clock; report contains partial findings.",
        "timeout_interrupted_no_final_report": "Hit the one-hour wall clock; only a partial Markdown report exists.",
        "partial_timeout_with_persisted_results": "Some RepoAudit categories timed out; persisted records are partial.",
        "invalid_json_parse_failure": "Process exited, but structured report parsing failed; empty JSON is not a valid zero result.",
    },
}
(RESULTS / "comparison-summary.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

for row in rows:
    print(row["tool"], row["target"], row["status"], row["raw_candidates"], row["deduplicated_issues"])
