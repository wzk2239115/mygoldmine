import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "redteam"))
import batch  # noqa: E402
import build_lab  # noqa: E402
import contracts  # noqa: E402
import judge  # noqa: E402
import lab as lab_module  # noqa: E402


def make_finding(tmp_path, identifier="F-1"):
    path = tmp_path / f"{identifier}.json"
    path.write_text(json.dumps({"id": identifier, "title": "test finding"}) + "\n", encoding="utf-8")
    return path


def make_scenario(finding_path, **overrides):
    finding_bytes = finding_path.read_bytes()
    finding = json.loads(finding_bytes)
    scenario = {
        "schema_version": 1,
        "finding_id": finding["id"],
        "finding_sha256": hashlib.sha256(finding_bytes).hexdigest(),
        "source": {"content_sha256": "a" * 64},
        "mode": "http",
        "victim_image": "fixture/victim:latest",
        "attacker_image": "fixture/attacker:latest",
        "launch": {"command": []},
        "target_url": "http://victim:8000",
        "health": {"path": "/health"},
    }
    scenario.update(overrides)
    return scenario


def validate(scenario, finding_path):
    return contracts.validate_scenario(
        scenario,
        expected_finding_id=json.loads(finding_path.read_text())["id"],
        expected_finding_sha256=hashlib.sha256(finding_path.read_bytes()).hexdigest(),
        expected_source=scenario["source"],
    )


def approved_verdict():
    return {
        "verdict": "approved",
        "intended_vulnerability": True,
        "flag_provenance": True,
        "no_cheat": True,
        "environment_plausible": True,
        "reproducible": True,
        "minimal": True,
        "confidence": "high",
        "reason": "tool output and trace match",
        "concerns": [],
        "recommended_status": "runtime-validated",
    }


def test_per_finding_scenario_is_preferred_and_hash_bound(tmp_path):
    finding_path = make_finding(tmp_path)
    finding = json.loads(finding_path.read_text())
    preferred = contracts.scenario_path(tmp_path, "project", finding)
    legacy = tmp_path / "labs" / "project" / "scenario.json"
    assert preferred == tmp_path / "labs" / "project" / "F-1" / "scenario.json"
    assert contracts.scenario_path(tmp_path, "project", "F-2") != preferred
    preferred.parent.mkdir(parents=True)
    legacy.write_text("not json", encoding="utf-8")
    preferred.write_text(json.dumps(make_scenario(finding_path)), encoding="utf-8")
    resolved, scenario = contracts.resolve_scenario(
        tmp_path, "project", finding, finding_path.read_bytes()
    )
    assert resolved == preferred
    assert scenario["finding_id"] == "F-1"


def test_wrong_scenario_and_stale_finding_are_rejected(tmp_path):
    finding_path = make_finding(tmp_path)
    with pytest.raises(contracts.ContractError) as mismatch:
        validate(make_scenario(finding_path, finding_id="F-other"), finding_path)
    assert mismatch.value.status == "blocked_scenario_mismatch"
    with pytest.raises(contracts.ContractError) as stale:
        validate(make_scenario(finding_path, finding_sha256="0" * 64), finding_path)
    assert stale.value.status == "blocked_scenario_stale"


@pytest.mark.parametrize(
    "mounts",
    [
        {"attacker_mounts": ["/host:/host"]},
        {"victim_mounts": ["/host:/host:ro"]},
        {"volumes": ["/host:/host"]},
        {"mounts": {"attacker": ["/host:/host"]}},
        {"mounts": {"unexpected": []}},
    ],
)
def test_static_preflight_rejects_mounts(tmp_path, mounts):
    finding_path = make_finding(tmp_path)
    with pytest.raises(contracts.ContractError) as error:
        validate(make_scenario(finding_path, **mounts), finding_path)
    assert error.value.status == "blocked_scenario_invalid"


def test_static_preflight_rejects_unsupported_mode(tmp_path):
    finding_path = make_finding(tmp_path)
    with pytest.raises(contracts.ContractError) as error:
        validate(make_scenario(finding_path, mode="stdio"), finding_path)
    assert error.value.status == "blocked_unsupported_mode"


def test_container_args_enforce_isolation_and_resource_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(lab_module, "RUNS", tmp_path / "runs")
    lab = lab_module.Lab("project", "victim", run_id="run", pids_limit=64, memory="512m", cpus="0.5")
    victim = lab.container_args("victim")
    attacker = lab.container_args("attacker")
    for args in (victim, attacker):
        assert ["--cap-drop", "ALL"] == args[args.index("--cap-drop"):args.index("--cap-drop") + 2]
        assert "no-new-privileges" in args
        assert args[args.index("--pids-limit") + 1] == "64"
        assert args[args.index("--memory") + 1] == "512m"
        assert args[args.index("--cpus") + 1] == "0.5"
    assert any("/flag:ro" in arg for arg in victim)
    assert not any("/flag" in arg for arg in attacker)


def make_captured_run(tmp_path, monkeypatch):
    monkeypatch.setattr(lab_module, "RUNS", tmp_path / "runs")
    lab = lab_module.Lab("project", "victim", run_id="run")
    lab.flag = "FLAG{real-tool-output}"
    lab.flag_sha256 = hashlib.sha256(lab.flag.encode()).hexdigest()
    lab.run_dir.mkdir(parents=True)
    lab.flag_file.write_text(lab.flag + "\n", encoding="utf-8")
    lab.trace_file.write_text("", encoding="utf-8")
    assert lab.capture_answer(lab.flag) is None
    assert lab.capture_from_tool(lab.flag) is None

    def fake_exec(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=lab.flag + "\n", stderr="")

    monkeypatch.setattr(lab_module.subprocess, "run", fake_exec)
    _, output = lab.exec("fixture request")
    provenance = lab.capture_from_tool(output)
    assert provenance is not None
    document = lab.finish({
        "status": "flag_captured",
        "captured": True,
        "answer": lab.flag,
        "flag_provenance": provenance,
    })
    (lab.run_dir / "finding.json").write_text(json.dumps({"id": "F-1", "title": "fixture"}), encoding="utf-8")
    (lab.run_dir / "agent.jsonl").write_text("", encoding="utf-8")
    return lab, document


def test_flag_capture_requires_real_tool_output_and_hashes(tmp_path, monkeypatch):
    lab, document = make_captured_run(tmp_path, monkeypatch)
    verified = contracts.recompute_flag_provenance(lab.run_dir, document)
    assert verified["verified"] is True
    assert verified["source"] == "tool_output"
    assert verified["flag_sha256"] == hashlib.sha256(lab.flag.encode()).hexdigest()
    trace = [json.loads(line) for line in lab.trace_file.read_text().splitlines()]
    tool = next(record for record in trace if record["kind"] == "tool_result")
    assert tool["output_sha256"] == hashlib.sha256(tool["output"].encode()).hexdigest()


@pytest.mark.parametrize("rc,status", [(2, "not_captured"), (4, "model_timeout"), (5, "lab_unhealthy")])
def test_agent_failure_classification(rc, status):
    assert contracts.classify_agent_failure(rc) == status


def test_agent_timeout_is_distinct():
    assert contracts.classify_agent_failure(0, timed_out=True) == "agent_timeout"


@pytest.mark.parametrize("mutation", ["missing", "string_bool", "false_bool"])
def test_approved_verdict_requires_complete_typed_true_schema(mutation):
    verdict = approved_verdict()
    if mutation == "missing":
        del verdict["no_cheat"]
    elif mutation == "string_bool":
        verdict["no_cheat"] = "true"
    else:
        verdict["minimal"] = False
    with pytest.raises(contracts.ContractError) as error:
        contracts.validate_verdict(verdict)
    assert error.value.status == "judge_schema_invalid"


def invoke_judge(tmp_path, monkeypatch, verdict):
    lab, _ = make_captured_run(tmp_path, monkeypatch)
    monkeypatch.setattr(judge, "ROOT", tmp_path / "judge-root")
    monkeypatch.setattr(judge, "language_directive", lambda: "")
    commands = []

    def fake_judge(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps(verdict), stderr="")

    monkeypatch.setattr(judge.subprocess, "run", fake_judge)
    monkeypatch.setattr(sys, "argv", ["judge.py", "--run-dir", str(lab.run_dir)])
    return judge.main(), commands


def test_judge_approved_writes_validation_only_after_provenance(tmp_path, monkeypatch, capsys):
    returncode, commands = invoke_judge(tmp_path, monkeypatch, approved_verdict())
    assert returncode == 0
    assert "--permission-mode=default" in commands[0]
    assert not any("bypassPermissions" in arg for arg in commands[0])
    records = (tmp_path / "judge-root" / "rsi" / "trajectories" / "validation.jsonl").read_text().splitlines()
    assert len(records) == 1
    assert json.loads(records[0])["flag_provenance"]["verified"] is True
    capsys.readouterr()


def test_judge_string_boolean_cannot_write_validation(tmp_path, monkeypatch, capsys):
    verdict = approved_verdict()
    verdict["no_cheat"] = "true"
    returncode, _ = invoke_judge(tmp_path, monkeypatch, verdict)
    assert returncode == 2
    assert not (tmp_path / "judge-root" / "rsi" / "trajectories" / "validation.jsonl").exists()
    capsys.readouterr()


def test_batch_marks_builder_failure_and_uses_finite_timeout(tmp_path, monkeypatch, capsys):
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps({"candidates": [{"project": "project", "id": "F-1"}]}), encoding="utf-8")
    monkeypatch.setattr(batch, "ROOT", tmp_path)
    monkeypatch.setattr(batch, "BATCH_ROOT", tmp_path / "batches")
    occurrence_id = "project/r1/F-1"
    semantic_id = "sem_fixture"
    ledger = {
        "occurrences": {occurrence_id: {"occurrence_id": occurrence_id}},
        "findings": {semantic_id: {"occurrence_ids": [occurrence_id]}},
        "indexes": {"legacy_to_semantics": {"project:F-1": [semantic_id]}},
    }
    monkeypatch.setattr(batch.base.finding_ledger, "build_ledger", lambda: ledger)
    monkeypatch.setattr(batch.base, "latest_findings", lambda _ledger: {
        occurrence_id: {"raw": {"id": "F-1", "title": "fixture"}}
    })
    calls = []

    def fake_builder(command, **kwargs):
        calls.append(kwargs["timeout"])
        return SimpleNamespace(returncode=1, stdout="", stderr="failed")

    monkeypatch.setattr(batch.subprocess, "run", fake_builder)
    monkeypatch.setattr(sys, "argv", [
        "batch.py", "--candidates", str(candidates), "--build-timeout", "7"
    ])
    assert batch.main() == 0
    assert calls == [7]
    summary_path = next((tmp_path / "batches").glob("*/summary.json"))
    result = json.loads(summary_path.read_text())["results"][0]
    assert result["status"] == "build_failed"
    capsys.readouterr()


def fake_builder_script(tmp_path):
    script = tmp_path / "fake-builder"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, re, sys\n"
        "prompt = sys.argv[-1]\n"
        "task_path = pathlib.Path(re.search(r'Read (\\S+) and follow', prompt).group(1))\n"
        "task = json.loads(task_path.read_text())\n"
        "scenario = {\n"
        " 'schema_version': 1, 'finding_id': task['finding_id'],\n"
        " 'finding_sha256': task['finding_sha256'], 'source': task['source_binding'],\n"
        " 'mode': os.environ.get('FAKE_SCENARIO_MODE', 'http'), 'victim_image': 'fixture/victim',\n"
        " 'attacker_image': 'fixture/attacker', 'launch': {'command': []},\n"
        " 'target_url': 'http://victim:8000', 'health': {'path': '/health'}\n"
        "}\n"
        "pathlib.Path(task['scenario_out']).write_text(json.dumps(scenario))\n"
        "sys.exit(int(os.environ.get('FAKE_BUILD_RC', '0')))\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


@pytest.mark.parametrize(
    "builder_rc,mode,expected_rc,status,valid",
    [(0, "http", 0, "built", True), (1, "http", 2, "build_failed", False),
     (0, "stdio", 2, "build_failed", False)],
)
def test_build_requires_exit_zero_and_structural_validation(
    tmp_path, builder_rc, mode, expected_rc, status, valid
):
    finding = make_finding(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "service.py").write_text("print('fixture')\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "redteam" / "build_lab.py"),
            "--project", "project", "--finding", str(finding), "--source", str(source),
            "--lab-dir", str(tmp_path / "lab"), "--claude", str(fake_builder_script(tmp_path)),
            "--timeout", "10",
        ],
        capture_output=True, text=True, timeout=20,
        env={**os.environ, "FAKE_BUILD_RC": str(builder_rc), "FAKE_SCENARIO_MODE": mode},
    )
    assert completed.returncode == expected_rc, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == status
    assert result["scenario_valid"] is valid
    assert result["finding_sha256"] == hashlib.sha256(finding.read_bytes()).hexdigest()
    assert result["source_binding"] == {"content_sha256": build_lab.hash_source(source)}


def test_builder_defaults_to_per_finding_lab_directory(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    finding = make_finding(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr(build_lab, "ROOT", root)
    monkeypatch.setattr(build_lab, "source_binding", lambda *_: {"content_sha256": "a" * 64})
    args = SimpleNamespace(
        finding=str(finding), project="project", lab_dir="", source=str(source), dry_run=True
    )
    assert build_lab.run(args) == 0
    task_path = root / "labs" / "project" / "F-1" / "lab-task.json"
    task = json.loads(task_path.read_text())
    assert task["scenario_out"] == str(task_path.parent / "scenario.json")
    assert task["finding_sha256"] == hashlib.sha256(finding.read_bytes()).hexdigest()
    capsys.readouterr()
