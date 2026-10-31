#!/usr/bin/env python3
"""Resume independent audit tasks from durable artifacts, with bounded attempts.

The model is a worker, not the owner of workflow state. Completed artifacts are
checksummed and never rerun on resume; a failed task cannot block report assembly.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/mine"))
sys.path.insert(0, str(ROOT / "scripts/workflow"))
import check_report  # noqa: E402
import report_quality  # noqa: E402


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid_artifact(path, report=False):
    data = read_json(path)
    if not isinstance(data, dict):
        return False
    if report:
        quality = check_report.check_report(path)
        return (
            quality["valid"]
            and quality["incomplete"] == 0
            and quality["language_mismatch"] == 0
        )
    return (
        isinstance(data.get("findings"), list)
        and isinstance(data.get("hypotheses", []), list)
        and isinstance(data.get("coverage"), dict)
        and all(isinstance(item, dict) for item in data["findings"])
    )


def valid_report(run):
    run = Path(run)
    markdown = run / "audit-report.md"
    return markdown.is_file() and markdown.stat().st_size > 0 and valid_artifact(
        run / "audit-report.json", report=True
    )


def plan_from_trace(source):
    tasks = {}
    for line in (source / "raw.jsonl").read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "assistant" or event.get("parent_tool_use_id"):
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") != "tool_use" or block.get("name") not in {"Task", "Agent"}:
                continue
            payload = block.get("input") or {}
            prompt = str(payload.get("prompt") or "")
            match = re.search(r"\.workspace/findings/(infra-[a-z0-9-]+)\.json", prompt)
            if match:
                key = match[1]
                tasks[key] = {
                    "id": key,
                    "description": payload.get("description") or key,
                    "prompt": prompt,
                    "call_id": block.get("id"),
                    "status": "pending",
                    "attempts": [],
                }
    for task in tasks.values():
        trace = []
        for line in (source / "raw.jsonl").read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("parent_tool_use_id") == task["call_id"]:
                trace.append(json.dumps(event.get("message"), ensure_ascii=False)[:1400])
        task["recovery_context"] = "\n".join(trace[-8:])
    if not tasks:
        raise ValueError("no recoverable infra tasks in source trace")
    return tasks


def stop_worker(process, container):
    # Independent container per attempt: cancellation cannot kill other tasks.
    try:
        subprocess.run(
            ["docker", "stop", "--time", "3", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["docker", "kill", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


class TranscriptProgress:
    def __init__(self, raw, initial_offset=0):
        self.raw = Path(raw)
        self.offset = initial_offset
        self.buffer = ""
        self.pending_tools = set()
        self.seen_event = False

    def poll(self):
        if not self.raw.exists():
            return False
        with self.raw.open(encoding="utf-8") as stream:
            stream.seek(self.offset)
            chunk = stream.read()
            self.offset = stream.tell()
        if not chunk:
            return False
        self.buffer += chunk
        lines = self.buffer.split("\n")
        self.buffer = lines.pop()
        changed = False
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            changed = self.seen_event = True
            message = event.get("message")
            blocks = message.get("content", []) if isinstance(message, dict) else []
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("id"):
                    self.pending_tools.add(block["id"])
                elif block.get("type") == "tool_result":
                    self.pending_tools.discard(block.get("tool_use_id"))
        return changed

    @property
    def phase(self):
        if not self.seen_event:
            return "setup"
        if self.pending_tools:
            return "tool_running"
        return "model_waiting"


def watch_process(
    process,
    raw,
    *,
    idle,
    timeout,
    stop,
    tick=None,
    poll=1,
    setup_idle=None,
    status=None,
    clock=time.monotonic,
    sleeper=time.sleep,
    initial_offset=0,
):
    """Bound setup/model inactivity while allowing an outstanding tool to finish."""
    started = last_progress = clock()
    progress = TranscriptProgress(raw, initial_offset=initial_offset)
    setup_idle = idle if setup_idle is None else setup_idle
    phase = progress.phase
    try:
        while True:
            current = clock()
            if progress.poll():
                last_progress = current
            phase = progress.phase
            if tick:
                tick()
            rc = process.poll()
            if rc is not None:
                return rc, "exited"
            elapsed = current - started
            quiet = current - last_progress
            if status:
                status(
                    {
                        "phase": phase,
                        "reason": "running",
                        "pending_tools": len(progress.pending_tools),
                        "elapsed_seconds": max(0, elapsed),
                        "quiet_seconds": max(0, quiet),
                    }
                )
            if elapsed >= timeout:
                stop()
                if tick:
                    tick()
                return 124, "wall_timeout"
            idle_limit = setup_idle if phase == "setup" else idle
            if phase != "tool_running" and quiet >= idle_limit:
                reason = "setup_timeout" if phase == "setup" else "model_idle_timeout"
                stop()
                if tick:
                    tick()
                return 125, reason
            sleeper(poll)
    except BaseException:
        stop()
        raise


class Recovery:
    def __init__(self, args):
        self.args = args
        self.run = Path(args.run_dir).resolve()
        self.source = Path(args.recover_from).resolve()
        self.target = Path(args.target).resolve()
        self.state_path = self.run / "checkpoint.json"
        self.deadline = time.monotonic() + args.budget
        self.state = read_json(self.state_path)
        if self.run == self.source:
            raise ValueError("run-dir must differ from recover-from; source evidence is immutable")
        if not self.state and (self.run / "raw.jsonl").exists():
            raise ValueError("run-dir has a transcript but no recovery checkpoint")
        commit = subprocess.check_output(
            ["git", "-C", str(self.target), "rev-parse", "HEAD"], text=True
        ).strip()
        if self.state:
            if self.state["target_commit"] != commit or self.state["target"] != str(self.target):
                raise ValueError("target revision changed: cannot reuse old task checkpoints")
        else:
            self.state = {
                "schema": 1,
                "session_id": str(uuid.uuid4()),
                "target": str(self.target),
                "target_commit": commit,
                "source_run": str(self.source),
                "started_at": now(),
                "tasks": plan_from_trace(self.source),
            }
        self.raw = self.run / "raw.jsonl"
        self.log = self.run / "claude.rendered.log"
        self.run.mkdir(parents=True, exist_ok=True)
        if not self.raw.exists():
            self.emit({"type": "system", "subtype": "init", "session_id": self.state["session_id"]})
        self.save()

    def save(self):
        self.state["updated_at"] = now()
        atomic_json(self.state_path, self.state)

    def emit(self, event):
        event = {
            **event,
            "uuid": event.get("uuid") or str(uuid.uuid4()),
            "session_id": self.state["session_id"],
            "timestamp": event.get("timestamp") or now(),
        }
        with self.raw.open("a") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    def note(self, text):
        self.emit(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
            }
        )
        with self.log.open("a") as stream:
            stream.write(f"[{now()}] {text}\n")

    def status(self, state="running", code=-1):
        atomic_json(
            Path(str(self.run) + ".meta") / "status.json",
            {
                "state": state,
                "project": self.run.parent.name,
                "started_at": self.state["started_at"],
                "updated_at": now(),
                "timeout_seconds": self.args.budget,
                "model": self.args.model,
                "agent": "durable-recovery",
                "exit_code": code,
                "recovery": self.state["tasks"],
            },
        )

    def seed(self):
        seed = self.source / "task-artifacts"
        if not seed.exists():
            seed = self.source / "recovery/findings-before-timeout"
        for key, task in self.state["tasks"].items():
            destination = self.run / "artifacts" / f"{key}.json"
            if task["status"] in {"completed", "reused"}:
                if valid_artifact(destination) and digest(destination) == task.get("sha256"):
                    continue
                task["status"] = "pending"
            candidate = seed / f"{key}.json"
            if not task["attempts"] and valid_artifact(candidate):
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, destination)
                task.update(status="reused", artifact=str(destination), sha256=digest(destination))
                self.note(f"复用检查点 {key}，不重新扫描")
        self.save()

    def execute(self, task, *, report=False):
        key = task["id"]
        task.setdefault("attempts", [])
        # A crash consumes the interrupted attempt and leaves previous outputs untouched.
        for attempt in task["attempts"]:
            if attempt["status"] == "running":
                subprocess.run(
                    ["docker", "stop", "--time", "3", attempt["container"]],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
                attempt["status"] = "interrupted"
        while len(task["attempts"]) < self.args.max_attempts and time.monotonic() < self.deadline:
            number = len(task["attempts"]) + 1
            attempt_dir = self.run / "attempts" / key / f"{number:02}"
            if attempt_dir.exists():
                # Retain preparation interrupted before the attempt was checkpointed.
                attempt_dir.rename(
                    attempt_dir.with_name(str(number) + ".abandoned-" + uuid.uuid4().hex[:8])
                )
            attempt_dir.mkdir(parents=True, exist_ok=True)
            output = attempt_dir / "output"
            prompt = attempt_dir / "prompt.txt"
            if report:
                inputs = attempt_dir / "inputs"
                inputs.mkdir(exist_ok=True)
                for artifact in (self.run / "artifacts").glob("*.json"):
                    shutil.copy2(artifact, inputs / artifact.name)
                atomic_json(inputs / "coverage.json", self.state["tasks"])
                prompt_text = (
                    "仅汇总已有审计产物，不启动新的扫描或子 Agent。输入目录：" + str(inputs) + "\n"
                    "阅读所有输入及必要源码证据，去重，保留来源，"
                    "所有漏洞 verification 保持 unverified。"
                    "不能把可信操作者主动配置、设计限制或纯假设直接认定为漏洞。"
                    "仅在证据支持时补充根因、影响和最小本地验证步骤；"
                    "无法补全的条目保留到 hypotheses，说明缺口。"
                    "输出中文 audit-report.json 和 audit-report.md；"
                    "JSON 顶层 findings 数组，每项必须有 "
                    "id,title,severity,root_cause,impact,reproduction,remediation,evidence。"
                    "缺失或失败的边界必须在 limitations 和 coverage 中明确，不得声称全量扫描成功。"
                )
                agent = "recovery-report-assembler"
            else:
                prompt_text = (
                    task["prompt"]
                    + "\n先前最后的进度（仅作线索，须核对源码）：\n"
                    + task.get("recovery_context", "")
                    + (
                        "\n这是失败任务的独立恢复，只处理上述边界，不重新启动其他边界或子 Agent。"
                        "\n尽快落盘阶段性结果；无法核实的内容写入 hypotheses，不要无限追查。"
                        "\n源码 /workspace/repo，知识库 /opt/mygoldmine/knowledge。"
                        "\n不访问公网，不读取宿主敏感文件，不编写武器化 exploit。"
                        "\n最终任务 JSON 至少包含 findings, hypotheses, coverage, limitations；"
                        "覆盖信息说明已读文件和未完成部分，"
                        "所有 finding 必须保留证据及 unverified 状态。"
                    )
                )
                agent = "recovery-infra-worker"
            if task.get("last_failure"):
                prompt_text += "\n上次尝试失败的机器诊断，请优先修正：\n" + json.dumps(
                    task["last_failure"], ensure_ascii=False
                )
            if task["attempts"]:
                previous_raw = (
                    Path(task["attempts"][-1].get("output", "/nonexistent")) / "raw.jsonl"
                )
                context = []
                if previous_raw.exists():
                    for line in previous_raw.read_text().splitlines():
                        try:
                            previous_event = json.loads(line)
                        except ValueError:
                            continue
                        if not isinstance(previous_event, dict):
                            continue
                        for block in previous_event.get("message", {}).get("content", []):
                            if isinstance(block, dict) and block.get("type") == "text":
                                context.append(str(block.get("text") or "")[:1500])
                if context:
                    prompt_text += (
                        "\n上次已落盘的分析线索（需核对，不是已验证结论）：\n"
                        + "\n".join(context[-6:])
                    )
            # Inputs must be mounted within the attempt output; parent state is not writable.
            if report:
                output.mkdir(exist_ok=True)
                shutil.move(str(attempt_dir / "inputs"), str(output / "inputs"))
                prompt_text = prompt_text.replace(
                    str(attempt_dir / "inputs"), str(output / "inputs")
                )
                # wrapper rejects nonempty RUN_DIR, so seeds live in a read-only target overlay.
                seed_target = attempt_dir / "target"
                shutil.copytree(
                    self.target,
                    seed_target,
                    symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "node_modules"),
                )
                shutil.move(str(output / "inputs"), str(seed_target / "recovery-inputs"))
                output.rmdir()
                prompt_text = prompt_text.replace(
                    str(output / "inputs"), "/workspace/repo/recovery-inputs"
                )
                target = seed_target
            else:
                target = self.target
            prompt_text += (
                f"\n交付路径以此覆盖前文：{output}/audit-report.json "
                f"和 {output}/audit-report.md。\n"
            )
            prompt.write_text(prompt_text)
            name = f"mg-recover-{self.state['session_id'][:8]}-{key}-{number}"
            attempt = {
                "number": number,
                "status": "running",
                "started_at": now(),
                "container": name,
                "output": str(output),
            }
            task["attempts"].append(attempt)
            task["status"] = "running"
            self.save()
            self.status()
            self.note(
                f"开始 {key}，第 {number}/{self.args.max_attempts} 次；"
                f"无输出上限 {self.args.idle_timeout}s"
            )
            self.emit(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": name,
                                "name": "Agent",
                                "input": {
                                    "description": task["description"],
                                    "prompt": prompt_text,
                                },
                            }
                        ],
                    },
                }
            )
            self.emit(
                {
                    "type": "system",
                    "subtype": "task_started",
                    "task_id": name,
                    "tool_use_id": name,
                    "description": task["description"],
                }
            )
            budget = max(1, min(self.args.task_timeout, int(self.deadline - time.monotonic())))
            command = [
                "bash",
                str(ROOT / "scripts/mine/mine_one_docker.sh"),
                "--target",
                str(target),
                "--project",
                self.run.parent.name,
                "--run-dir",
                str(output),
                "--prompt",
                str(prompt),
                "--timeout",
                str(budget),
                "--agent",
                agent,
                "--model",
                self.args.model,
            ]
            env = {
                **os.environ,
                "JEV_TRIAGE": "0",
                "MAX_ATTEMPTS": "1",
                "MYGOLDMINE_CONTAINER_NAME": name,
            }
            offset = 0
            last_render = 0.0

            def relay():
                nonlocal offset, last_render
                raw = output / "raw.jsonl"
                if raw.exists():
                    with raw.open() as stream:
                        stream.seek(offset)
                        while True:
                            position = stream.tell()
                            line = stream.readline()
                            if not line or not line.endswith("\n"):
                                offset = position
                                break
                            offset = stream.tell()
                            try:
                                event = json.loads(line)
                            except ValueError:
                                continue
                            if isinstance(event, dict) and event.get("type") in {
                                "assistant",
                                "user",
                            }:
                                self.emit({**event, "parent_tool_use_id": name})
                if time.monotonic() - last_render > 3:
                    subprocess.run(
                        [
                            sys.executable,
                            str(ROOT / "scripts/mine/render_claude_log.py"),
                            "--input",
                            str(self.raw),
                            "--output",
                            str(self.log),
                            "--quiet",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    last_render = time.monotonic()

            with (attempt_dir / "wrapper.log").open("w") as log:
                process = subprocess.Popen(
                    command, env=env, stdout=log, stderr=log, start_new_session=True
                )
                code, reason = watch_process(
                    process,
                    output / "raw.jsonl",
                    idle=self.args.idle_timeout,
                    setup_idle=max(
                        self.args.idle_timeout, getattr(self.args, "setup_timeout", 900)
                    ),
                    timeout=budget,
                    stop=lambda: stop_worker(process, name),
                    tick=relay,
                )
            artifact = output / "audit-report.json"
            ok = code in {0, 2} and (
                valid_report(output) if report else valid_artifact(artifact)
            )
            attempt.update(
                status="completed" if ok else reason if reason != "exited" else "failed",
                ended_at=now(),
                exit_code=code,
            )
            if ok:
                destination = self.run / (
                    "audit-report.json" if report else f"artifacts/{key}.json"
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(artifact, destination)
                if report and (output / "audit-report.md").exists():
                    shutil.copy2(output / "audit-report.md", self.run / "audit-report.md")
                task.update(
                    status="completed", artifact=str(destination), sha256=digest(destination)
                )
            else:
                task["last_failure"] = {"exit_code": code, "reason": reason}
                if artifact.exists():
                    data = read_json(artifact)
                    errors = report_quality.schema_errors(data)
                    missing = []
                    if isinstance(data, dict):
                        for item in report_quality.findings_of(data):
                            quality = report_quality.quality_of(
                                item, report_quality.system_language()
                            )
                            if not quality["ok"]:
                                missing.append(
                                    {
                                        "id": item.get("id") if isinstance(item, dict) else "",
                                        "missing": quality["missing"],
                                    }
                                )
                    task["last_failure"]["validation_errors"] = errors
                    task["last_failure"]["incomplete_findings"] = missing
                task["status"] = "retrying"
            self.emit(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": name,
                                "content": f"{key}: {task['status']}; {reason}; exit={code}",
                                "is_error": not ok,
                            }
                        ],
                    },
                    "tool_use_result": {"agentId": name, "status": "completed" if ok else "failed"},
                }
            )
            self.save()
            self.note(f"{key}: {task['status']} ({reason}, exit={code})，产物和日志已保留")
            if ok:
                return True
        task["status"] = "failed"
        self.save()
        return False

    def run_all(self):
        self.status()
        self.seed()
        for task in self.state["tasks"].values():
            if task["status"] not in {"completed", "reused"}:
                self.execute(task)
        assembler = self.state.setdefault(
            "assembly",
            {
                "id": "assembly",
                "description": "汇总已有产物并检查格式",
                "attempts": [],
                "status": "pending",
            },
        )
        self.save()
        if not valid_report(self.run):
            self.execute(assembler, report=True)
        failed = [key for key, task in self.state["tasks"].items() if task["status"] == "failed"]
        final_path = self.run / "audit-report.json"
        final = read_json(final_path)
        if isinstance(final, dict):
            final["execution"] = {
                "source_run": str(self.source),
                "target_commit": self.state["target_commit"],
                "failed_tasks": failed,
                "task_states": {key: task["status"] for key, task in self.state["tasks"].items()},
                "verification": "unverified",
            }
            if failed:
                limitations = final.get("limitations")
                if not isinstance(limitations, list):
                    limitations = [str(limitations)] if limitations else []
                final["limitations"] = limitations + ["未完成的信任边界：" + ", ".join(failed)]
            atomic_json(final_path, final)
            assembler["sha256"] = digest(final_path)
        good_report = valid_report(self.run)
        timeout_codes = []
        for task in [*self.state["tasks"].values(), assembler]:
            if task["status"] == "failed" and task.get("attempts"):
                code = task["attempts"][-1].get("exit_code")
                if code in {124, 125, 137}:
                    timeout_codes.append(code)
        if timeout_codes:
            result, code = "timeout", timeout_codes[-1]
        elif not good_report:
            result, code = "failed", 2
        elif failed:
            result, code = "partial", 2
        else:
            result, code = "success", 0
        self.state["status"] = result
        self.save()
        if not good_report:
            partial = {
                "findings": [],
                "status": "partial",
                "limitations": [
                    "最终报告格式未通过，已有任务产物保留在 artifacts；"
                    "不能据空 findings 判断无漏洞。"
                ],
                "task_artifacts": {
                    key: task.get("artifact") for key, task in self.state["tasks"].items()
                },
                "failed_tasks": failed,
            }
            atomic_json(self.run / "partial-report.json", partial)
        atomic_json(
            self.run / "run-meta.json",
            {
                "project": self.run.parent.name,
                "started_at": self.state["started_at"],
                "ended_at": now(),
                "commit": self.state["target_commit"],
                "model": self.args.model,
                "agent": "durable-recovery",
                "exit_code": code,
                "timed_out": result == "timeout",
                "reports_complete": good_report,
                "recovered_from": str(self.source),
                "failed_tasks": failed,
                "status": result,
            },
        )
        self.status(result, code)
        self.note(f"流程收尾：{result}，失败任务={failed}；不会丢弃已完成任务")
        return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--recover-from", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--idle-timeout", type=int, default=180)
    parser.add_argument("--task-timeout", type=int, default=600)
    parser.add_argument("--budget", type=int, default=1800)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--model", default="360-proxy/deepseek/deepseek-v4.1-flash")
    args = parser.parse_args()

    def interrupted(_signal, _frame):
        raise KeyboardInterrupt("recovery runner stopped")

    signal.signal(signal.SIGTERM, interrupted)
    if min(args.idle_timeout, args.task_timeout, args.budget, args.max_attempts) <= 0:
        parser.error("budgets and attempt count must be positive")
    run = Path(args.run_dir)
    run.mkdir(parents=True, exist_ok=True)
    with (run / ".recovery.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recovery = Recovery(args)
        try:
            return recovery.run_all()
        except BaseException:
            recovery.state["status"] = "interrupted"
            recovery.save()
            recovery.status("stopped", 130)
            raise


if __name__ == "__main__":
    raise SystemExit(main())
