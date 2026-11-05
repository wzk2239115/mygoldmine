import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "redteam"))
sys.path.insert(0, str(ROOT / "scripts" / "stages"))
import build_lab  # noqa: E402
import contracts  # noqa: E402
import lab as lab_module  # noqa: E402
import submission  # noqa: E402


def binding(tmp_path, identifier="F-1"):
    finding = tmp_path / f"{identifier}.json"
    finding.write_text(json.dumps({"id": identifier, "title": "fixture"}) + "\n", encoding="utf-8")
    return finding, hashlib.sha256(finding.read_bytes()).hexdigest()


def base_scenario(tmp_path, mode):
    finding, digest = binding(tmp_path)
    return finding, digest, {
        "schema_version": 1,
        "finding_id": "F-1",
        "finding_sha256": digest,
        "source": {"commit": "a" * 40},
        "mode": mode,
        "victim_image": "fixture/victim:latest",
        "attacker_image": "fixture/attacker:latest",
        "launch": {"command": ["python3", "/lab/driver.py"]},
        "input": {"path": "/input"},
    }


def validate(scenario, finding, digest):
    return contracts.validate_scenario(
        scenario,
        expected_finding_id="F-1",
        expected_finding_sha256=digest,
        expected_source=scenario["source"],
    )


def test_cli_and_library_scenarios_are_valid(tmp_path):
    finding, digest, cli = base_scenario(tmp_path, "cli")
    assert validate(cli, finding, digest)["input"] == {"path": "/input"}
    library = dict(cli)
    library.update({
        "mode": "library",
        "driver": "driver.py",
        "entry": {"module": "pkg.mod", "qualname": "real_entry", "source_ref": "pkg/mod.py:1"},
    })
    normalized = validate(library, finding, digest)
    assert normalized["driver"] == "driver.py"
    assert normalized["negative_control"] == {"kind": "empty_input"}


@pytest.mark.parametrize(
    "mutation",
    [
        {"launch": {"command": "python3 -m pkg"}},
        {"input": {"path": "/flag"}},
        {"input": {"path": "/input/../flag"}},
        {"target_url": "http://victim:8000"},
        {"mounts": {"attacker": ["/host:/host"]}},
    ],
)
def test_cli_rejects_unsafe_or_http_only_fields(tmp_path, mutation):
    finding, digest, scenario = base_scenario(tmp_path, "cli")
    scenario.update(mutation)
    with pytest.raises(contracts.ContractError):
        validate(scenario, finding, digest)


def test_library_requires_driver_and_entry(tmp_path):
    finding, digest, scenario = base_scenario(tmp_path, "library")
    with pytest.raises(contracts.ContractError) as error:
        validate(scenario, finding, digest)
    assert error.value.status == "blocked_scenario_invalid"


def test_blocked_delivery_validates_and_rejects_fake_dynamic_claims(tmp_path):
    _, digest = binding(tmp_path)
    document = {
        "schema_version": 1,
        "status": "blocked",
        "finding_id": "F-1",
        "finding_sha256": digest,
        "source": {"commit": "a" * 40},
        "mode": "library",
        "attacked_surface": "library",
        "reason": "当前执行器没有可用的进程内入口",
        "checked_entries": ["pkg/mod.py:10"],
        "missing_capabilities": ["需要真实入口驱动"],
        "evidence": ["BLOCKED.md"],
        "attempted": ["核对了调用链"],
        "next_conditions": ["补齐执行原语后重试"],
        "claims_dynamic_validation": False,
    }
    normalized = contracts.validate_blocked(
        document, expected_finding_id="F-1", expected_finding_sha256=digest
    )
    assert normalized["status"] == "blocked"
    fake = dict(document)
    fake["claims_dynamic_validation"] = True
    with pytest.raises(contracts.ContractError):
        contracts.validate_blocked(fake)
    escaped = dict(document)
    escaped["evidence"] = ["../outside"]
    with pytest.raises(contracts.ContractError):
        contracts.validate_blocked(escaped)


def test_input_snapshot_rejects_symlink_and_copies_regular_files(tmp_path, monkeypatch):
    monkeypatch.setattr(lab_module, "RUNS", tmp_path / "runs")
    lab = lab_module.Lab(
        "demo", "victim", mode="cli", input_config={"path": "/input"}, run_id="run"
    )
    lab.input_dir.mkdir(parents=True)
    (lab.input_dir / "artifact.bin").write_bytes(b"payload")
    snapshot = lab._snapshot_input()
    assert (snapshot / "artifact.bin").read_bytes() == b"payload"
    (lab.input_dir / "link").symlink_to(lab.input_dir / "artifact.bin")
    with pytest.raises(lab_module.LabError) as error:
        lab._snapshot_input()
    assert error.value.status == "agent_input_error"


def test_direct_attacker_mounts_only_input_and_victim_runs_fixed_command(tmp_path, monkeypatch):
    monkeypatch.setattr(lab_module, "RUNS", tmp_path / "runs")
    lab = lab_module.Lab(
        "demo", "fixture/victim", mode="cli", input_config={"path": "/input"}, run_id="run",
        launch={"command": ["python3", "-m", "pkg", "--input", "/input/artifact"]},
    )
    attacker = lab.container_args("attacker")
    assert any(str(lab.input_dir) + ":/input:rw" in arg for arg in attacker)
    assert not any("/flag" in arg for arg in attacker)
    assert "--read-only" in attacker

    lab.flag = "FLAG{fixture}"
    lab.flag_sha256 = hashlib.sha256(lab.flag.encode()).hexdigest()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=lab.flag + "\n", stderr="")

    monkeypatch.setattr(lab_module.subprocess, "run", fake_run)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    code, output = lab._run_victim(snapshot, timeout=5)
    assert code == 0
    args = calls[0]
    assert "/flag:ro" in " ".join(args)
    assert any(str(snapshot) + ":/input:ro" in arg for arg in args)
    image_index = args.index("fixture/victim")
    assert args[image_index + 1:] == ["python3", "-m", "pkg", "--input", "/input/artifact"]
    assert lab.capture_from_tool(output)["source"] == "tool_output"


def test_negative_control_aborts_when_flag_leaks(tmp_path, monkeypatch):
    monkeypatch.setattr(lab_module, "RUNS", tmp_path / "runs")
    lab = lab_module.Lab(
        "demo", "fixture/victim", mode="cli", input_config={"path": "/input"}, run_id="run"
    )
    lab.input_dir.mkdir(parents=True)
    lab.flag = "FLAG{leaked}"
    lab.flag_sha256 = hashlib.sha256(lab.flag.encode()).hexdigest()
    monkeypatch.setattr(lab, "_run_victim", lambda snapshot, timeout, control=False: (0, lab.flag))
    with pytest.raises(lab_module.LabError) as error:
        lab.run_negative_control()
    assert error.value.status == "blocked_scenario_invalid"


def test_build_lab_preserves_structured_blocker(tmp_path, monkeypatch, capsys):
    finding, digest = binding(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    lab_dir = tmp_path / "lab"
    monkeypatch.setattr(build_lab, "ROOT", tmp_path)
    monkeypatch.setattr(build_lab, "language_directive", lambda: "")
    monkeypatch.setattr(build_lab, "source_binding", lambda *_: {"commit": "a" * 40})
    monkeypatch.setattr(build_lab, "claude_connection", lambda _: ("fixture", {}))
    monkeypatch.setattr(build_lab, "delivery_config", lambda *_: {})
    monkeypatch.setattr(build_lab, "layered_skill_instruction", lambda *_: "")

    def invoke(command, **kwargs):
        document = {
            "schema_version": 1,
            "status": "blocked",
            "finding_id": "F-1",
            "finding_sha256": digest,
            "source": {"commit": "a" * 40},
            "mode": "library",
            "attacked_surface": "library",
            "reason": "没有可执行的真实入口",
            "checked_entries": ["pkg/mod.py:10"],
            "missing_capabilities": ["需要真实入口驱动"],
            "evidence": ["BLOCKED.md"],
            "attempted": ["核对调用链"],
            "next_conditions": ["补齐后重试"],
            "claims_dynamic_validation": False,
        }
        (lab_dir / "blocked.json").write_text(json.dumps(document), encoding="utf-8")
        (lab_dir / "BLOCKED.md").write_text("# BLOCKED\n\n没有可执行的真实入口\n", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(build_lab.subprocess, "run", invoke)
    args = SimpleNamespace(
        project="demo", finding=str(finding), source=str(source), lab_dir=str(lab_dir),
        blue_handoff="", dry_run=False, build_only=True, claude="fixture",
        claude_model="fixture", timeout=60,
    )
    assert build_lab.run(args) == 0
    task = json.loads((lab_dir / "lab-task.json").read_text())
    assert task["supported_modes"] == ["cli", "http", "library"]
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "blocked"
    assert output["blocked_valid"] is True
    assert output["blocked_reason"] == "没有可执行的真实入口"
    assert output["scenario_valid"] is False


def test_submission_accepts_blocked_json_and_rejects_markdown(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    _, digest = binding(tmp_path)
    document = {
        "schema_version": 1,
        "status": "blocked",
        "finding_id": "F-1",
        "finding_sha256": digest,
        "source": {"commit": "a" * 40},
        "mode": "library",
        "attacked_surface": "library",
        "reason": "没有可执行的真实入口",
        "checked_entries": ["pkg/mod.py:10"],
        "missing_capabilities": ["需要真实入口驱动"],
        "evidence": ["BLOCKED.md"],
        "attempted": ["核对调用链"],
        "next_conditions": ["补齐后重试"],
        "claims_dynamic_validation": False,
    }
    artifact = root / "blocked.json"
    artifact.write_text(json.dumps(document), encoding="utf-8")
    receipt = submission.submit("redteam-lab", root, {
        "artifact": str(artifact), "summary": "受阻", "limitations": ["缺少入口"],
    })
    assert receipt["decision"] == "accepted"
    markdown = root / "BLOCKED.md"
    markdown.write_text("# BLOCKED\n", encoding="utf-8")
    receipt = submission.submit("redteam-lab", root, {
        "artifact": str(markdown), "summary": "受阻", "limitations": ["缺少入口"],
    })
    assert receipt["decision"] == "needs_revision"
    assert any("结构化受阻文件" in error for error in receipt["errors"])


def test_scenario_safety_rejects_shell_wrapper_and_flag_driver(tmp_path):
    finding, digest, cli = base_scenario(tmp_path, "cli")
    cli["launch"] = {"command": ["sh", "-c", "python3 -m pkg"]}
    with pytest.raises(contracts.ContractError):
        build_lab.scenario_safety(validate(cli, finding, digest), tmp_path)
    (tmp_path / "driver.py").write_text("print(open('/flag').read())\n", encoding="utf-8")
    library = dict(cli)
    library.update({
        "mode": "library",
        "launch": {"entrypoint": "python3", "command": ["/lab/driver.py"]},
        "driver": "driver.py",
        "entry": {"module": "pkg.mod", "qualname": "real_entry", "source_ref": "pkg/mod.py:1"},
    })
    with pytest.raises(contracts.ContractError):
        build_lab.scenario_safety(validate(library, finding, digest), tmp_path)


def test_direct_launch_accepts_optional_entrypoint(tmp_path):
    finding, digest, cli = base_scenario(tmp_path, "cli")
    cli["launch"] = {"entrypoint": "python3", "command": ["-m", "pkg"]}
    assert validate(cli, finding, digest)["launch"]["entrypoint"] == "python3"


def test_batch_propagates_structured_blocker(tmp_path, monkeypatch):
    import batch

    monkeypatch.setattr(batch, "ROOT", tmp_path)
    monkeypatch.setattr(batch, "BATCH_ROOT", tmp_path / "batches")
    monkeypatch.setattr(batch, "resolve_candidate", lambda candidate, *_: {"raw": {"id": candidate["id"]}})
    monkeypatch.setattr(batch, "record_stage", lambda *args, **kwargs: None)
    payload = {
        "status": "blocked",
        "blocked_valid": True,
        "finding_id": "F-1",
        "scenario_valid": False,
        "blocked": str(tmp_path / "blocked.json"),
        "blocked_reason": "没有可执行的真实入口",
        "blocked_surface": "library",
        "missing_capabilities": ["需要真实入口驱动"],
        "mode": "library",
        "error": "没有可执行的真实入口",
    }

    def invoke(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(batch.subprocess, "run", invoke)
    candidates = [{"project": "demo", "id": "F-1", "run_id": "one"}]
    snapshot = {"project": "demo", "run_id": "one", "sha256": "a" * 64, "items": {"F-1": {"raw": {"id": "F-1"}}}}
    args = SimpleNamespace(build_jobs=1, model="fixture", build_timeout=30)
    out = tmp_path / "out"
    out.mkdir()
    results = batch.build_parallel(candidates, {}, None, out, args)
    plan = results["demo:F-1"]
    assert plan["status"] == "blocked"
    assert plan["blocked_reason"] == "没有可执行的真实入口"
    assert plan["missing_capabilities"] == ["需要真实入口驱动"]


def test_timeout_blocked_delivery_is_structured_and_valid(tmp_path):
    _, digest = binding(tmp_path)
    lab_dir = tmp_path / "lab"
    lab_dir.mkdir()
    (lab_dir / "builder.log").write_text("started\n", encoding="utf-8")
    path = build_lab.write_blocked_delivery(
        lab_dir, "F-1", digest, {"commit": "a" * 40},
        "lab builder timed out after 1s",
    )
    document = json.loads(path.read_text())
    assert contracts.validate_blocked(
        document, expected_finding_id="F-1", expected_finding_sha256=digest
    )["status"] == "blocked"
    assert (lab_dir / "BLOCKED.md").is_file()
