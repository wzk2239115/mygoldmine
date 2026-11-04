import json
import os
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/stages'))
from skill_bank import SkillBank, spool_proposal, ingest_requests, write
from learning_cycle import cycle


def fixture(tmp_path,scope='project'):
    repo=tmp_path/'repo';repo.mkdir();bank=SkillBank(repo)
    evidence=repo/'proof.txt';evidence.write_text('实际验收记录')
    candidate=bank.propose('environment','verl',scope,'复用已通过验收的镜像',[str(evidence)])
    program=repo/'evaluate.py'
    program.write_text('import os,json\nfrom pathlib import Path\np=Path(os.environ["STAGE_EVAL_OUTPUT"])\np.write_text(json.dumps({"valid":True,"quality":2 if os.environ.get("STAGE_SKILL_OVERRIDE") else 1,"errors":0}))\n')
    suite=repo/'config/stage-evals/environment.json'
    write(suite,{'stage':'environment','metrics':{'quality':'higher','errors':'lower'},'cases':[{'id':'case-1','project':'verl','argv':[sys.executable,str(program)]}]})
    return repo,bank,candidate,suite


def test_candidate_not_loaded_until_evaluated_and_rollback(tmp_path):
    repo,bank,candidate,suite=fixture(tmp_path)
    assert not bank.render('environment','verl')['versions']
    evaluation=bank.evaluate(candidate['id'],suite)
    assert evaluation['decision']=='accepted'
    bank.publish(evaluation['id'])
    assert bank.render('environment','verl')['versions'][0]['id']==candidate['id']
    assert not bank.render('environment','other')['versions']
    assert not bank.render('verify','verl')['versions']
    publication=next((bank.root/'publications').glob('*.json')).stem
    bank.rollback(publication)
    assert not bank.render('environment','verl')['versions']


def test_general_requires_two_independent_other_repositories(tmp_path):
    repo,bank,candidate,suite=fixture(tmp_path,'general')
    assert bank.evaluate(candidate['id'],suite)['decision']=='rejected'
    data=json.loads(suite.read_text());base=data['cases'][0]
    data['cases']=[dict(base,id='heldout-1',project='sglang'),dict(base,id='heldout-2',project='codex')]
    write(suite,data)
    result=bank.evaluate(candidate['id'],suite);assert result['decision']=='accepted'
    bank.publish(result['id'])
    assert bank.render('environment','new-project')['versions']


def test_non_regression_missing_metrics_and_stale_publication(tmp_path):
    repo,bank,candidate,suite=fixture(tmp_path)
    data=json.loads(suite.read_text());data['metrics']['quality']='lower';write(suite,data)
    assert bank.evaluate(candidate['id'],suite)['decision']=='rejected'
    data['metrics']={'missing':'higher'};write(suite,data)
    assert bank.evaluate(candidate['id'],suite)['decision']=='rejected'
    data['metrics']={'quality':'higher'};write(suite,data)
    result=bank.evaluate(candidate['id'],suite)
    write(bank.root/'active.json',{'other':'new-version'})
    with pytest.raises(ValueError,match='变化'):bank.publish(result['id'])


def test_readonly_producer_spools_and_host_imports_once(tmp_path):
    repo=tmp_path/'repo';run=repo/'runs/verl/one';run.mkdir(parents=True)
    proof=run/'receipt.json';proof.write_text('{"decision":"needs_revision"}')
    request=spool_proposal('orchestrator',run,'project','报告交付前先检查字段',[str(proof)])
    proof.write_text('后续原始文件改变，不得改变提炼依据')
    bank=SkillBank(repo);result=ingest_requests(bank,run,'verl')
    assert len(result)==1
    candidate=bank.candidate(result[0]);snapshot=repo/candidate['evidence'][0]['path']
    assert 'needs_revision' in snapshot.read_text()
    assert ingest_requests(bank,run,'verl')==[]
    assert not bank.active()
    assert request['project']=='verl'


def test_suite_cannot_execute_from_candidate_directory(tmp_path):
    repo,bank,candidate,suite=fixture(tmp_path)
    outside=repo/'rsi/eval.json';write(outside,json.loads(suite.read_text()))
    with pytest.raises(ValueError,match='管理员'):bank.evaluate(candidate['id'],outside)


def test_cycle_stops_without_claiming_improvement(tmp_path):
    repo=tmp_path/'repo';source=repo/'targets/verl';source.mkdir(parents=True)
    (repo/'run.sh').write_text('''while [ "$1" != "--run-dir" ]; do shift; done
shift
mkdir -p "$1.meta"
printf '{"state":"failed"}' > "$1.meta/status.json"
''')
    state=cycle(source,'verl',rounds=5,patience=2,repo=repo,poll=0)
    assert state['status']=='no_improvement'
    assert len(state['rounds'])==2
    assert not any(row['published'] for row in state['rounds'])


def test_conditions_and_baseline_are_respected(tmp_path,monkeypatch):
    repo,bank,candidate,suite=fixture(tmp_path)
    other=bank.propose('environment','verl','project','只适用于特定平台',[str(repo/'proof.txt')],{'machine':'different-machine'})
    write(bank.root/'active.json',{other['key']:other['id']})
    assert not bank.render('environment','verl')['versions']
    baseline=repo/'saved-baseline.json';write(baseline,{candidate['key']:candidate['id']})
    monkeypatch.setenv('STAGE_SKILL_BASELINE',str(baseline))
    assert bank.render('environment','verl')['versions'][0]['id']==candidate['id']
    monkeypatch.setenv('STAGE_SKILL_OVERRIDE','')


def test_candidate_tampering_rejected(tmp_path):
    repo,bank,candidate,suite=fixture(tmp_path)
    file=bank.root/'candidates'/f"{candidate['id']}.json"
    altered=json.loads(file.read_text());altered['content']='篡改规则';write(file,altered)
    with pytest.raises(ValueError,match='摘要'):bank.candidate(candidate['id'])


def test_feedback_preserves_blocked_stage_despite_successful_run(tmp_path):
    repo=tmp_path/'repo';run=repo/'runs/verl/one';run.mkdir(parents=True)
    write(Path(str(run)+'.meta')/'status.json',{'state':'success','project':'verl'})
    write(run/'verify/agent/summary.json',{'status':'completed','counts':{'blocked':4}})
    bank=SkillBank(repo);records=bank.feedback(run,'verl')
    verify=next(row for row in records if row['stage']=='verify')
    assert verify['state']=='blocked'
    assert verify['run_state']=='success'
    assert next(row for row in records if row['stage']=='visual')['evidence_status']=='missing'


def test_advance_publishes_only_after_real_runner_and_skips_nested_evaluation(tmp_path,monkeypatch):
    repo,bank,candidate,suite=fixture(tmp_path)
    monkeypatch.setenv('STAGE_SKILL_EVALUATING','1')
    assert not bank.advance('verl')['published']
    monkeypatch.delenv('STAGE_SKILL_EVALUATING')
    suite_data=json.loads(suite.read_text())
    suite.unlink()
    assert bank.advance('verl')['results'][0]['status']=='missing_evaluation_suite'
    assert not bank.active()
    write(suite,suite_data)
    assert bank.advance('verl')['published']==[candidate['id']]


def test_same_rule_and_evidence_bytes_do_not_duplicate_across_output_paths(tmp_path):
    repo,bank,candidate,suite=fixture(tmp_path)
    evidence=repo/'same-proof-new-location.txt';evidence.write_bytes((repo/'proof.txt').read_bytes())
    duplicate=bank.propose('environment','verl','project',candidate['content'],[str(evidence)])
    assert duplicate['id']==candidate['id']
    assert len(list((bank.root/'candidates').glob('*.json')))==1
