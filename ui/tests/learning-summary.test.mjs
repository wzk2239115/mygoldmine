import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {learningSummary} from '../server/learning-summary.mjs';
function fixture(t){
 const repo=fs.mkdtempSync(path.join(os.tmpdir(),'learning-summary-'));
 t.after(()=>fs.rmSync(repo,{recursive:true,force:true}));
 const runDir=path.join(repo,'runs/demo/one');fs.mkdirSync(path.join(runDir,'rsi'),{recursive:true});
 return {repo,run:{runDir,project:'demo',runId:'one'}};
}
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value));};
test('展示正式归因、按实际候选记录区分发布及当前启用状态',t=>{
 const {repo,run}=fixture(t);
 fs.writeFileSync(path.join(run.runDir,'evidence.txt'),'actual evidence');
 write(path.join(run.runDir,'rsi/learning-result.json'),{status:'completed',conclusions:[{stage:'verify',category:'method_gap',reason:'reason',next_action:'next',evidence:['evidence.txt']}],proposal_ids:['new']});
 write(path.join(repo,'rsi/stage-skills/candidates/new.json'),{key:'verify/general/shared',parent:'old',content:'new rule',stage:'verify',scope:'general'});
 write(path.join(repo,'rsi/stage-skills/candidates/old.json'),{content:'old rule'});
 write(path.join(repo,'rsi/stage-skills/active.json'),{'verify/general/shared':'new'});
 const summary=learningSummary(repo,run);
 assert.equal(summary.proposals[0].before,'old rule');
 assert.equal(summary.proposals[0].active,true);
 assert.equal(summary.accepted,false);
 assert.equal(learningSummary(repo,run,summary.conclusions[0].evidence[0].id).text,'actual evidence');
 assert.equal(learningSummary(repo,run,'arbitrary'),null);
});
test('最新重跑尚无结果时不借用旧批次成功结果',t=>{
 const {repo,run}=fixture(t);
 write(path.join(run.runDir,'rsi/learning-result.json'),{status:'completed',conclusions:[{}],proposal_ids:[]});
 const root=path.join(run.runDir+'.meta/node-retries/learner/new');
 write(path.join(root,'attempt.json'),{id:'new',workspace:path.join(root,'output'),status:'running',startedAt:'2026-11-10'});
 const data=learningSummary(repo,run);
 assert.equal(data.status,'running');assert.equal(data.resultAvailable,false);
 assert.equal(data.conclusions.length,0);assert.equal(data.metrics,null);
});
test('外部及符号链接证据不可读取，预览截断长单行文件',t=>{
 const {repo,run}=fixture(t);
 fs.writeFileSync(path.join(run.runDir,'long.log'),'x'.repeat(20000));
 fs.symlinkSync('/etc/passwd',path.join(run.runDir,'link.txt'));
 write(path.join(run.runDir,'rsi/learning-result.json'),{conclusions:[{evidence:['/etc/passwd','link.txt','long.log']} ]});
 const refs=learningSummary(repo,run).conclusions[0].evidence;
 assert.deepEqual(refs.map(r=>r.available),[false,false,true]);
 const data=learningSummary(repo,run,refs[2].id);
 assert.equal(data.text.length,6000);assert.equal(data.truncated,true);
});
