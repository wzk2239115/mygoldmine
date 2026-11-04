import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {verifyTasks,verifyTaskReport} from '../server/verify-tasks.mjs';
import {listAgenticTraces} from '../server/agentic-traces.mjs';
const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data));};
function fixture(t) {
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'verify-tasks-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const run={runDir:path.join(root,'runs/demo/run'),project:'demo',runId:'run',isLive:false};
 fs.mkdirSync(run.runDir,{recursive:true});return run;
}

test('历史候选各自绑定报告，不按模型给出的报告路径读取',t=>{
 const run=fixture(t),root=path.join(run.runDir,'verify/agent');
 write(path.join(root,'summary.json'),{findings:[{finding_id:'F-1',title:'候选一',verdict:'blocked',report_path:'/wrong'}]});
 write(path.join(root,'F-1/verify-report.json'),{finding_id:'F-1',verdict:'blocked',reason:'缺少条件'});
 const data=verifyTasks(run);
 assert.equal(data.concurrency,1);assert.equal(data.legacy,true);
 assert.equal(data.tasks[0].traceId,'F-1');assert.equal(data.tasks[0].label,'受阻');
 assert.equal(verifyTaskReport(run,'F-1').finding_id,'F-1');
 assert.equal(verifyTaskReport(run,'..'),null);
 assert.equal(verifyTaskReport(run,'F-2'),null);
});

test('并发候选在新批次独立定位，新增日志不会改变已有轨迹编号',t=>{
 const run=fixture(t),attemptRoot=`${run.runDir}.meta/node-retries/verify/retry-one`,workspace=path.join(attemptRoot,'output');
 const attempt={id:'retry-one',workspace,root:attemptRoot,status:'running',startedAt:'2026-11-04T01:00:00Z'};
 write(path.join(attemptRoot,'attempt.json'),attempt);
 const root=path.join(workspace,'verify/agent');
 write(path.join(root,'tasks/F-2.json'),{finding_id:'F-2',entry:{index:1},state:'running',concurrency:10});
 write(path.join(root,'tasks/F-3.json'),{finding_id:'F-3',entry:{index:2},state:'queued',concurrency:10});
 const file=path.join(root,'logs/F-2.agent.log');fs.mkdirSync(path.dirname(file),{recursive:true});
 fs.writeFileSync(file,'{"type":"assistant","message":{"content":[]}}\n');
 let data=verifyTasks(run);
 assert.equal(data.concurrency,10);assert.equal(data.tasks[0].label,'运行中');
 assert.ok(listAgenticTraces(run,'verify').some(trace=>trace.id===data.tasks[0].traceId));
 fs.writeFileSync(path.join(root,'logs/F-1.runner.log'),'runner');
 assert.ok(listAgenticTraces(run,'verify').some(trace=>trace.id===data.tasks[0].traceId));
 write(path.join(root,'F-2/verify-report.json'),{finding_id:'F-2',verdict:'confirmed'});
 assert.equal(verifyTaskReport(run,'F-2','retry-one').verdict,'confirmed');
 assert.equal(verifyTaskReport(run,'F-2','old-attempt'),null);
 write(path.join(attemptRoot,'attempt.json'),{...attempt,status:'failed'});
 data=verifyTasks(run);assert.equal(data.tasks[0].label,'已中断');assert.equal(data.tasks[1].label,'已中断');
});
