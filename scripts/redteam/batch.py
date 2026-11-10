#!/usr/bin/env python3
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import build_state as base  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts/runner"))
from auto_repair import ensure_runner
from model_config import DEFAULT_MODEL  # noqa: E402
from pipeline_stage import record_stage  # noqa: E402
from blue_handoff import validate_packet
from contracts import (  # noqa: E402
    ContractError,
    classify_agent_failure,
    finding_id as validate_finding_id,
    resolve_scenario,
    scenario_path,
    validate_scenario,
)

CANDIDATES = ROOT / "docs" / "redteam-candidates.json"
BATCH_ROOT = ROOT / "runs" / "redteam" / "batch"
HARNESS_MODULES = ("openai",)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def output_tail(value, limit):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "")[-limit:]


def missing_harness_modules(modules=HARNESS_MODULES):
    missing = []
    for name in modules:
        try:
            found = importlib.util.find_spec(name)
        except (ImportError, AttributeError, ValueError):
            found = None
        if found is None:
            missing.append(name)
    return missing


def harness_missing_module(stderr):
    pattern = r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
    match = re.search(pattern, str(stderr or ""))
    return match.group(1).split(".")[0] if match else ""


def write_harness_block(batch_dir, candidates, missing, model):
    results = []
    for candidate in candidates:
        project = str(candidate.get("project", ""))
        identifier = str(candidate.get("id") or candidate.get("finding_id") or "")
        results.append({
            "project": project,
            "id": identifier,
            "key": base.canon(project, identifier),
            "status": "blocked_harness_dependency",
            "error_scope": "harness_dependency",
            "retry_owner": "runner-environment",
            "auto_retry": False,
            "missing_modules": missing,
            "python": sys.executable,
            "python_version": sys.version.split()[0],
            "runner_image": os.environ.get("MYGOLDMINE_RUNNER_IMAGE", ""),
            "error": "审计运行镜像缺少执行依赖：" + ", ".join(missing),
        })
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "error_scope": "harness_dependency",
        "retry_owner": "runner-environment",
        "results": results,
    }
    summary_path = batch_dir / "summary.json"
    summary_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    counts = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"batch": str(batch_dir), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


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


def build_parallel(candidates, ledger, snapshot, batch_dir, args):
    root = batch_dir / "construction"
    plans = []
    for index, candidate in enumerate(candidates, 1):
        project, identifier = candidate.get("project", ""), candidate.get("id", "")
        item = resolve_candidate(candidate, ledger, snapshot)
        if not item:
            continue
        try:
            if snapshot is not None:
                context = validate_packet(candidate.get('blue_handoff', ''), item.get('raw') or {}, project)
                if context.get('run_id') != candidate.get('run_id') or context.get('report_sha256') != snapshot['sha256']:
                    raise ValueError('蓝队交付不属于本轮审计报告')
            preferred = scenario_path(ROOT, project, identifier)
            finding = dict(item.get("raw") or {})
            if snapshot is None:
                finding.setdefault("id", identifier)
            if validate_finding_id(finding) != str(identifier) or preferred.exists():
                continue
        except (ContractError, OSError, ValueError, KeyError, TypeError):
            continue
        file = batch_dir / f"{index:02d}-{project}-{identifier}.json"
        file.write_text(json.dumps(finding, ensure_ascii=False, indent=2) + "\n")
        key = base.canon(project, identifier)
        if any(plan["key"] == key for plan in plans):
            continue
        plans.append({"id": identifier, "project": project, "key": key,
                      "title": finding.get("title", identifier), "finding": str(file), "state": "queued", "blue_handoff": candidate.get("blue_handoff", "")})
    if not plans:
        return {}
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    def write(file, value):
        temp = file.with_suffix(".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
        temp.replace(file)

    def save():
        for plan in plans:
            write(root / "tasks" / f"{plan['project']}--{plan['id']}.json", plan)
        write(root / "summary.json", {"concurrency": args.build_jobs, "selected": len(plans),
              "processed": sum(plan["state"] == "completed" for plan in plans),
              "results": [plan for plan in plans if plan["state"] == "completed"]})

    write(root / "selection.json", {"candidates": plans})
    save()
    record_stage("redteam-lab")

    def execute(plan):
        lab = root / "labs" / plan["project"] / plan["id"]
        lab.mkdir(parents=True, exist_ok=True)
        with lock:
            plan["state"] = "running"
            save()
        try:
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/redteam/build_lab.py"),
                 "--project", plan["project"], "--finding", plan["finding"],
                 "--lab-dir", str(lab), "--claude-model", args.model, "--build-only"]
                + (["--blue-handoff", plan["blue_handoff"]] if plan["blue_handoff"] else []),
                capture_output=True, text=True, cwd=ROOT, timeout=args.build_timeout)
            rc, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            rc, stdout, stderr, timed_out = 124, exc.stdout, exc.stderr, True
        except OSError as exc:
            rc, stdout, stderr, timed_out = 1, "", str(exc), False
        try:
            delivery = json.loads(stdout)
        except (ValueError, TypeError):
            delivery = {}
        if not isinstance(delivery, dict):
            delivery = {}
        scenario = lab / "scenario.json"
        ready = (rc == 0 and delivery.get("scenario_valid") is True
                 and delivery.get("finding_id") == plan["id"]
                 and delivery.get("scenario") == str(scenario) and scenario.is_file())
        blocked = (
            delivery.get("status") == "blocked"
            and delivery.get("blocked_valid") is True
            and delivery.get("finding_id") == plan["id"]
        )
        if ready:
            status = "built"
        elif blocked:
            status = "blocked"
        elif delivery.get("status") == "blocked_unstructured":
            status = "blocked_unstructured"
        else:
            status = "build_failed"
        with lock:
            plan.update({
                "state": "completed",
                "status": status,
                "scenario": str(scenario) if ready else "",
                "blocked": delivery.get("blocked", ""),
                "blocked_reason": delivery.get("blocked_reason", ""),
                "blocked_surface": delivery.get("blocked_surface", ""),
                "missing_capabilities": delivery.get("missing_capabilities", []),
                "mode": delivery.get("mode", ""),
                "builder_returncode": rc,
                "builder_stdout": output_tail(stdout, 1200),
                "builder_stderr": output_tail(stderr, 1200),
                "builder_timed_out": timed_out,
                "error": "" if ready else (
                    delivery.get("blocked_reason")
                    or delivery.get("error")
                    or "场景构建未通过检查"
                ),
            })
            save()
        return plan

    def safe_execute(plan):
        try:
            return execute(plan)
        except Exception as exc:
            # A worker bookkeeping/runtime error belongs to this candidate, not
            # the whole batch. Persist it so downstream stages can skip it.
            with lock:
                plan.update({"state": "completed", "status": "build_failed",
                             "error": f"构建工作项异常：{type(exc).__name__}: {exc}"})
                save()
            return plan

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.build_jobs) as pool:
        results = list(pool.map(safe_execute, plans))
    return {plan["key"]: plan for plan in results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default=str(CANDIDATES))
    parser.add_argument("--report", default="", help="本轮已验收报告；不通过全局完成态索引读取")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--build-labs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--build-jobs", type=int, choices=range(1, 11), default=10)
    parser.add_argument("--agent-jobs", type=int, choices=range(1, 11), default=10)
    parser.add_argument("--judge-jobs", type=int, choices=range(1, 11), default=10)
    parser.add_argument("--build-timeout", type=int, default=1260)
    parser.add_argument("--agent-timeout", type=int, default=7200)
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
    missing = missing_harness_modules() if candidates and not args.dry_run else []
    if missing:
        repair = ensure_runner(sys.executable, batch_dir / "runner-repair", args.model)
        if repair["status"] != "ready":
            return write_harness_block(batch_dir, candidates, missing, args.model)

    prebuilt = (
        build_parallel(candidates, ledger, snapshot, batch_dir, args)
        if args.build_labs and not args.dry_run
        else {}
    )
    summary = []
    execution_jobs = []
    stage_lock = threading.Lock()

    def record_stage_safe(node, identifier):
        with stage_lock:
            record_stage(node, str(identifier))

    def run_agent_job(job):
        entry = job["entry"]
        run_id = job["run_id"]
        run_dir = ROOT / "runs" / "redteam" / job["project"] / run_id
        entry["run_dir"] = str(run_dir)
        record_stage_safe("redteam-agent", job["candidate_id"])
        command = [
            sys.executable, str(ROOT / "scripts/runner/auto_repair.py"),
            "--python", sys.executable,
            "--output", str(batch_dir / "runner-executions" / job["candidate_id"]),
            "--model", args.model, "--execute-agent", "--",
            "--finding", str(job["finding"]),
            "--project", job["project"],
            "--scenario", str(job["scenario"]),
            "--run-id", run_id,
            "--model", args.model,
            "--base-url", args.base_url,
            "--api-key", args.api_key,
            "--max-steps", str(args.max_steps),
            "--max-tokens", str(args.max_tokens),
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, cwd=ROOT, timeout=args.agent_timeout,
            )
            entry["agent_returncode"] = completed.returncode
            entry["stdout"] = output_tail(completed.stdout, 1000)
            entry["stderr"] = output_tail(completed.stderr, 1000)
        except subprocess.TimeoutExpired as exc:
            entry.update({
                "agent_returncode": 124, "agent_timed_out": True,
                "stdout": output_tail(exc.stdout, 1000),
                "stderr": output_tail(exc.stderr, 1000),
            })
        except OSError as exc:
            entry.update({"agent_returncode": 1, "status": "agent_error", "stderr": str(exc)})
        if entry.get("agent_timed_out") or entry.get("agent_returncode") != 0:
            result = load(run_dir / "result.json", {})
            missing = harness_missing_module(entry.get("stderr", ""))
            if missing or entry.get("agent_returncode") == 78:
                entry.update({
                    "status": "blocked_harness_dependency",
                    "error_scope": "harness_dependency",
                    "retry_owner": "runner-environment",
                    "auto_retry": False,
                    "missing_modules": [missing],
                    "python": sys.executable,
                })
            else:
                entry["status"] = classify_agent_failure(
                    entry.get("agent_returncode"), result, timed_out=bool(entry.get("agent_timed_out"))
                )
        else:
            entry["status"] = "agent_completed"

    def run_judge_job(job):
        entry = job["entry"]
        run_dir = ROOT / "runs" / "redteam" / job["project"] / job["run_id"]
        command = [
            sys.executable, str(ROOT / "scripts" / "redteam" / "judge.py"),
            "--run-dir", str(run_dir), "--timeout", str(args.judge_timeout),
            "--claude", args.judge_claude,
        ]
        if args.judge_claude_model:
            command += ["--claude-model", args.judge_claude_model]
        record_stage_safe("judge", job["candidate_id"])
        try:
            judge = subprocess.run(
                command, capture_output=True, text=True, cwd=ROOT, timeout=args.judge_timeout,
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
        except OSError as exc:
            entry.update({"status": "judge_error", "judge_returncode": 1, "judge_stderr": str(exc)})
    for index, candidate in enumerate(candidates, 1):
        project = candidate.get("project", "")
        candidate_id = candidate.get("id", "")
        key = base.canon(project, candidate_id)
        item = resolve_candidate(candidate, ledger, snapshot)
        entry = {"project": project, "id": candidate_id, "key": key, "status": "blocked_no_finding"}
        if snapshot is not None:
            entry["report_sha256"] = snapshot["sha256"]
        if not item:
            entry["error"] = "候选问题不在本轮报告或发现记录中"
        if item:
            if snapshot is not None:
                try:
                    context = validate_packet(candidate.get('blue_handoff', ''), item.get('raw') or {}, project)
                    if context.get('run_id') != candidate.get('run_id') or context.get('report_sha256') != snapshot['sha256']:
                        raise ValueError('蓝队交付不属于本轮审计报告')
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    entry.update({'status': 'blocked_blue_handoff', 'error': str(exc)})
                    summary.append(entry)
                    continue
            try:
                preferred_path = scenario_path(ROOT, project, candidate_id)
            except ContractError as exc:
                entry.update({"status": exc.status, "error": str(exc)})
                summary.append(entry)
                print(json.dumps(entry, ensure_ascii=False))
                continue
            finding_path = batch_dir / f"{index:02d}-{project}-{candidate_id}.json"
            finding = dict(item.get("raw") or {})
            if snapshot is None:
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
            build_attempted = key in prebuilt
            if key in prebuilt:
                built = prebuilt[key]
                entry.update({field: built[field] for field in (
                    "builder_returncode", "builder_stdout", "builder_stderr", "builder_timed_out",
                    "blocked", "blocked_reason", "blocked_surface", "missing_capabilities", "mode",
                )})
                if built["status"] != "built":
                    entry.update({"status": built["status"], "scenario": "", "error": built["error"]})
                    summary.append(entry)
                    print(json.dumps(entry, ensure_ascii=False))
                    continue
                preferred_path = Path(built["scenario"])
                entry["scenario"] = str(preferred_path)
            if key not in prebuilt and not preferred_path.exists() and args.build_labs and not args.dry_run:
                build_attempted = True
                try:
                    record_stage("redteam-lab", str(candidate_id))
                    builder = subprocess.run(
                        [sys.executable, str(ROOT / "scripts" / "redteam" / "build_lab.py"),
                         "--project", project, "--finding", str(finding_path),
                         "--claude-model", args.model]
                        + (["--blue-handoff", candidate["blue_handoff"]] if candidate.get("blue_handoff") else []),
                        capture_output=True, text=True, cwd=ROOT, timeout=args.build_timeout,
                    )
                    entry["builder_returncode"] = builder.returncode
                    entry["builder_stdout"] = output_tail(builder.stdout, 1200)
                    entry["builder_stderr"] = output_tail(builder.stderr, 1200)
                    try:
                        delivery = json.loads(builder.stdout)
                    except (TypeError, ValueError):
                        delivery = {}
                    if isinstance(delivery, dict) and delivery.get("status") in {"blocked", "blocked_unstructured"}:
                        entry.update({
                            "status": delivery["status"],
                            "scenario": "",
                            "blocked": delivery.get("blocked", ""),
                            "blocked_reason": delivery.get("blocked_reason", ""),
                            "blocked_surface": delivery.get("blocked_surface", ""),
                            "missing_capabilities": delivery.get("missing_capabilities", []),
                            "mode": delivery.get("mode", ""),
                            "error": delivery.get("error") or delivery.get("blocked_reason") or "场景构建受阻",
                        })
                        summary.append(entry)
                        print(json.dumps(entry, ensure_ascii=False))
                        continue
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
                if key in prebuilt:
                    resolved_path = preferred_path
                    scenario = validate_scenario(load(resolved_path, {}), expected_finding_id=str(candidate_id),
                                                 expected_finding_sha256=hashlib.sha256(finding_path.read_bytes()).hexdigest())
                else:
                    resolved_path, scenario = resolve_scenario(ROOT, project, finding, finding_path.read_bytes())
                if snapshot is not None:
                    validate_scenario(scenario, expected_finding_id=str(candidate_id),
                                      expected_finding_sha256=hashlib.sha256(finding_path.read_bytes()).hexdigest(),
                                      expected_source=context["source"])
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
                entry["run_dir"] = str(ROOT / "runs" / "redteam" / project / run_id)
                execution_jobs.append({
                    "entry": entry,
                    "finding": finding_path,
                    "scenario": resolved_path,
                    "run_id": run_id,
                    "project": project,
                    "candidate_id": candidate_id,
                })
        summary.append(entry)
    if execution_jobs:
        def safe_agent_job(job):
            try:
                run_agent_job(job)
            except Exception as exc:
                job["entry"].update({"status": "agent_error", "agent_returncode": 1,
                                     "error": f"红队工作项异常：{type(exc).__name__}: {exc}"})

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.agent_jobs) as pool:
            list(pool.map(safe_agent_job, execution_jobs))
        judge_jobs = [
            job for job in execution_jobs
            if not job["entry"].get("agent_timed_out") and job["entry"].get("agent_returncode") == 0
        ]
        if judge_jobs:
            def safe_judge_job(job):
                try:
                    run_judge_job(job)
                except Exception as exc:
                    job["entry"].update({"status": "judge_error", "judge_returncode": 1,
                                         "judge_stderr": f"审核工作项异常：{type(exc).__name__}: {exc}"})

            with concurrent.futures.ThreadPoolExecutor(max_workers=args.judge_jobs) as pool:
                list(pool.map(safe_judge_job, judge_jobs))
    for item in summary:
        print(json.dumps(item, ensure_ascii=False))
    output = {"generated_at": datetime.now(timezone.utc).isoformat(), "model": args.model, "results": summary}
    summary_path = batch_dir / "summary.json"
    summary_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    counts = {}
    for item in summary:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"batch": str(batch_dir), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
