import subprocess
import sys
from pathlib import Path

from scripts.ci.check_expression import audit, fingerprint, line_findings

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ci" / "check_expression.py"


def test_audit_covers_documentation_interface_and_cli(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "ui" / "src").mkdir(parents=True)
    (tmp_path / "node_modules" / "ignored").mkdir(parents=True)
    (tmp_path / "AGENTS.md").write_text("所有文案使用清楚的中文。\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text(
        "每次审计运行（run）使用独立沙箱。\n"
        "技术字段 `run` 保持原样。\n"
        "```text\n每个 run 不应在代码块中命中。\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "ui" / "src" / "App.jsx").write_text(
        "const text = '每个 run 使用独立沙箱，verify 前断开网络。';\n",
        encoding="utf-8",
    )
    (tmp_path / "run.sh").write_text("echo '所有尝试共享墙钟预算'\n", encoding="utf-8")
    (tmp_path / "node_modules" / "ignored" / "bad.md").write_text(
        "每个 run 不应被扫描。\n",
        encoding="utf-8",
    )

    report = audit(tmp_path)

    assert report["coverage"] == {
        "discovered_files": 4,
        "scanned_files": 4,
        "percent": 100.0,
        "cjk_lines": 5,
        "errors": [],
    }
    terms = {(item["path"], item["term"]) for item in report["findings"]}
    assert ("ui/src/App.jsx", "run") in terms
    assert ("ui/src/App.jsx", "verify") in terms
    assert ("run.sh", "墙钟") in terms
    assert all(item["path"] != "docs/guide.md" for item in report["findings"])
    assert all("node_modules" not in item["path"] for item in report["findings"])


def test_audit_detects_agent_markdown_and_english_phrases(tmp_path: Path):
    agent_file = tmp_path / ".claude" / "agents" / "reviewer.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text(
        "先检查 editable surface，再执行 review。\n"
        "使用 quality cost frontier 比较结果。\n",
        encoding="utf-8",
    )

    report = audit(tmp_path)

    assert report["coverage"]["scanned_files"] == 1
    assert report["scopes"]["agent-instructions"]["scanned"] == 1
    kinds = {item["kind"] for item in report["findings"]}
    assert kinds == {"mixed-language", "english-phrase"}


def test_fingerprint_does_not_depend_on_line_number():
    first = line_findings("docs/a.md", 1, "每个 run 一个沙箱", "每个 run 一个沙箱")
    moved = line_findings("docs/a.md", 20, "每个 run 一个沙箱", "每个 run 一个沙箱")

    assert fingerprint(first[0]) == fingerprint(moved[0])


def test_cli_baseline_rejects_new_mixed_language(tmp_path: Path):
    document = tmp_path / "README.md"
    document.write_text("所有文案使用清楚的中文。\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    create = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--write-baseline", str(baseline)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert create.returncode == 0

    document.write_text("所有文案使用清楚的中文。\n每个 run 使用独立沙箱。\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--baseline", str(baseline)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "相对基线新增：1 条" in result.stdout
