import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "redteam"))
import batch  # noqa: E402


def test_harness_missing_module_extracts_package():
    assert batch.harness_missing_module(
        "Traceback (most recent call last):\n"
        "ModuleNotFoundError: No module named 'openai'\n"
    ) == "openai"
    assert batch.harness_missing_module("ModuleNotFoundError: No module named 'pkg.sub'") == "pkg"
    assert batch.harness_missing_module("ordinary failure") == ""


def test_missing_harness_modules_uses_find_spec(monkeypatch):
    monkeypatch.setattr(batch.importlib.util, "find_spec", lambda name: None)
    assert batch.missing_harness_modules(("openai", "json")) == ["openai", "json"]


def test_batch_blocks_before_building_labs_when_runner_dependency_is_missing(
    tmp_path, monkeypatch, capsys
):
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps({
        "candidates": [{"project": "demo", "id": "F-1", "run_id": "r1"}],
    }), encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "BATCH_ROOT", tmp_path / "batches")
    monkeypatch.setattr(batch.base.finding_ledger, "build_ledger", lambda: {})
    monkeypatch.setattr(batch, "missing_harness_modules", lambda: ["openai"])
    monkeypatch.setattr(batch, "ensure_runner", lambda *a, **k: {"status": "blocked"})
    monkeypatch.setattr(sys, "argv", [
        "batch.py", "--candidates", str(candidates), "--out-dir", str(out),
    ])

    assert batch.main() == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["error_scope"] == "harness_dependency"
    assert summary["retry_owner"] == "runner-environment"
    assert summary["results"][0]["status"] == "blocked_harness_dependency"
    assert summary["results"][0]["missing_modules"] == ["openai"]
    assert not (out / "construction").exists()
    capsys.readouterr()
