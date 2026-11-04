import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stop_hook', ROOT / '.claude/hooks/security-orchestrator-stop.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def test_stop_checks_actual_delivery_report(monkeypatch, tmp_path):
    monkeypatch.setenv('RUN_DIR', str(tmp_path))
    report = tmp_path / 'audit-report.json'
    report.write_text(json.dumps({'findings': [{'id': 'F-1', 'title': '候选问题', 'severity': 'high'}]}))
    checker = hook.TaskChecker()
    checker.check_run_report()
    assert checker.has_issues
    assert 'rootCause' in checker.artifact_issues[-1]
    assert 'impact' in checker.artifact_issues[-1]
    assert 'reproduction' in checker.artifact_issues[-1]


def test_stop_does_not_reject_valid_empty_findings(monkeypatch, tmp_path):
    monkeypatch.setenv('RUN_DIR', str(tmp_path))
    (tmp_path / 'audit-report.json').write_text(json.dumps({'findings': []}))
    checker = hook.TaskChecker()
    checker.check_run_report()
    assert not checker.has_issues
