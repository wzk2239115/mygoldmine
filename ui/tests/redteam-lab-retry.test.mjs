import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {startNodeRetry,nodeAttempts,retryEligibility} from '../server/node-retries.mjs';
import {listAgenticTraces} from '../server/agentic-traces.mjs';
import {labTasks} from '../server/lab-tasks.mjs';
import {buildAgenticPipeline} from '../server/agentic-pipeline.mjs';
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value));};
function blueReports(repoRoot,run,findings) {
 write(path.join(repoRoot,'env/demo/env-manifest.json'),{image:'fixture:test',image_id:'sha256:fixture',commit:'a'.repeat(40)});
 const root=path.join(run.runDir,'verify/agent');write(path.join(root,'summary.json'),{project:'demo'});
 for(const finding of findings) {
  const folder=path.join(root,finding.id);
  write(path.join(folder,'finding.json'),finding);
  write(path.join(folder,'verify-report.json'),{project:'demo',finding_id:finding.id,verdict:'confirmed',evidence_class:'runtime',image:'fixture:test',image_id:'sha256:fixture',evidence:['result.txt']});
  fs.writeFileSync(path.join(folder,'verify-report.md'),'real fixture report');
  fs.mkdirSync(path.join(folder,'harness'),{recursive:true});fs.writeFileSync(path.join(folder,'harness/probe.py'),'print("fixture proof")');
  fs.mkdirSync(path.join(folder,'evidence'),{recursive:true});fs.writeFileSync(path.join(folder,'evidence/result.txt'),'fixture observation');
 }
}
function fixture(t) {
 const repoRoot=fs.mkdtempSync(path.join(os.tmpdir(),'lab-retry-'));
 t.after(()=>fs.rmSync(repoRoot,{recursive:true,force:true}));
 const runDir=path.join(repoRoot,'runs/demo/one'), source=path.join(repoRoot,'source');fs.mkdirSync(source);
 const run={runDir,project:'demo',runId:'one',isLive:false};
 write(path.join(runDir,'audit-report.json'),{findings:['F-1','F-2','F-3'].map(id=>({id,title:id,severity:'high'}))});
 write(`${runDir}.meta/status.json`,{target:source,env_image:'fixture:test'});
 write(path.join(runDir,'redteam/candidates.json'),{candidates:['F-1','F-2'].map(id=>({id,project:'demo',run_id:'one'}))});
 write(path.join(runDir,'redteam/summary.json'),{results:[{id:'F-1',status:'blocked_no_finding'}]});
 blueReports(repoRoot,run,['F-1','F-2','F-3'].map(id=>({id,title:id,severity:'high'})));
 return {repoRoot,run};
}

test('红队场景重跑使用本轮候选和红队模型，隔离产物、区分受阻，不启动后续阶段',async t=>{
 const {repoRoot,run}=fixture(t);
 const original=fs.readFileSync(path.join(run.runDir,'redteam/summary.json'),'utf8');
 const shared=path.join(repoRoot,'labs/demo/F-1/scenario.json');write(shared,{original:true});
 const script=path.join(repoRoot,'scripts/redteam/build_lab.py');fs.mkdirSync(path.dirname(script),{recursive:true});
 fs.writeFileSync(script,`import sys,json,time
from pathlib import Path
args=sys.argv[1:]
def arg(name): return args[args.index(name)+1]
assert '--build-only' in args
context=Path(arg('--blue-handoff'));assert context.is_file();assert json.loads(context.read_text())['role']=='builder_only'
assert arg('--claude-model')=='red-fixture'
lab=Path(arg('--lab-dir')); finding=json.loads(Path(arg('--finding')).read_text()); identifier=finding['id']
assert '/node-retries/redteam-lab/' in str(lab)
(lab/'builder.log').write_text(json.dumps({'type':'assistant','message':{'content':[]}})+'\\n')
time.sleep(.25)
if identifier=='F-2':
 (lab/'BLOCKED.md').write_text('当前执行器不支持该攻击面')
 print(json.dumps({'scenario_valid':False,'finding_id':identifier,'error':'不支持的攻击面'}));sys.exit(2)
scenario=lab/'scenario.json';scenario.write_text(json.dumps({'finding_id':identifier}))
print(json.dumps({'scenario_valid':True,'finding_id':identifier,'scenario':str(scenario)}))
`);
 assert.equal(retryEligibility(run,'redteam-lab'),'');
 const started=startNodeRetry({repoRoot,run,node:'redteam-lab',models:{redteam:'red-fixture',audit:'wrong-model'}});
 assert.throws(()=>startNodeRetry({repoRoot,run,node:'verify',models:{audit:'test'}}),/已有节点/);
 let latest;
 for(let i=0;i<150;i++) {latest=nodeAttempts(run.runDir,'redteam-lab')[0];if(latest.status!=='running')break;await new Promise(r=>setTimeout(r,50));}
 assert.equal(latest.status,'completed');assert.equal(latest.resultStatus,'degraded');
 const summary=JSON.parse(fs.readFileSync(path.join(latest.workspace,'redteam/summary.json')));
 assert.equal(summary.buildOnly,true);assert.equal(summary.selected,2);assert.equal(summary.ready,1);assert.equal(summary.blocked,1);
 assert.deepEqual(summary.results.map(row=>row.id),['F-1','F-2']);
 assert.deepEqual(JSON.parse(fs.readFileSync(shared)),{original:true});
 assert.equal(fs.readFileSync(path.join(run.runDir,'redteam/summary.json'),'utf8'),original);
 assert.equal(fs.existsSync(latest.lock),false);
 const traces=listAgenticTraces(run,'redteam-lab');
 assert.ok(traces.some(trace=>trace.id===`${started.id}-redteam-lab-F-1-agent` && trace.kind==='claude'));
 const nodes=Object.fromEntries(buildAgenticPipeline(run).nodes.map(node=>[node.id,node]));
 assert.equal(nodes['redteam-lab'].status,'degraded');assert.match(nodes['redteam-lab'].detail,/可用 1.*受阻 1/);
 assert.equal(nodes['redteam-agent'].status,'pending');assert.equal(nodes.judge.status,'pending');
});

test('红队场景重跑拒绝缺失源码、跨运行清单、危险编号与不属于本轮报告的候选',t=>{
 const {repoRoot,run}=fixture(t);
 write(`${run.runDir}.meta/status.json`,{target:path.join(repoRoot,'missing')});
 assert.match(retryEligibility(run,'redteam-lab'),/源码/);
 write(`${run.runDir}.meta/status.json`,{target:path.join(repoRoot,'source')});
 for(const candidate of [{id:'F-1',project:'other',run_id:'one'},{id:'F-1',project:'demo',run_id:'other'},{id:'../F-1',project:'demo',run_id:'one'},{id:'F-9',project:'demo',run_id:'one'}]) {
  write(path.join(run.runDir,'redteam/candidates.json'),{candidates:[candidate]});
  assert.notEqual(retryEligibility(run,'redteam-lab'),'');
 }
});

for(const [jobs,count,peak] of [[undefined,12,10],[2,4,2]])test(`红队候选池限制并发 ${jobs || 10}，结果保持原顺序并分别保存`,async t=>{
 const {repoRoot,run}=fixture(t),workspace=path.join(`${run.runDir}.meta/node-retries/redteam-lab/parallel/output`);
 const findings=Array.from({length:count},(_,i)=>({id:`F-${String(i).padStart(2,'0')}`,severity:'high'}));
 write(path.join(run.runDir,'audit-report.json'),{findings});
 write(path.join(run.runDir,'redteam/candidates.json'),{candidates:findings.map(item=>({id:item.id,project:'demo',run_id:'one'}))});
 write(path.join(workspace,'audit-report.json'),{findings});
 blueReports(repoRoot,run,findings);
 const {prepareLabRetry,runLabRetry}=await import('../server/redteam-lab-retry.mjs');
 prepareLabRetry(run,workspace);
 const script=path.join(repoRoot,'scripts/redteam/build_lab.py');fs.mkdirSync(path.dirname(script),{recursive:true});
 fs.writeFileSync(script,`import sys,json,time,fcntl
from pathlib import Path
args=sys.argv[1:]
def arg(name):return args[args.index(name)+1]
state=Path(__file__).parents[2]/'counter.json'
def update(delta):
 with state.open('a+') as file:
  fcntl.flock(file,fcntl.LOCK_EX);file.seek(0);data=json.loads(file.read() or '{"active":0,"peak":0}')
  data['active']+=delta;data['peak']=max(data['peak'],data['active'])
  file.seek(0);file.truncate();file.write(json.dumps(data));file.flush()
update(1);time.sleep(.5)
lab=Path(arg('--lab-dir'));finding=json.loads(Path(arg('--finding')).read_text())
scenario=lab/'scenario.json';scenario.write_text(json.dumps({'finding_id':finding['id']}))
update(-1)
print(json.dumps({'scenario_valid':True,'finding_id':finding['id'],'scenario':str(scenario)}))
`);
 const job={repoRoot,workspace,project:'demo',source:path.join(repoRoot,'source'),model:'fixture'};
 assert.equal(await runLabRetry(job,jobs),'completed');
 const observed=JSON.parse(fs.readFileSync(path.join(repoRoot,'counter.json')));
 assert.equal(observed.active,0);assert.equal(observed.peak,peak);
 const summary=JSON.parse(fs.readFileSync(path.join(workspace,'redteam/summary.json')));
 assert.equal(summary.concurrency,jobs || 10);assert.equal(summary.processed,count);
 assert.deepEqual(summary.results.map(item=>item.id),findings.map(item=>item.id));
 for(const finding of findings)assert.equal(JSON.parse(fs.readFileSync(path.join(workspace,'redteam/tasks',`${finding.id}.json`))).state,'completed');
 await assert.rejects(()=>runLabRetry(job,11),/并发数/);
});

test('红队节点只接收蓝队确认且完整的交付，最新蓝队运行时不能使用旧结果',t=>{
 const {repoRoot,run}=fixture(t);
 const root=path.join(run.runDir,'verify/agent');
 const report=JSON.parse(fs.readFileSync(path.join(root,'F-2/verify-report.json')));report.verdict='blocked';write(path.join(root,'F-2/verify-report.json'),report);
 const workspace=path.join(repoRoot,'workspace');write(path.join(workspace,'audit-report.json'),JSON.parse(fs.readFileSync(path.join(run.runDir,'audit-report.json'))));
 return import('../server/redteam-lab-retry.mjs').then(({prepareLabRetry})=>{
  prepareLabRetry(run,workspace);
  const selected=JSON.parse(fs.readFileSync(path.join(workspace,'redteam/selection.json')));
  assert.deepEqual(selected.candidates.map(x=>x.id),['F-1']);assert.equal(selected.excluded[0].id,'F-2');
  assert.ok(fs.existsSync(path.join(workspace,'redteam/blue-handoff/F-1/harness/probe.py')));
  write(`${run.runDir}.meta/node-retries/redteam-lab/new/attempt.json`,{id:'red-new',project:'demo',runId:'one',workspace,status:'completed',startedAt:'2026-11-05'});
  const roster=labTasks(run);assert.equal(roster.blueHandoffCount,1);assert.equal(roster.blueAttemptId,'original');
  assert.equal(roster.excluded[0].id,'F-2');assert.deepEqual(roster.tasks.map(x=>x.id),['F-1']);
  write(`${run.runDir}.meta/node-retries/verify/new/attempt.json`,{id:'new',project:'demo',runId:'one',workspace:path.join(repoRoot,'new'),status:'running',startedAt:'2026-11-05'});
  assert.match(retryEligibility(run,'redteam-lab'),/蓝队验证正在运行/);
 });
});
