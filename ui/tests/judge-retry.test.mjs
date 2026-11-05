import {judgeTasks} from '../server/judge-tasks.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {judgeCandidates,prepareJudgeRetry,runJudgeRetry} from '../server/judge-retry.mjs';
import {retryEligibility} from '../server/node-retries.mjs';
import {listAgenticTraces} from '../server/agentic-traces.mjs';
const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data));};
function fixture(t) {
 const repoRoot=fs.mkdtempSync(path.join(os.tmpdir(),'judge-retry-'));t.after(()=>fs.rmSync(repoRoot,{recursive:true,force:true}));
 const runDir=path.join(repoRoot,'runs/demo/one');
 const run={project:'demo',runId:'one',runDir,isLive:false};
 const source=path.join(runDir,'redteam/execution/F-1');
 write(path.join(runDir,'audit-report.json'),{findings:[{id:'F-1'}]});
 write(path.join(runDir,'redteam/summary.json'),{results:[{id:'F-1',run_dir:source}]});
 for(const file of ['trace.jsonl','agent.jsonl','flag.txt','scenario.json'])write(path.join(source,file),{});
 write(path.join(source,'finding.json'),{id:'F-1',title:'候选'});
 write(path.join(source,'result.json'),{result:{captured:true,flag_provenance:{source:'tool_output'}}});
 return {repoRoot,run,source};
}
test('审核重跑复制证据、使用审核模型，拒绝结果与执行错误分别记录且不修改原结果',async t=>{
 const {repoRoot,run,source}=fixture(t);
 assert.equal(retryEligibility(run,'judge'),'');
 const root=path.join(`${run.runDir}.meta`,'node-retries/judge/test');
 const workspace=path.join(root,'output');
 prepareJudgeRetry(run,workspace);
 const original=fs.readFileSync(path.join(source,'result.json'),'utf8');
 const script=path.join(repoRoot,'scripts/redteam/judge.py');fs.mkdirSync(path.dirname(script),{recursive:true});
 fs.writeFileSync(script,`import sys,json,os
from pathlib import Path
args=sys.argv
assert args[args.index('--claude-model')+1]=='judge-fixture'
run=Path(args[args.index('--run-dir')+1])
assert 'node-retries' in str(run)
assert str(run.parent.parent) in os.environ['RSI_VALIDATION_TRAJECTORY']
(run/'judge.json').write_text(json.dumps({'verdict':'rejected'}))
(run/'judge.log').write_text(json.dumps({'type':'assistant','message':{'role':'assistant','content':[{'type':'text','text':'证据不足'}]}})+'\\n')
(run/'result.json').write_text('{}')
sys.exit(2)
`);
 const job={repoRoot,workspace,model:'judge-fixture'};
 assert.equal(await runJudgeRetry(job),'completed');
 const summary=JSON.parse(fs.readFileSync(path.join(workspace,'judge/summary.json')));
 assert.equal(summary.results[0].status,'judge_rejected');assert.equal(summary.approved,0);
 assert.equal(fs.readFileSync(path.join(source,'result.json'),'utf8'),original);
 write(path.join(root,'attempt.json'),{id:'test',workspace,root,startedAt:'2026-11-05',status:'completed'});
 assert.ok(listAgenticTraces(run,'judge').some(trace=>trace.kind==='claude' && trace.id==='test-judge-F-1'));
 const roster=judgeTasks(run);
 assert.equal(roster.tasks[0].label,'未通过');
 assert.equal(roster.tasks[0].traceId,'test-judge-F-1');
 assert.equal(roster.tasks[0].state,'completed');
});
test('未捕获或缺证据时禁止审核，不将普通红队完成视为成功证据',t=>{
 const {run,source}=fixture(t);
 write(path.join(source,'result.json'),{result:{captured:false}});
 assert.equal(judgeCandidates(run).length,0);
 assert.equal(judgeTasks(run).tasks[0].state,'blocked');
 assert.equal(judgeTasks(run).tasks[0].traceId,'');
 assert.match(retryEligibility(run,'judge'),/已捕获随机标记/);
});
test('最新红队批次无成功结果时不借用历史成功证据，运行中时拒绝审核',t=>{
 const {run}=fixture(t);
 const root=path.join(`${run.runDir}.meta`,'node-retries/redteam-agent/latest');
 const workspace=path.join(root,'output');
 const attempt={id:'latest',root,workspace,status:'completed',startedAt:'2026-11-05'};
 write(path.join(root,'attempt.json'),attempt);
 write(path.join(workspace,'redteam/summary.json'),{results:[]});
 assert.equal(judgeCandidates(run).length,0);
 write(path.join(root,'attempt.json'),{...attempt,status:'running'});
 assert.match(retryEligibility(run,'judge'),/正在重跑/);
});
