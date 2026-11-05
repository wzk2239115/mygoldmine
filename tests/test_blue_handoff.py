import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/redteam'))
import blue_handoff as handoff
import batch


def write(file, data):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data))


def fixture(tmp_path):
    run = tmp_path / 'runs/demo/one'
    findings = [{'id': f'F-{i}', 'title': f'candidate {i}', 'severity': 'high'} for i in range(1, 5)]
    write(run / 'audit-report.json', {'project': 'demo', 'findings': findings})
    write(tmp_path / 'env/demo/env-manifest.json', {'image': 'test:image', 'image_id': 'sha256:test', 'commit': 'a' * 40})
    root = run / 'verify/agent'
    write(root / 'summary.json', {'project': 'demo', 'status': 'completed'})
    for finding in findings:
        directory = root / finding['id']
        write(directory / 'finding.json', finding)
        write(directory / 'verify-report.json', {'project': 'demo', 'finding_id': finding['id'],
              'verdict': 'confirmed', 'evidence_class': 'runtime', 'image': 'test:image', 'image_id': 'sha256:test', 'evidence': ['proof.txt']})
        (directory / 'verify-report.md').write_text('observed runtime')
        (directory / 'harness').mkdir()
        (directory / 'harness/probe.py').write_text('print("PRIVATE_BLUE_POC")')
        (directory / 'evidence').mkdir()
        (directory / 'evidence/proof.txt').write_text('PRIVATE_BLUE_EVIDENCE')
    return run, findings, root


def test_filters_verdicts_and_incomplete_artifacts_and_copies_snapshot(tmp_path):
    run, findings, root = fixture(tmp_path)
    for identifier, verdict in [('F-2', 'blocked'), ('F-3', 'rejected')]:
        file = root / identifier / 'verify-report.json'
        data = handoff.read(file)
        data['verdict'] = verdict
        write(file, data)
    (root / 'F-4/evidence/proof.txt').unlink()
    selection = handoff.prepare(run, 'demo', tmp_path / 'out')
    assert [item['id'] for item in selection['candidates']] == ['F-1']
    assert len(selection['excluded']) == 3
    packet = selection['candidates'][0]['blue_handoff']
    data = handoff.validate_packet(packet, findings[0], 'demo', {'commit': 'a' * 40})
    assert data['role'] == 'builder_only'
    assert (Path(packet).parent / 'harness/probe.py').read_text() == 'print("PRIVATE_BLUE_POC")'
    (root / 'F-1/evidence/proof.txt').write_text('changed after snapshot')
    assert (Path(packet).parent / 'evidence/proof.txt').read_text() == 'PRIVATE_BLUE_EVIDENCE'
    copied = handoff.copy_packet(packet, tmp_path / 'lab/blue-verification', findings[0], 'demo', {'commit': 'a' * 40})
    assert copied.is_file()
    with pytest.raises(ValueError, match='源码版本'):
        handoff.validate_packet(packet, findings[0], 'demo', {'commit': 'b' * 40})
    (Path(packet).parent / 'harness/probe.py').write_text('tampered')
    with pytest.raises(ValueError, match='被修改'):
        handoff.validate_packet(packet, findings[0], 'demo')


@pytest.mark.parametrize('kind', ['running', 'failed', 'stale_report', 'wrong_identity'])
def test_latest_blue_attempt_never_falls_back_to_original(tmp_path, kind):
    run, _, _ = fixture(tmp_path)
    attempt = Path(str(run) + '.meta/node-retries/verify/latest')
    output = attempt / 'output'
    output.mkdir(parents=True)
    (output / 'audit-report.json').write_bytes((run / 'audit-report.json').read_bytes())
    write(attempt / 'attempt.json', {'id': 'latest', 'project': 'other' if kind == 'wrong_identity' else 'demo',
          'runId': 'one', 'workspace': str(output), 'status': kind if kind in ['running', 'failed'] else 'completed', 'startedAt': '2026-11-05'})
    if kind == 'stale_report':
        write(output / 'audit-report.json', {'findings': []})
    selection, _, _ = handoff.collect(run, 'demo')
    assert selection['candidates'] == []
    assert selection['gate_reason']


@pytest.mark.parametrize('kind', ['static', 'synthesized', 'wrong_image', 'wrong_finding', 'symlink', 'traversal', 'no_harness'])
def test_rejects_stale_or_untrusted_blue_artifacts(tmp_path, kind):
    run, _, root = fixture(tmp_path)
    report_file = root / 'F-1/verify-report.json'
    data = handoff.read(report_file)
    if kind == 'static':
        data['evidence_class'] = 'source-semantic'
    elif kind == 'synthesized':
        data['synthesized'] = True
    elif kind == 'wrong_image':
        data['image_id'] = 'old'
    elif kind == 'wrong_finding':
        write(root / 'F-1/finding.json', {'id': 'F-1', 'title': 'different'})
    elif kind == 'symlink':
        file = root / 'F-1/evidence/proof.txt'
        file.unlink()
        file.symlink_to(root / 'F-2/evidence/proof.txt')
    elif kind == 'traversal':
        data['evidence'] = ['../F-2/evidence/proof.txt']
    elif kind == 'no_harness':
        (root / 'F-1/harness/probe.py').unlink()
    write(report_file, data)
    result, _, _ = handoff.collect(run, 'demo')
    assert 'F-1' not in [item['id'] for item in result['candidates']]
    assert result['excluded'][0]['id'] == 'F-1'


@pytest.mark.parametrize('id_field', ['id', 'finding_id'])
def test_main_flow_passes_blue_packet_only_to_builder_not_attacker(tmp_path, monkeypatch, id_field):
    from types import SimpleNamespace
    run, findings, root = fixture(tmp_path)
    if id_field == 'finding_id':
        for finding in findings:
            finding['finding_id'] = finding.pop('id')
            write(root / finding['finding_id'] / 'finding.json', finding)
        write(run / 'audit-report.json', {'project': 'demo', 'findings': findings})
    selection = handoff.prepare(run, 'demo', tmp_path / 'selection', maximum=1)
    snapshot = {'project': 'demo', 'run_id': 'one', 'sha256': hashlib.sha256((run / 'audit-report.json').read_bytes()).hexdigest(),
                'items': {finding.get('id') or finding['finding_id']: {'raw': finding} for finding in findings}}
    monkeypatch.setattr(batch, 'ROOT', tmp_path)
    monkeypatch.setattr(batch, 'report_snapshot', lambda _: snapshot)
    calls = []

    def invoke(command, **kwargs):
        calls.append(command)
        if command[1].endswith('build_lab.py'):
            assert '--blue-handoff' in command
            folder = Path(command[command.index('--lab-dir') + 1])
            file = Path(command[command.index('--finding') + 1])
            assert 'PRIVATE_BLUE' not in file.read_text() and 'blue_handoff' not in file.read_text()
            scenario = folder / 'scenario.json'
            write(scenario, {'schema_version': 1, 'finding_id': 'F-1', 'finding_sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                  'source': {'commit': 'a' * 40}, 'mode': 'http', 'victim_image': 'fixture:victim', 'attacker_image': 'fixture:attacker',
                  'target_url': 'http://victim:8000', 'health': {'path': '/health'}, 'launch': {'command': []}})
            return SimpleNamespace(returncode=0, stdout=json.dumps({'scenario_valid': True, 'finding_id': 'F-1', 'scenario': str(scenario)}), stderr='')
        assert command[1].endswith('auto_repair.py')
        assert '--blue-handoff' not in command
        finding_file = Path(command[command.index('--finding') + 1])
        assert json.loads(finding_file.read_text()) == findings[0]
        assert all('blue-handoff' not in str(arg) for arg in command)
        return SimpleNamespace(returncode=1, stdout='', stderr='fixture stop')

    monkeypatch.setattr(batch.subprocess, 'run', invoke)
    monkeypatch.setattr(sys, 'argv', ['batch.py', '--report', str(run / 'audit-report.json'), '--candidates', str(tmp_path / 'selection/candidates.json'), '--out-dir', str(tmp_path / 'batch')])
    assert batch.main() == 0
    assert len(calls) == 2
    candidate = selection['candidates'][0]
    candidate.pop('blue_handoff')
    write(tmp_path / 'selection/candidates.json', {'candidates': [candidate]})
    calls.clear()
    assert batch.main() == 0
    assert not calls


def test_builder_receives_own_checked_packet_before_agent_starts(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import build_lab
    run, findings, _ = fixture(tmp_path)
    selection = handoff.prepare(run, 'demo', tmp_path / 'selection', maximum=1)
    finding = tmp_path / 'finding.json'
    write(finding, findings[0])
    source = tmp_path / 'source'
    source.mkdir()
    lab = tmp_path / 'lab'
    monkeypatch.setattr(build_lab, 'ROOT', tmp_path)
    monkeypatch.setattr(build_lab, 'source_binding', lambda *_: {'commit': 'a' * 40})
    monkeypatch.setattr(build_lab, 'language_directive', lambda: '')
    monkeypatch.setattr(build_lab, 'claude_connection', lambda _: ('fixture', {}))
    monkeypatch.setattr(build_lab, 'delivery_config', lambda *_: {})
    monkeypatch.setattr(build_lab, 'layered_skill_instruction', lambda *_: '')
    calls = []

    def invoke(command, **kwargs):
        calls.append(command)
        task = handoff.read(lab / 'lab-task.json')
        assert task['blue_handoff_scope'] == 'builder_only'
        assert task['blue_handoff'] == str(lab / 'blue-verification/handoff.json')
        assert (lab / 'blue-verification/harness/probe.py').is_file()
        assert (lab / 'blue-verification/evidence/proof.txt').read_text() == 'PRIVATE_BLUE_EVIDENCE'
        assert task['blue_handoff'] in command[-1]
        assert '不把验证脚本、载荷或证据复制进攻击者镜像或可见路径' in command[-1]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(build_lab, 'run_session', invoke)
    args = SimpleNamespace(project='demo', finding=str(finding), source=str(source), lab_dir=str(lab),
                           blue_handoff=selection['candidates'][0]['blue_handoff'], dry_run=False,
                           build_only=True, claude='fixture', claude_model='fixture', timeout=60)
    assert build_lab.run(args) == 2  # fake agent writes no valid scenario
    assert len(calls) == 1
    (Path(args.blue_handoff).parent / 'harness/probe.py').write_text('tampered')
    args.lab_dir = str(tmp_path / 'second-lab')
    assert build_lab.run(args) == 2
    assert len(calls) == 1  # invalid packet rejected before agent launch


def test_non_git_source_uses_same_content_binding_as_builder(tmp_path):
    import build_lab
    run, _, _ = fixture(tmp_path)
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'library.py').write_text('print(1)')
    file = tmp_path / 'env/demo/env-manifest.json'
    manifest = handoff.read(file)
    manifest.pop('commit')
    manifest['source'] = str(source)
    write(file, manifest)
    result, _, _ = handoff.collect(run, 'demo')
    assert result['source'] == build_lab.source_binding(source, file)
    assert result['selected'] == 4


def test_reused_scenario_with_different_source_does_not_reach_attacker(tmp_path, monkeypatch):
    run, findings, _ = fixture(tmp_path)
    handoff.prepare(run, 'demo', tmp_path / 'selection', maximum=1)
    snapshot = {'project': 'demo', 'run_id': 'one', 'sha256': hashlib.sha256((run / 'audit-report.json').read_bytes()).hexdigest(),
                'items': {finding.get('id') or finding['finding_id']: {'raw': finding} for finding in findings}}
    finding_bytes = (json.dumps(findings[0], ensure_ascii=False, indent=2) + '\n').encode()
    write(tmp_path / 'labs/demo/F-1/scenario.json', {
        'schema_version': 1, 'finding_id': 'F-1', 'finding_sha256': hashlib.sha256(finding_bytes).hexdigest(),
        'source': {'commit': 'b' * 40}, 'mode': 'http', 'victim_image': 'fixture:victim', 'attacker_image': 'fixture:attacker',
        'target_url': 'http://victim:8000', 'health': {'path': '/health'}, 'launch': {'command': []},
    })
    monkeypatch.setattr(batch, 'ROOT', tmp_path)
    monkeypatch.setattr(batch, 'report_snapshot', lambda _: snapshot)
    monkeypatch.setattr(batch.subprocess, 'run', lambda *_args, **_kwargs: pytest.fail('must not launch attacker or builder'))
    monkeypatch.setattr(sys, 'argv', ['batch.py', '--report', str(run / 'audit-report.json'), '--candidates', str(tmp_path / 'selection/candidates.json'), '--out-dir', str(tmp_path / 'batch')])
    assert batch.main() == 0
    summary = handoff.read(tmp_path / 'batch/summary.json')
    assert summary['results'][0]['status'] == 'blocked_scenario_stale'

def test_all_candidates_have_a_destination_and_refresh_adds_new_confirmations(tmp_path):
    run, findings, root = fixture(tmp_path)
    findings[3]["severity"] = "low"
    write(run/"audit-report.json", {"project":"demo","findings":findings})
    write(root/"F-4/finding.json", findings[3])
    write(run/"redteam/candidates.json", {"candidates":[{"id":"F-1","project":"demo","run_id":"one"}]})
    selection, _, _ = handoff.collect(run, "demo", maximum=1)
    assert selection["accounted"] == len(findings)
    assert {row["id"] for row in selection["deferred"]} == {"F-4"}
    updated, _, _ = handoff.collect(run, "demo", maximum=10, reuse=True, refresh=True,
                                    severities=("critical","high","medium","low","info"))
    assert {row["id"] for row in updated["candidates"]} == {"F-1","F-2","F-3","F-4"}


def test_stale_blue_selection_cannot_transfer_old_verdict(tmp_path):
    run, _, root = fixture(tmp_path)
    write(root/"selection.json", {"report_sha256":"outdated"})
    selection, _, _ = handoff.collect(run, "demo")
    assert selection["selected"] == 0
    assert "过期" in selection["gate_reason"]

def test_autonomous_handoff_does_not_truncate_confirmed_candidates(tmp_path):
    run, findings, _ = fixture(tmp_path)
    selection, _, _ = handoff.collect(run,"demo",maximum=1,drain=True)
    assert selection["selected"] == len(findings)
    assert selection["accounted"] == len(findings)
