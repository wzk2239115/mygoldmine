from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".claude"
    / "skills"
    / "jev-triage"
    / "jev_triage.py"
)
spec = importlib.util.spec_from_file_location("jev_triage", SCRIPT)
assert spec and spec.loader
jev = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = jev
spec.loader.exec_module(jev)


def test_negative_question_does_not_inflate_priority() -> None:
    profile = {
        "load": {"type": "noul"},
        "path_allowlist": {"type": "noul", "positive": False},
    }
    priority, flags, mitigations = jev.score_answers(
        {"path_allowlist": {"noul": 0.05}},
        profile,
        0.5,
    )
    assert priority == 0.0
    assert flags == {}
    assert mitigations == {}

    priority, flags, mitigations = jev.score_answers(
        {
            "load": {"noul": 0.8},
            "path_allowlist": {"noul": 0.9},
        },
        profile,
        0.5,
    )
    assert flags["load"] == 0.8
    assert mitigations["path_allowlist"] == 0.9
    assert abs(priority - 0.35) < 1e-9


def test_auto_split_covers_all_lines() -> None:
    text = "\n".join(f"line {i} " + "x" * 20 for i in range(1, 21)) + "\n"
    units = list(jev.split_blocks("demo.py", text, 0, 120))
    assert len(units) > 1
    assert units[0].line_start == 1
    assert units[-1].line_end == 20
    assert all("#L" in unit.id for unit in units)
    joined = "".join(unit.text for unit in units)
    assert "line 1 " in joined and "line 20 " in joined


def test_redact_masks_common_secrets() -> None:
    text = (
        "key = 'sk-abcdefghijklmnop123456'\n"
        "password = 'supersecret123'\n"
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz\n"
    )
    redacted = jev.redact(text)
    assert "sk-abcdefghijklmnop123456" not in redacted
    assert "supersecret123" not in redacted
    assert "abcdefghijklmnopqrstuvwxyz" not in redacted
