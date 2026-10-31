import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "mine"))

import check_report


def test_check_report_counts_complete_and_incomplete(tmp_path):
    report = {
        "findings": [
            {
                "id": "OK-1",
                "title": "未认证接口允许远程关闭服务",
                "root_cause": "缺少认证",
                "impact": "拒绝服务",
                "reproduction": "启动服务并调用接口",
                "remediation": "增加认证",
                "evidence": ["app.py:10"],
            },
            {
                "id": "BAD-1",
                "title": "Unauthenticated shutdown",
                "root_cause": "missing auth",
                "impact": "DoS",
                "verification": {"idea": "POST /shutdown"},
                "fix": "require token",
                "evidence": ["app.py:20"],
            },
        ]
    }
    path = tmp_path / "audit-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    result = check_report.check_report(path, "zh")
    assert result["findings"] == 2
    assert result["complete"] == 1
    assert result["incomplete"] == 1
    assert result["language_mismatch"] == 1
    assert result["missing"] == {"titleLanguage": 1}


def test_missing_fields_are_reported(tmp_path):
    report = {"findings": [{"id": "EMPTY-1", "title": "只有标题"}]}
    path = tmp_path / "audit-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    result = check_report.check_report(path, "zh")
    assert result["incomplete"] == 1
    for field in ("rootCause", "impact", "reproduction", "remediation", "evidence"):
        assert result["missing"][field] == 1
