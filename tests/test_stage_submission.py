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
    assert rows[1]['result']['tools'][0]['name'] == 'submit_stage_result'
    receipt = json.loads(rows[2]['result']['content'][0]['text'])
    assert receipt['decision'] == 'accepted'
    assert receipt['validation_scope'] == 'artifact_contract'
