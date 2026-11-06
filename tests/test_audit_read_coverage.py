import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_read_coverage", ROOT / "scripts/audit/read_coverage.py"
)
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


@pytest.fixture
def setup(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    (target / "app.py").write_text("line1\nline2\nline3\nline4\n")
    subprocess.run(["git", "-C", str(target), "add", "app.py"], check=True)
    root = tmp_path / "run/task-artifacts/read-coverage"
    root.mkdir(parents=True)
    return target, root, tmp_path


def prompt(identifier="auth", intent="检查鉴权边界"):
    return (
        f"AUDIT_INTENT_ID: {identifier}\nAUDIT_INTENT: {intent}\n"
        "COVERAGE_ID: cov-1\nHYPOTHESIS: 入口可能缺少鉴权\nAUDIT_SCOPE: app.py\n"
    )


def register(root, text):
    coverage.observe(
        {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"prompt": text}},
        root,
        root,
        "demo",
        "commit",
    )


def payload(target, transcript, tool="Read", result=None, tool_input=None):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": tool,
        "tool_use_id": "read-1",
        "cwd": str(target),
        "session_id": "session1",
        "transcript_path": str(transcript),
        "tool_input": tool_input or {"file_path": str(target / "app.py"), "limit": 1000},
        "tool_response": result
        if result is not None
        else {
            "file": {
                "filePath": str(target / "app.py"),
                "startLine": 2,
                "numLines": 2,
                "content": "line2\nline3\n",
            }
        },
    }


def transcript(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "user", "message": {"content": text}}) + "\n")
    return path


def test_actual_response_bounds_not_requested_full_file(setup):
    target, root, temp = setup
    register(root, prompt())
    file = transcript(temp / "child.jsonl", prompt())
    coverage.observe(payload(target, file), root, target, "demo", "commit")
    data = coverage.summarize(root, "demo", "commit")
    row = data["files"][0]
    assert row["ranges"][0]["start"] == 2 and row["ranges"][0]["end"] == 3
    assert row["intent"]["AUDIT_INTENT_ID"] == "auth"
    assert row["file"] == "app.py" and len(row["file_sha256"]) == 64


def test_parallel_agents_same_file_keep_different_intents(setup):
    target, root, temp = setup
    main = temp / "main.jsonl"
    for agent, identifier in [("aaa", "auth"), ("bbb", "injection")]:
        text = prompt(identifier)
        register(root, text)
        transcript(temp / "main/subagents" / f"agent-{agent}.jsonl", text)
        event = payload(target, main)
        event["agent_id"] = agent
        coverage.observe(event, root, target, "demo", "commit")
    data = coverage.summarize(root, "demo", "commit")
    assert {x["intent"]["AUDIT_INTENT_ID"] for x in data["files"]} == {"auth", "injection"}
    assert data["unattributed"] == 0


def test_missing_or_conflicting_declaration_denies_dispatch(setup, capsys):
    _, root, _ = setup
    register(root, "look at all files")
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    register(root, prompt())
    assert capsys.readouterr().out == ""
    register(root, prompt(intent="另一个意图"))
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_no_declaration_is_unattributed_not_latest_task(setup):
    target, root, temp = setup
    register(root, prompt())
    file = transcript(temp / "other.jsonl", "阅读 app.py")
    coverage.observe(payload(target, file), root, target, "demo", "commit")
    assert coverage.summarize(root, "demo", "commit")["unattributed"] == 1


@pytest.mark.parametrize("result", [{"is_error": True}, {"error": "failed"}, {"exitCode": 1}])
def test_failed_read_does_not_become_coverage(setup, result):
    target, root, temp = setup
    coverage.observe(
        payload(target, temp / "no.jsonl", result=result), root, target, "demo", "commit"
    )
    assert not coverage.summarize(root, "demo", "commit")["files"]


def test_unknown_return_range_not_full_file(setup):
    target, root, temp = setup
    coverage.observe(
        payload(target, temp / "no.jsonl", result="unrecognized"), root, target, "demo", "commit"
    )
    rows = coverage.summarize(root, "demo", "commit")["files"]
    assert rows[0]["kind"] == "unknown" and rows[0]["ranges"] == []


def test_search_is_separate_from_direct_reads(setup):
    target, root, temp = setup
    event = payload(
        target,
        temp / "no.jsonl",
        tool="Grep",
        tool_input={"path": str(target / "app.py"), "pattern": "line2", "output_mode": "content"},
        result="2:line2",
    )
    coverage.observe(event, root, target, "demo", "commit")
    rows = coverage.summarize(root, "demo", "commit")["files"]
    assert rows and all(x["kind"] == "search_seen" for x in rows)


def test_external_and_untracked_files_excluded(setup):
    target, root, temp = setup
    for file in [temp / "secret.py", target / "report.md"]:
        file.write_text("secret\n")
        event = payload(
            target,
            temp / "no.jsonl",
            tool_input={"file_path": str(file)},
            result={"file": {"filePath": str(file), "startLine": 1, "numLines": 1}},
        )
        coverage.observe(event, root, target, "demo", "commit")
    assert not coverage.summarize(root, "demo", "commit")["files"]


def test_subagent_stop_backfill_and_realtime_are_deduplicated(setup):
    target, root, temp = setup
    register(root, prompt())
    file = transcript(temp / "child.jsonl", prompt())
    event = payload(target, file)
    coverage.observe(event, root, target, "demo", "commit")
    with file.open("a") as stream:
        for row in [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "read-1",
                            "name": "Read",
                            "input": event["tool_input"],
                        }
                    ]
                },
            },
            {
                "type": "user",
                "toolUseResult": event["tool_response"],
                "message": {
                    "content": [{"type": "tool_result", "tool_use_id": "read-1", "content": "ok"}]
                },
            },
        ]:
            stream.write(json.dumps(row) + "\n")
    coverage.observe(
        {**event, "hook_event_name": "SubagentStop", "agent_transcript_path": str(file)},
        root,
        target,
        "demo",
        "commit",
    )
    assert coverage.summarize(root, "demo", "commit")["observations"] == 1


def test_hook_disabled_outside_stage_two(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("MYGOLDMINE_READ_COVERAGE_")}
    result = subprocess.run(
        ["python3", str(ROOT / ".claude/hooks/audit-read-coverage.py")],
        input="invalid",
        text=True,
        env=env,
        cwd=tmp_path,
        capture_output=True,
    )
    assert result.returncode == 0 and not list(tmp_path.iterdir())


def test_new_run_does_not_reuse_old_workspace_observations(setup):
    target, root, temp = setup
    (root / "events.jsonl").write_text('{"kind":"read"}\n')
    (root.parent.parent / "task-state").mkdir()
    env = {
        **os.environ,
        "MYGOLDMINE_READ_COVERAGE_ROOT": str(root),
        "MYGOLDMINE_READ_COVERAGE_TARGET": str(target),
        "MYGOLDMINE_READ_COVERAGE_PROJECT": "demo",
        "MYGOLDMINE_READ_COVERAGE_VERSION": "commit",
    }
    subprocess.run(
        ["python3", str(ROOT / "scripts/audit/read_coverage.py"), "init"], env=env, check=True
    )
    assert not (root / "events.jsonl").exists()
    assert list((root.parent.parent / "task-state").glob("previous-read-coverage-*"))


def test_learning_receives_read_evidence_without_overriding_stage_status(tmp_path):
    import sys

    sys.path.insert(0, str(ROOT / "scripts/stages"))
    from skill_bank import SkillBank, write

    repo = tmp_path / "engine"
    run = repo / "runs/demo/one"
    write(run / "audit-report.json", {"project": "demo", "status": "complete"})
    write(run / "report-quality.json", {"valid": True, "incomplete": 0})
    summary = run / "task-artifacts/read-coverage/summary.json"
    write(summary, {"status": "observed", "observations": 5})
    rows = SkillBank(repo).feedback(run, "demo")
    row = next(x for x in rows if x["stage"] == "orchestrator")
    assert row["state"] == "complete"
    assert any(x["path"].endswith("read-coverage/summary.json") for x in row["evidence"])
