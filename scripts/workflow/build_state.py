#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
DATA = ROOT / "ui" / "data"
OUT = DATA / "auto-state.json"
EXCLUDED = {"smoke", "smoke-real", "smoke-target"}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def norm_id(value) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def canon(project: str, finding_id) -> str:
    return f"{project}:{norm_id(finding_id)}"


def split_key(key: str):
    project, _, finding_id = str(key).partition(":")
    return project, finding_id


def sev(value) -> str:
    raw = str(value or "info").lower()
    if raw.startswith("critical") or raw == "crit":
        return "critical"
    if raw.startswith("high"):
        return "high"
    if raw.startswith("medium") or raw.startswith("moderate"):
        return "medium"
    if raw.startswith("low"):
        return "low"
    return "info"


def is_verified(raw: dict) -> bool:
    if raw.get("verified"):
        return True
    text = f"{raw.get('verification', '')} {raw.get('severity_raw', '')}"
    return bool(re.search(r"confirm|verified|已.*验证|reproduced", text, re.I))


def latest_findings():
    latest = {}
    for project_dir in sorted(RUNS.iterdir() if RUNS.exists() else []):
        if not project_dir.is_dir() or project_dir.name.startswith(".") or project_dir.name in EXCLUDED:
            continue
        candidates = []
        for report_path in project_dir.glob("*/audit-report.json"):
            report = load(report_path)
            meta = load(report_path.parent / "run-meta.json")
            stamp = meta.get("started_at") or report.get("generated_at") or report_path.parent.name
            candidates.append((str(stamp), report_path.parent.name, report_path, report))
        if not candidates:
            continue
        _, _, report_path, report = max(candidates)
        findings = report.get("findings") if isinstance(report.get("findings"), list) else report.get("vulnerabilities")
        if not isinstance(findings, list):
            continue
        for index, raw in enumerate(findings):
            if not isinstance(raw, dict):
                continue
            finding_id = raw.get("id") or raw.get("finding_id") or f"F-{index + 1:02d}"
            key = canon(project_dir.name, finding_id)
            latest[key] = {
                "project": project_dir.name,
                "id": finding_id,
                "severity": sev(raw.get("severity") or raw.get("severity_raw")),
                "verified": is_verified(raw),
                "report": report_path.relative_to(ROOT).as_posix(),
            }
    return latest


def pick_verdict(entry: dict, outer: dict):
    verification = entry.get("verification") if isinstance(entry.get("verification"), dict) else {}
    return (
        entry.get("verdict")
        or entry.get("status")
        or verification.get("status")
        or verification.get("verdict")
        or outer.get("verdict")
        or outer.get("status")
    )


def verify_candidates(report_path: Path, outer: dict):
    results = outer.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                yield str(item.get("id") or item.get("finding_id") or ""), item
        return
    findings = outer.get("findings")
    if isinstance(findings, list):
        for item in findings:
            if isinstance(item, dict):
                yield str(item.get("finding_id") or item.get("id") or ""), item
        return
    if isinstance(findings, dict):
        for finding_id, item in findings.items():
            if isinstance(item, dict):
                yield str(item.get("finding_id") or finding_id), item
        return
    finding_id = outer.get("finding_id") or outer.get("id") or report_path.parent.name
    yield str(finding_id), outer


def build_verify_state(latest: dict, manual: set):
    state = {}
    for report_path in sorted(RUNS.glob("*/*/verify/**/verify-report.json")) if RUNS.exists() else []:
        relative = report_path.relative_to(RUNS)
        project = relative.parts[0]
        outer = load(report_path)
        if not outer:
            continue
        ended_at = outer.get("ended_at") or datetime.fromtimestamp(report_path.stat().st_mtime, timezone.utc).isoformat()
        for raw_id, entry in verify_candidates(report_path, outer):
            finding_id = norm_id(raw_id)
            key = canon(project, finding_id)
            if not finding_id or finding_id in {"VERIFY", "RECHECK", "SUMMARY"} or key not in latest or key in manual:
                continue
            verdict = str(pick_verdict(entry, outer) or "").lower()
            if not verdict:
                continue
            verification = entry.get("verification") if isinstance(entry.get("verification"), dict) else {}
            evidence_class = (
                entry.get("evidence_class")
                or verification.get("method")
                or outer.get("evidence_class")
                or ""
            )
            reason = entry.get("reason") or verification.get("reason") or outer.get("reason") or ""
            if verdict in {"rejected", "false-positive", "fp"}:
                status = "closed"
                auto_verdict = "fp"
            else:
                status = "reproduce"
                auto_verdict = None
            patch = {
                "status": status,
                "reason": f"verify: {verdict}" + (f" · {evidence_class}" if evidence_class else ""),
                "source": "verify",
                "source_detail": reason[:500],
                "artifacts": [report_path.relative_to(ROOT).as_posix()],
                "verifyVerdict": verdict,
                "verifyEvidenceClass": evidence_class,
                "updatedAt": ended_at,
            }
            if auto_verdict:
                patch["verdict"] = auto_verdict
            previous = state.get(key)
            if not previous or str(patch["updatedAt"]) >= str(previous.get("updatedAt", "")):
                state[key] = {**previous, **patch} if previous else patch
    return state


def build_source_state(latest: dict, manual: set):
    state = {}
    handoff = load(ROOT / "docs" / "cve-handoff.json")
    for candidate in handoff.get("candidates", []) if isinstance(handoff.get("candidates"), list) else []:
        key = canon(candidate.get("project", ""), candidate.get("finding_id", ""))
        if key not in latest or key in manual:
            continue
        tier = candidate.get("tier")
        state[key] = {
            "status": "reproduce",
            "cveTier": tier if tier in (1, 2) else None,
            "cveStatus": "tracking",
            "reason": f"CVE handoff Tier {tier}" if tier else "CVE handoff",
            "source": "handoff",
            "source_detail": str(candidate.get("known_overlap", ""))[:500],
            "artifacts": ["docs/cve-handoff.json"],
        }
    adjudication = load(ROOT / "docs" / "cve-adjudication.json")
    for raw_key, item in adjudication.get("findings", {}).items() if isinstance(adjudication.get("findings"), dict) else []:
        project, finding_id = split_key(raw_key)
        key = canon(project, finding_id)
        if key not in latest or key in manual or not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict", "")).lower()
        known = str(item.get("knownCve", "")).strip()
        if known:
            state[key] = {
                "status": "closed",
                "cveTier": None,
                "cveStatus": "known",
                "knownCve": known,
                "reason": f"adjudication: known {known}",
                "source": "adjudication",
                "artifacts": ["docs/cve-adjudication.json"],
            }
        elif verdict in {"fp", "duplicate", "design"}:
            state[key] = {
                "status": "closed",
                "verdict": "duplicate" if verdict == "duplicate" else ("fp" if verdict == "fp" else "unclear"),
                "cveTier": None,
                "cveStatus": "blocked" if verdict == "design" else "none",
                "reason": f"adjudication: {verdict}",
                "source": "adjudication",
                "source_detail": str(item.get("note", ""))[:500],
                "artifacts": ["docs/cve-adjudication.json"],
            }
        elif item.get("cveTier") in (1, 2):
            state[key] = {
                "status": "cve" if verdict == "tp" else "reproduce",
                "cveTier": item.get("cveTier"),
                "cveStatus": "tracking",
                "reason": f"adjudication: Tier {item.get('cveTier')}",
                "source": "adjudication",
                "source_detail": str(item.get("note", ""))[:500],
                "artifacts": ["docs/cve-adjudication.json"],
            }
    return state


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    latest = latest_findings()
    manual = set()
    for name in ("curated.json", "state.json"):
        payload = load(DATA / name)
        for raw_key in payload if isinstance(payload, dict) else []:
            project, finding_id = split_key(raw_key)
            manual.add(canon(project, finding_id))

    state = build_verify_state(latest, manual)
    for key, patch in build_source_state(latest, manual).items():
        if key in state:
            state[key] = {**state[key], **patch}
        else:
            state[key] = patch

    for key, item in latest.items():
        if key in manual or key in state:
            continue
        if item["severity"] == "critical" or (item["severity"] == "high" and item["verified"]):
            state[key] = {
                "status": "triage",
                "reason": "自动入队: Critical" if item["severity"] == "critical" else "自动入队: High + verified",
                "source": "severity",
                "artifacts": [item["report"]],
            }

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings_total": len(latest),
        "auto_total": len(state),
        "findings": dict(sorted(state.items())),
    }
    temp = OUT.with_name(f".{OUT.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUT)
    print(f"[workflow] latest={len(latest)} auto={len(state)} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
