import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hook_keeps_immutable_workspace_untouched(tmp_path):
    target = tmp_path / "delivered"
    logs = target / ".workspace/logs"
    logs.mkdir(parents=True)
    original = logs / "operations.jsonl"
    original.write_text("frozen\n")
    env = {**os.environ, "XDG_STATE_HOME": str(tmp_path / "state")}
    for session in ["first", "second"]:
        payload = {
            "session_id": session,
            "tool_name": "Read",
            "tool_input": {},
            "tool_response": {},
        }
        result = subprocess.run(
            ["python3", str(ROOT / ".claude/hooks/operation-logger.py")],
            input=json.dumps(payload),
            text=True,
            cwd=target,
            env=env,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
    assert original.read_text() == "frozen\n"
    assert len(list((tmp_path / "state/mygoldmine/operation-logs").glob("*/operations.jsonl"))) == 2


def test_toolchain_preflight_distinguishes_missing_package_and_missing_index():
    import importlib.util
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "preflight", ROOT / "scripts/env/preflight_toolchain.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def runner(index):
        return lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=(
                "ID=debian\nVERSION_CODENAME=trixie\n__ARCH__\narm64\n__PACKAGES__\n"
                + "indexes="
                + index
                + "\nPACKAGE=openjdk-17-jdk-headless\n  Candidate: (none)\n"
            ),
        )

    assert (
        module.inspect("base", ["openjdk-17-jdk-headless"], runner("present"))["status"]
        == "blocked"
    )
    unknown = module.inspect("base", ["openjdk-17-jdk-headless"], runner("missing"))
    assert unknown["packages"][0]["status"] == "unknown"
    assert unknown["architecture"] == "arm64"
