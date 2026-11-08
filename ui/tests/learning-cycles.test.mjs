import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {EventEmitter} from 'node:events';
import {startCycle,stopCycle,cycleStatus} from '../server/learning-cycles.mjs';

function fixture(t) {
 const repoRoot=fs.mkdtempSync(path.join(os.tmpdir(),'cycle-control-'));
 t.after(()=>fs.rmSync(repoRoot,{recursive:true,force:true}));
 const run={project:'demo',runDir:path.join(repoRoot,'runs/demo/one'),isLive:false};
 const source=path.join(repoRoot,'targets/demo');fs.mkdirSync(source,{recursive:true});
 fs.mkdirSync(run.runDir+'.meta',{recursive:true});
 fs.writeFileSync(path.join(run.runDir+'.meta','status.json'),JSON.stringify({target:source}));
 const child=new EventEmitter();child.unref=()=>{};
 const calls=[];const launch=(...args)=>{calls.push(args);return child;};
 return {repoRoot,run,launch,child,calls};
}
test('循环启动保留互斥锁，停止请求等待当前轮结束',t=>{
 const f=fixture(t);const started=startCycle(f);
 assert.equal(started.max_rounds,8);assert.equal(started.patience,2);
 assert.equal(cycleStatus(f.repoRoot,'demo').active,true);
 assert.ok(f.calls[0][1].includes('--claim-token'));
 assert.equal(f.calls[0][1][f.calls[0][1].indexOf('--rounds')+1],'8');
 assert.throws(()=>startCycle(f),/已有学习循环/);
 assert.equal(stopCycle(f.repoRoot,'demo').stopRequested,true);
 assert.equal(cycleStatus(f.repoRoot,'demo').active,true);
 f.child.emit('exit',1);
 assert.equal(cycleStatus(f.repoRoot,'demo').active,false);
 assert.equal(cycleStatus(f.repoRoot,'demo').status,'failed');
});
test('拒绝与当前审计或节点重跑并发启动',t=>{
 const f=fixture(t);
 assert.throws(()=>startCycle({...f,liveRuns:[{project:'demo',isLive:true}]}),/正在审计/);
 const guard=path.join(f.repoRoot,'runs/.node-retry-demo.lock');fs.mkdirSync(guard);
 assert.throws(()=>startCycle(f),/正在执行节点任务/);
 assert.equal(f.calls.length,0);
});
test('启动失败释放循环锁，保留失败记录',t=>{
 const f=fixture(t);startCycle(f);f.child.emit('error',new Error('missing python'));
 assert.equal(cycleStatus(f.repoRoot,'demo').status,'failed');
 assert.equal(fs.existsSync(path.join(f.repoRoot,'runs/.learning-cycle-demo.lock')),false);
});
test('非法参数与缺失源码不创建循环',t=>{
 const f=fixture(t);assert.throws(()=>startCycle({...f,rounds:0}),/轮数/);
 fs.rmSync(path.join(f.repoRoot,'targets/demo'),{recursive:true});
 assert.throws(()=>startCycle(f),/源码/);
 assert.equal(f.calls.length,0);
});

test('持续模式显式交给控制器，完整轮数排除节点重跑和失败流程',t=>{
 const f=fixture(t);startCycle({...f,continuous:true});
 assert.ok(f.calls[0][1].includes('--continuous'));
 assert.equal(cycleStatus(f.repoRoot,'demo').continuous,true);
 const folder=path.join(f.run.runDir+'.meta','workflows','one');fs.mkdirSync(folder,{recursive:true});
 const steps=['environment','orchestrator','visual','verify','redteam-lab','redteam-agent','judge','learner'];
 const state={project:'demo',runDir:f.run.runDir,engine:'claude-workflow',status:'completed',steps,receipts:steps.map(node=>({node,status:'degraded'}))};
 const save=()=>fs.writeFileSync(path.join(folder,'state.json'),JSON.stringify(state));
 save();assert.equal(cycleStatus(f.repoRoot,'demo').completed_rounds,1);
 state.steps=steps.slice(5);save();assert.equal(cycleStatus(f.repoRoot,'demo').completed_rounds,0);
 state.steps=steps;state.status='failed';save();assert.equal(cycleStatus(f.repoRoot,'demo').completed_rounds,0);
});
