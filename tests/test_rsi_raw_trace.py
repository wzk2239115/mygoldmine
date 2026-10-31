import importlib.util
import json
import sys
from pathlib import Path

import pytest

from audit_rsi.adapters.raw_trace import parse_raw_trace, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "scripts" / "workflow"
sys.path.insert(0, str(WORKFLOW))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


refine = load_module("refine_worker_raw_trace_test", WORKFLOW / "refine_worker.py")


def assistant(content, uuid, timestamp=None, parent=None, usage=None):
    event = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": content,
            "usage": usage or {"input_tokens": 0, "output_tokens": 0},
        },
        "uuid": uuid,
        "parent_tool_use_id": parent,
    }
    if timestamp:
        event["timestamp"] = timestamp
    return event


def tool_result(tool_id, content, uuid, timestamp=None, parent=None, error=False):
    event = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": content,
                    "is_error": error,
                }
            ],
        },
        "uuid": uuid,
        "parent_tool_use_id": parent,
    }
    if timestamp:
        event["timestamp"] = timestamp
    return event


def write_stream(path, events):
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


def claude_fixture(path):
    secret = "sk-abcdefghijklmnop"
    events = [
        {
            "type": "system",
            "subtype": "init",
            "cwd": "/workspace/repo",
            "tools": ["Read", "Bash", "Task", "Agent"],
            "uuid": "init",
            "timestamp": "2026-10-30T10:00:00Z",
        },
        assistant(
            [{"type": "text", "text": f"检查 api_key=supersecretvalue 和 {secret}"}],
            "text",
            "2026-10-30T10:00:01Z",
            usage={"input_tokens": 8, "output_tokens": 2},
        ),
        assistant(
            [
                {
                    "type": "tool_use",
                    "id": "task-a",
                    "name": "Agent",
                    "input": {
                        "description": "Analyze filesystem boundary",
                        "subagent_type": "infra-analyst",
                        "prompt": f"SENSITIVE_PROMPT_DO_NOT_RECORD {secret}",
                    },
                }
            ],
            "agent",
            "2026-10-30T10:00:02Z",
        ),
        {
            "type": "system",
            "subtype": "task_started",
            "task_id": "task-a",
            "tool_use_id": "task-a",
            "uuid": "started-a",
        },
        assistant(
            [
                {
                    "type": "tool_use",
                    "id": "task-b",
                    "name": "Task",
                    "input": {"prompt": "负责 **network（网络）信任边界**"},
                }
            ],
            "task",
        ),
        assistant(
            [
                {
                    "type": "tool_use",
                    "id": "read-a",
                    "name": "Read",
                    "input": {"file_path": "/workspace/repo/src/a.py"},
                }
            ],
            "read",
            "2026-10-30T10:00:04Z",
            parent="task-a",
            usage={"input_tokens": 5, "output_tokens": 0},
        ),
        assistant(
            [
                {
                    "type": "tool_use",
                    "id": "bash-b",
                    "name": "Bash",
                    "input": {"command": f"export ACCESS_TOKEN={secret}; pytest"},
                }
            ],
            "bash",
            "2026-10-30T10:00:05Z",
            parent="task-b",
            usage={"input_tokens": 0, "output_tokens": 3},
        ),
        tool_result(
            "bash-b",
            f"Exit code 2\nBearer abcdefghijklmnop {secret}",
            "bash-result",
            "2026-10-30T10:00:07Z",
            parent="task-b",
            error=True,
        ),
        tool_result(
            "read-a",
            "Exit code 0\nfile summary",
            "read-result",
            "2026-10-30T10:00:06Z",
            parent="task-a",
        ),
        tool_result("task-a", "agent done", "agent-result", "2026-10-30T10:00:08Z"),
        tool_result("task-b", "task done", "task-result"),
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "duration_ms": 12000,
            "total_cost_usd": 0.25,
            "usage": {"input_tokens": 10, "output_tokens": 4},
            "result": f"done {secret}",
            "uuid": "result",
            "timestamp": "2026-10-30T10:00:12Z",
        },
    ]
    write_stream(path, events)
    return secret


def test_parallel_tasks_results_costs_redaction_and_stable_sequence(tmp_path):
    raw = tmp_path / "raw.jsonl"
    secret = claude_fixture(raw)

    actions = parse_raw_trace(raw, "demo", "run-1")

    assert [action["sequence"] for action in actions] == list(range(1, 8))
    assert [action["action"] for action in actions] == [
        "init",
        "text",
        "Agent",
        "Task",
        "Read",
        "Bash",
        "result",
    ]
    agent, task, read, bash = actions[2:6]
    assert read["parent_action_id"] == agent["action_id"]
    assert bash["parent_action_id"] == task["action_id"]
    assert agent["parent_action_id"] is None
    assert task["parent_action_id"] is None
    assert agent["pre_action"]["boundary"] == "filesystem"
    assert agent["pre_action"]["skill"] == "infra-analyst"
    assert task["pre_action"]["boundary"] == "network"
    assert read["context"]["boundary"] == "filesystem"
    assert read["context"]["files"] == [
        {"path": "/workspace/repo/src/a.py", "operation": "read"}
    ]

    assert read["post_action"]["status"] == "completed"
    assert read["outcome"] == {"returncode": 0, "error": False, "duration_ms": 2000.0}
    assert bash["post_action"]["status"] == "error"
    assert bash["outcome"] == {"returncode": 2, "error": True, "duration_ms": 2000.0}
    assert bash["cost"]["tokens"] == 3
    assert bash["cost"]["cost_estimated"] is False
    assert task["ts"] == ""
    assert task["cost"]["duration_ms"] == 0
    assert task["cost"]["tokens"] == 0
    assert task["cost"]["cost_estimated"] is True
    assert actions[-1]["cost"]["tokens"] == 14
    assert actions[-1]["cost"]["total_cost_usd"] == 0.25
    assert all(action["policy"] is None for action in actions)
    assert all(action["action_propensity"] is None for action in actions)

    serialized = json.dumps(actions, ensure_ascii=False)
    assert secret not in serialized
    assert "supersecretvalue" not in serialized
    assert "SENSITIVE_PROMPT_DO_NOT_RECORD" not in serialized
    assert "abcdefghijklmnop" not in serialized
    assert "[REDACTED]" in serialized
    assert parse_raw_trace(raw, "demo", "run-1") == actions

    output = tmp_path / "actions.jsonl"
    write_jsonl(actions, output)
    loaded = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert loaded == actions


def test_missing_tool_result_stays_pending_without_invented_outcome(tmp_path):
    raw = tmp_path / "raw.jsonl"
    write_stream(
        raw,
        [
            assistant(
                [{"type": "tool_use", "id": "read-1", "name": "Read", "input": {}}],
                "read",
            )
        ],
    )

    action = parse_raw_trace(raw, "demo", "run-without-result")[0]

    assert action["post_action"] == {"status": "pending", "result_summary": ""}
    assert action["outcome"] == {"returncode": None, "error": None, "duration_ms": 0}
    assert action["cost"]["cost_estimated"] is True


def refine_item(tmp_path):
    return {
        "id": "F-1",
        "project": "demo",
        "occurrence_id": "demo/run-1/F-1",
        "semantic_id": "semantic-1",
        "report": str(tmp_path / "runs" / "demo" / "run-1" / "audit-report.json"),
        "severity": "low",
        "verified": False,
        "confidence": "medium",
        "raw": {"title": "example", "evidence": [{"path": "src/a.py"}]},
        "raw_hash": "raw-hash",
        "report_hash": "report-hash",
    }


@pytest.mark.parametrize(
    ("status", "severity", "duplicate_of", "expected"),
    [
        ("reproduce", "low", "", "verify"),
        ("triage", "medium", "", "deep_read"),
        ("triage", "high", "", "human_review"),
        ("archived", "low", "demo/run-0/F-0", "duplicate_candidate"),
        ("archived", "low", "", "defer"),
    ],
)
def test_refine_action_mapping(status, severity, duplicate_of, expected):
    assert refine.trajectory_action(status, severity, duplicate_of) == expected


def test_refine_log_has_identity_action_and_provenance_without_changing_decision(
    tmp_path, monkeypatch
):
    item = refine_item(tmp_path)
    key = item["occurrence_id"]
    latest = {key: item}
    monkeypatch.setattr(refine, "DATA", tmp_path / "data")
    monkeypatch.setattr(refine, "QUEUE", refine.DATA / "refine-queue.json")
    monkeypatch.setattr(refine, "REFINE", refine.DATA / "refine-state.json")
    monkeypatch.setattr(refine, "PAUSE", refine.DATA / "refine.pause")
    monkeypatch.setattr(refine, "STOP", refine.DATA / "refine.stop")
    monkeypatch.setattr(refine, "LOCK", refine.DATA / ".refine-worker.lock")
    monkeypatch.setattr(refine, "TRAJECTORY", tmp_path / "refine.jsonl")
    refine.DATA.mkdir(parents=True)
    (refine.DATA / "auto-state.json").write_text(
        json.dumps({"findings": {key: {"verifyVerdict": "confirmed"}}}), encoding="utf-8"
    )
    (refine.DATA / "refine-state.json").write_text(
        json.dumps({"findings": {key: {"status": "archived", "source_hash": "old"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(refine.base.finding_ledger, "build_ledger", lambda: {})
    monkeypatch.setattr(refine.base, "latest_findings", lambda ledger: latest)
    monkeypatch.setattr(
        refine.base.finding_ledger,
        "merge_manual_state",
        lambda ledger, payloads: payloads[0].get("findings", {}),
    )
    monkeypatch.setattr(
        refine.base.finding_ledger, "identified_states", lambda states, ledger: states
    )
    monkeypatch.setattr(sys, "argv", ["refine_worker.py", "--once"])

    assert refine.main() == 0

    row = json.loads(refine.TRAJECTORY.read_text(encoding="utf-8"))
    patch = {"verifyVerdict": "confirmed"}
    expected_decision = refine.classify(item, patch, refine.score(item, patch), "")[0]
    assert row["decision"] == expected_decision == "reproduce"
    assert row["action"] == "verify"
    assert row["occurrence_id"] == key
    assert row["semantic_id"] == "semantic-1"
    assert row["schema_version"] == 1
    assert row["policy"] == {"name": "legacy_refine", "version": "1"}
    assert row["action_propensity"] == 1.0
    assert row["context"]["verification"] == row["features"]
    assert row["context"]["source_hash"] == row["source_hash"]
    assert row["features"]["verify_verdict"] == "confirmed"
    assert row["reason"] == "自动精炼：已有 confirmed verify 记录"
