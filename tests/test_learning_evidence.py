import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/stages"))
from learning_evidence import rank_evidence, read_evidence


def test_single_huge_line_is_bounded_and_can_continue(tmp_path):
    source = tmp_path / "trace.jsonl"
    source.write_text("x" * 100000)
    result = read_evidence(tmp_path, {"path": str(source), "length": 8000})
    assert len(result["content"]) == 8000
    assert result["next_offset"] == 8000
    assert read_evidence(tmp_path, {"path": str(source), "offset": 8000})["offset"] == 8000


def test_no_low_scoring_excerpt_is_dropped_and_failures_prioritized(tmp_path):
    source = tmp_path / "trace.jsonl"
    source.write_text("x" * 4000 + "TimeoutExpired" + "x" * 5000)

    def ask(state, questions):
        assert "goal" in questions["relevant"]["instructions"]
        return {"answers": {"relevant": {"noul": 0.01}}}

    result = rank_evidence(tmp_path, {"path": str(source), "goal": "goal", "chunks": 2}, ask)
    assert len(result["items"]) == 2
    assert result["items"][0]["failure_signal"]
    assert result["items"][0]["offset"] == 4000
    assert result["next_offset"] == 8000


def test_model_failure_keeps_original_locations(tmp_path):
    source = tmp_path / "trace.log"
    source.write_text("actual")

    def fail(*args):
        raise RuntimeError("secret must not leak")

    result = rank_evidence(tmp_path, {"path": str(source), "goal": "find gaps"}, fail)
    assert result["status"] == "degraded"
    assert result["items"][0]["offset"] == 0
    assert "secret" not in str(result)


def test_only_current_directory_and_regular_text_allowed(tmp_path):
    link = tmp_path / "link.log"
    link.symlink_to("/etc/passwd")
    for name in (str(link), "/etc/passwd", "../outside.log"):
        with pytest.raises(ValueError):
            read_evidence(tmp_path, {"path": name})
    with pytest.raises(ValueError):
        read_evidence(tmp_path, {"path": "test.log", "length": 999999})


def test_missing_key_does_not_terminate_mcp_server(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import learning_evidence

    source = tmp_path / "feedback.json"
    source.write_text("{}")

    def missing_key(_):
        raise SystemExit("missing key")

    monkeypatch.setattr(
        learning_evidence, "jev_module", lambda: SimpleNamespace(resolve_api_key=missing_key)
    )
    result = rank_evidence(tmp_path, {"path": str(source), "goal": "find gaps"})
    assert result["status"] == "unavailable"
