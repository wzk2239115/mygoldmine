import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {createHash} from 'node:crypto';
import {verifiedReports} from '../server/verified-reports.mjs';
function fixture(t){
 const repo=fs.mkdtempSync(path.join(os.tmpdir(),'verified-reports-'));t.after(()=>fs.rmSync(repo,{recursive:true,force:true}));
 const runDir=path.join(repo,'runs/demo/one');const folder=path.join(runDir,'visual-rendered');fs.mkdirSync(folder,{recursive:true});
 const file=path.join(folder,'scene-DEMO-1.webp');const bytes=Buffer.from('RIFF0000WEBPfixture');fs.writeFileSync(file,bytes);
 const proof={source:'text-to-image',model:'image-model',prompt_hash:'prompt',sha256:createHash('sha256').update(bytes).digest('hex')};
 fs.writeFileSync(file+'.generation.json',JSON.stringify(proof));
 fs.writeFileSync(path.join(folder,'report-illustrated.md'),'![scene](scene-DEMO-1.webp)');
 const stages={blue:{status:'confirmed',attemptId:'b'},red:{status:'flag_captured',provenanceVerified:true,attemptId:'r'},judge:{status:'judge_approved',provenanceVerified:true,attemptId:'j'}};
 const f={key:'demo/one/DEMO-1',project:'demo',runId:'one',runDir,id:'DEMO-1',title:'验证示例',reviewReady:true,stageResults:stages};
 for(const [node,key] of [['verify','blue'],['redteam-agent','red'],['judge','judge']]){
  const dir=path.join(runDir+'.meta','node-retries',node,stages[key].attemptId);fs.mkdirSync(dir,{recursive:true});
  fs.writeFileSync(path.join(dir,'attempt.json'),JSON.stringify({id:stages[key].attemptId,project:'demo',runId:'one',startedAt:'2026-11-06',status:'completed'}));
 }
 return {repo,f,file,folder};
}
test('单独整理核验报告，不包含其他候选章节',t=>{
 const x=fixture(t);const rows=verifiedReports(x.repo,[x.f]);
 assert.equal(rows.length,1);assert.match(rows[0].markdown,/独立审核结论/);assert.match(rows[0].markdown,/DEMO-1/);
 assert.ok(rows[0].imageUrl.includes('/nodes/visual/artifacts/'));
});
test('缺少任一阶段通过或文生图生成记录则拒绝',t=>{
 const x=fixture(t);x.f.stageResults.blue.status='inconclusive';assert.equal(verifiedReports(x.repo,[x.f]).length,0);
 x.f.stageResults.blue.status='confirmed';fs.rmSync(x.file+'.generation.json');assert.equal(verifiedReports(x.repo,[x.f]).length,0);
});
test('图片更改、历史结构图或未嵌入插图均不满足通过条件',t=>{
 const x=fixture(t);fs.appendFileSync(x.file,'tampered');assert.equal(verifiedReports(x.repo,[x.f]).length,0);
});
test('新的验证批次运行时不能展示旧结论',t=>{
 const x=fixture(t);const dir=path.join(x.f.runDir+'.meta/node-retries/verify/new');fs.mkdirSync(dir,{recursive:true});
 fs.writeFileSync(path.join(dir,'attempt.json'),JSON.stringify({id:'new',status:'running',startedAt:'2026-11-07'}));
 assert.equal(verifiedReports(x.repo,[x.f]).length,0);
});
