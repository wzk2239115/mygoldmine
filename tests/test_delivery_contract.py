import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "delivery_contract", ROOT / "scripts/workflow/delivery_contract.py"
)
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


@pytest.mark.parametrize(
    "report",
    [
        {"project": "rakazo"},
        {"metadata": {"project_id": "rakazo", "project_name": "Rakazo"}},
        {"project": "rakazo", "metadata": {"project_id": "rakazo"}},
    ],
)
def test_report_identity_compatibility(report):
    before = json.dumps(report)
    assert contract.report_project(report, "rakazo") == "rakazo"
    assert json.dumps(report) == before


@pytest.mark.parametrize(
    "report",
    [
        {"metadata": {"project_name": "rakazo"}},
        {"project": "Rakazo"},
        {"project": "other", "metadata": {"project_id": "rakazo"}},
        {"project": None, "metadata": {"project_id": "rakazo"}},
        {"metadata": {"project_id": "other"}},
        {"project": "../rakazo"},
    ],
)
def test_report_identity_rejects_missing_wrong_conflicting_or_invalid(report):
    with pytest.raises(ValueError):
        contract.report_project(report, "rakazo")


def make_environment(root):
    root.mkdir(parents=True)
    (root / "pyvenv.cfg").write_text("home = /container/python\nversion = 3.12.14\n")
    (root / "bin").mkdir()
    os.symlink("/not-on-host/python3", root / "bin/python3")
    os.symlink("python3", root / "bin/python")
    (root / "package.py").write_text("package\n")
    return root


def test_runtime_snapshot_preserves_link_metadata_without_following_it(tmp_path):
    root = make_environment(tmp_path / "arbitrary-name")
    snapshot = contract.runtime_environment(root)
    assert snapshot["role"] == "runtime_only" and snapshot["portable"] is False
    assert any(x.get("link") == "/not-on-host/python3" for x in snapshot["entries"])
    assert contract.runtime_environment(root)["sha256"] == snapshot["sha256"]
    (root / "package.py").write_text("changed\n")
    assert contract.runtime_environment(root)["sha256"] != snapshot["sha256"]


def test_directory_name_alone_does_not_exclude_files(tmp_path):
    root = tmp_path / "venv"
    root.mkdir()
    (root / "evidence.log").write_text("important")
    assert contract.runtime_environment(root) is None
    (root / "pyvenv.cfg").write_text("not a virtual environment")
    assert contract.runtime_environment(root) is None


def verification(root, evidence="result.log", **extra):
    (root / "evidence").mkdir(exist_ok=True)
    (root / "evidence/result.log").write_text("actual result")
    (root / "verify.sh").write_text("echo actual result")
    file = root / "verify-report.json"
    file.write_text(
        json.dumps(
            {"verdict": "confirmed", "evidence": [evidence], "harness": "verify.sh", **extra}
        )
    )
    return file


def test_required_evidence_and_script_checked(tmp_path):
    file = verification(tmp_path)
    assert len(contract.validate_verification_report(file, tmp_path)["files"]) == 2
    (tmp_path / "verify.sh").unlink()
    with pytest.raises(ValueError, match="缺失"):
        contract.validate_verification_report(file, tmp_path)


@pytest.mark.parametrize("value", ["missing.log", "../outside", "/etc/passwd"])
def test_missing_or_outside_evidence_is_not_silently_omitted(tmp_path, value):
    file = verification(tmp_path, value)
    with pytest.raises(ValueError):
        contract.validate_verification_report(file, tmp_path)


def test_environment_cannot_replace_evidence(tmp_path):
    make_environment(tmp_path / "evidence/runtime")
    file = verification(tmp_path, "runtime/package.py")
    with pytest.raises(ValueError, match="临时运行环境"):
        contract.validate_verification_report(file, tmp_path)


def test_container_mount_references_are_resolved_only_within_candidate_root(tmp_path):
    file = verification(tmp_path, harness="/verify/verify.sh")
    assert contract.validate_verification_report(file, tmp_path)["files"]


def test_recovery_restores_complete_matching_execution(tmp_path):
    import shutil

    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    report = verification(source, artifacts={"stdout": "harness.stdout.log"})
    (source / "harness.stdout.log").write_text("actual stdout")
    shutil.copy2(report, target / report.name)
    result = contract.recover_verification_delivery(target / report.name, source)
    assert (target / "harness.stdout.log").read_text() == "actual stdout"
    assert result["restored"]
    assert contract.validate_verification_report(target / report.name, target)


def test_recovery_rejects_different_report_and_conflicting_files(tmp_path):
    import shutil

    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    report = verification(source)
    shutil.copy2(report, target / report.name)
    (target / "verify.sh").write_text("different script")
    with pytest.raises(ValueError, match="禁止覆盖"):
        contract.recover_verification_delivery(target / report.name, source)
    (target / report.name).write_text("{}")
    with pytest.raises(ValueError, match="摘要不同"):
        contract.recover_verification_delivery(target / report.name, source)


def test_download_policy_is_generic_and_idempotent():
    spec = importlib.util.spec_from_file_location("download_policy", ROOT / "scripts/env/download_policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = "FROM base\nRUN apt-get update && apt-get install -y default-jdk unzip && rm -rf /var/lib/apt/lists/*\nCOPY . /source\n"
    result = module.apply(source)
    assert "default-jdk-headless unzip" in result
    assert "--mount=type=cache" in result
    assert "Acquire::Retries=3" in result
    assert result == module.apply(result)
    assert "COPY . /source" in result
