import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {partialJudgeDelivery} from '../server/partial-judge-delivery.mjs';
function fixture(t){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'partial-judge-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data));};
 const candidates=Array.from({length:6},(_,i)=>({id:'F-'+i,run_dir:path.join(root,'judge/runs/F-'+i)}));
 for(const row of candidates.slice(0,5)){
  const file=path.join(row.run_dir,'judge.json');write(file,{verdict:'approved'});
  write(path.join(row.run_dir,'.stage-submissions/judge/r.json'),{
   stage:'judge',decision:'accepted',artifact:file,
   sha256:createHash('sha256').update(fs.readFileSync(file)).digest('hex')});
 }
 write(path.join(root,'judge/selection.json'),{candidates});
 write(path.join(root,'judge/summary.json'),{selected:6,results:candidates.map(row=>({...row,status:'judge_approved'}))});
 return {root,candidates,write};
}
test('六名审核成员五份交付继续，缺失成员不能保留通过状态',t=>{
 const {root}=fixture(t),result=partialJudgeDelivery(root);
 assert.equal(result.accepted,5);assert.equal(result.excluded.length,1);
 const summary=JSON.parse(fs.readFileSync(path.join(root,'judge/summary.json')));
 assert.equal(summary.status,'degraded');assert.equal(summary.approved,5);
 assert.equal(summary.results[5].status,'judge_error');
 assert.equal(summary.results[5].delivery_status,'missing');
});
test('全部缺失也进入学习；损坏回执只隔离该成员；只读检查不改历史',t=>{
 const {root,candidates}=fixture(t),file=path.join(root,'judge/summary.json');
 fs.writeFileSync(path.join(candidates[0].run_dir,'judge.json'),'changed');
 const original=fs.readFileSync(file);
 assert.equal(partialJudgeDelivery(root,{persist:false}).accepted,4);
 assert.deepEqual(fs.readFileSync(file),original);
 for(const row of candidates)fs.rmSync(row.run_dir,{recursive:true,force:true});
 const result=partialJudgeDelivery(root);
 assert.equal(result.accepted,0);assert.equal(result.excluded.length,6);
 assert.equal(JSON.parse(fs.readFileSync(file)).approved,0);
});
test('选择清单成员缺少汇总记录也单独登记；目录越界不交接',t=>{
 const {root,candidates,write}=fixture(t);
 write(path.join(root,'judge/summary.json'),{results:candidates.slice(0,4).map(row=>({...row,status:'judge_approved'}))});
 const result=partialJudgeDelivery(root);
 assert.equal(result.excluded.length,1);
 assert.equal(result.accepted,5);
 const summary=JSON.parse(fs.readFileSync(path.join(root,'judge/summary.json')));
 assert.equal(summary.results.length,6);
});
