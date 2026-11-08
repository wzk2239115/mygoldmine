"""确保没有奖励时仍执行默认八轮，并在第八轮结束。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/stages"))
import learning_cycle as module


def test_default_eight_rounds_without_reward(tmp_path, monkeypatch):
    source = tmp_path / "targets/demo"
    source.mkdir(parents=True)
    native = tmp_path / "ui/server/claude-workflows.mjs"
    native.parent.mkdir(parents=True)
    native.touch()
    calls = []

    class Bank:
        def __init__(self, repo):
            pass

        def active(self):
            return {}

        def feedback(self, run, project):
            pass

    class Process:
        def __init__(self, command, **kwargs):
            options = json.loads(command[-1])
            run = Path(options["runDir"])
            run.mkdir(parents=True)
            module.write(Path(str(run) + ".meta/status.json"), {"state": "completed"})
            calls.append(run.name)

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(module, "SkillBank", Bank)
    monkeypatch.setattr(module.subprocess, "Popen", Process)
    monkeypatch.setenv("GOLDMINE_NATIVE_WORKFLOW", "1")
    result = module.cycle(source, "demo", repo=tmp_path, continuous=True, cooldown=0)
    assert len(calls) == 8
    assert result["max_rounds"] == 8
    assert len(result["rounds"]) == 8
    assert result["status"] == "completed"
    assert "waiting_until" not in result
    assert not (tmp_path / "runs/.learning-cycle-demo.lock").exists()
