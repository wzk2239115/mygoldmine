#!/usr/bin/env python3
import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ui" / "data"
QUEUE = DATA / "refine-queue.json"
REFINE = DATA / "refine-state.json"
PAUSE = DATA / "refine.pause"
STOP = DATA / "refine.stop"
LOCK = DATA / ".refine-worker.lock"
TRAJECTORY = ROOT / "rsi" / "trajectories" / "refine.jsonl"

sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import build_state as base  # noqa: E402


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def item_paths(raw):
    values = []
    for key in ("evidence", "files", "location"):
        value = raw.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    result = []
    for item in values:
        if isinstance(item, dict):
            item = item.get("path") or item.get("file") or item.get("location") or ""
        value = str(item).split(":")[0].strip().replace("\\", "/").strip("/")
        if value:
            result.append(value)
    return result


def fingerprint(item):
    raw = item.get("raw") or {}
    path = (item_paths(raw) or [""])[0]
    root = raw.get("root_cause") or raw.get("title") or ""
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(root).lower()).strip()
    digest = hashlib.sha1(f"{item['project']}|{path}|{text[:240]}".encode("utf-8")).hexdigest()
    return digest


def source_hash(item, patch):
    material = {
        "raw_hash": item.get("raw_hash") or hashlib.sha256(
            json.dumps(item.get("raw") or {}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "report_hash": item.get("report_hash") or "",
        "evidence": patch,
    }
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evidence_patch(key, auto, manual_data):
    return {**auto.get(key, {}), **manual_data.get(key, {})}


def needs_processing(key, latest, auto, refine, manual_data):
    item = latest.get(key)
    if not item:
        return False
    record = refine.get(key)
    if not isinstance(record, dict):
        return key not in auto and key not in manual_data
    return record.get("source_hash") != source_hash(item, evidence_patch(key, auto, manual_data))


def score(item, patch):
    raw = item.get("raw") or {}
    severity = item.get("severity") or "info"
    value = {"critical": 40, "high": 28, "medium": 12, "low": 3}.get(severity, 0)
    tier = patch.get("cveTier")
    verify_verdict = base.finding_ledger.normalized_verdict(patch.get("verifyVerdict"))
    if tier in (1, 2):
        value += 20
    if verify_verdict in base.finding_ledger.CONFIRMED_VERDICTS:
        value += 15
    elif verify_verdict in {"blocked", "inconclusive"}:
        value += 8
    if item.get("verified") is True:
        value += 6
    if str(raw.get("confidence") or "").lower() in {"high", "verified", "medium-high"}:
        value += 3
    if str(patch.get("verdict") or "") in {"fp", "duplicate"}:
        value -= 30
    if patch.get("knownCve"):
        value -= 30
    return value


def classify(item, patch, value, dup):
    severity = item.get("severity") or "info"
    verify_verdict = base.finding_ledger.normalized_verdict(patch.get("verifyVerdict"))
    if patch.get("cveTier") in (1, 2):
        return "reproduce", "自动分类：CVE Tier 候选，进入去重/验证", ""
    if verify_verdict in base.finding_ledger.CONFIRMED_VERDICTS:
        return "reproduce", "自动分类：已有 confirmed verify 记录", ""
    if dup and severity in {"critical", "high"}:
        return "triage", "自动分类：高危弱指纹疑似重复，保留人工分诊", ""
    if dup:
        return "archived", "自动分类：与已有 finding 重复", dup
    if severity in {"critical", "high"}:
        return "triage", "自动分类：Critical/High 入队，等待人工分诊", ""
    if value >= 40:
        return "triage", "自动分类：证据评分达到分诊门槛", ""
    reason = "自动分类：未达晋级门槛（低优先级/证据不足）"
    return "archived", reason, ""


def trajectory_action(status, severity, duplicate_of):
    if duplicate_of:
        return "duplicate_candidate"
    if status == "reproduce":
        return "verify"
    if status == "triage":
        return "human_review" if severity in {"critical", "high"} else "deep_read"
    return "defer"


def trajectory_record(item, key, patch, status, reason, value, duplicate_of, provenance_hash, now):
    features = {
        "severity": item["severity"],
        "verified": item.get("verified", False),
        "confidence": item.get("confidence", ""),
        "cve_tier": patch.get("cveTier"),
        "verify_verdict": patch.get("verifyVerdict", ""),
        "evidence_count": len(item_paths(item.get("raw") or {})),
    }
    return {
        "schema_version": 1,
        "ts": now,
        "project": item["project"],
        "finding_id": item["id"],
        "occurrence_id": item.get("occurrence_id") or key,
        "semantic_id": item.get("semantic_id") or "",
        "run_id": str(Path(item["report"]).parent.name),
        "features": features,
        "context": {
            "stage": "refine",
            "verification": dict(features),
            "source_hash": provenance_hash,
        },
        "policy": {"name": "legacy_refine", "version": "1"},
        "action_propensity": 1.0,
        "action": trajectory_action(status, item["severity"], duplicate_of),
        "decision": status,
        "reason": reason,
        "score": value,
        "source_hash": provenance_hash,
        "duplicate_of": duplicate_of,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK, "w", encoding="utf-8")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[refine] already running", file=sys.stderr)
        return 0
    lock.write(str(os.getpid()))
    lock.flush()

    if args.reset and not args.dry_run:
        for path in (QUEUE, REFINE):
            path.unlink(missing_ok=True)

    while True:
        if STOP.exists():
            break
        if PAUSE.exists():
            if args.once:
                print("[refine] paused", file=sys.stderr)
                break
            time.sleep(max(1, args.interval))
            continue

        ledger = base.finding_ledger.build_ledger()
        latest = base.latest_findings(ledger)
        curated = load(DATA / "curated.json", {})
        manual = load(DATA / "state.json", {})
        auto_payload = load(DATA / "auto-state.json", {})
        refine_payload = load(REFINE, {})
        auto = base.finding_ledger.merge_manual_state(ledger, [auto_payload])
        refine = base.finding_ledger.merge_manual_state(ledger, [refine_payload])
        queue = load(QUEUE, {"items": {}})
        items = queue.get("items") if isinstance(queue.get("items"), dict) else {}
        manual_data = base.finding_ledger.merge_manual_state(ledger, [curated, manual])

        pending = [
            key for key in latest
            if needs_processing(key, latest, auto, refine, manual_data)
        ]
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        pending.sort(key=lambda key: (severity_order.get(latest[key]["severity"], 9), key))
        pending = pending[: args.batch]

        seen = {}
        for key in list(manual_data) + list(auto):
            if key in latest:
                seen.setdefault(fingerprint(latest[key]), key)

        now = datetime.now(timezone.utc).isoformat()
        made = 0
        for key in pending:
            item = latest[key]
            patch = evidence_patch(key, auto, manual_data)
            fp = fingerprint(item)
            dup = seen.get(fp)
            value = score(item, patch)
            status, reason, duplicate_of = classify(item, patch, value, dup)
            if status != "archived":
                seen.setdefault(fp, key)
            record = {
                "status": status,
                "reason": reason,
                "source": "refine",
                "score": value,
                "source_hash": source_hash(item, patch),
                "updatedAt": now,
            }
            if duplicate_of:
                record["duplicate_of"] = duplicate_of
            if not args.dry_run:
                refine[key] = record
                items[key] = {
                    "state": "done",
                    "status": status,
                    "reason": reason,
                    "score": value,
                    "updatedAt": now,
                }
                TRAJECTORY.parent.mkdir(parents=True, exist_ok=True)
                trajectory = trajectory_record(
                    item,
                    key,
                    patch,
                    status,
                    reason,
                    value,
                    duplicate_of,
                    record["source_hash"],
                    now,
                )
                with TRAJECTORY.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(trajectory, ensure_ascii=False) + "\n")
            made += 1
            print(f"[refine] {key} -> {status} ({value})", file=sys.stderr)

        if not args.dry_run:
            write(REFINE, {
                "schema_version": 2,
                "generated_at": now,
                "findings": base.finding_ledger.identified_states(refine, ledger),
            })
            remaining = sum(
                1 for key in latest
                if needs_processing(key, latest, auto, refine, manual_data)
            )
            stats = {
                "total": len(latest),
                "processed": len(latest) - remaining,
                "pending": remaining,
                "archived": len(
                    [key for key in refine if refine[key].get("status") == "archived"]
                ),
                "promoted": len(
                    [
                        key
                        for key in refine
                        if refine[key].get("status") in {"triage", "reproduce", "cve"}
                    ]
                ),
                "last_batch": now,
                "pid": os.getpid(),
            }
            queue = {
                "schema_version": 1,
                "updated_at": now,
                "paused": PAUSE.exists(),
                "stats": stats,
                "items": items,
            }
            write(QUEUE, queue)
        else:
            remaining = sum(
                1 for key in latest
                if needs_processing(key, latest, auto, refine, manual_data)
            )
            print(
                f"[refine] dry-run batch={made} pending~{max(0, remaining - made)}",
                file=sys.stderr,
            )

        if not args.loop:
            break
        time.sleep(max(1, args.interval))

    lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
