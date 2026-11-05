import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createState,manifest,verifyManifest,step,requestStep} from '../server/claude-workflows.mjs';

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
