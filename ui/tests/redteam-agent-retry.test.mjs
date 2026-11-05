import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {startNodeRetry,nodeAttempts,retryEligibility} from '../server/node-retries.mjs';
import {agentCandidates} from '../server/redteam-agent-retry.mjs';
import {listAgenticTraces} from '../server/agentic-traces.mjs';
import {buildAgenticPipeline} from '../server/agentic-pipeline.mjs';

const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value));};

function fixture(t) {
  const repoRoot=fs.mkdtempSync(path.join(os.tmpdir(),'agent-retry-'));
  t.after(()=>fs.rmSync(repoRoot,{recursive:true,force:true}));
  const runDir=path.join(repoRoot,'runs/demo/one');
  const run={runDir,project:'demo',runId:'one',isLive:false};
  const findings=['F-1','F-2'].map(id=>({id,title:`候选 ${id}`,severity:'high'}));
  write(path.join(runDir,'audit-report.json'),{findings});
  write(`${runDir}.meta/status.json`,{target:path.join(repoRoot,'source'),env_image:'fixture:test'});
  write(path.join(runDir,'redteam/candidates.json'),{candidates:findings.map(item=>({id:item.id,project:'demo',run_id:'one'}))});
  const results=[];
  for(const finding of findings) {
    const findingFile=path.join(runDir,'redteam/batch',`01-demo-${finding.id}.json`);
    write(findingFile,finding);
    const scenario=path.join(repoRoot,'labs/demo',finding.id,'scenario.json');
    write(scenario,{finding_id:finding.id});
    results.push({id:finding.id,status:'built',finding:findingFile,scenario});
  }
  write(path.join(runDir,'redteam/summary.json'),{results});
  const script=path.join(repoRoot,'scripts/redteam/agent.py');
  fs.mkdirSync(path.dirname(script),{recursive:true});
  fs.writeFileSync(script,`import json,sys,time
from pathlib import Path
args=sys.argv[1:]
def arg(name): return args[args.index(name)+1]
runs=Path(arg('--runs-root'));project=arg('--project');run_id=arg('--run-id')
finding=json.loads(Path(arg('--finding')).read_text())
run=runs/project/run_id;run.mkdir(parents=True,exist_ok=True)
(run/'agent.jsonl').write_text(json.dumps({'step':1,'role':'assistant','content':'fixture'})+'\\n')
captured=finding['id']=='F-1'
(run/'result.json').write_text(json.dumps({'result':{'status':'flag_captured' if captured else 'not_captured','captured':captured}}))
time.sleep(.2)
sys.exit(0 if captured else 2)
`);
  return {repoRoot,run,runDir,findings};
}

test('红队执行节点重跑按候选并行并隔离产物，不自动启动审核', async t=>{
  const {repoRoot,run,runDir}=fixture(t);
  const original=fs.readFileSync(path.join(runDir,'redteam/summary.json'),'utf8');
  assert.equal(retryEligibility(run,'redteam-agent'),'');
  assert.deepEqual(agentCandidates(run).map(item=>item.status),['ready','ready']);
  const started=startNodeRetry({repoRoot,run,node:'redteam-agent',models:{redteam:'red-fixture',audit:'wrong-model'}});
  let latest;
  for(let i=0;i<200;i++) {latest=nodeAttempts(run.runDir,'redteam-agent')[0];if(latest.status!=='running' && !fs.existsSync(latest.lock))break;await new Promise(r=>setTimeout(r,50));}
  assert.equal(latest.id,started.id);
  assert.equal(latest.resultStatus,'degraded');
  const summary=JSON.parse(fs.readFileSync(path.join(latest.workspace,'redteam/summary.json')));
  assert.equal(summary.selected,2);assert.equal(summary.ready,2);assert.equal(summary.processed,2);assert.equal(summary.captured,1);
  assert.equal(summary.concurrency,10);
  assert.deepEqual(summary.results.map(item=>item.id),['F-1','F-2']);
  assert.equal(summary.results[0].status,'flag_captured');
  assert.equal(summary.results[1].status,'not_captured');
  assert.ok(summary.results.every(item=>item.run_dir.includes('node-retries/redteam-agent/')));
  assert.equal(fs.readFileSync(path.join(runDir,'redteam/summary.json'),'utf8'),original);
  assert.equal(fs.existsSync(latest.lock),false);
  const traces=listAgenticTraces(run,'redteam-agent');
  assert.ok(traces.some(trace=>trace.id===`${started.id}-worker`));
  assert.ok(traces.some(trace=>trace.kind==='execution' && trace.path.endsWith('agent.jsonl')));
  const nodes=Object.fromEntries(buildAgenticPipeline(run).nodes.map(node=>[node.id,node]));
  assert.equal(nodes['redteam-agent'].status,'degraded');
  assert.match(nodes['redteam-agent'].detail,/捕获 1/);
  assert.equal(nodes.judge.status,'pending');
});

test('没有可用红队场景时拒绝重跑，并保留候选受阻原因', t=>{
  const {repoRoot,run,runDir}=fixture(t);
  for(const id of ['F-1','F-2'])fs.rmSync(path.join(repoRoot,'labs/demo',id,'scenario.json'));
  assert.match(retryEligibility(run,'redteam-agent'),/没有可用红队场景/);
  const candidates=agentCandidates(run);
  assert.equal(candidates.length,2);
  assert.ok(candidates.every(item=>item.status==='blocked' && item.reason.includes('场景')));
  assert.equal(fs.existsSync(path.join(runDir,'redteam/summary.json')),true);
});

test('红队执行并发上限按参数生效，结果保持候选顺序', async t=>{
  const repoRoot=fs.mkdtempSync(path.join(os.tmpdir(),'agent-retry-parallel-'));
  t.after(()=>fs.rmSync(repoRoot,{recursive:true,force:true}));
  const runDir=path.join(repoRoot,'runs/demo/one');
  const findings=Array.from({length:4},(_,i)=>({id:`F-${i+1}`,title:`候选 ${i+1}`,severity:'high'}));
  write(path.join(runDir,'audit-report.json'),{findings});
  write(path.join(runDir,'redteam/candidates.json'),{candidates:findings.map(item=>({id:item.id,project:'demo',run_id:'one'}))});
  const results=findings.map(finding=>{
    const findingFile=path.join(runDir,'redteam/batch',`01-demo-${finding.id}.json`);write(findingFile,finding);
    const scenario=path.join(repoRoot,'labs/demo',finding.id,'scenario.json');write(scenario,{finding_id:finding.id});
    return {id:finding.id,status:'built',finding:findingFile,scenario};
  });
  write(path.join(runDir,'redteam/summary.json'),{results});
  const script=path.join(repoRoot,'scripts/redteam/agent.py');fs.mkdirSync(path.dirname(script),{recursive:true});
  fs.writeFileSync(script,`import json,sys,time,fcntl
from pathlib import Path
args=sys.argv[1:]
def arg(name): return args[args.index(name)+1]
state=Path(__file__).parents[2]/'counter.json'
def update(delta):
 with state.open('a+') as file:
  fcntl.flock(file,fcntl.LOCK_EX);file.seek(0);data=json.loads(file.read() or '{"active":0,"peak":0}')
  data['active']+=delta;data['peak']=max(data['peak'],data['active'])
  file.seek(0);file.truncate();file.write(json.dumps(data));file.flush()
update(1);time.sleep(.3)
runs=Path(arg('--runs-root'));run=runs/arg('--project')/arg('--run-id');run.mkdir(parents=True,exist_ok=True)
(run/'result.json').write_text(json.dumps({'result':{'status':'flag_captured','captured':True}}))
update(-1);sys.exit(0)
`);
  const workspace=path.join(`${runDir}.meta/node-retries/redteam-agent/parallel/output`);fs.mkdirSync(workspace,{recursive:true});
  const {prepareAgentRetry,runAgentRetry}=await import('../server/redteam-agent-retry.mjs');
  const run={runDir,project:'demo',runId:'one',isLive:false};
  prepareAgentRetry(run,workspace);
  const job={repoRoot,workspace,project:'demo',runId:'one',model:'fixture',id:'parallel-one'};
  assert.equal(await runAgentRetry(job,2),'completed');
  const first=JSON.parse(fs.readFileSync(path.join(repoRoot,'counter.json')));
  assert.equal(first.active,0);assert.equal(first.peak,2);
  const summary=JSON.parse(fs.readFileSync(path.join(workspace,'redteam/summary.json')));
  assert.deepEqual(summary.results.map(item=>item.id),['F-1','F-2','F-3','F-4']);
  assert.equal(summary.concurrency,2);
  fs.writeFileSync(path.join(repoRoot,'counter.json'),JSON.stringify({active:0,peak:0}));
  assert.equal(await runAgentRetry({...job,id:'parallel-two'},10),'completed');
  const second=JSON.parse(fs.readFileSync(path.join(repoRoot,'counter.json')));
  assert.equal(second.active,0);assert.equal(second.peak,4);
});

test('红队执行重跑拒绝跨运行或跨项目候选', t=>{
  const {repoRoot,run,runDir}=fixture(t);
  write(path.join(runDir,'redteam/candidates.json'),{candidates:[
    {id:'F-1',project:'demo',run_id:'other'},
    {id:'F-2',project:'other',run_id:'one'}
  ]});
  assert.deepEqual(agentCandidates(run),[]);
  assert.match(retryEligibility(run,'redteam-agent'),/没有可用红队场景/);
});
