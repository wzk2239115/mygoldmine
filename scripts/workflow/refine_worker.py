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


def score(item, patch):
    raw = item.get("raw") or {}
    severity = item.get("severity") or "info"
    value = {"critical": 40, "high": 28, "medium": 12, "low": 3}.get(severity, 0)
    tier = patch.get("cveTier")
    verify_verdict = str(patch.get("verifyVerdict") or "").lower()
    if tier in (1, 2):
        value += 20
    if verify_verdict in {"confirmed", "verified", "reproduced"}:
        value += 15
    elif verify_verdict in {"blocked", "inconclusive"}:
        value += 8
    if raw.get("verified"):
        value += 6
    if str(raw.get("confidence") or "").lower() in {"high", "verified", "medium-high"}:
        value += 3
    if str(patch.get("verdict") or "") in {"fp", "duplicate"}:
        value -= 30
    if patch.get("knownCve"):
        value -= 30
    return value


def classify(item, patch, value, dup):
    if dup:
        return "archived", "自动精炼：与已有 finding 重复", dup
    raw = item.get("raw") or {}
    severity = item.get("severity") or "info"
    if patch.get("cveTier") in (1, 2):
        return "reproduce", "自动精炼：CVE Tier 候选，进入去重/复现", ""
    if str(patch.get("verifyVerdict") or "").lower() in {"confirmed", "verified", "reproduced"}:
        return "reproduce", "自动精炼：已有 confirmed verify 记录", ""
    if severity in {"critical", "high"}:
        return "triage", "自动精炼：Critical/High 入队，等待人工分诊", ""
    if value >= 40:
        return "triage", "自动精炼：证据评分达到分诊门槛", ""
    reason = "自动精炼：未达晋级门槛（低优先级/证据不足）"
    return "archived", reason, ""


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

        latest = base.latest_findings()
        curated = load(DATA / "curated.json", {})
        manual = load(DATA / "state.json", {})
        auto_payload = load(DATA / "auto-state.json", {})
        refine_payload = load(REFINE, {})
        auto = auto_payload.get("findings") or {}
        refine = refine_payload.get("findings") or {}
        queue = load(QUEUE, {"items": {}})
        items = queue.get("items") if isinstance(queue.get("items"), dict) else {}

        manual_data = {}
        for payload in (curated, manual):
            for raw_key, value in payload.items() if isinstance(payload, dict) else []:
                project, finding_id = base.split_key(raw_key)
                key = base.canon(project, finding_id)
                if isinstance(value, dict):
                    manual_data[key] = {**manual_data.get(key, {}), **value}

        done = set(manual_data) | set(auto) | set(refine)
        pending = [key for key in latest if key not in done]
        pending.sort(key=lambda key: ({"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(latest[key]["severity"], 9), key))
        pending = pending[: args.batch]

        seen = {}
        for key in list(manual_data) + list(auto):
            if key in latest:
                seen.setdefault(fingerprint(latest[key]), key)

        now = datetime.now(timezone.utc).isoformat()
        made = 0
        for key in pending:
            item = latest[key]
            patch = {**auto.get(key, {}), **refine.get(key, {}), **manual_data.get(key, {})}
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
                "updatedAt": now,
            }
            if duplicate_of:
                record["duplicate_of"] = duplicate_of
            if not args.dry_run:
                refine[key] = record
                items[key] = {"state": "done", "status": status, "reason": reason, "score": value, "updatedAt": now}
                TRAJECTORY.parent.mkdir(parents=True, exist_ok=True)
                with TRAJECTORY.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({
                        "ts": now,
                        "project": item["project"],
                        "finding_id": item["id"],
                        "run_id": str(Path(item["report"]).parent.name),
                        "features": {
                            "severity": item["severity"],
                            "verified": item.get("verified", False),
                            "confidence": item.get("confidence", ""),
                            "cve_tier": patch.get("cveTier"),
                            "verify_verdict": patch.get("verifyVerdict", ""),
                            "evidence_count": len(item_paths(item.get("raw") or {})),
                        },
                        "decision": status,
                        "reason": reason,
                        "score": value,
                    }, ensure_ascii=False) + "\n")
            made += 1
            print(f"[refine] {key} -> {status} ({value})", file=sys.stderr)

        if not args.dry_run:
            write(REFINE, {"schema_version": 1, "generated_at": now, "findings": refine})
            done = set(manual_data) | set(auto) | set(refine)
            remaining = sum(1 for key in latest if key not in done)
            stats = {
                "total": len(latest),
                "processed": len([key for key in latest if key in done]),
                "pending": remaining,
                "archived": len([key for key in refine if refine[key].get("status") == "archived"]),
                "promoted": len([key for key in refine if refine[key].get("status") in {"triage", "reproduce", "cve"}]),
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
            remaining = sum(1 for key in latest if key not in done)
            print(f"[refine] dry-run batch={made} pending~{max(0, remaining - made)}", file=sys.stderr)

        if not args.loop or remaining == 0:
            break
        time.sleep(max(1, args.interval))

    lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
