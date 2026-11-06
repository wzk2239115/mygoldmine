#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
OUT = ROOT / "ui" / "data" / "finding-ledger.json"
EXCLUDED = {"smoke", "smoke-real", "smoke-target"}
CONFIRMED_VERDICTS = {"confirmed", "verified", "reproduced", "tp", "true-positive", "true_positive", "已确认", "已验证", "复现成功"}
REJECTED_VERDICTS = {"rejected", "false-positive", "false_positive", "fp", "not-a-vulnerability"}
UNVERIFIED_VERDICTS = REJECTED_VERDICTS | {"unverified", "not-verified", "not_verified", "未验证", "未确认"}


def load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def norm_id(value) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def canon(project: str, finding_id) -> str:
    return f"{project}:{norm_id(finding_id)}"


def severity(value) -> str:
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


def normalized_verdict(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def is_verified(raw: dict) -> bool:
    if not isinstance(raw, dict):
        return False
    verification = raw.get("verification")
    verdicts = [raw.get("verdict")]
    verified_values = [raw.get("verified")]
    if isinstance(verification, dict):
        verdicts.extend((verification.get("verdict"), verification.get("status")))
        verified_values.append(verification.get("verified"))
    else:
        verdicts.append(verification)
    normalized = [normalized_verdict(value) for value in verdicts]
    if any(value in UNVERIFIED_VERDICTS for value in normalized):
        return False
    return any(value is True for value in verified_values) or any(
        value in CONFIRMED_VERDICTS for value in normalized
    )


def verify_transition(value):
    verdict = normalized_verdict(value)
    if verdict in REJECTED_VERDICTS:
        return "closed", "fp"
    if verdict in CONFIRMED_VERDICTS:
        return "reproduce", None
    return None


def digest(value, prefix="") -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return prefix + hashlib.sha256(encoded).hexdigest()[:24]


def text_value(value) -> str:
    if isinstance(value, list):
        return " ".join(filter(None, (text_value(item) for item in value)))
    if isinstance(value, dict):
        return text_value(value.get("idea") or value.get("steps") or value.get("note") or value.get("description") or "")
    return str(value or "").strip()


def normalize_path(value) -> str:
    value = str(value or "").strip().replace("\\", "/")
    value = re.sub(r":\d+(?:[-:]\d+)?(?:-\d+)?$", "", value)
    value = re.sub(r"^(?:\./|/+)+", "", value)
    return value.strip().lower()


def evidence_paths(raw: dict):
    values = []
    for key in ("evidence", "files", "location"):
        value = raw.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    paths = []
    for item in values:
        if isinstance(item, dict):
            item = item.get("path") or item.get("file") or item.get("location") or ""
        path = normalize_path(item)
        if path:
            paths.append(path)
    return sorted(set(paths))


def cwe_values(raw: dict):
    value = raw.get("cwe") or raw.get("cwe_id") or []
    if not isinstance(value, list):
        value = re.split(r"[,;]", str(value))
    result = []
    for item in value:
        match = re.search(r"(?:CWE[-\s]*)?(\d+)", str(item), re.I)
        if match:
            result.append(f"CWE-{int(match.group(1))}")
    return sorted(set(result))


def semantic_material(project: str, raw: dict, local_id: str):
    paths = evidence_paths(raw)
    root = raw.get("root_cause") or raw.get("rootCause") or raw.get("title") or raw.get("description") or raw.get("type") or ""
    root = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text_value(root).lower()).strip()
    cwes = cwe_values(raw)
    fallback = norm_id(local_id) if not paths and not root and not cwes else ""
    return {"project": project, "paths": paths, "root_cause": root, "cwe": cwes, "fallback": fallback}


def workflow_report_delivery(report_path):
    directory = Path(str(report_path.parent) + ".meta") / "workflows"
    owned = False
    for file in directory.glob("*/state.json"):
        state = load(file)
        if not isinstance(state, dict):
            continue
        if state.get("project") != report_path.parent.parent.name:
            continue
        if Path(state.get("runDir") or "").resolve() != report_path.parent.resolve():
            continue
        owned = True
        for receipt in state.get("receipts") or []:
            if receipt.get("node") != "orchestrator":
                continue
            if receipt.get("status") not in ("completed", "degraded"):
                continue
            for item in receipt.get("outputs") or []:
                if Path(item.get("file") or "").resolve() != report_path.resolve():
                    continue
                try:
                    actual = hashlib.sha256(report_path.read_bytes()).hexdigest()
                    if not report_path.is_symlink() and item.get("sha256") == actual:
                        return True, True
                except OSError:
                    pass
    return owned, False


def valid_report(report_path: Path):
    report = load(report_path)
    meta = load(report_path.parent / "run-meta.json")
    status = load(report_path.parent.parent / f"{report_path.parent.name}.meta" / "status.json")
    owned, delivered = workflow_report_delivery(report_path)
    if owned:
        # The audit receipt remains valid when later stages are running or degraded.
        if not delivered:
            return None
    else:
        state = normalized_verdict(status.get("state"))
        if state in {"starting", "running", "stopping", "draft", "partial", "failed",
                     "error", "timeout", "stopped", "interrupted"}:
            return None
        if meta.get("reports_complete") is not True or meta.get("exit_code") != 0:
            return None
        if meta.get("timed_out") or meta.get("interrupted"):
            return None
    if not isinstance(report, dict) or report.get("draft") is True:
        return None
    try:
        from report_quality import schema_errors
        if schema_errors(report):
            return None
    except (ImportError, TypeError):
        return None
    findings = report.get("findings") if isinstance(report.get("findings"), list) else report.get("vulnerabilities")
    if not isinstance(findings, list):
        return None
    return report, meta, findings


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def empty_ledger():
    return {
        "schema_version": 2,
        "generated_at": None,
        "findings": {},
        "occurrences": {},
        "indexes": {"legacy_to_semantics": {}, "legacy_to_occurrences": {}},
        "latest_by_project": {},
    }


def build_ledger(runs_root: Path = RUNS, root: Path = ROOT):
    ledger = empty_ledger()
    if not runs_root.exists():
        return ledger
    candidates = []
    for report_path in runs_root.glob("*/*/audit-report.json"):
        project = report_path.parent.parent.name
        run_id = report_path.parent.name
        if project.startswith(".") or run_id.startswith(".") or project in EXCLUDED:
            continue
        valid = valid_report(report_path)
        if not valid:
            continue
        report, meta, findings = valid
        stamp = str(meta.get("started_at") or report.get("generated_at") or run_id)
        candidates.append((stamp, run_id, project, report_path, report, meta, findings))

    for stamp, run_id, project, report_path, report, meta, findings in sorted(candidates):
        report_rel = relative_path(report_path, root)
        report_hash = digest(report)
        ledger["latest_by_project"][project] = {
            "run_id": run_id,
            "generated_at": report.get("generated_at") or meta.get("ended_at") or meta.get("started_at"),
            "report": report_rel,
            "report_hash": report_hash,
        }
        seen = {}
        for index, raw in enumerate(findings):
            if not isinstance(raw, dict):
                continue
            base_id = str(raw.get("id") or raw.get("finding_id") or f"F-{index + 1:02d}").strip()
            seen[base_id] = seen.get(base_id, 0) + 1
            local_id = base_id if seen[base_id] == 1 else f"{base_id}~{seen[base_id]}"
            occurrence_id = f"{project}/{run_id}/{local_id}"
            semantic_id = digest(semantic_material(project, raw, local_id), "sem_")
            legacy_key = canon(project, base_id)
            occurrence = {
                "occurrence_id": occurrence_id,
                "semantic_id": semantic_id,
                "project": project,
                "run_id": run_id,
                "finding_id": base_id,
                "local_id": local_id,
                "id": local_id,
                "key": occurrence_id,
                "legacy_key": legacy_key,
                "severity": severity(raw.get("severity") or raw.get("severity_raw")),
                "verified": is_verified(raw),
                "confidence": str(raw.get("confidence") or "").lower(),
                "report": report_rel,
                "report_hash": report_hash,
                "raw_hash": digest(raw),
                "generated_at": report.get("generated_at") or meta.get("ended_at") or meta.get("started_at"),
                "commit": meta.get("commit") or "",
                "raw": raw,
                "_sort": [stamp, run_id, index],
            }
            ledger["occurrences"][occurrence_id] = occurrence
            semantic = ledger["findings"].setdefault(semantic_id, {
                "semantic_id": semantic_id,
                "project": project,
                "aliases": [],
                "occurrence_ids": [],
                "latest_occurrence_id": None,
            })
            semantic["occurrence_ids"].append(occurrence_id)
            aliases = raw.get("aliases") if isinstance(raw.get("aliases"), list) else []
            semantic["aliases"] = sorted(set(semantic["aliases"] + [occurrence_id, legacy_key] + [str(item) for item in aliases if str(item)]))
            semantic["latest_occurrence_id"] = occurrence_id

    for semantic in ledger["findings"].values():
        occurrences = [ledger["occurrences"][item] for item in semantic["occurrence_ids"]]
        latest = max(occurrences, key=lambda item: item["_sort"])
        semantic["latest_occurrence_id"] = latest["occurrence_id"]
        semantic["aliases"] = sorted(set(semantic["aliases"]))

    for occurrence in ledger["occurrences"].values():
        occurrence.pop("_sort", None)
        ledger["indexes"]["legacy_to_semantics"].setdefault(occurrence["legacy_key"], set()).add(occurrence["semantic_id"])
        ledger["indexes"]["legacy_to_occurrences"].setdefault(occurrence["legacy_key"], []).append(occurrence["occurrence_id"])

    ledger["indexes"]["legacy_to_semantics"] = {key: sorted(value) for key, value in sorted(ledger["indexes"]["legacy_to_semantics"].items())}
    ledger["indexes"]["legacy_to_occurrences"] = {key: sorted(value) for key, value in sorted(ledger["indexes"]["legacy_to_occurrences"].items())}
    ledger["generated_at"] = datetime.now(timezone.utc).isoformat()
    return ledger


def latest_occurrences(ledger: dict):
    result = {}
    for semantic in ledger.get("findings", {}).values():
        occurrence_id = semantic.get("latest_occurrence_id")
        occurrence = ledger.get("occurrences", {}).get(occurrence_id)
        if occurrence:
            result[occurrence_id] = occurrence
    return result


def resolve_reference(ledger: dict, project="", finding_id="", run_id="", occurrence_id="", semantic_id=""):
    occurrences = ledger.get("occurrences", {})
    if occurrence_id in occurrences:
        return [occurrence_id]
    if semantic_id in ledger.get("findings", {}):
        return list(ledger["findings"][semantic_id].get("occurrence_ids", []))
    key = canon(project, finding_id)
    if run_id:
        matches = [
            occurrence_id for occurrence_id in ledger.get("indexes", {}).get("legacy_to_occurrences", {}).get(key, [])
            if occurrences[occurrence_id]["run_id"] == run_id
        ]
        return matches if len(matches) == 1 else []
    semantics = ledger.get("indexes", {}).get("legacy_to_semantics", {}).get(key, [])
    if len(semantics) != 1:
        return []
    return list(ledger["findings"][semantics[0]].get("occurrence_ids", []))


def resolve_state_map(payload: dict, ledger: dict):
    if not isinstance(payload, dict):
        return {}
    findings = payload.get("findings") if isinstance(payload.get("findings"), dict) else payload
    occurrences = payload.get("occurrences") if isinstance(payload.get("occurrences"), dict) else {}
    result = {}

    def merge(keys, exact=False):
        for key, value in keys.items() if isinstance(keys, dict) else []:
            if not isinstance(value, dict):
                continue
            matches = resolve_reference(ledger, occurrence_id=key) if exact else resolve_reference(ledger, semantic_id=key)
            if not exact and not matches and str(key) in ledger.get("occurrences", {}):
                matches = [str(key)]
            if not exact and not matches and ":" in str(key):
                project, finding_id = str(key).split(":", 1)
                matches = resolve_reference(ledger, project=project, finding_id=finding_id)
            for occurrence_id in matches:
                result[occurrence_id] = {**result.get(occurrence_id, {}), **value}

    merge(findings)
    semantic_keys = {key: value for key, value in findings.items() if key in ledger.get("findings", {})} if isinstance(findings, dict) else {}
    merge(semantic_keys)
    merge(occurrences, exact=True)
    return result


def merge_manual_state(ledger: dict, payloads):
    result = {}
    for payload in payloads:
        resolved = resolve_state_map(payload, ledger)
        for key, value in resolved.items():
            result[key] = {**result.get(key, {}), **value}
    return result


def identity_patch(occurrence: dict):
    return {
        "occurrence_id": occurrence["occurrence_id"],
        "semantic_id": occurrence["semantic_id"],
        "project": occurrence["project"],
        "run_id": occurrence["run_id"],
        "finding_id": occurrence["finding_id"],
        "legacy_key": occurrence["legacy_key"],
    }


def legacy_state_view(states: dict, ledger: dict):
    result = {}
    latest = latest_occurrences(ledger)
    for legacy_key, semantics in ledger.get("indexes", {}).get("legacy_to_semantics", {}).items():
        if len(semantics) != 1:
            continue
        semantic = ledger["findings"][semantics[0]]
        occurrence_id = semantic.get("latest_occurrence_id")
        if occurrence_id not in states or occurrence_id not in latest:
            continue
        occurrence = ledger["occurrences"][occurrence_id]
        result[legacy_key] = {**states[occurrence_id], **identity_patch(occurrence)}
    return dict(sorted(result.items()))


def identified_states(states: dict, ledger: dict):
    result = {}
    for occurrence_id, value in states.items():
        occurrence = ledger.get("occurrences", {}).get(occurrence_id)
        if occurrence and isinstance(value, dict):
            result[occurrence_id] = {**value, **identity_patch(occurrence)}
    return dict(sorted(result.items()))


def write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=RUNS)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    ledger = build_ledger(args.runs, args.root)
    write(args.output, ledger)
    print(f"[workflow] ledger semantics={len(ledger['findings'])} occurrences={len(ledger['occurrences'])} -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
