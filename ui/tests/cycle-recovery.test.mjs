
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {EventEmitter} from 'node:events';
import {resumeAfterLearning} from '../server/learning-cycles.mjs';

function setup(t,index=7) {
 const repo=fs.mkdtempSync(path.join(os.tmpdir(),'cycle-recovery-'));
 t.after(()=>fs.rmSync(repo,{recursive:true,force:true}));
 const runDir=path.join(repo,'runs/demo/learning-cycle-1-'+index);
 const folder=path.join(repo,'rsi/stage-skills/cycles/cycle-1'),file=path.join(folder,'status.json');
 const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data));};
 const source=path.join(repo,'targets/demo');fs.mkdirSync(source,{recursive:true});
 write(runDir+'.meta/status.json',{target:source});
 write(file,{id:'cycle-1',project:'demo',status:'failed',current_round:index,max_rounds:8,
 rounds:Array.from({length:index-1},(_,i)=>({index:i+1})),error:'旧故障'});
 return {repo,folder,file,workflow:{id:'repaired',project:'demo',runDir,status:'completed',start:'learner',receipts:[{node:'learner',status:'completed'}]}};
}
test('完成学习重跑后继续原循环剩余轮次，不重置为八轮',t=>{
 const f=setup(t);let launched;
 const launch=(program,args)=>{launched=args;const child=new EventEmitter();child.unref=()=>{};return child;};
 const state=resumeAfterLearning(f.repo,f.workflow,launch);
 assert.equal(state.rounds.length,7);assert.equal(state.max_rounds,8);
 assert.equal(state.id,'cycle-1');assert.equal(state.status,'queued');
 assert.ok(launched.includes('--resume'));
 assert.equal(resumeAfterLearning(f.repo,f.workflow,launch),null);
});
test('第八轮修复完成后结束，不再启动第九轮',t=>{
 const f=setup(t,8);
 assert.equal(resumeAfterLearning(f.repo,f.workflow,()=>assert.fail('不应启动')).status,'completed');
});
test('显式停止的循环不会自动恢复',t=>{
 const f=setup(t);fs.writeFileSync(path.join(f.folder,'stop'),'stop');
 assert.equal(resumeAfterLearning(f.repo,f.workflow,()=>assert.fail('不应启动')),null);
});
