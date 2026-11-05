import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/redteam'))
sys.path.insert(0, str(ROOT / 'scripts/stages'))
import build_lab
from skill_bank import SkillBank


def test_build_only_keeps_contract_and_passes_stop_boundary_to_skill(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    finding = tmp_path / 'finding.json'
    finding.write_text(json.dumps({'id': 'F-1'}))
    lab = tmp_path / 'retry/labs/F-1'
    binding = {'commit': 'a' * 40}
    monkeypatch.setattr(build_lab, 'ROOT', tmp_path)
    monkeypatch.setattr(build_lab, 'language_directive', lambda: '')
    monkeypatch.setattr(build_lab, 'source_binding', lambda *_: binding)
    monkeypatch.setattr(build_lab, 'claude_connection', lambda _: ('fixture', {}))
    monkeypatch.setattr(build_lab, 'delivery_config', lambda *_: {})
    monkeypatch.setattr(build_lab, 'layered_skill_instruction', lambda *_: '')
    monkeypatch.setattr(build_lab, 'images_available', lambda _: True)

    def invoke(command, **kwargs):
        assert command[command.index('--agent') + 1] == 'redteam-lab-builder'
        assert '不要运行红队 agent.py 或 judge.py' in command[-1]
        assert '指定的 lab_dir' in command[-1]
        task = json.loads((lab / 'lab-task.json').read_text())
        assert task['build_only'] is True
        (lab / 'scenario.json').write_text(json.dumps({
            'schema_version': 1, 'finding_id': 'F-1',
            'finding_sha256': hashlib.sha256(finding.read_bytes()).hexdigest(),
            'source': binding, 'mode': 'http', 'victim_image': 'fixture:victim',
            'attacker_image': 'fixture:attacker', 'target_url': 'http://victim:8000',
            'health': {'path': '/health'}, 'launch': {'command': []},
        }))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(build_lab, 'run_session', invoke)
    args = SimpleNamespace(project='demo', finding=str(finding), source=str(source), lab_dir=str(lab),
                           dry_run=False, build_only=True, claude='claude', claude_model='fixture', timeout=60)
    assert build_lab.run(args) == 0
    assert not (tmp_path / 'labs').exists()


def test_skill_feedback_reads_latest_lab_retry_and_keeps_partial_status(tmp_path):
    run = tmp_path / 'runs/demo/one'
    run.mkdir(parents=True)
    attempt = Path(str(run) + '.meta') / 'node-retries/redteam-lab/one'
    workspace = attempt / 'output'
    (workspace / 'redteam').mkdir(parents=True)
    (workspace / 'redteam/summary.json').write_text(json.dumps({
        'status': 'degraded', 'counts': {'built': 1, 'blocked': 1},
        'results': [{'status': 'built'}, {'status': 'build_failed'}],
    }))
    (attempt / 'attempt.json').write_text(json.dumps({
        'workspace': str(workspace), 'root': str(attempt), 'status': 'completed',
        'resultStatus': 'degraded', 'startedAt': '2026-11-04T01:00:00Z',
    }))
    records = SkillBank(tmp_path).feedback(run, 'demo')
    row = next(item for item in records if item['stage'] == 'redteam-lab')
    assert row['state'] == 'degraded'
    assert row['counts'] == {'built': 1, 'blocked': 1}
    assert any('node-retries/redteam-lab' in item['path'] for item in row['evidence'])
