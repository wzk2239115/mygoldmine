#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finding_ledger

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
    return finding_ledger.is_verified(raw)


def latest_findings(ledger=None):
    ledger = ledger if ledger is not None else finding_ledger.build_ledger()
    return finding_ledger.latest_occurrences(ledger)


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


def build_verify_state(latest: dict, manual: set, ledger=None):
    ledger = ledger if ledger is not None else finding_ledger.build_ledger()
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
            if not finding_id or finding_id in {"VERIFY", "RECHECK", "SUMMARY"}:
                continue
            verdict = finding_ledger.normalized_verdict(pick_verdict(entry, outer))
            transition = finding_ledger.verify_transition(verdict)
            if not transition:
                continue
            status, auto_verdict = transition
            matches = finding_ledger.resolve_reference(
                ledger,
                project=project,
                finding_id=finding_id,
                run_id=entry.get("run_id") or outer.get("run_id") or "",
                occurrence_id=entry.get("occurrence_id") or outer.get("occurrence_id") or "",
                semantic_id=entry.get("semantic_id") or outer.get("semantic_id") or "",
            )
            verification = entry.get("verification") if isinstance(entry.get("verification"), dict) else {}
            evidence_class = entry.get("evidence_class") or verification.get("method") or outer.get("evidence_class") or ""
            reason = str(entry.get("reason") or verification.get("reason") or outer.get("reason") or "")
            for key in matches:
                if key in manual:
                    continue
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


def build_source_state(latest: dict, manual: set, ledger=None):
    ledger = ledger if ledger is not None else finding_ledger.build_ledger()
    state = {}

    def resolve(project, finding_id, item=None):
        item = item if isinstance(item, dict) else {}
        matches = finding_ledger.resolve_reference(
            ledger,
            project=project,
            finding_id=finding_id,
            occurrence_id=item.get("occurrence_id") or "",
            semantic_id=item.get("semantic_id") or "",
        )
        return next((key for key in matches if key in latest and key not in manual), None)

    handoff = load(ROOT / "docs" / "cve-handoff.json")
    for candidate in handoff.get("candidates", []) if isinstance(handoff.get("candidates"), list) else []:
        if not isinstance(candidate, dict):
            continue
        key = resolve(candidate.get("project", ""), candidate.get("finding_id", ""), candidate)
        if not key:
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
        if not isinstance(item, dict):
            continue
        key = resolve(project, finding_id, item)
        if not key:
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


def verified_redteam_provenance(result_path: Path, result: dict):
    redteam_dir = str(ROOT / "scripts" / "redteam")
    if redteam_dir not in sys.path:
        sys.path.insert(0, redteam_dir)
    from contracts import ContractError, recompute_flag_provenance, validate_verdict

    judge = result.get("judge") if isinstance(result.get("judge"), dict) else {}
    status = str(result.get("status") or "").lower()
    if status not in {"judge_approved", "runtime-validated"} or judge.get("verdict") != "approved":
        return None
    try:
        validate_verdict(judge)
        provenance = recompute_flag_provenance(result_path.parent, result)
    except ContractError:
        return None
    if result.get("flag_provenance_verified") != provenance:
        return None
    return provenance


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    ledger = finding_ledger.build_ledger()
    finding_ledger.write(finding_ledger.OUT, ledger)
    latest = latest_findings(ledger)
    manual_data = finding_ledger.merge_manual_state(
        ledger, [load(DATA / "curated.json"), load(DATA / "state.json")]
    )
    manual = set(manual_data)

    state = build_verify_state(latest, manual, ledger)
    for key, patch in build_source_state(latest, manual, ledger).items():
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

    review = {}
    for result_path in sorted((ROOT / "runs" / "redteam").glob("*/*/result.json")):
        result = load(result_path)
        provenance = verified_redteam_provenance(result_path, result)
        if not provenance:
            continue
        finding_data = load(result_path.parent / "finding.json")
        project = result.get("project") or result_path.parent.parent.name
        finding_id = finding_data.get("id")
        matches = finding_ledger.resolve_reference(
            ledger,
            project=project,
            finding_id=finding_id,
            occurrence_id=finding_data.get("occurrence_id") or result.get("occurrence_id") or "",
            semantic_id=finding_data.get("semantic_id") or result.get("semantic_id") or "",
        )
        key = next((match for match in matches if match in latest), None)
        item = latest.get(key)
        if not item:
            continue
        run_dir = ROOT / Path(item["report"]).parent
        illustrated = run_dir / "visual-rendered" / "report-illustrated.md"
        scene_image = run_dir / "visual-rendered" / f"scene-{finding_id}.webp"
        if not illustrated.exists() or not scene_image.exists():
            continue
        review[key] = {
            "score": 100,
            "reason": "红队已捕获随机标记 · 独立审核通过 · 图文报告已生成",
            "runtime": "runtime-validated",
            "trace": str(result_path),
            "flag_provenance": provenance,
        }

    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings_total": len(latest),
        "auto_total": len(state),
        "review_total": len(review),
        "findings": finding_ledger.identified_states(state, ledger),
        "review": finding_ledger.identified_states(review, ledger),
    }
    finding_ledger.write(OUT, payload)
    print(f"[workflow] latest={len(latest)} auto={len(state)} review={len(review)} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
