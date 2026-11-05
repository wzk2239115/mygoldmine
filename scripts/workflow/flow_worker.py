#!/usr/bin/env python3
"""Consume classified findings and advance them through verify and red-team.

The worker only records a transition after the underlying phase produced a
report. It never synthesizes `confirmed`, `judge_approved` or `review` state.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ui" / "data"
FLOW_STATE = DATA / "flow-state.json"
FLOW_QUEUE = DATA / "flow-queue.json"
PAUSE = DATA / "flow.pause"
STOP = DATA / "flow.stop"
LOCK = DATA / ".flow-worker.lock"
TRAJECTORY = ROOT / "rsi" / "trajectories" / "flow.jsonl"

sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import build_state as base  # noqa: E402

PHASE4 = ROOT / "scripts" / "verify" / "phase4_verify_agent.sh"
PHASE5 = ROOT / "scripts" / "redteam" / "phase5_redteam.sh"
VISUAL = ROOT / "scripts" / "mine" / "visual_report.sh"
PHASE0 = ROOT / "scripts" / "env" / "phase0_env.sh"
BUILD_STATE = ROOT / "scripts" / "workflow" / "build_state.py"

CONFIRMED = base.finding_ledger.CONFIRMED_VERDICTS
REJECTED = base.finding_ledger.REJECTED_VERDICTS
TERMINAL = {"closed", "archived"}


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def now():
    return datetime.now(timezone.utc)


def iso(value=None):
    return (value or now()).isoformat()


def safe_component(value):
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
    return (text or "finding")[:80]


def flow_id(item):
    digest = hashlib.sha1(str(item["occurrence_id"]).encode("utf-8")).hexdigest()[:8]
    return f"flow-{safe_component(item.get('local_id') or item.get('finding_id'))}-{digest}"


def run_id(item):
    return str(item.get("run_id") or "")


def report_dir(item):
    return Path(base.ROOT / item["report"]).parent


def identity(item):
    return {
        "occurrence_id": item.get("occurrence_id") or "",
        "semantic_id": item.get("semantic_id") or "",
        "run_id": item.get("run_id") or "",
    }


def normalize_verdict(value):
    return base.finding_ledger.normalized_verdict(value)


def payload_maps(ledger):
    auto_payload = load(DATA / "auto-state.json", {})
    refine_payload = load(DATA / "refine-state.json", {})
    flow_payload = load(FLOW_STATE, {})
    curated = load(DATA / "curated.json", {})
    manual = load(DATA / "state.json", {})
    return {
        "auto": base.finding_ledger.merge_manual_state(ledger, [auto_payload]),
        "refine": base.finding_ledger.merge_manual_state(ledger, [refine_payload]),
        "flow": base.finding_ledger.merge_manual_state(ledger, [flow_payload]),
        "curated": base.finding_ledger.merge_manual_state(ledger, [curated]),
        "manual": base.finding_ledger.merge_manual_state(ledger, [manual]),
        "review": base.finding_ledger.merge_manual_state(
            ledger, [{"findings": auto_payload.get("review") or {}}]
        ),
        "auto_payload": auto_payload,
        "flow_payload": flow_payload,
    }


def effective_state(key, maps):
    merged = {}
    for name in ("auto", "refine", "flow", "curated", "manual"):
        value = maps[name].get(key)
        if isinstance(value, dict):
            merged.update(value)
    return merged


def target_source(project):
    payload = load(ROOT / "targets" / "manifest.json", {})
    projects = payload.get("projects") if isinstance(payload, dict) else {}
    entry = projects.get(project) if isinstance(projects, dict) else {}
    return str(entry.get("path") or "") if isinstance(entry, dict) else ""


def build_env(item, args):
    manifest = load(ROOT / "env" / item["project"] / "env-manifest.json", {})
    source = str(manifest.get("source") or target_source(item["project"]) or "")
    if not source or not Path(source).is_dir():
        return None, "env manifest/source missing"
    meta_dir = DATA / "flow-env" / item["project"]
    command = [
        "bash", str(PHASE0), source,
        "--project", item["project"],
        "--mode", "auto",
        "--meta-dir", str(meta_dir),
        "--agent", "auto",
        "--build-timeout", str(args.env_build_timeout),
        "--agent-timeout", str(args.env_agent_timeout),
        "--claude-bin", args.claude,
    ]
    if args.model:
        command.extend(["--model", args.model])
    result = call(
        command,
        args.env_build_timeout + args.env_agent_timeout + 180,
        meta_dir / "flow-env.log",
    )
    env, error = env_for(item)
    if env:
        return env, ""
    return None, f"env build rc={result['returncode']}: {error}"


def env_for(item):
    project = item["project"]
    manifest_path = ROOT / "env" / project / "env-manifest.json"
    manifest = load(manifest_path, {})
    if not manifest:
        return None, "env manifest missing"
    status = str(manifest.get("env_status") or "").lower()
    if status in {"blocked", "missing", "failed"}:
        return None, f"env_status={status}"
    image = str(manifest.get("image") or "").strip()
    source = str(manifest.get("source") or "").strip()
    if not image or not source:
        return None, "env manifest has no image/source"
    if not Path(source).is_dir():
        return None, f"source missing: {source}"
    docker = os.environ.get("FLOW_DOCKER_BIN", "docker")
    if shutil.which(docker):
        try:
            checked = subprocess.run(
                [docker, "image", "inspect", image],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"docker unavailable: {exc}"
        if checked.returncode != 0:
            return None, f"image missing: {image}"
    else:
        return None, f"docker unavailable: {docker}"
    return {"image": image, "source": source, "manifest": str(manifest_path)}, ""


def call(command, timeout, log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, timeout=timeout
        )
        result = {
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "returncode": 124,
            "stdout": str(exc.stdout or "")[-4000:],
            "stderr": f"timeout after {timeout}s",
        }
    log_path.write_text(
        f"$ {' '.join(str(part) for part in command)}\n"
        f"rc={result['returncode']}\n"
        f"--- stdout ---\n{result['stdout']}\n--- stderr ---\n{result['stderr']}\n",
        encoding="utf-8",
    )
    return result


def build_state():
    command = [sys.executable, str(BUILD_STATE)]
    return call(command, 300, DATA / "flow-build-state.log")


def verify_one(item, env, args):
    run_dir = report_dir(item)
    output = run_dir / "verify" / "flow" / flow_id(item)
    output.mkdir(parents=True, exist_ok=True)
    command = [
        "bash", str(PHASE4),
        "--project", item["project"],
        "--run-dir", str(run_dir),
        "--image", env["image"],
        "--source", env["source"],
        "--max", "1",
        "--severity", "critical,high,medium,low,info",
        "--timeout", str(args.verify_timeout),
        "--agent-timeout", str(args.agent_timeout),
        "--claude-bin", args.claude,
        "--output", str(output),
        "--finding-id", str(item.get("local_id") or item.get("finding_id") or ""),
        "--occurrence-id", item.get("occurrence_id") or "",
        "--semantic-id", item.get("semantic_id") or "",
        "--run-id", run_id(item),
    ]
    if args.model:
        command.extend(["--model", args.model])
    result = call(command, args.agent_timeout + args.verify_timeout + 180, output / "flow.log")
    summary_path = output / "summary.json"
    summary = load(summary_path, {})
    findings = summary.get("findings") if isinstance(summary.get("findings"), list) else []
    entry = findings[0] if findings else {}
    verdict = normalize_verdict(entry.get("verdict"))
    report_path = entry.get("report_path") or ""
    if result["returncode"] == 4:
        return "blocked", "自动流转受阻：Claude 命令行工具不可用", verdict, [], summary_path
    if not entry:
        return "blocked", "自动流转受阻：第 4 阶段没有候选问题记录", verdict, [], summary_path
    if verdict in REJECTED:
        return (
            "closed", f"自动流转：验证未通过（{verdict}）",
            verdict, [report_path], summary_path,
        )
    if verdict in CONFIRMED:
        return (
            "reproduce", f"自动流转：验证已确认（{verdict}）",
            verdict, [report_path], summary_path,
        )
    return (
        "triage", f"自动流转：验证结论为 {verdict or '未知'}，等待重试",
        verdict, [report_path], summary_path,
    )


def visual_ready(item):
    run_dir = report_dir(item)
    finding = str(item.get("local_id") or item.get("finding_id") or "")
    return (
        (run_dir / "visual-rendered" / "report-illustrated.md").exists()
        and (run_dir / "visual-rendered" / f"scene-{finding}.webp").exists()
    )


def prepare_visual(item, args):
    if args.skip_visual or visual_ready(item):
        return True, "ready"
    run_dir = report_dir(item)
    output = run_dir / "visual-rendered"
    command = [
        "bash", str(VISUAL),
        "--project", item["project"],
        "--run-dir", str(run_dir),
        "--max", "1",
        "--finding-id", str(item.get("local_id") or item.get("finding_id") or ""),
        "--timeout", str(args.visual_timeout),
        "--agent-timeout", str(args.visual_agent_timeout),
        "--claude-bin", args.claude,
        "--output", str(output),
    ]
    if args.model:
        command.extend(["--model", args.model])
    result = call(
        command,
        args.visual_agent_timeout + args.visual_timeout + 120,
        output / "flow-visual.log",
    )
    summary = load(output / "visual-summary.json", {})
    status = str(summary.get("status") or "")
    if result["returncode"] == 0 and visual_ready(item):
        return True, "ready"
    return False, status or f"visual rc={result['returncode']}"


def redteam_one(item, args):
    run_dir = report_dir(item)
    output = run_dir / "redteam" / flow_id(item)
    output.mkdir(parents=True, exist_ok=True)
    command = [
        "bash", str(PHASE5),
        "--project", item["project"],
        "--run-dir", str(run_dir),
        "--max", "1",
        "--severity", "critical,high,medium,low,info",
        "--finding-id", str(item.get("local_id") or item.get("finding_id") or ""),
        "--model", args.redteam_model,
        "--base-url", args.redteam_base_url,
        "--api-key", args.redteam_api_key,
        "--build-timeout", str(args.build_timeout),
        "--agent-timeout", str(args.redteam_agent_timeout),
        "--judge-timeout", str(args.judge_timeout),
        "--judge-claude", args.claude,
        "--output", str(output),
    ]
    if args.model:
        command.extend(["--judge-claude-model", args.model])
    call(
        command,
        args.build_timeout + args.redteam_agent_timeout + args.judge_timeout + 180,
        output / "flow.log",
    )
    summary = load(output / "summary.json", {})
    results = summary.get("results") if isinstance(summary.get("results"), list) else []
    wanted = str(item.get("local_id") or item.get("finding_id") or "")
    entry = next(
        (
            row for row in results
            if str(row.get("id") or row.get("finding_id") or "") == wanted
        ),
        results[0] if results else {},
    )
    outcome = str(entry.get("status") or summary.get("status") or "unknown")
    artifact = str(output / "summary.json")
    if outcome == "judge_approved":
        return (
            "reproduce", "自动流转：红队独立审核通过，检查待人工验收条件",
            outcome, [artifact],
        )
    return "reproduce", f"自动流转：红队验证结束（结果：{outcome}）", outcome, [artifact]


def update_record(state, key, status, reason, stage, outcome, attempts, artifacts, extra=None):
    record = {
        "status": status,
        "source": "flow",
        "reason": reason,
        "flowStage": stage,
        "flowOutcome": outcome,
        "flowAttempts": attempts,
        "flowUpdatedAt": iso(),
        "artifacts": [str(path) for path in artifacts if path],
    }
    if extra:
        record.update(extra)
    state.setdefault("findings", {})[key] = record
    return record


def append_trajectory(item, record):
    row = {
        "schema_version": 1,
        "ts": record["flowUpdatedAt"],
        "project": item["project"],
        "finding_id": item.get("finding_id"),
        "occurrence_id": item.get("occurrence_id"),
        "semantic_id": item.get("semantic_id"),
        "run_id": item.get("run_id"),
        "stage": record.get("flowStage"),
        "outcome": record.get("flowOutcome"),
        "status": record.get("status"),
        "attempts": record.get("flowAttempts"),
        "reason": record.get("reason"),
        "artifacts": record.get("artifacts", []),
    }
    TRAJECTORY.parent.mkdir(parents=True, exist_ok=True)
    with TRAJECTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def candidates(ledger, maps, args):
    latest = base.latest_findings(ledger)
    flow_payload = maps["flow_payload"]
    flow_findings = flow_payload.get("findings") if isinstance(flow_payload, dict) else {}
    flow_records = flow_findings if isinstance(flow_findings, dict) else {}
    result = []
    for key, item in latest.items():
        if args.project and item.get("project") != args.project:
            continue
        if key in maps["review"]:
            continue
        merged = effective_state(key, maps)
        status = merged.get("status") or "inbox"
        if status not in {"triage", "reproduce"}:
            continue
        record = flow_records.get(key) if isinstance(flow_records.get(key), dict) else {}
        attempts = int(record.get("flowAttempts") or 0)
        if attempts >= args.max_attempts:
            continue
        next_at = str(record.get("flowNextAt") or "")
        if next_at:
            try:
                if datetime.fromisoformat(next_at.replace("Z", "+00:00")) > now():
                    continue
            except ValueError:
                pass
        result.append((key, item, merged, record))
    def env_rank(item):
        manifest = load(ROOT / "env" / item["project"] / "env-manifest.json", {})
        source = str(manifest.get("source") or "")
        return 0 if manifest.get("image") and source and Path(source).is_dir() else 1

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    result.sort(
        key=lambda row: (
            env_rank(row[1]),
            severity_rank.get(row[1].get("severity"), 9),
            str(row[0]),
        )
    )
    return result[: args.batch]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=1)
    parser.add_argument("--project", default="")
    parser.add_argument("--model", default=os.environ.get("FLOW_MODEL", ""))
    parser.add_argument("--claude", default=os.environ.get("CLAUDE_BIN", "claude"))
    parser.add_argument("--verify-timeout", type=int, default=300)
    parser.add_argument("--agent-timeout", type=int, default=900)
    parser.add_argument("--visual-timeout", type=int, default=300)
    parser.add_argument("--visual-agent-timeout", type=int, default=900)
    parser.add_argument("--redteam-model", default=os.environ.get("REDTEAM_MODEL", "flint"))
    parser.add_argument("--redteam-base-url", default=os.environ.get("REDTEAM_BASE_URL", "http://100.81.81.75:8081/v1"))
    parser.add_argument("--redteam-api-key", default=os.environ.get("REDTEAM_API_KEY", "local"))
    parser.add_argument("--build-timeout", type=int, default=1260)
    parser.add_argument("--redteam-agent-timeout", type=int, default=900)
    parser.add_argument("--judge-timeout", type=int, default=360)
    parser.add_argument("--skip-visual", action="store_true")
    parser.add_argument(
        "--build-env",
        action="store_true",
        default=os.environ.get("FLOW_BUILD_ENV") == "1",
    )
    parser.add_argument("--env-build-timeout", type=int, default=3600)
    parser.add_argument("--env-agent-timeout", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if min(args.interval, args.batch, args.max_attempts) <= 0:
        parser.error("interval/batch/max-attempts must be positive")

    DATA.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK, "w", encoding="utf-8")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[flow] already running", file=sys.stderr)
        return 0
    lock.write(str(os.getpid()))
    lock.flush()

    if args.reset and not args.dry_run:
        for path in (FLOW_STATE, FLOW_QUEUE):
            path.unlink(missing_ok=True)

    while True:
        if STOP.exists():
            break
        if PAUSE.exists():
            if args.once:
                print("[flow] paused", file=sys.stderr)
                break
            time.sleep(max(1, args.interval))
            continue

        ledger = base.finding_ledger.build_ledger()
        maps = payload_maps(ledger)
        state = load(FLOW_STATE, {"schema_version": 1, "findings": {}})
        if not isinstance(state.get("findings"), dict):
            state["findings"] = {}
        queue_items = load(FLOW_QUEUE, {}).get("items")
        queue_items = queue_items if isinstance(queue_items, dict) else {}
        pending = candidates(ledger, maps, args)
        made = 0
        for key, item, merged, previous in pending:
            stage = "redteam" if (merged.get("status") == "reproduce") else "verify"
            flow = dict(previous)
            attempts = int(flow.get("flowAttempts") or 0) + 1
            if args.dry_run:
                print(f"[flow] would {stage} {key} attempt={attempts}", file=sys.stderr)
                made += 1
                continue
            env, env_error = env_for(item)
            if not env and args.build_env:
                env, env_error = build_env(item, args)
            if not env:
                record = update_record(
                    state, key, merged.get("status") or "triage",
                    f"自动流转受阻: {env_error}", stage, "blocked", 0,
                    [], {"flowBlocked": True, "flowNextAt": iso(now() + timedelta(hours=1))},
                )
                queue_items[key] = {**record, "state": "blocked"}
                append_trajectory(item, record)
                made += 1
                continue

            artifacts = []
            extra = {}
            if stage == "verify":
                status, reason, outcome, artifacts, summary_path = verify_one(item, env, args)
                if status == "reproduce":
                    extra["verifyVerdict"] = outcome
                if status == "closed":
                    extra["verdict"] = "fp"
                if summary_path:
                    artifacts.append(summary_path)
                if status == "triage":
                    record = update_record(
                        state, key, status, reason, stage, outcome, attempts, artifacts,
                        {**extra, "flowNextAt": iso(now() + timedelta(hours=1))},
                    )
                else:
                    record = update_record(
                        state, key, status, reason, stage, outcome, attempts, artifacts, extra
                    )
            else:
                visual_ok, visual_status = prepare_visual(item, args)
                status, reason, outcome, artifacts = redteam_one(item, args)
                if not visual_ok:
                    reason = f"{reason}；图文报告未就绪: {visual_status}"
                    extra["visualStatus"] = visual_status
                else:
                    extra["visualStatus"] = "ready"
                record = update_record(
                    state, key, status, reason, stage, outcome, attempts, artifacts, extra
                )
                if outcome == "judge_approved":
                    built = build_state()
                    if built.get("returncode") != 0:
                        record["reason"] += "；build_state 失败"
                    else:
                        review = load(DATA / "auto-state.json", {}).get("review") or {}
                        if isinstance(review, dict) and key in review:
                            record["reason"] = "自动流转：待人工验收条件已满足，等待人工验收"
                            record["flowOutcome"] = "review_ready"
            queue_items[key] = {**record, "state": "done"}
            append_trajectory(item, record)
            made += 1
            print(
                f"[flow] {key} -> {record['status']} "
                f"({record['flowStage']}/{record['flowOutcome']})",
                file=sys.stderr,
            )

        if not args.dry_run:
            maps_now = {
                **maps,
                "flow": state["findings"],
                "flow_payload": {"findings": state["findings"]},
            }
            remaining = len(candidates(ledger, maps_now, args))
            stats = {
                "total": len(base.latest_findings(ledger)),
                "processed": made,
                "pending": remaining,
                "blocked": sum(
                    1 for value in state["findings"].values()
                    if value.get("flowBlocked")
                ),
                "by_stage": {
                    "verify": sum(
                        1 for value in state["findings"].values()
                        if value.get("flowStage") == "verify"
                    ),
                    "redteam": sum(
                        1 for value in state["findings"].values()
                        if value.get("flowStage") == "redteam"
                    ),
                },
                "last_cycle": iso(),
                "pid": os.getpid(),
            }
            write(FLOW_STATE, {
                "schema_version": 1,
                "generated_at": iso(),
                "findings": state["findings"],
            })
            write(FLOW_QUEUE, {
                "schema_version": 1,
                "updated_at": iso(),
                "paused": PAUSE.exists(),
                "stats": stats,
                "items": queue_items,
            })
        if not args.loop:
            break
        time.sleep(max(1, args.interval))

    lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
