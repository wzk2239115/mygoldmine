import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/redteam'))
import batch


@pytest.mark.parametrize('jobs', [1, 3, 10])
def test_main_flow_builds_candidates_concurrently_before_execution(tmp_path, monkeypatch, jobs):
    monkeypatch.setattr(batch, 'ROOT', tmp_path)
    out = tmp_path / 'output'
    out.mkdir()
    candidates = [{'project': 'demo', 'id': f'F-{i}', 'run_id': 'one'} for i in range(12)]
    snapshot = {'project': 'demo', 'run_id': 'one', 'items': {
        item['id']: {'raw': {'id': item['id'], 'severity': 'high'}} for item in candidates}}
    state = {'active': 0, 'peak': 0}
    lock = threading.Lock()

    def invoke(command, **kwargs):
        assert '--build-only' in command
        with lock:
            state['active'] += 1
            state['peak'] = max(state['peak'], state['active'])
        time.sleep(.12)
        lab = Path(command[command.index('--lab-dir') + 1])
        finding = json.loads(Path(command[command.index('--finding') + 1]).read_text())
        scenario = lab / 'scenario.json'
        scenario.write_text(json.dumps({'finding_id': finding['id']}))
        with lock:
            state['active'] -= 1
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            'scenario_valid': True, 'finding_id': finding['id'], 'scenario': str(scenario)}), stderr='')

    monkeypatch.setattr(batch.subprocess, 'run', invoke)
    args = SimpleNamespace(build_jobs=jobs, model='fixture', build_timeout=30)
    monkeypatch.setattr(batch, 'resolve_candidate', lambda candidate, *_: snapshot['items'][candidate['id']])
    results = batch.build_parallel(candidates, {}, None, out, args)
    assert state == {'active': 0, 'peak': jobs}
    assert list(results) == [f"demo:{candidate['id']}" for candidate in candidates]
    summary = json.loads((out / 'construction/summary.json').read_text())
    assert summary['processed'] == 12
    assert summary['concurrency'] == jobs
    assert not (tmp_path / 'labs').exists()
    for candidate in candidates:
        task = json.loads((out / 'construction/tasks' / f"demo--{candidate['id']}.json").read_text())
        assert task['state'] == 'completed'
        assert task['status'] == 'built'


def test_main_flow_waits_for_all_builds_then_uses_isolated_scenarios(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr(batch, 'ROOT', tmp_path)
    monkeypatch.setattr(batch, 'BATCH_ROOT', tmp_path / 'batches')
    candidates = [{'project': 'demo', 'id': f'F-{i}'} for i in range(4)]
    file = tmp_path / 'candidates.json'
    file.write_text(json.dumps({'candidates': candidates}))
    monkeypatch.setattr(batch.base.finding_ledger, 'build_ledger', lambda: {})
    monkeypatch.setattr(batch, 'resolve_candidate', lambda candidate, *_: {'raw': {'id': candidate['id']}})
    state = {'active': 0, 'finished': 0, 'agents': 0}
    lock = threading.Lock()

    def invoke(command, **kwargs):
        if command[1].endswith('build_lab.py'):
            with lock:
                state['active'] += 1
            time.sleep(.1)
            lab = Path(command[command.index('--lab-dir') + 1])
            finding = Path(command[command.index('--finding') + 1])
            identifier = json.loads(finding.read_text())['id']
            scenario = lab / 'scenario.json'
            scenario.write_text(json.dumps({'schema_version': 1, 'finding_id': identifier,
                'finding_sha256': hashlib.sha256(finding.read_bytes()).hexdigest(),
                'source': {'commit': 'a' * 40}, 'mode': 'http', 'victim_image': 'fixture:victim',
                'attacker_image': 'fixture:attacker', 'target_url': 'http://victim:8000',
                'health': {'path': '/health'}, 'launch': {'command': []}}))
            with lock:
                state['active'] -= 1
                state['finished'] += 1
            return SimpleNamespace(returncode=0, stdout=json.dumps({'scenario_valid': True,
                'finding_id': identifier, 'scenario': str(scenario)}), stderr='')
        assert command[1].endswith('agent.py')
        assert state['active'] == 0 and state['finished'] == 4
        scenario = Path(command[command.index('--scenario') + 1])
        assert 'construction/labs/demo' in str(scenario)
        state['agents'] += 1
        return SimpleNamespace(returncode=1, stdout='', stderr='fixture failure')

    monkeypatch.setattr(batch.subprocess, 'run', invoke)
    monkeypatch.setattr(sys, 'argv', ['batch.py', '--candidates', str(file), '--build-jobs', '3'])
    assert batch.main() == 0
    assert state == {'active': 0, 'finished': 4, 'agents': 4}


def test_main_flow_runs_agents_and_judges_in_bounded_parallel(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, 'ROOT', tmp_path)
    monkeypatch.setattr(batch, 'BATCH_ROOT', tmp_path / 'batches')
    monkeypatch.setattr(batch, 'record_stage', lambda *args, **kwargs: None)
    candidates = [{'project': 'demo', 'id': f'F-{i}'} for i in range(4)]
    file = tmp_path / 'candidates.json'
    file.write_text(json.dumps({'candidates': candidates}))
    monkeypatch.setattr(batch.base.finding_ledger, 'build_ledger', lambda: {})
    monkeypatch.setattr(batch, 'resolve_candidate', lambda candidate, *_: {'raw': {'id': candidate['id'], 'title': candidate['id']}})
    for candidate in candidates:
        preferred = tmp_path / 'labs' / 'demo' / candidate['id'] / 'scenario.json'
        preferred.parent.mkdir(parents=True)
        preferred.write_text('{}')
    monkeypatch.setattr(batch, 'resolve_scenario', lambda root, project, finding, data: (
        tmp_path / 'labs' / 'demo' / finding['id'] / 'scenario.json', {'mode': 'http'}
    ))
    state = {'agent': 0, 'judge': 0, 'peak_agent': 0, 'peak_judge': 0}
    lock = threading.Lock()

    def invoke(command, **kwargs):
        kind = 'agent' if any('agent.py' in str(item) for item in command) else 'judge'
        with lock:
            state[kind] += 1
            state[f'peak_{kind}'] = max(state[f'peak_{kind}'], state[kind])
        time.sleep(0.1)
        with lock:
            state[kind] -= 1
        return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'flag_captured'}), stderr='')

    monkeypatch.setattr(batch.subprocess, 'run', invoke)
    out = tmp_path / 'out'
    monkeypatch.setattr(sys, 'argv', [
        'batch.py', '--candidates', str(file), '--out-dir', str(out),
        '--no-build-labs', '--agent-jobs', '2', '--judge-jobs', '2',
    ])
    assert batch.main() == 0
    assert state['peak_agent'] == 2
    assert state['peak_judge'] == 2
    summary = json.loads((out / 'summary.json').read_text())
    assert [item['id'] for item in summary['results']] == [item['id'] for item in candidates]
    assert all(item['status'] == 'judge_approved' for item in summary['results'])
