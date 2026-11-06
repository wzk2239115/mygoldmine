
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/mine"))
import check_report  # noqa: E402


def test_report_identity_rejects_brand_and_other_project(tmp_path):
    report = tmp_path / "audit-report.json"
    for value in ("OpenAI Codex", "opencode", None):
        report.write_text(json.dumps({"project": value, "findings": []}))
        result = check_report.check_report(report, expected_project="codex")
        assert not result["valid"]
        assert any("project_name" in error for error in result["errors"])
    payload = {"project": "codex", "project_name": "OpenAI Codex", "findings": []}
    report.write_text(json.dumps(payload))
    assert check_report.check_report(report, expected_project="codex")["valid"]


def test_identity_comes_from_owned_run_path_not_model_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(check_report, "ROOT", tmp_path)
    root = tmp_path / "runs/codex/one"
    root.mkdir(parents=True)
    report = root / "audit-report.json"
    report.write_text(json.dumps({"project": "OpenAI Codex", "findings": []}))
    assert not check_report.check_report(report)["valid"]
    report.write_text(json.dumps({"project": "codex", "findings": []}))
    assert check_report.check_report(report)["valid"]
