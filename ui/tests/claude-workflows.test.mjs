import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createState,manifest,verifyManifest,step,requestStep,sourceReport,resumeState} from '../server/claude-workflows.mjs';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
function fixture(t) {
  const project='workflow-test-'+randomUUID(),runDir=path.join(repo,'runs',project,'one');
  const file=createState({runDir,project,source:'/tmp',models:{audit:'test'},start:'visual'});
  t.after(()=>{fs.rmSync(path.dirname(runDir),{recursive:true,force:true});fs.rmSync(path.join(repo,'runs',`.node-retry-${project}.lock`),{recursive:true,force:true});});
  return {file,runDir,project};
}
test('上游清单不使用界面条数上限，改动和缺失均停止交付',t=>{
  const {runDir}=fixture(t),root=path.join(runDir,'artifacts');fs.mkdirSync(root);
  for(let i=0;i<130;i++)fs.writeFileSync(path.join(root,`${i}.json`),'{}');
  const files=manifest([root]);assert.equal(files.length,130);verifyManifest(files);
  fs.writeFileSync(files[0].file,'changed');assert.throws(()=>verifyManifest(files),/已改变/);
  fs.unlinkSync(files[1].file);assert.throws(()=>manifest([files[1].file]),/缺失/);
  fs.symlinkSync(files[0].file,path.join(root,'link'));assert.throws(()=>manifest([root]),/符号链接/);
});
test('顺序由磁盘计划约束，同一步重复调用不重复审计',async t=>{
  const {file,runDir}=fixture(t);let called=0;
  const execute=async(_state,node)=>{called++;const output=path.join(runDir,'proof.json');fs.writeFileSync(output,'{}');return {node,status:'completed',outputs:manifest([output])};};
  await assert.rejects(step(file,'verify',execute),/顺序/);
  assert.deepEqual(await step(file,'visual',execute),{node:'visual',status:'completed'});
  await step(file,'visual',execute);assert.equal(called,1);
  fs.writeFileSync(path.join(runDir,'proof.json'),'changed');
  await assert.rejects(step(file,'visual',execute),/已改变/);
  await assert.rejects(step(file,'verify'),/已改变/);
});
test('并发调用同一节点只启动一个执行器',async t=>{
  const {file}=fixture(t);let release;
  const waiting=new Promise(resolve=>{release=resolve;});
  const first=step(file,'visual',async(_state,node)=>{await waiting;return {node,status:'completed',outputs:[]};});
  await assert.rejects(step(file,'visual',async()=>{}),/EEXIST/);
  release();await first;
});
test('执行器失败不产生成功回执，保留错误与项目锁',async t=>{
  const {file}=fixture(t);
  await assert.rejects(step(file,'visual',async()=>{throw Error('产物不完整');}),/不完整/);
  const state=JSON.parse(fs.readFileSync(file));assert.equal(state.receipts.length,0);assert.equal(state.error,'产物不完整');assert.ok(fs.existsSync(state.lock));
});
test('新一轮拒绝覆盖目录，其他项目任务不能取得已有锁',t=>{
  const {runDir,project}=fixture(t);
  assert.throws(()=>createState({runDir,project,source:'/tmp',models:{},start:'environment'}),/独立产物目录/);
  assert.throws(()=>createState({runDir,project,source:'/tmp',models:{},start:'visual'}),/EEXIST/);
});


test('重复查询已登记任务不会重启节点，完成时仍核对真实回执',async t=>{
 const {file}=fixture(t),state=JSON.parse(fs.readFileSync(file)),directory=path.join(path.dirname(file),'tasks/visual');
 fs.mkdirSync(directory,{recursive:true});
 const task={status:'queued',startedAt:new Date().toISOString(),fingerprint:'fixture'};
 fs.writeFileSync(path.join(directory,'task.json'),JSON.stringify(task));
 assert.deepEqual(requestStep(file,'visual'),{node:'visual',status:'running'});
 assert.deepEqual(requestStep(file,'visual'),{node:'visual',status:'running'});
 assert.equal(JSON.parse(fs.readFileSync(file)).receipts.length,0);
 assert.equal(state.current,undefined);
});


test('01回执保存在元数据目录，不提前占用02的审计输出目录',async t=>{
 const {file,runDir}=fixture(t);const data=JSON.parse(fs.readFileSync(file));data.start='environment';data.steps=['environment','orchestrator'];fs.writeFileSync(file,JSON.stringify(data));
 await step(file,'environment',async(_state,node)=>({node,status:'completed',outputs:[]}));
 assert.deepEqual(fs.readdirSync(runDir),[]);
 assert.ok(fs.existsSync(path.join(path.dirname(file),'receipts/environment.json')));
});

test('报告兼容两种候选字段，拒绝冲突和无效条目',t=>{
  const {runDir}=fixture(t),file=path.join(runDir,'audit-report.json'),state={runDir};
  for(const key of ['findings','vulnerabilities']){fs.writeFileSync(file,JSON.stringify({[key]:[{id:'F-1'}]}));assert.equal(sourceReport(state),file);}
  for(const value of [{findings:null},{findings:[null]},{findings:[],vulnerabilities:[{id:'F-1'}]}]){
    fs.writeFileSync(file,JSON.stringify(value));assert.throws(()=>sourceReport(state),/数组/);
  }
});
test('恢复保留成功回执，归档失败任务，拒绝重复恢复',async t=>{
  const {file,runDir}=fixture(t),proof=path.join(runDir,'proof.json');fs.writeFileSync(proof,'{}');
  await step(file,'visual',async(_state,node)=>({node,status:'completed',outputs:manifest([proof])}));
  const state=JSON.parse(fs.readFileSync(file)),dir=path.join(path.dirname(file),'tasks','verify');
  fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,'task.json'),JSON.stringify({status:'failed'}));
  Object.assign(state,{status:'failed',error:'失败证据',activeTask:path.join(dir,'task.json')});
  fs.writeFileSync(file,JSON.stringify(state));fs.rmSync(state.lock,{recursive:true});
  const restored=resumeState(file);assert.equal(restored.receipts.length,1);assert.equal(restored.status,'running');
  assert.equal(JSON.parse(fs.readFileSync(runDir+'.meta/status.json')).state,'running');
  assert.ok(!fs.existsSync(dir));assert.equal(restored.error,undefined);
  const history=path.join(path.dirname(file),'recovery-history');
  assert.equal(JSON.parse(fs.readFileSync(path.join(history,fs.readdirSync(history)[0],'state.json'))).error,'失败证据');
  assert.throws(()=>resumeState(file),/只能恢复/);
});
test('恢复前仍检查上游产物，失败不得取得项目锁',async t=>{
  const {file,runDir}=fixture(t),proof=path.join(runDir,'proof.json');fs.writeFileSync(proof,'{}');
  await step(file,'visual',async(_state,node)=>({node,status:'completed',outputs:manifest([proof])}));
  const state=JSON.parse(fs.readFileSync(file));state.status='failed';fs.writeFileSync(file,JSON.stringify(state));
  fs.rmSync(state.lock,{recursive:true});fs.writeFileSync(proof,'changed');
  assert.throws(()=>resumeState(file),/已改变/);assert.ok(!fs.existsSync(state.lock));
});

test('相对文件链接记录目标和内容，改动、越界、悬空和循环均阻断',t=>{
 const {runDir}=fixture(t),root=path.join(runDir,'output');fs.mkdirSync(root);
 const library=path.join(root,'lib.so.1.2');fs.writeFileSync(library,'library');
 const link=path.join(root,'lib.so.1');fs.symlinkSync('lib.so.1.2',link);
 const rows=manifest([root]);assert.equal(rows.filter(x=>x.type==='symlink').length,1);verifyManifest(rows);
 fs.writeFileSync(library,'tampered');assert.throws(()=>verifyManifest(rows),/已改变/);fs.writeFileSync(library,'library');
 fs.unlinkSync(link);fs.symlinkSync('../../outside',link);assert.throws(()=>manifest([root]),/超出/);
 fs.unlinkSync(link);fs.symlinkSync('missing',link);assert.throws(()=>manifest([root]),/悬空/);
 fs.unlinkSync(link);fs.symlinkSync('lib.so.1',link);assert.throws(()=>manifest([root]),/循环/);
});
test('交付失败保留完成批次，恢复只重验已有结果且不再次启动执行器',async t=>{
 const {file,runDir,project}=fixture(t),state=JSON.parse(fs.readFileSync(file));
 const report=path.join(runDir,'audit-report.json');fs.writeFileSync(report,JSON.stringify({project,findings:[{id:'F-1'}]}));
 const root=path.join(runDir+'.meta','node-retries','visual','finished'),workspace=path.join(root,'output'),outputs=path.join(workspace,'visual-rendered');
 fs.mkdirSync(outputs,{recursive:true});fs.copyFileSync(report,path.join(workspace,'audit-report.json'));
 fs.writeFileSync(path.join(outputs,'report.md'),'done');fs.symlinkSync('/etc/passwd',path.join(outputs,'unsafe'));
 const attempt=path.join(root,'attempt.json');fs.writeFileSync(attempt,JSON.stringify({id:'finished',root,workspace,node:'visual',project,runId:'one',workflowOwner:state.id,status:'completed',resultStatus:'completed',startedAt:'2026-11-06'}));
 state.activeAttempt=attempt;fs.writeFileSync(file,JSON.stringify(state));
 await assert.rejects(step(file,'visual'),/符号链接/);
 const failed=JSON.parse(fs.readFileSync(file));assert.equal(failed.activeAttempt,attempt);assert.equal(failed.failure.scope,'artifact_contract');
 fs.unlinkSync(path.join(outputs,'unsafe'));failed.status='failed';delete failed.activeAttempt;fs.writeFileSync(file,JSON.stringify(failed));fs.rmSync(failed.lock,{recursive:true});
 const restored=resumeState(file);assert.equal(restored.activeAttempt,attempt);
 assert.deepEqual(await step(file,'visual'),{node:'visual',status:'completed'});
 assert.equal(JSON.parse(fs.readFileSync(file)).receipts[0].attempt,attempt);
});

test('报告在首次交付与后续读取时绑定任务编号，品牌名不能替代项目编号',t=>{
 const {runDir,project}=fixture(t),file=path.join(runDir,'audit-report.json'),state={runDir,project};
 for(const value of ['OpenAI Codex','other-project',null]){
  fs.writeFileSync(file,JSON.stringify({project:value,findings:[]}));
  assert.throws(()=>sourceReport(state),/报告项目编号必须/);
 }
 fs.writeFileSync(file,JSON.stringify({project,project_name:'展示名称',findings:[]}));
 assert.equal(sourceReport(state),file);
});
