#!/usr/bin/env python3
import hashlib
import json
import os
import secrets
import shlex
import shutil
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from contracts import SUPPORTED_MODES

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "redteam"
INPUT_MOUNT = "/input"
DRIVER_MOUNT = "/lab/driver.py"
MAX_INPUT_FILES = 512
MAX_INPUT_BYTES = 64 * 1024 * 1024


class LabError(RuntimeError):
    def __init__(self, message, status="lab_error"):
        super().__init__(message)
        self.status = status


class Lab:
    def __init__(
        self,
        project,
        victim_image,
        attacker_image="curlimages/curl:latest",
        target_url="http://victim:8000",
        health_path="/health",
        run_id=None,
        launch=None,
        health=None,
        pids_limit=128,
        memory="1g",
        cpus="1",
        mode="http",
        input_config=None,
        driver_path=None,
        entry=None,
        negative_control=None,
        lab_dir=None,
        runs_root=None,
    ):
        if mode not in SUPPORTED_MODES:
            raise LabError(f"unsupported scenario mode: {mode}", status="blocked_unsupported_mode")
        self.project = project
        self.mode = mode
        self.victim_image = victim_image
        self.attacker_image = attacker_image
        self.target_url = target_url.rstrip("/")
        health = health or {}
        self.health_path = health.get("path", health_path)
        self.health_url = f"{self.target_url}{self.health_path}"
        self.health_attempts = int(health.get("attempts", 30))
        self.health_interval = float(health.get("interval_seconds", 0.5))
        self.health_timeout = int(health.get("timeout_seconds", 2))
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.runs_root = Path(runs_root).resolve() if runs_root else RUNS
        self.run_dir = self.runs_root / project / self.run_id
        self.lab_dir = Path(lab_dir).resolve() if lab_dir else self.run_dir
        self.flag = f"FLAG{{{secrets.token_hex(24)}}}"
        self.flag_sha256 = hashlib.sha256(self.flag.encode("utf-8")).hexdigest()
        self.flag_file = self.run_dir / "flag.txt"
        self.trace_file = self.run_dir / "trace.jsonl"
        suffix = f"{project}-{self.run_id}-{secrets.token_hex(3)}".lower()
        self.network = f"mygoldmine-lab-{suffix}"
        self.victim_name = f"mygoldmine-victim-{suffix}"
        self.attacker_name = f"mygoldmine-attacker-{suffix}"
        self.trace = []
        self.launch = launch or {"command": []}
        self.pids_limit = int(pids_limit)
        self.memory = str(memory)
        self.cpus = str(cpus)
        self.flag_provenance = None
        self._event_sequence = 0
        self._snapshot_sequence = 0
        self.input_path = (input_config or {}).get("path", INPUT_MOUNT) if mode != "http" else None
        self.driver_path = Path(driver_path).resolve() if driver_path else None
        self.entry = entry or {}
        self.negative_control = negative_control or {"kind": "empty_input"}
        self.input_dir = self.run_dir / "input"
        self.snapshots_dir = self.run_dir / "snapshots"
        self.use_network = mode == "http"

    def _event_id(self, prefix):
        self._event_sequence += 1
        return f"{prefix}-{self._event_sequence:06d}"

    def log(self, kind, **payload):
        record = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload}
        self.trace.append(record)
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def docker(self, args, timeout=60, check=True):
        try:
            completed = subprocess.run(
                ["docker", *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise LabError(f"docker command timed out after {timeout}s") from exc
        if check and completed.returncode != 0:
            raise LabError((completed.stderr or completed.stdout or "docker failed")[-1200:])
        return completed

    def container_args(self, role):
        if role not in {"victim", "attacker"}:
            raise ValueError("unknown container role")
        name = self.victim_name if role == "victim" else self.attacker_name
        args = [
            "run", "-d", "--rm",
            "--name", name,
            "--network", self.network if self.use_network else "none",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.pids_limit),
            "--memory", self.memory,
            "--cpus", self.cpus,
        ]
        if self.use_network:
            args += ["--network-alias", role]
        if role == "victim":
            args += ["-v", f"{self.flag_file}:/flag:ro", self.victim_image]
            command = self.launch.get("command", [])
            if isinstance(command, str):
                args += ["sh", "-lc", command]
            else:
                args += command
        else:
            args += ["--user", f"{os.getuid()}:{os.getgid()}"]
            if not self.use_network:
                args += ["--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"]
                if self.input_dir is not None:
                    args += ["-v", f"{self.input_dir}:{self.input_path}:rw"]
            args += ["--entrypoint", "sh", self.attacker_image, "-c", "sleep infinity"]
        return args

    def start(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.flag_file.write_text(self.flag + "\n", encoding="utf-8")
        self.flag_file.chmod(0o644)
        self.trace_file.write_text("", encoding="utf-8")
        if self.mode != "http":
            shutil.rmtree(self.input_dir, ignore_errors=True)
            shutil.rmtree(self.snapshots_dir, ignore_errors=True)
            self.input_dir.mkdir(parents=True, exist_ok=True)
            self.input_dir.chmod(0o700)
        self.log(
            "lab_start",
            mode=self.mode,
            network=self.network if self.use_network else "none",
            network_internal=self.use_network,
            victim_image=self.victim_image,
            attacker_image=self.attacker_image,
            flag_sha256=self.flag_sha256,
            attacker_flag_mount=False,
            cap_drop_all=True,
            no_new_privileges=True,
            pids_limit=self.pids_limit,
            memory=self.memory,
            cpus=self.cpus,
            input_path=self.input_path,
            driver_mounted=bool(self.driver_path),
        )
        try:
            if self.use_network:
                self.docker(["network", "create", "--internal", self.network])
            self.docker(self.container_args("attacker"))
            if self.use_network:
                self.docker(self.container_args("victim"))
                self.wait_ready()
            else:
                self.run_negative_control()
        except LabError:
            raise
        except Exception as exc:
            raise LabError(str(exc)) from exc
        return self

    def wait_ready(self, attempts=None):
        last = ""
        attempts = attempts or self.health_attempts
        command = f"curl -fsS --max-time {self.health_timeout} {shlex.quote(self.health_url)}"
        for _ in range(attempts):
            completed = self.docker(
                ["exec", self.attacker_name, "sh", "-lc", command],
                timeout=self.health_timeout + 3,
                check=False,
            )
            if completed.returncode == 0:
                self.log("health_ok", output=completed.stdout.strip()[:200])
                return
            last = (completed.stderr or completed.stdout or "").strip()
            time.sleep(self.health_interval)
        raise LabError(f"victim not ready: {last[-500:]}", status="lab_unhealthy")

    def exec(self, command, timeout=30):
        event_id = self._event_id("tool")
        self.log("tool", event_id=event_id, tool="shell", command=command)
        try:
            completed = subprocess.run(
                ["docker", "exec", self.attacker_name, "sh", "-lc", command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            returncode = completed.returncode
        except subprocess.TimeoutExpired as exc:
            output = f"TIMEOUT after {timeout}s: {exc}"
            returncode = 124
        self.log(
            "tool_result",
            event_id=event_id,
            command=command,
            returncode=returncode,
            output=output,
            output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
        )
        self._last_tool_event = (event_id, output)
        return returncode, output

    def _control_source(self):
        kind = self.negative_control.get("kind", "empty_input")
        if kind == "empty_input":
            return None
        fixture = self.negative_control.get("fixture")
        if not fixture:
            raise LabError("negative control fixture is missing", status="blocked_scenario_invalid")
        source = (self.lab_dir / fixture).resolve()
        if not source.is_relative_to(self.lab_dir) or not source.exists():
            raise LabError("negative control fixture is outside the lab or missing", status="blocked_scenario_invalid")
        return source

    def _copy_input_tree(self, source, destination):
        if not source.exists():
            return
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        source_fd = os.open(source, flags)
        destination_fd = os.open(destination, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        total = 0
        count = 0

        def copy_directory(src_fd, dst_fd):
            nonlocal total, count
            with os.scandir(src_fd) as entries:
                for entry in entries:
                    name = entry.name
                    metadata = os.stat(name, dir_fd=src_fd, follow_symlinks=False)
                    if stat.S_ISLNK(metadata.st_mode):
                        raise LabError("input contains a symbolic link", status="agent_input_error")
                    if stat.S_ISDIR(metadata.st_mode):
                        child_source = os.open(
                            name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                            dir_fd=src_fd,
                        )
                        try:
                            try:
                                os.mkdir(name, 0o700, dir_fd=dst_fd)
                            except FileExistsError:
                                pass
                            child_destination = os.open(
                                name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0), dir_fd=dst_fd
                            )
                            try:
                                copy_directory(child_source, child_destination)
                            finally:
                                os.close(child_destination)
                        finally:
                            os.close(child_source)
                        continue
                    if not stat.S_ISREG(metadata.st_mode):
                        raise LabError("input contains a non-regular file", status="blocked_scenario_invalid")
                    count += 1
                    total += metadata.st_size
                    if count > MAX_INPUT_FILES or total > MAX_INPUT_BYTES:
                        raise LabError("input exceeds the size limit", status="blocked_scenario_invalid")
                    descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=src_fd)
                    try:
                        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                            raise LabError("input changed while preparing the victim run", status="blocked_scenario_invalid")
                        output = os.open(
                            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400, dir_fd=dst_fd
                        )
                        try:
                            with os.fdopen(descriptor, "rb") as reader, os.fdopen(output, "wb") as writer:
                                descriptor = None
                                output = None
                                shutil.copyfileobj(reader, writer)
                        finally:
                            if output is not None:
                                os.close(output)
                    finally:
                        if descriptor is not None:
                            os.close(descriptor)

        try:
            copy_directory(source_fd, destination_fd)
        finally:
            os.close(source_fd)
            os.close(destination_fd)

    def _snapshot_input(self, source=None):
        source = Path(source) if source else self.input_dir
        self._snapshot_sequence += 1
        destination = self.snapshots_dir / f"{self._snapshot_sequence:04d}"
        destination.mkdir(parents=True, mode=0o700)
        self._copy_input_tree(source, destination)
        return destination

    def _victim_command(self):
        command = self.launch.get("command")
        if isinstance(command, str):
            raise LabError("cli/library launch.command must be an argument list", status="blocked_scenario_invalid")
        if not isinstance(command, list) or not command:
            raise LabError("cli/library launch.command is empty", status="blocked_scenario_invalid")
        return list(command)

    def _run_victim(self, snapshot, timeout, control=False):
        command = self._victim_command()
        name = f"{self.victim_name}-run-{self._snapshot_sequence:04d}"
        args = [
            "run", "--rm",
            "--name", name,
            "--network", "none",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.pids_limit),
            "--memory", self.memory,
            "--cpus", self.cpus,
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{self.flag_file}:/flag:ro",
            "-v", f"{snapshot}:{self.input_path}:ro",
        ]
        if self.driver_path is not None:
            args += ["-v", f"{self.driver_path}:{DRIVER_MOUNT}:ro"]
        entrypoint = self.launch.get("entrypoint")
        if entrypoint:
            args += ["--entrypoint", entrypoint]
        args += [self.victim_image, *command]
        event_id = self._event_id("tool")
        self.log(
            "tool",
            event_id=event_id,
            tool="victim",
            mode=self.mode,
            command=command,
            control=control,
            input_path=self.input_path,
        )
        try:
            completed = subprocess.run(
                ["docker", *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            returncode = completed.returncode
        except subprocess.TimeoutExpired as exc:
            output = f"TIMEOUT after {timeout}s: {exc}"
            returncode = 124
            self.docker(["rm", "-f", name], check=False)
        self.log(
            "tool_result",
            event_id=event_id,
            tool="victim",
            command=command,
            returncode=returncode,
            output=output,
            output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
            control=control,
        )
        if not control:
            self._last_tool_event = (event_id, output)
        return returncode, output

    def run_negative_control(self):
        if self.mode == "http":
            return
        source = self._control_source()
        snapshot = self._snapshot_input(source)
        try:
            returncode, output = self._run_victim(snapshot, timeout=max(30, self.health_timeout), control=True)
        finally:
            shutil.rmtree(snapshot, ignore_errors=True)
        leaked = self.check_flag(output)
        self.log(
            "negative_control",
            ok=not leaked,
            returncode=returncode,
            output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
            fixture=str(source) if source else "",
        )
        if leaked:
            raise LabError(
                "negative control leaked the flag before the attacker acted",
                status="blocked_scenario_invalid",
            )

    def trigger(self, timeout=30):
        if self.mode == "http":
            raise LabError("trigger is only available for cli/library scenarios", status="lab_error")
        snapshot = self._snapshot_input()
        self.log("trigger", mode=self.mode, snapshot=str(snapshot))
        return self._run_victim(snapshot, timeout=timeout)

    def check_flag(self, output):
        return self.flag in str(output or "")

    def capture_from_tool(self, output):
        if self.flag_provenance or not self.check_flag(output):
            return self.flag_provenance if self.check_flag(output) else None
        event_id, actual_output = getattr(self, "_last_tool_event", (None, None))
        if event_id is None or output != actual_output:
            return None
        output_sha256 = hashlib.sha256(output.encode("utf-8")).hexdigest()
        capture_event_id = self._event_id("capture")
        provenance = {
            "source": "tool_output",
            "event_id": event_id,
            "capture_event_id": capture_event_id,
            "output_sha256": output_sha256,
            "flag_sha256": self.flag_sha256,
        }
        self.log(
            "flag_capture",
            event_id=capture_event_id,
            tool_event_id=event_id,
            output_sha256=output_sha256,
            flag_sha256=self.flag_sha256,
        )
        self.flag_provenance = provenance
        return dict(provenance)

    def capture_answer(self, answer):
        if answer == self.flag and self.flag_provenance:
            return dict(self.flag_provenance)
        return None

    def finish(self, result):
        payload = {
            "schema_version": 2,
            "project": self.project,
            "run_id": self.run_id,
            "flag_sha256": self.flag_sha256,
            "trace": str(self.trace_file),
            "result": result,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        (self.run_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.log("lab_finish", result=result)
        return payload

    def stop(self):
        self.docker(["rm", "-f", self.attacker_name], check=False)
        self.docker(["rm", "-f", self.victim_name], check=False)
        if self.use_network:
            self.docker(["network", "rm", self.network], check=False)


def demo_lab(**kwargs):
    return Lab("demo", "mygoldmine/lab-demo-victim", **kwargs)


if __name__ == "__main__":
    lab = demo_lab()
    try:
        lab.start()
        code, output = lab.exec(
            "curl -fsS --get --data-urlencode 'cmd=cat /flag' http://victim:8000/api/run"
        )
        provenance = lab.capture_from_tool(output)
        print(json.dumps({"exit": code, "captured": bool(provenance), "output": output[:200]}, ensure_ascii=False))
    finally:
        lab.stop()
