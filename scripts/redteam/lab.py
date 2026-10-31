#!/usr/bin/env python3
import hashlib
import json
import secrets
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "redteam"


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
    ):
        self.project = project
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
        self.run_dir = RUNS / project / self.run_id
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
            "--network", self.network,
            "--network-alias", role,
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.pids_limit),
            "--memory", self.memory,
            "--cpus", self.cpus,
        ]
        if role == "victim":
            args += ["-v", f"{self.flag_file}:/flag:ro", self.victim_image]
            command = self.launch.get("command", [])
            if isinstance(command, str):
                args += ["sh", "-lc", command]
            else:
                args += command
        else:
            args += ["--entrypoint", "sh", self.attacker_image, "-c", "sleep infinity"]
        return args

    def start(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.flag_file.write_text(self.flag + "\n", encoding="utf-8")
        self.flag_file.chmod(0o644)
        self.trace_file.write_text("", encoding="utf-8")
        self.log(
            "lab_start",
            network=self.network,
            network_internal=True,
            victim_image=self.victim_image,
            attacker_image=self.attacker_image,
            flag_sha256=self.flag_sha256,
            attacker_flag_mount=False,
            cap_drop_all=True,
            no_new_privileges=True,
            pids_limit=self.pids_limit,
            memory=self.memory,
            cpus=self.cpus,
        )
        try:
            self.docker(["network", "create", "--internal", self.network])
            self.docker(self.container_args("victim"))
            self.docker(self.container_args("attacker"))
            self.wait_ready()
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
