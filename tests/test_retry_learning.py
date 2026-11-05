import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/stages'))
import retry_learning as module
from skill_bank import SkillBank, write, read


def test_retry_freezes_latest_feedback_and_limits_publication(tmp_path, monkeypatch):
    repo = tmp_path
    source = repo/'runs/demo/one'
    output = repo/'runs/demo/one.meta/node-retries/learner/new/output'
    write(source/'audit-report.json', {'findings': []})
    for stage, artifact in [('redteam-agent','redteam/summary.json'),('judge','judge/summary.json')]:
        root = Path(str(source)+'.meta')/'node-retries'/stage/'latest'
        write(root/'attempt.json', {'workspace': str(root/'output'), 'root': str(root), 'startedAt': '2026-11-05'})
        write(root/'output'/artifact, {'status': 'completed', 'results': [{'id': 'F-1', 'status': 'judge_approved'}]})
    monkeypatch.setattr(module, 'ROOT', repo)
    calls = []
    def learn(run, project, **kwargs):
        records = SkillBank(repo).feedback(run, project)
        assert len(records) == 7
        for stage in ['redteam-agent', 'judge']:
            record = next(row for row in records if row['stage'] == stage)
            assert record['state'] == 'completed'
            assert record['evidence']
            assert all((repo/ref['path']).is_relative_to(output) for ref in record['evidence'])
        write(repo/'rsi/stage-skills/candidates/new.json', {'id': 'new'})
        return {'exit_code': 0, 'skillopt': {'results': []}}
    monkeypatch.setattr(module, 'learn', learn)
    monkeypatch.setattr(SkillBank, 'advance', lambda self, project, candidate_ids=None: calls.append(candidate_ids) or {'status': 'no_verified_improvement', 'published': [], 'results': []})
    assert module.retry_learning(source, output, 'demo')['status'] == 'completed'
    assert calls == [{'new'}]
    assert read(output/'rsi/feedback-snapshot.json')['source_run'] == str(source)
