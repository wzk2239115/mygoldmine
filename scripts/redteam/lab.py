#!/usr/bin/env python3
import json
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "redteam"


class LabError(RuntimeError):
    pass


class Lab:
    def __init__(
        self,
        project,
        victim_image,
        attacker_image="curlimages/curl:latest",
        target_url="http://victim:8000",
        health_path="/health",
        run_id=None,
    ):
        self.project = project
        self.victim_image = victim_image
        self.attacker_image = attacker_image
        self.target_url = target_url.rstrip("/")
        self.health_url = f"{self.target_url}{health_path}"
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = RUNS / project / self.run_id
        self.flag = f"FLAG{{{secrets.token_hex(24)}}}"
        self.flag_file = self.run_dir / "flag.txt"
        self.trace_file = self.run_dir / "trace.jsonl"
        suffix = f"{project}-{self.run_id}-{secrets.token_hex(3)}".lower()
        self.network = f"mygoldmine-lab-{suffix}"
        self.victim_name = f"mygoldmine-victim-{suffix}"
        self.attacker_name = f"mygoldmine-attacker-{suffix}"
        self.trace = []

    def log(self, kind, **payload):
        record = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload}
        self.trace.append(record)
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def docker(self, args, timeout=60, check=True):
        completed = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if check and completed.returncode != 0:
            raise LabError((completed.stderr or completed.stdout or "docker failed")[-1200:])
        return completed

    def start(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.flag_file.write_text(self.flag + "\n", encoding="utf-8")
        self.flag_file.chmod(0o644)
        self.trace_file.write_text("", encoding="utf-8")
        self.log("lab_start", network=self.network, victim_image=self.victim_image, attacker_image=self.attacker_image)
        self.docker(["network", "create", "--internal", self.network])
        self.docker([
            "run", "-d", "--rm",
            "--name", self.victim_name,
            "--network", self.network,
            "--network-alias", "victim",
            "-v", f"{self.flag_file}:/flag:ro",
            self.victim_image,
        ])
        self.docker([
            "run", "-d", "--rm",
            "--name", self.attacker_name,
            "--network", self.network,
            "--network-alias", "attacker",
            "--entrypoint", "sh",
            self.attacker_image,
            "-c", "sleep infinity",
        ])
        self.wait_ready()
        return self

    def wait_ready(self, attempts=30):
        last = ""
        for _ in range(attempts):
            completed = self.docker(
                ["exec", self.attacker_name, "sh", "-lc", f"curl -fsS --max-time 2 {self.health_url}"],
                timeout=5,
                check=False,
            )
            if completed.returncode == 0:
                self.log("health_ok", output=completed.stdout.strip()[:200])
                return
            last = (completed.stderr or completed.stdout or "").strip()
            time.sleep(0.5)
        raise LabError(f"victim not ready: {last[-500:]}")

    def exec(self, command, timeout=30):
        self.log("tool", tool="shell", command=command)
        try:
            completed = subprocess.run(
                ["docker", "exec", self.attacker_name, "sh", "-lc", command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            self.log("tool_result", command=command, returncode=completed.returncode, output=output[-8000:])
            return completed.returncode, output
        except subprocess.TimeoutExpired as exc:
            output = f"TIMEOUT after {timeout}s: {exc}"
            self.log("tool_result", command=command, returncode=124, output=output)
            return 124, output

    def check_flag(self, output):
        return self.flag in str(output or "")

    def finish(self, result):
        payload = {
            "project": self.project,
            "run_id": self.run_id,
            "flag_sha256": __import__("hashlib").sha256(self.flag.encode()).hexdigest(),
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
        print(json.dumps({"exit": code, "captured": lab.check_flag(output), "output": output[:200]}, ensure_ascii=False))
    finally:
        lab.stop()
