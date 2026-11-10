import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/stages/submission.py'
spec = importlib.util.spec_from_file_location('delivery', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reject_repair_resubmit_preserves_attempts(tmp_path):
    report = tmp_path / 'audit-report.json'
    args = {'artifact':str(report), 'summary':'报告交付', 'limitations':['未动态验证']}
    report.write_text(json.dumps({'findings':[{'id':'F-1','title':'测试问题','severity':'high'}]}))
    rejected = module.submit('orchestrator', tmp_path, args)
    assert rejected['decision'] == 'needs_revision'
    assert rejected['errors'][0]['report_quality']['incomplete'] == 1
    report.write_text(json.dumps({'findings':[]}))
    accepted = module.submit('orchestrator', tmp_path, args)
    assert accepted['decision'] == 'accepted'
    assert accepted['sha256'] != rejected['sha256']
    assert len(list((tmp_path / '.stage-submissions/orchestrator').glob('*.json'))) == 2


def test_path_escape_and_symlink_rejected(tmp_path):
    output = tmp_path / 'output';output.mkdir()
    outside = tmp_path / 'outside.json';outside.write_text('{"findings":[]}')
    link = output / 'report.json';link.symlink_to(outside)
    result = module.submit('orchestrator', output, {'artifact':str(link),'summary':'提交','limitations':[]})
    assert result['decision'] == 'needs_revision'


def test_mcp_initialize_discovery_and_call(tmp_path):
    artifact = tmp_path / 'report.json';artifact.write_text('{"findings":[]}')
    messages = [
        {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
        {'jsonrpc':'2.0','id':2,'method':'tools/list'},
        {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'submit_stage_result','arguments':{'artifact':str(artifact),'summary':'未发现候选','limitations':[]}}},
    ]
    result = subprocess.run([sys.executable,str(SCRIPT),'serve','--stage','orchestrator','--root',str(tmp_path)],input='\n'.join(map(json.dumps,messages))+'\n',text=True,capture_output=True,check=True)
    rows = list(map(json.loads,result.stdout.splitlines()))
    assert len(rows) == 3
    assert {tool['name'] for tool in rows[1]['result']['tools']} == {'submit_audit_report', 'submit_stage_result', 'propose_skill_update'}
    receipt = json.loads(rows[2]['result']['content'][0]['text'])
    assert receipt['decision'] == 'accepted'
    assert receipt['validation_scope'] == 'artifact_contract'


def test_mcp_proposal_is_scoped_and_queued_not_published(tmp_path):
    root=tmp_path/'runs/verl/one';root.mkdir(parents=True)
    evidence=root/'receipt.json';evidence.write_text('{"decision":"needs_revision"}')
    messages=[{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'propose_skill_update','arguments':{'scope':'project','target_stage':'verify','content':'先读取实际失败原因再修正','evidence':[str(evidence)]}}}]
    def invoke(stage):
        result=subprocess.run([sys.executable,str(SCRIPT),'serve','--stage',stage,'--root',str(root)],input='\n'.join(map(json.dumps,messages))+'\n',text=True,capture_output=True,check=True)
        return json.loads(result.stdout)
    assert 'error' in invoke('visual')
    assert not (root/'.stage-skill-proposals').exists()
    accepted=invoke('learner')
    payload=json.loads(accepted['result']['content'][0]['text'])
    assert payload['status']=='queued_candidate'
    assert len(list((root/'.stage-skill-proposals').glob('*.json')))==1

def test_orchestrator_identity_returns_revision_before_acceptance(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'infer_project', lambda root: 'codex')
    report = tmp_path / 'audit-report.json'
    args = {'artifact': str(report), 'summary': '交付', 'limitations': []}
    report.write_text(json.dumps({'project': 'OpenAI Codex', 'findings': []}))
    result = module.submit('orchestrator', tmp_path, args)
    assert result['decision'] == 'needs_revision'
    assert 'codex' in str(result['errors'])
    report.write_text(json.dumps({'project': 'codex', 'project_name': 'OpenAI Codex', 'findings': []}))
    assert module.submit('orchestrator', tmp_path, args)['decision'] == 'accepted'


def test_orchestrator_finalization_revalidates_all_declared_attachments(tmp_path):
    report = tmp_path / 'audit-report.json'
    report.write_text('{"findings":[]}')
    attachment = tmp_path / 'notes.md'
    attachment.write_text('first')
    args = {'artifact': str(report), 'artifacts': [str(attachment)],
            'summary': '交付', 'limitations': []}
    assert module.submit('orchestrator', tmp_path, args)['decision'] == 'accepted'
    attachment.write_text('final')
    result = module.finalize_orchestrator(tmp_path)
    assert result['revalidated'] is True
    assert len(list((tmp_path / '.stage-submissions/orchestrator').glob('*.json'))) == 2
    assert str(attachment) in {f['path'] for f in result['deliveries'][0]['files']}
    assert module.finalize_orchestrator(tmp_path).get('revalidated') is None


def test_orchestrator_finalization_never_drops_missing_dependencies(tmp_path):
    import pytest
    report = tmp_path / 'audit-report.json'
    report.write_text('{"findings":[]}')
    attachment = tmp_path / 'notes.md'
    attachment.write_text('first')
    module.submit('orchestrator', tmp_path, {
        'artifact': str(report), 'artifacts': [str(attachment)],
        'summary': '交付', 'limitations': [],
    })
    attachment.unlink()
    with pytest.raises(ValueError):
        module.finalize_orchestrator(tmp_path)


def test_orchestrator_finalization_rejects_changed_report_and_invalid_ledger(tmp_path):
    import pytest
    report = tmp_path / 'audit-report.json'
    report.write_text('{"findings":[]}')
    ledger = tmp_path / 'coverage-ledger.json'
    ledger.write_text(json.dumps({
        'schema_version': 1, 'project': 'demo', 'source_version': 'abc',
        'limitations': [], 'entries': [{'id': 'COV-1', 'area': 'audit', 'view': 'review',
        'hypothesis': '复核', 'status': 'unchecked', 'next_action': '继续核对'}]}))
    module.submit('orchestrator', tmp_path, {
        'artifact': str(report), 'artifacts': [str(ledger)],
        'summary': '交付', 'limitations': [],
    })
    ledger.write_text('{"entries":[]}')
    with pytest.raises(ValueError, match='覆盖记录'):
        module.finalize_orchestrator(tmp_path)
    report.write_text('{"findings":[], "changed":true}')
    with pytest.raises(ValueError):
        module.finalize_orchestrator(tmp_path)


def test_orchestrator_rejects_all_invalid_ledger_copies_before_acceptance(tmp_path):
    report = tmp_path / 'audit-report.json'
    report.write_text('{"findings":[]}')
    paths = [tmp_path / 'findings/coverage-ledger.json',
             tmp_path / 'task-artifacts/coverage-ledger.json']
    ledger = {
        'schema_version': 1, 'project': 'demo', 'source_version': 'abc',
        'limitations': [], 'entries': [{
            'id': 'COV-1', 'area': 'merge', 'view': 'dedupe-calibration',
            'hypothesis': '复核重复候选', 'status': 'unchecked',
            'next_action': '核对证据'
        }]
    }
    for file in paths:
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps(ledger))
    args = {'artifact': str(report), 'artifacts': [str(paths[0])],
            'summary': '提交', 'limitations': []}
    rejected = module.submit('orchestrator', tmp_path, args)
    assert rejected['decision'] == 'needs_revision'
    assert {row['artifact'] for row in rejected['errors']} == {str(p) for p in paths}
    assert all('review' in row['allowed_views'] for row in rejected['errors'])
    ledger['entries'][0]['view'] = 'review'
    paths[1].write_text(json.dumps(ledger))
    again = module.submit('orchestrator', tmp_path, args)
    assert again['decision'] == 'needs_revision'
    assert again['errors'][0]['artifact'] == str(paths[0])
    paths[0].write_text(json.dumps(ledger))
    assert module.submit('orchestrator', tmp_path, args)['decision'] == 'accepted'
