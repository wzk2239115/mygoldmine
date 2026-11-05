import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/stages"))
from owned_process import run_session
from stage_builds import start_build, wait_builds


def test_timeout_cleans_detached_descendant(tmp_path):
    pid_file = tmp_path / "pid"
    grandchild = "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
    parent = (
        "import subprocess,sys,time;from pathlib import Path;"
        f"p=subprocess.Popen([sys.executable,'-c',{grandchild!r}],start_new_session=True);"
        f"Path({str(pid_file)!r}).write_text(str(p.pid));time.sleep(30)"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        run_session([sys.executable, "-c", parent], timeout=0.5, capture_output=True)
    pid = int(pid_file.read_text())
    stat = Path(f"/proc/{pid}/stat")
    assert not stat.exists() or stat.read_text().split(") ")[1].startswith("Z ")


def test_stage_image_build_survives_launcher_and_is_deduplicated(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    lab.mkdir()
    (lab / "Dockerfile").write_text("FROM scratch")
    (lab / "lab-task.json").write_text(json.dumps({"source": str(lab), "build_deadline": time.time() + 30}))
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nsleep 1\nprintf built >> proof\n")
    docker.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    arguments = {"dockerfile": str(lab / "Dockerfile"), "context": str(lab), "image": "test:stage", "timeout_seconds": 10}
    first = start_build("redteam-lab", lab, arguments)
    second = start_build("redteam-lab", lab, arguments)
    assert first["task_file"] == second["task_file"]
    assert second["reused"] is True
    assert wait_builds(lab)[0]["status"] == "completed"
    assert (lab / "proof").read_text() == "built"
    monkeypatch.setenv("STAGE_BUILD_VERIFY_ONLY", "1")
    with pytest.raises(ValueError, match="验收"):
        start_build("redteam-lab", lab, arguments)


def test_scene_partial_files_with_nonzero_exit_are_not_success(tmp_path):
    model = tmp_path / "visual-model.json"
    out = tmp_path / "out"
    out.mkdir()
    (out / "scene-F-1.webp").write_bytes(b"unfinished")
    (out / "scene-F-1.director.json").write_text("{}")
    model.write_text(json.dumps({"project": "fixture", "trees": {"attacks": [{"finding_id": "F-1", "scene": { "title": "test" }}]}}))
    cli = tmp_path / "claude"
    cli.write_text("#!/bin/sh\nexit 7\n")
    cli.chmod(0o700)
    result = subprocess.run([sys.executable, str(ROOT / ".claude/skills/project-cartographer/scripts/render_attack_scenes_agentic.py"), "--model", str(model), "--out-dir", str(out), "--claude", str(cli)], capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["failed"] == 1


def test_failed_learner_does_not_launch_optimizer(tmp_path, monkeypatch):
    import learn_round
    from types import SimpleNamespace
    monkeypatch.setattr(learn_round, 'SkillBank', lambda _: SimpleNamespace(feedback=lambda *a: [], render=lambda *a, **kw: {'versions': []}))
    monkeypatch.setattr(learn_round, "run_session", lambda *a, **kw: subprocess.CompletedProcess(a, 7))
    monkeypatch.setattr(learn_round, "_run_skillopt", lambda *a, **kw: pytest.fail("failed learner must not optimize"))
    run = tmp_path / "run"
    run.mkdir()
    result = learn_round.learn(run, "fixture", repo=ROOT)
    assert result["exit_code"] == 7
    assert result["skillopt"]["status"] == "skipped_failed_learning"
