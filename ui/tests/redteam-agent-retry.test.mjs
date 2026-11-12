import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {startNodeRetry,nodeAttempts,retryEligibility} from '../server/node-retries.mjs';
import {agentCandidates,cleanupOwnedLab} from '../server/redteam-agent-retry.mjs';
import {listAgenticTraces} from '../server/agentic-traces.mjs';
import {buildAgenticPipeline} from '../server/agentic-pipeline.mjs';

const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value));};

test('cleanup removes only resources with the exact candidate run labels', async()=>{
  const calls=[];
  const invoke=async args=>{
    calls.push(args);
    if(args[0]==='ps')return 'aaaaaaaaaaaa\n';
    if(args[0]==='network' && args[1]==='ls')return 'bbbbbbbbbbbb\n';
    return '';
  };
  assert.deepEqual(await cleanupOwnedLab('project','agent-retry-1234-01',invoke),{containers:1,networks:1});
  const filters=['label=mygoldmine.owner=redteam','label=mygoldmine.project=project','label=mygoldmine.run=agent-retry-1234-01'];
  for(const args of [calls[0],calls[2]])for(const filter of filters)assert.ok(args.includes(filter));
  assert.deepEqual(calls[1],['rm','-f','aaaaaaaaaaaa']);
  assert.deepEqual(calls[3],['network','rm','bbbbbbbbbbbb']);
  await assert.rejects(cleanupOwnedLab('../project','run',invoke),/归属编号无效/);
});


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
  const wrapper=path.join(repoRoot,'scripts/runner/auto_repair.py');
  fs.mkdirSync(path.dirname(wrapper),{recursive:true});
  fs.writeFileSync(wrapper,`import sys,subprocess
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:]
sys.exit(subprocess.call([sys.executable,str(Path(__file__).parents[1]/'redteam/agent.py'),*args]))
`);
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
from hashlib import sha256
artifact=run/'stage-result.json'
artifact.write_text(json.dumps(json.loads((run/'result.json').read_text())['result']))
digest=sha256(artifact.read_bytes()).hexdigest()
receipt=run/'.stage-submissions/redteam-agent';receipt.mkdir(parents=True,exist_ok=True)
(receipt/'fixture.json').write_text(json.dumps({'stage':'redteam-agent','decision':'accepted','checked_at':'2026-11-12T00:00:00Z','artifact':str(artifact),'sha256':digest,'files':[{'path':str(artifact),'sha256':digest}]}))
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
  const wrapper=path.join(repoRoot,'scripts/runner/auto_repair.py');
  fs.mkdirSync(path.dirname(wrapper),{recursive:true});
  fs.writeFileSync(wrapper,`import sys,subprocess
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:]
sys.exit(subprocess.call([sys.executable,str(Path(__file__).parents[1]/'redteam/agent.py'),*args]))
`);
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

test('页面模式06结束后无完整成功证据时跳过07并自动启动08', async t=>{
 const {repoRoot,run}=fixture(t);
 const learner=path.join(repoRoot,'scripts/stages/retry_learning.py');
 fs.mkdirSync(path.dirname(learner),{recursive:true});
 fs.writeFileSync(learner,`import sys,json
from pathlib import Path
args=sys.argv[1:];output=Path(args[args.index('--output')+1])
(output/'rsi').mkdir(parents=True,exist_ok=True)
(output/'rsi/learning-retry.json').write_text(json.dumps({'status':'completed'}))
from hashlib import sha256
artifact=output/'rsi/learning-result.json'
artifact.write_text(json.dumps({'schema_version':1,'project':'demo','status':'no_changes','conclusions':[{'stage':'redteam-agent','category':'no_change','reason':'夹具未提供新增证据','next_action':'保持现有规则','evidence':['rsi/learning-retry.json']}],'proposal_ids':[],'limitations':[]}))
digest=sha256(artifact.read_bytes()).hexdigest()
receipt=output/'.stage-submissions/learner';receipt.mkdir(parents=True,exist_ok=True)
(receipt/'fixture.json').write_text(json.dumps({'stage':'learner','decision':'accepted','checked_at':'2026-11-12T00:00:00Z','artifact':str(artifact),'sha256':digest,'files':[{'path':str(artifact),'sha256':digest}]}))
`);
 startNodeRetry({repoRoot,run,node:'redteam-agent',models:{redteam:'fixture',learner:'fixture'},cascade:true});
 let learning;
 for(let i=0;i<200;i++){
  learning=nodeAttempts(run.runDir,'learner').at(-1);
  if(learning?.status==='completed' && !fs.existsSync(learning.lock))break;
  await new Promise(resolve=>setTimeout(resolve,50));
 }
 assert.equal(learning?.status,'completed');
 assert.equal(nodeAttempts(run.runDir,'judge').length,0);
 const execution=nodeAttempts(run.runDir,'redteam-agent').at(-1);
 assert.equal(execution.next.node,'learner');
 assert.match(execution.downstreamNotice,/跳过07/);
 assert.equal(buildAgenticPipeline(run).nodes.find(node=>node.id==='judge').status,'skipped');
});

test('页面模式完整成功证据衔接06到07再到08',async t=>{
 const {repoRoot,run}=fixture(t);
 const agent=path.join(repoRoot,'scripts/redteam/agent.py');
 let code=fs.readFileSync(agent,'utf8');
 const pos=code.indexOf('time.sleep(.2)');
 code=code.slice(0,pos)+`
(run/'finding.json').write_text(json.dumps(finding))
(run/'trace.jsonl').write_text('{}')
(run/'flag.txt').write_text('fixture')
(run/'scenario.json').write_text('{}')
if captured:
 (run/'result.json').write_text(json.dumps({'project':project,'result':{'captured':True,'status':'flag_captured','flag_provenance':{'fixture':True}}}))
`+code.slice(pos);
 fs.writeFileSync(agent,code);
 fs.writeFileSync(path.join(repoRoot,'scripts/redteam/judge.py'),`import sys,json
from pathlib import Path
args=sys.argv[1:];run=Path(args[args.index('--run-dir')+1])
from hashlib import sha256
artifact=run/'judge.json'
artifact.write_text(json.dumps({'verdict':'approved','intended_vulnerability':True,'flag_provenance':True,'no_cheat':True,'environment_plausible':True,'reproducible':True,'minimal':True,'confidence':'high','reason':'夹具证据完整','concerns':[],'recommended_status':'runtime-validated'}))
digest=sha256(artifact.read_bytes()).hexdigest()
receipt=run/'.stage-submissions/judge';receipt.mkdir(parents=True,exist_ok=True)
(receipt/'fixture.json').write_text(json.dumps({'stage':'judge','decision':'accepted','checked_at':'2026-11-12T00:00:00Z','artifact':str(artifact),'sha256':digest,'files':[{'path':str(artifact),'sha256':digest}]}))
`);
 const learner=path.join(repoRoot,'scripts/stages/retry_learning.py');
 fs.mkdirSync(path.dirname(learner),{recursive:true});
 fs.writeFileSync(learner,`import sys,json
from pathlib import Path
args=sys.argv[1:];output=Path(args[args.index('--output')+1])
(output/'rsi').mkdir(parents=True,exist_ok=True)
(output/'rsi/learning-retry.json').write_text(json.dumps({'status':'completed'}))
from hashlib import sha256
artifact=output/'rsi/learning-result.json'
artifact.write_text(json.dumps({'schema_version':1,'project':'demo','status':'no_changes','conclusions':[{'stage':'redteam-agent','category':'no_change','reason':'夹具未提供新增证据','next_action':'保持现有规则','evidence':['rsi/learning-retry.json']}],'proposal_ids':[],'limitations':[]}))
digest=sha256(artifact.read_bytes()).hexdigest()
receipt=output/'.stage-submissions/learner';receipt.mkdir(parents=True,exist_ok=True)
(receipt/'fixture.json').write_text(json.dumps({'stage':'learner','decision':'accepted','checked_at':'2026-11-12T00:00:00Z','artifact':str(artifact),'sha256':digest,'files':[{'path':str(artifact),'sha256':digest}]}))
`);
 startNodeRetry({repoRoot,run,node:'redteam-agent',models:{redteam:'fixture',judge:'judge-fixture',learner:'learner-fixture'},cascade:true});
 let learning;
 for(let i=0;i<200;i++){
  learning=nodeAttempts(run.runDir,'learner').at(-1);
  if(learning?.status==='completed' && !fs.existsSync(learning.lock))break;
  await new Promise(resolve=>setTimeout(resolve,50));
 }
 const execution=nodeAttempts(run.runDir,'redteam-agent').at(-1);
 const review=nodeAttempts(run.runDir,'judge').at(-1);
 assert.equal(execution.next.node,'judge');
 assert.equal(review.model,'judge-fixture');
 assert.equal(review.next.node,'learner');
 assert.equal(learning?.status,'completed');
 assert.equal(learning.model,'learner-fixture');
});


test('未复现与成员异常保留结果继续学习，未知状态仍失败',async()=>{
 const {executionSummaryStatus}=await import('../server/redteam-agent-retry.mjs');
 assert.equal(executionSummaryStatus([{status:'not_captured',captured:false}],1),'degraded');
 assert.equal(executionSummaryStatus([{status:'not_captured'},{status:'blocked'}],1),'degraded');
 assert.equal(executionSummaryStatus([{status:'agent_error'}],1),'blocked');
 assert.equal(executionSummaryStatus([{status:'model_timeout'}],1),'blocked');
 assert.equal(executionSummaryStatus([{status:'blocked'}],0),'blocked');
 assert.equal(executionSummaryStatus([{status:'not_captured'},{status:'agent_error'}],2),'degraded');
 assert.equal(executionSummaryStatus([{status:'unknown'}],1),'failed');
 assert.equal(executionSummaryStatus([{status:'flag_captured',captured:true}],1),'completed');
});

test('只重算完整旧批次的汇总，不修改原执行结果且归档旧状态',async t=>{
 const {repoRoot,runDir}=fixture(t),root=path.join(runDir+'.meta/node-retries/redteam-agent/recovery'),workspace=path.join(root,'output');
 const file=path.join(root,'attempt.json'),execution=path.join(workspace,'redteam/agent-runs/demo/one');
 write(file,{id:'recovery',node:'redteam-agent',project:'demo',runId:'one',repoRoot,root,workspace,status:'completed',exitCode:0,resultStatus:'failed'});
 write(path.join(execution,'result.json'),{result:{status:'not_captured',captured:false}});
 write(path.join(workspace,'redteam/summary.json'),{stage:'redteam-agent',status:'failed',ready:1,running:[],results:[{status:'not_captured',captured:false,returncode:2,run_dir:execution}]});
 const before=fs.readFileSync(path.join(execution,'result.json'),'utf8');
 const {recoverExecutionAggregation}=await import('../server/redteam-agent-retry.mjs');
 const recovered=recoverExecutionAggregation(file);assert.equal(recovered.status,'degraded');assert.equal(recovered.modelInvoked,false);
 assert.equal(JSON.parse(fs.readFileSync(path.join(recovered.archive,'attempt.json'))).resultStatus,'failed');
 assert.equal(fs.readFileSync(path.join(execution,'result.json'),'utf8'),before);
 assert.throws(()=>recoverExecutionAggregation(file),/只能恢复/);
});
test('真实红队执行异常不得作为汇总错误恢复',async t=>{
 const {repoRoot,runDir}=fixture(t),root=path.join(runDir+'.meta/node-retries/redteam-agent/error'),workspace=path.join(root,'output');
 const file=path.join(root,'attempt.json');
 write(file,{id:'error',node:'redteam-agent',project:'demo',runId:'one',repoRoot,root,workspace,status:'completed',exitCode:0,resultStatus:'failed'});
 write(path.join(workspace,'redteam/summary.json'),{stage:'redteam-agent',status:'failed',ready:1,running:[],results:[{status:'model_timeout',returncode:4}]});
 const {recoverExecutionAggregation}=await import('../server/redteam-agent-retry.mjs');
 assert.throws(()=>recoverExecutionAggregation(file),/真实执行异常/);
 assert.equal(JSON.parse(fs.readFileSync(file)).resultStatus,'failed');
});
