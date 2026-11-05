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


def test_progress_reports_partial_work_without_network(tmp_path, monkeypatch):
    import json
    source = tmp_path/'source'
    source.mkdir()
    (source/'good.py').write_text('print(1)')
    (source/'bad.py').write_text('print(2)')
    output = tmp_path/'triage/jev-infra.json'
    progress = output.with_suffix('.progress.json')
    monkeypatch.setattr(jev, 'resolve_api_key', lambda value: 'test-only')
    def process(client, cache, group, *args):
        # The progress file must exist before a remote request is dispatched.
        assert json.loads(progress.read_text())['status'] == 'running'
        if group[0].path.endswith('bad.py'):
            raise RuntimeError('fixture failure')
        return ({unit.id: {'priority': .8} for unit in group}, {}, 'fixture-model', False)
    monkeypatch.setattr(jev, 'process_request', process)
    args = jev.build_parser().parse_args(
        ["--root", str(source), "--out", str(output), "--no-cache", "--workers", "1"]
    )
    jev.run(args)
    result = json.loads(progress.read_text())
    assert result['status'] == 'partial'
    assert result['processed_units'] == 1
    assert result['failed_units'] == 1
    assert result['stats']['units'] == 2
    assert json.loads(output.read_text())['units'][0]['priority'] == .8
