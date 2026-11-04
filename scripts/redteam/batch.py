#!/usr/bin/env python3
import argparse
import json
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import build_state as base  # noqa: E402
from model_config import DEFAULT_MODEL  # noqa: E402
from pipeline_stage import record_stage  # noqa: E402
from contracts import (  # noqa: E402
    ContractError,
    classify_agent_failure,
    finding_id as validate_finding_id,
    resolve_scenario,
    scenario_path,
)

CANDIDATES = ROOT / "docs" / "redteam-candidates.json"
BATCH_ROOT = ROOT / "runs" / "redteam" / "batch"


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def output_tail(value, limit):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "")[-limit:]


def report_snapshot(file):
    file = Path(file).resolve()
    sys.path.insert(0, str(ROOT / "scripts" / "mine"))
    from check_report import check_report

    data = file.read_bytes()
    quality = check_report(file)
    if not quality["valid"] or quality["incomplete"]:
        raise ValueError("本轮报告未通过质量检查")
    if file.read_bytes() != data:
        raise ValueError("报告在校验期间发生变化")
    report = json.loads(data)
    items = {}
    for raw in report.get("findings", report.get("vulnerabilities", [])):
        fid = str(raw.get("id") or raw.get("finding_id") or "")
        if not fid or fid in items:
            raise ValueError("报告中的候选问题编号缺失或重复")
        items[fid] = {"raw": raw}
    return {
        "project": report.get("project"), "run_id": file.parent.name,
        "items": items, "sha256": hashlib.sha256(data).hexdigest(),
    }


def resolve_candidate(candidate, ledger, snapshot=None):
    if snapshot is not None:
        if snapshot["project"] and snapshot["project"] != candidate.get("project"):
            return None
        if candidate.get("run_id") != snapshot["run_id"]:
            return None
        return snapshot["items"].get(candidate.get("id"))
    matches = base.finding_ledger.resolve_reference(
        ledger, project=candidate.get("project", ""), finding_id=candidate.get("id", ""),
        run_id=candidate.get("run_id", ""), occurrence_id=candidate.get("occurrence_id", ""),
        semantic_id=candidate.get("semantic_id", ""),
    )
    return next((ledger["occurrences"][key] for key in matches
                 if key in ledger.get("occurrences", {})), None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default=str(CANDIDATES))
    parser.add_argument("--report", default="", help="本轮已验收报告；不通过全局完成态索引读取")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--build-labs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--build-timeout", type=int, default=1260)
    parser.add_argument("--agent-timeout", type=int, default=900)
    parser.add_argument("--judge-timeout", type=int, default=360)
    parser.add_argument("--judge-claude", default="claude")
    parser.add_argument("--judge-claude-model", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if min(args.build_timeout, args.agent_timeout, args.judge_timeout) <= 0:
        parser.error("timeouts must be positive")

    candidates = load(Path(args.candidates), {}).get("candidates", [])
    snapshot = report_snapshot(args.report) if args.report else None
    ledger = base.finding_ledger.build_ledger() if snapshot is None else {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_dir = Path(args.out_dir).resolve() if args.out_dir else BATCH_ROOT / stamp
    batch_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for index, candidate in enumerate(candidates, 1):
        project = candidate.get("project", "")
        candidate_id = candidate.get("id", "")
        key = base.canon(project, candidate_id)
        item = resolve_candidate(candidate, ledger, snapshot)
        entry = {"project": project, "id": candidate_id, "key": key, "status": "blocked_no_finding"}
        if snapshot is not None:
            entry["report_sha256"] = snapshot["sha256"]
        if item:
            try:
                preferred_path = scenario_path(ROOT, project, candidate_id)
            except ContractError as exc:
                entry.update({"status": exc.status, "error": str(exc)})
                summary.append(entry)
                print(json.dumps(entry, ensure_ascii=False))
                continue
            finding_path = batch_dir / f"{index:02d}-{project}-{candidate_id}.json"
            finding = dict(item.get("raw") or {})
            finding.setdefault("id", candidate_id)
            try:
                if validate_finding_id(finding) != str(candidate_id):
                    raise ContractError("blocked_finding_mismatch", "candidate and finding ids differ")
            except ContractError as exc:
                entry.update({"status": exc.status, "error": str(exc)})
                summary.append(entry)
                print(json.dumps(entry, ensure_ascii=False))
                continue
            finding_path.write_text(json.dumps(finding, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            entry.update({"finding": str(finding_path), "scenario": str(preferred_path)})
            build_attempted = False
            if not preferred_path.exists() and args.build_labs and not args.dry_run:
                build_attempted = True
                try:
                    record_stage("redteam-lab", str(candidate_id))
                    builder = subprocess.run(
                        [sys.executable, str(ROOT / "scripts" / "redteam" / "build_lab.py"),
                         "--project", project, "--finding", str(finding_path),
                         "--claude-model", args.model],
                        capture_output=True, text=True, cwd=ROOT, timeout=args.build_timeout,
                    )
                    entry["builder_returncode"] = builder.returncode
                    entry["builder_stdout"] = output_tail(builder.stdout, 1200)
                    entry["builder_stderr"] = output_tail(builder.stderr, 1200)
                except subprocess.TimeoutExpired as exc:
                    entry.update({
                        "status": "build_failed", "builder_returncode": 124,
                        "builder_timed_out": True,
                        "builder_stdout": output_tail(exc.stdout, 1200),
                        "builder_stderr": output_tail(exc.stderr, 1200),
                    })
                if entry.get("builder_returncode") != 0:
                    entry["status"] = "build_failed"
                    summary.append(entry)
                    print(json.dumps(entry, ensure_ascii=False))
                    continue
            try:
                resolved_path, scenario = resolve_scenario(
                    ROOT, project, finding, finding_path.read_bytes()
                )
                entry["scenario"] = str(resolved_path)
            except ContractError as exc:
                entry.update({
                    "status": "build_failed" if build_attempted else exc.status,
                    "validation_status": exc.status,
                    "error": str(exc),
                })
                summary.append(entry)
                print(json.dumps(entry, ensure_ascii=False))
                continue
            if args.dry_run:
                entry["status"] = "ready"
            else:
                run_id = f"batch-{stamp}-{index:02d}"
                agent = [
                    sys.executable, str(ROOT / "scripts" / "redteam" / "agent.py"),
                    "--finding", str(finding_path),
                    "--project", project,
                    "--scenario", str(resolved_path),
                    "--run-id", run_id,
                    "--model", args.model,
                    "--base-url", args.base_url,
                    "--api-key", args.api_key,
                    "--max-steps", str(args.max_steps),
                    "--max-tokens", str(args.max_tokens),
                ]
                run_dir = ROOT / "runs" / "redteam" / project / run_id
                entry["run_dir"] = str(run_dir)
                agent_timed_out = False
                try:
                    record_stage("redteam-agent", str(candidate_id))
                    completed = subprocess.run(
                        agent, capture_output=True, text=True, cwd=ROOT,
                        timeout=args.agent_timeout,
                    )
                    entry["agent_returncode"] = completed.returncode
                    entry["stdout"] = output_tail(completed.stdout, 1000)
                    entry["stderr"] = output_tail(completed.stderr, 1000)
                except subprocess.TimeoutExpired as exc:
                    agent_timed_out = True
                    entry.update({
                        "agent_returncode": 124, "agent_timed_out": True,
                        "stdout": output_tail(exc.stdout, 1000),
                        "stderr": output_tail(exc.stderr, 1000),
                    })
                if not agent_timed_out and entry["agent_returncode"] == 0:
                    judge_command = [
                        sys.executable, str(ROOT / "scripts" / "redteam" / "judge.py"),
                        "--run-dir", str(run_dir), "--timeout", str(args.judge_timeout),
                        "--claude", args.judge_claude,
                    ]
                    if args.judge_claude_model:
                        judge_command += ["--claude-model", args.judge_claude_model]
                    try:
                        record_stage("judge", str(candidate_id))
                        judge = subprocess.run(
                            judge_command,
                            capture_output=True, text=True, cwd=ROOT, timeout=args.judge_timeout,
                        )
                        entry["judge_returncode"] = judge.returncode
                        entry["judge_stdout"] = output_tail(judge.stdout, 1000)
                        entry["judge_stderr"] = output_tail(judge.stderr, 1000)
                        entry["status"] = "judge_approved" if judge.returncode == 0 else "judge_rejected"
                    except subprocess.TimeoutExpired:
                        entry.update({
                            "status": "judge_timeout", "judge_returncode": 124,
                            "judge_timed_out": True,
                        })
                else:
                    result = load(run_dir / "result.json", {})
                    entry["status"] = classify_agent_failure(
                        entry["agent_returncode"], result, timed_out=agent_timed_out
                    )
        summary.append(entry)
        print(json.dumps(entry, ensure_ascii=False))
    output = {"generated_at": datetime.now(timezone.utc).isoformat(), "model": args.model, "results": summary}
    (batch_dir / "summary.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for item in summary:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"batch": str(batch_dir), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
