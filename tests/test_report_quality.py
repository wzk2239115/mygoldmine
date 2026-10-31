import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))

import report_quality
import localize_titles


def test_schema_fallbacks_fill_reproduction_and_remediation():
    finding = {
        "title": "English title",
        "verification": {"idea": "run the minimal server and POST /shutdown"},
        "fix": "require a control token",
        "root_cause": "missing auth",
        "impact": "remote DoS",
        "evidence": [{"path": "app.py", "line": 10}],
    }
    quality = report_quality.quality_of(finding, "zh")
    assert "reproduction" not in quality["missing"]
    assert "remediation" not in quality["missing"]
    assert quality["languageMismatch"] is True
    assert quality["titleLanguage"] == "en"


def test_chinese_title_passes_language_check():
    finding = {
        "title": "未认证的 /shutdown 允许任意客户端终止服务",
        "root_cause": "缺少认证",
        "impact": "拒绝服务",
        "reproduction": "启动服务并 POST /shutdown",
        "remediation": "要求控制令牌",
        "evidence": ["app.py:10"],
    }
    quality = report_quality.quality_of(finding, "zh")
    assert quality["ok"] is True
    assert quality["languageMismatch"] is False


def test_empty_title_is_reported_once_without_language_flag():
    quality = report_quality.quality_of({}, "zh")
    assert "title" in quality["missing"]
    assert "titleLanguage" not in quality["missing"]
    assert quality["languageMismatch"] is False


def test_localization_targets_only_english_titles():
    assert localize_titles.needs_localization({"title": "English only"}) is True
    assert localize_titles.needs_localization({"title": "未认证的 /shutdown"}) is False
    assert localize_titles.needs_localization({"title": ""}) is False
