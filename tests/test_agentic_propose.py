from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from test_mining_driver import _install_baseline, _install_candidate
from test_mining_repair import ROOT_CAUSE, _record

from audit_rsi.mining_driver import drive_mining_repairs
from audit_rsi.mining_repair import load_active_mining_repairs

ROOT = Path(__file__).resolve().parents[1]


def test_agentic_markdown_drives_real_main_pipeline(tmp_path: Path) -> None:
    candidate = {
        "proposal": {
            "scope": "project",
            "project": "alpha",
            "kind": "false_positive",
            "pattern": {"root_cause": ROOT_CAUSE},
            "trusted_support": 1,
        },
        "content": (
            "# 误报排除：回环绑定\n\n"
            f"{ROOT_CAUSE}\n\n"
            "## 下一轮挖掘动作\n\n"
            "1. 先确认默认绑定地址和真实远程入口。\n"
        ),
    }
    seed = _record("alpha", "sem-fp-a", "fp")
    from test_mining_driver import _candidate

    installed = _candidate([seed])
    _install_candidate(tmp_path, installed)
    baseline = [
        _record("alpha", "sem-fp-a", "fp", run="before"),
        _record("alpha", "sem-tp-a", "runtime-confirmed", run="before"),
    ]
    baseline_run = _install_baseline(tmp_path, "alpha", baseline)

    def runner(**request):
        context = request["context_file"].read_text(encoding="utf-8")
        assert installed["content"] in context
        assert "尚未发布" in context
        return [
            _record(
                "alpha",
                "sem-tp-a",
                "runtime-confirmed",
                run=request["run_dir"].name,
            )
        ]

    report = drive_mining_repairs(
        tmp_path,
        scope="project",
        project="alpha",
        target=tmp_path,
        baseline_run=baseline_run,
        runner=runner,
    )
    assert report["status"] == "ok"
    assert report["published"] == 1
    result = report["results"][0]
    assert result["evaluation"]["accepted"] is True
    assert Path(result["context_file"]).is_file()
    rules, _ = load_active_mining_repairs(tmp_path, "alpha")
    assert rules[0]["kind"] == "false_positive"
    assert candidate["proposal"]["kind"] == "false_positive"


def test_invalid_agentic_markdown_cannot_enter_candidate_pipeline(tmp_path: Path) -> None:
    from test_mining_driver import _candidate

    installed = _candidate([_record("alpha", "sem-fp-a", "fp")])
    _install_candidate(tmp_path, installed)
    path = tmp_path / "rsi/mining-repairs/agentic" / f"{installed['candidate_id']}.md"
    path.write_text("# 缺少根因\n", encoding="utf-8")
    with pytest.raises(ValueError, match="agentic repair is invalid"):
        drive_mining_repairs(
            tmp_path,
            scope="project",
            project="alpha",
            target=tmp_path,
            baseline_run=tmp_path / "before",
        )


def test_post_validation_uses_claude_code_to_write_markdown(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    script_dir = engine / "scripts/rsi"
    script_dir.mkdir(parents=True)
    script = script_dir / "post_validation.sh"
    shutil.copy2(ROOT / "scripts/rsi/post_validation.sh", script)
    shutil.copytree(ROOT / "scripts/stages", engine / "scripts/stages")
    (engine / "audit_rsi").symlink_to(ROOT / "audit_rsi")
    ledger = engine / "ui/data/finding-ledger.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text('{"occurrences":{}}', encoding="utf-8")
    (engine / "runs").mkdir()
    claude = tmp_path / "claude"
    claude.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys\n"
        "pathlib.Path(os.environ['CLAUDE_CALLS']).write_text(' '.join(sys.argv[1:]))\n"
        "output = pathlib.Path(os.environ['AGENTIC_DIR'])\n"
        "output.mkdir(parents=True, exist_ok=True)\n"
        "(output / 'mrc_test.md').write_text('# 修复\\n')\n"
        "print('{\\\"type\\\":\\\"result\\\"}')\n",
        encoding="utf-8",
    )
    claude.chmod(0o755)
    calls = tmp_path / "claude-calls.txt"
    run_dir = engine / "runs" / "one"
    run_dir.mkdir(parents=True)
    subprocess.run(
        [
            "bash",
            str(script),
            "--project",
            "alpha",
            "--run-dir",
            str(run_dir),
        ],
        env={
            **os.environ,
            "CLAUDE_BIN": str(claude),
            "CLAUDE_CALLS": str(calls),
            "AGENTIC_DIR": str(engine / "rsi/mining-repairs/agentic"),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert (run_dir / "rsi/learner.jsonl").is_file()
    assert "--agent mining-repair-learner" in calls.read_text()
    assert json.loads((run_dir / "rsi/post-validation.json").read_text())["candidates"] == 1
    assert (engine / "rsi/mining-repairs/agentic/mrc_test.md").is_file()
