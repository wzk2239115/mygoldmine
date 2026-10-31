"""Regression cases from malformed agent output; no model/network calls."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "mine"))
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import check_report  # noqa: E402
import report_quality  # noqa: E402

GOOD = {
    "id": "TEST-1",
    "title": "缺少认证导致服务关闭",
    "root_cause": "控制接口缺少认证",
    "impact": "服务不可用",
    "reproduction": "本地测试实例请求关闭接口",
    "remediation": "为控制接口增加令牌校验",
    "evidence": ["app.py:10"],
}


def write_report(tmp_path, report):
    path = tmp_path / "audit-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("field", ["title", "root_cause", "impact", "reproduction", "remediation"])
@pytest.mark.parametrize("empty", ["", " \n ", None, False, 12, {}, []])
def test_empty_or_wrong_typed_required_fields(field, empty):
    finding = copy.deepcopy(GOOD)
    finding[field] = empty
    assert not report_quality.quality_of(finding)["ok"]


@pytest.mark.parametrize(
    "evidence",
    [
        [],
        [""],
        ["  ", None],
        [{}],
        [False, 12],
        {"path": "app.py"},
        [{"path": " "}],
        [{"line": 10}],
    ],
)
def test_truthy_but_empty_evidence_fails(evidence):
    finding = {**GOOD, "evidence": evidence}
    assert "evidence" in report_quality.quality_of(finding)["missing"]


@pytest.mark.parametrize(
    "evidence",
    [
        "app.py:10\n",
        ["app.py:10"],
        [{"path": "app.py", "line": 10}],
        [{"file": "app.py", "line": 10}],
        [{"snippet": "missing_auth()"}],
    ],
)
def test_supported_evidence_shapes(evidence):
    assert report_quality.quality_of({**GOOD, "evidence": evidence})["ok"]


def test_description_or_type_cannot_replace_explicit_title():
    finding = {**GOOD, "title": "", "type": "认证绕过", "description": "接口缺少认证"}
    assert "title" in report_quality.quality_of(finding)["missing"]


@pytest.mark.parametrize(
    "report",
    [
        None,
        [],
        1,
        {},
        {"findings": {}},
        {"findings": None},
        {"findings": [None]},
        {"vulnerabilities": ["bad"]},
        {"findings": [], "vulnerabilities": [GOOD]},
    ],
)
def test_invalid_report_structure_is_not_clean_zero(tmp_path, report):
    result = check_report.check_report(write_report(tmp_path, report), "zh")
    assert not result["valid"]
    assert result["errors"]


@pytest.mark.parametrize("key", ["findings", "vulnerabilities"])
def test_explicit_zero_findings_is_valid(tmp_path, key):
    result = check_report.check_report(write_report(tmp_path, {key: []}), "zh")
    assert result["valid"] and result["findings"] == result["incomplete"] == 0


def test_invalid_json_cli_writes_diagnostic_and_exits_two(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{bad json")
    out = tmp_path / "nested" / "quality.json"
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/mine/check_report.py"),
            "--report",
            str(path),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 2
    assert json.loads(out.read_text())["valid"] is False
    assert "Traceback" not in run.stderr


@pytest.mark.parametrize("flag", ["--fail-missing", "--fail-language"])
def test_cli_enforces_title_language(tmp_path, flag):
    path = write_report(tmp_path, {"findings": [{**GOOD, "title": "Missing authorization"}]})
    # Pin system language without depending on a machine's config.
    code = (
        "import sys; sys.path.insert(0, sys.argv.pop(1)); import check_report; "
        "check_report.report_quality.system_language=lambda: 'zh'; "
        "raise SystemExit(check_report.main())"
    )
    run = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "scripts/mine"), "--report", str(path), flag],
        capture_output=True,
    )
    assert run.returncode == 1


@pytest.mark.skipif(sys.platform != "linux", reason="miner uses GNU timeout/realpath")
@pytest.mark.parametrize(
    "report,expected",
    [({"findings": [GOOD]}, 0), ({"findings": [{**GOOD, "evidence": [" "]}]}, 2), ({}, 2)],
)
def test_miner_exit_and_metadata_follow_report_quality(tmp_path, report, expected):
    target = tmp_path / "target"
    target.mkdir()
    run_dir = tmp_path / "run"
    fake = tmp_path / "fake-claude"
    fake.write_text(
        "#!/usr/bin/env python3\nimport os,json,pathlib\n"
        'p=pathlib.Path(os.environ["RUN_DIR"])\n'
        '(p/"audit-report.md").write_text("# Test report")\n'
        '(p/"audit-report.json").write_text('
        + repr(json.dumps(report))
        + ')\nprint(json.dumps({"type":"result","is_error":False}))\n'
    )
    fake.chmod(0o700)
    env = {
        **os.environ,
        "CLAUDE_BIN": str(fake),
        "JEV_TRIAGE": "0",
        "MAX_ATTEMPTS": "1",
        "RETRY_DELAY": "0",
    }
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/mine/mine_one.sh"),
            "--target",
            str(target),
            "--run-dir",
            str(run_dir),
            "--timeout",
            "10",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == expected, result.stderr
    assert json.loads((run_dir / "run-meta.json").read_text())["exit_code"] == expected
    assert (run_dir / "report-quality.json").exists()
    assert not (run_dir / "run-meta.json" / "report-quality.log").exists()
