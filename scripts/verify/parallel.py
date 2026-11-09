#!/usr/bin/env python3
"""调度相互隔离的蓝队候选任务，原子保存进度并回收任务进程组。"""

import argparse
import concurrent.futures
import json
import os
import shutil
import signal
import sys
import uuid
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def write(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)



def finalize_deliveries(output, results, project):
    """Isolate candidate contract failures before publishing the batch."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stages"))
    from submission import accepted_submissions, submit

    output = Path(output).resolve()
    (output / "tasks").mkdir(parents=True, exist_ok=True)
    for result in results:
        sid = result["finding_id"]
        if not isinstance(sid, str) or not sid or sid in {".", ".."} or any(
            char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
            for char in sid
        ):
            raise ValueError("批次候选编号无效")
        folder = output / sid
        report = folder / "verify-report.json"
        try:
            if folder.is_symlink() or report.is_symlink():
                raise ValueError("候选交付不能是符号链接")
            data = json.loads(report.read_text())
            if data.get("finding_id") != sid or data.get("project") != project:
                raise ValueError("验证报告的项目或候选编号不一致")
            # Finalize actual runner output and explicit blocked outcomes through the same tool.
            if (data.get("synthesized") is True and data.get("verdict") == "blocked") or (
                result.get("status") == "runner_reported"
            ):
                receipt = submit("verify", folder, {
                    "artifact": str(report), "summary": data.get("reason") or "候选验证受阻",
                    "limitations": data.get("limitations") or (
                        [data.get("reason") or "候选验证受阻"]
                        if data.get("verdict") in {"blocked", "inconclusive"} else []
                    ),
                })
                if receipt["decision"] != "accepted":
                    raise ValueError(str(receipt["errors"]))
            delivery = accepted_submissions("verify", folder)
            if not any(item["artifact"] == str(report) for item in delivery["deliveries"]):
                raise ValueError("当前验证报告没有有效交付回执")
            result["delivery_status"] = "accepted"
        except (OSError, ValueError, TypeError, KeyError) as exc:
            # Preserve the failed attempt outside the formal batch. Never waive hashes.
            archive = output.parent / "delivery-failures" / sid / uuid.uuid4().hex
            archive.parent.mkdir(parents=True, exist_ok=True)
            if folder.exists() or folder.is_symlink():
                shutil.move(str(folder), str(archive))
            folder.mkdir(parents=True)
            reason = f"候选交付未通过：{exc}"
            data = {
                "project": project, "finding_id": sid, "verdict": "blocked",
                "status": "delivery_failed", "reason": reason, "evidence": [],
                "synthesized": True,
                **{key: result.get(key) for key in ("occurrence_id", "semantic_id", "run_id")},
                "limitations": ["原始产物已归档；未通过验收，不作为漏洞确认依据"],
            }
            write(report, data)
            receipt = submit("verify", folder, {
                "artifact": str(report), "summary": reason,
                "limitations": data["limitations"],
            })
            if receipt["decision"] != "accepted":
                raise ValueError("候选受阻记录无法保存：" + str(receipt["errors"]))
            result.update(
                verdict="blocked", status="delivery_failed", reason=reason,
                delivery_status="rejected", delivery_archive=str(archive),
                report_path=str(report), run_dir=str(folder), harness_path=None,
            )
        write(folder / "result.json", result)
        task_path = output / "tasks" / f"{sid}.json"
        task = json.loads(task_path.read_text()) if task_path.exists() else {}
        task.update({key: result.get(key) for key in (
            "verdict", "status", "reason", "delivery_status", "delivery_archive", "report_path"
        )})
        if result["delivery_status"] == "rejected":
            task["state"] = "failed"
        write(task_path, task)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery-project", help="按候选验收交付并隔离失败结果")
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--attempts", type=int, choices=[1, 2], default=1)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 10:
        parser.error("并发数必须在 1 到 10 之间")
    output = Path(args.output)
    tasks = output / "tasks"
    tasks.mkdir(exist_ok=True)
    jobs = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line]
    stopped = threading.Event()
    lock = threading.Lock()
    processes = {}
    cancelled_groups = set()
    cancelled_at = []

    def cancel(signum, frame):
        stopped.set()
        if not cancelled_at:
            cancelled_at.append(time.monotonic())
        with lock:
            for process in processes.values():
                cancelled_groups.add(process.pid)
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)

    def execute(job):
        sid, entry = job["id"], job["entry"]
        progress = {
            **job,
            "state": "queued",
            "concurrency": args.jobs,
            "finding_id": sid,
            "title": entry.get("title", ""),
            "agent_log": str(output / "logs" / f"{sid}.agent.log"),
            "report_path": str(output / sid / "verify-report.json"),
        }
        state_path = tasks / f"{sid}.json"

        def update(state):
            progress["state"] = state
            progress["updatedAt"] = datetime.now(timezone.utc).isoformat()
            write(state_path, progress)

        result_path = output / sid / "result.json"
        previous = None
        for attempt in range(1, args.attempts + 1):
            if attempt > 1:
                previous = output / "retry-history" / sid / str(attempt - 1)
                previous.parent.mkdir(parents=True, exist_ok=True)
                if (output / sid).exists():
                    shutil.move(str(output / sid), str(previous))
                for suffix in ["agent.log", "runner.log"]:
                    log = output / "logs" / (sid + "." + suffix)
                    if log.exists():
                        shutil.copy2(log, previous / suffix)
            progress["attempt"] = attempt
            rc = 130
            if not stopped.is_set():
                update("running")
                with lock:
                    if not stopped.is_set():
                        entry_path = output / "inputs" / sid / "entry.json"
                        entry_path.parent.mkdir(parents=True, exist_ok=True)
                        write(entry_path, entry)
                        retry_env = dict(os.environ)
                        if previous:
                            retry_env["PHASE4_RETRY_CONTEXT"] = str(previous / "result.json")
                        process = subprocess.Popen(
                            [
                                "bash",
                                "-c",
                                'set -uo pipefail; verify_one "$(cat "$1")" "$2"',
                                "verify-worker",
                                str(entry_path),
                                sid,
                            ],
                            start_new_session=True,
                            env=retry_env,
                        )
                        processes[sid] = process
                    else:
                        process = None
                if process:
                    while True:
                        try:
                            rc = process.wait(timeout=0.2)
                            break
                        except subprocess.TimeoutExpired:
                            if stopped.is_set():
                                try:
                                    rc = process.wait(timeout=5)
                                except subprocess.TimeoutExpired:
                                    try:
                                        os.killpg(process.pid, signal.SIGKILL)
                                    except ProcessLookupError:
                                        pass
                                    rc = process.wait()
                                break
                    with lock:
                        processes.pop(sid, None)
            if not result_path.exists():
                result_path.parent.mkdir(parents=True, exist_ok=True)
                write(
                    result_path,
                    {
                        "finding_id": sid,
                        "original_id": entry.get("orig_id"),
                        "source_index": entry["index"],
                        "title": entry.get("title", ""),
                        "severity": entry.get("severity", ""),
                        "status": "worker_interrupted" if stopped.is_set() else "worker_failed",
                        "verdict": "blocked",
                        "reason": "候选任务已中断"
                        if stopped.is_set()
                        else f"候选任务异常退出（退出码 {rc}）",
                        "agent_return_code": rc,
                        "agent_log": progress["agent_log"],
                        "report_path": None,
                    },
                )
            result = json.loads(result_path.read_text())
            result["attempts"] = attempt
            if stopped.is_set() or result.get("verdict") not in ["blocked", "inconclusive"]:
                break
        result["retry_exhausted"] = result.get("verdict") in ["blocked", "inconclusive"]
        write(result_path, result)
        progress.update({k: result.get(k) for k in ["status", "verdict", "reason", "report_path"]})
        update("cancelled" if stopped.is_set() else "completed" if rc == 0 else "failed")
        return result

    # 先登记全部排队任务，使尚未启动的候选也能出现在界面中。
    for job in jobs:
        write(
            tasks / f"{job['id']}.json",
            {
                **job,
                "finding_id": job["id"],
                "title": job["entry"].get("title", ""),
                "state": "queued",
                "concurrency": args.jobs,
            },
        )
    def safe_execute(job):
        try:
            return execute(job)
        except Exception as exc:
            # Keep one unexpected candidate-worker exception from aborting
            # collection of all other verification results.
            sid, entry = job["id"], job["entry"]
            result = {
                "finding_id": sid,
                "original_id": entry.get("orig_id"),
                "source_index": entry.get("index"),
                "title": entry.get("title", ""),
                "severity": entry.get("severity", ""),
                "status": "worker_failed",
                "verdict": "blocked",
                "reason": f"候选工作项异常：{type(exc).__name__}: {exc}",
                "report_path": None,
            }
            result_path = output / sid / "result.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            write(result_path, result)
            task_path = tasks / f"{sid}.json"
            task = json.loads(task_path.read_text()) if task_path.exists() else dict(job)
            task.update({"state": "failed", "status": "worker_failed",
                         "error": result["reason"],
                         "updatedAt": datetime.now(timezone.utc).isoformat()})
            write(task_path, task)
            return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(safe_execute, jobs))
    if stopped.is_set():
        # 组长退出不代表全部后代已退出；给执行器清理容器的时间，再回收残留进程。
        time.sleep(max(0, cancelled_at[0] + 5 - time.monotonic()))
        for group in cancelled_groups:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
    if args.delivery_project and not stopped.is_set():
        results = finalize_deliveries(output, results, args.delivery_project)
    write(output / ".parallel-results.json", results)
    return 130 if stopped.is_set() else 0


if __name__ == "__main__":
    raise SystemExit(main())
