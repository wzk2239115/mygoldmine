import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash,randomUUID} from 'node:crypto';
import {createState,manifest,verifyManifest,step,requestStep,sourceReport,resumeState,execute} from '../server/claude-workflows.mjs';

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
 const design=path.join(outputs,'scene-F-1.director.json');
 fs.writeFileSync(design,JSON.stringify({finding_id:'F-1',mechanism:{missing_check:'缺少权限检查'}}));
 const digest=createHash('sha256').update(fs.readFileSync(design)).digest('hex');
 const receipts=path.join(workspace,'.stage-submissions/visual');fs.mkdirSync(receipts,{recursive:true});
 fs.writeFileSync(path.join(receipts,'fixture.json'),JSON.stringify({
  stage:'visual',decision:'accepted',checked_at:new Date().toISOString(),artifact:design,
  sha256:digest,files:[{path:design,sha256:digest}]
 }));
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

test('旧版项目字段兼容且冲突拒绝，不修改原报告',t=>{
 const {runDir,project}=fixture(t),file=path.join(runDir,'audit-report.json');
 const bytes=JSON.stringify({metadata:{project_id:project},findings:[]});fs.writeFileSync(file,bytes);
 assert.equal(sourceReport({runDir,project}),file);assert.equal(fs.readFileSync(file,'utf8'),bytes);
 fs.writeFileSync(file,JSON.stringify({project,metadata:{project_id:'other'},findings:[]}));
 assert.throws(()=>sourceReport({runDir,project}),/冲突/);
});
test('虚拟环境交付为可核验快照，普通悬空链接仍拒绝',t=>{
 const {runDir}=fixture(t),env=path.join(runDir,'custom-env');fs.mkdirSync(path.join(env,'bin'),{recursive:true});
 fs.writeFileSync(path.join(env,'pyvenv.cfg'),'home = /container/python\nversion = 3.12.14\n');
 fs.symlinkSync('/not-on-host/python3',path.join(env,'bin/python'));
 fs.writeFileSync(path.join(env,'dependency.py'),'original');
 const rows=manifest([runDir]);assert.equal(rows.filter(x=>x.type==='runtime-environment').length,1);verifyManifest(rows);
 fs.writeFileSync(path.join(env,'dependency.py'),'changed');assert.throws(()=>verifyManifest(rows),/已改变/);
 fs.symlinkSync('missing',path.join(runDir,'proof'));assert.throws(()=>manifest([runDir]),/悬空/);
});


test('第三阶段零图片降级交付后下一步仍为蓝队验证',async t=>{
 const {file,runDir,project}=fixture(t),state=JSON.parse(fs.readFileSync(file));
 fs.writeFileSync(path.join(runDir,'audit-report.json'),JSON.stringify({project,findings:[]}));
 const root=path.join(runDir+'.meta/node-retries/visual/zero-images'),workspace=path.join(root,'output');
 const visual=path.join(workspace,'visual-rendered');fs.mkdirSync(visual,{recursive:true});
 fs.copyFileSync(path.join(runDir,'audit-report.json'),path.join(workspace,'audit-report.json'));
 fs.writeFileSync(path.join(visual,'delivery-status.json'),JSON.stringify({optional:true,status:'degraded',scene_count:0}));
 const attempt=path.join(root,'attempt.json');
 fs.writeFileSync(attempt,JSON.stringify({id:'zero-images',root,workspace,node:'visual',project,runId:'one',workflowOwner:state.id,status:'completed',resultStatus:'degraded',deliveryAcceptance:{accepted:0,deliveries:[],optional:true}}));
 state.initialJob=attempt;fs.writeFileSync(file,JSON.stringify(state));
 assert.deepEqual(await step(file,'visual'),{node:'visual',status:'degraded'});
 const saved=JSON.parse(fs.readFileSync(file));
 assert.equal(saved.steps[saved.receipts.length],'verify');
 let next;
 await step(file,'verify',async(_state,node)=>{next=node;return {node,status:'completed',outputs:[]};});
 assert.equal(next,'verify');
});

test('恢复第二阶段前归档旧审计目录，防止原始轨迹被覆盖',t=>{
 const {file,runDir}=fixture(t),state=JSON.parse(fs.readFileSync(file));
 fs.writeFileSync(path.join(runDir,'raw.jsonl'),'old audit trace\n');
 Object.assign(state,{start:'environment',steps:['environment','orchestrator'],receipts:[{node:'environment',status:'completed',outputs:[]}],status:'failed'});
 fs.writeFileSync(file,JSON.stringify(state));fs.rmSync(state.lock,{recursive:true,force:true});
 const restored=resumeState(file);
 assert.equal(restored.status,'running');assert.equal(restored.receipts.length,1);
 assert.equal(fs.existsSync(path.join(runDir,'raw.jsonl')),false);
 const history=path.join(path.dirname(file),'recovery-history');
 const folders=fs.readdirSync(history);
 assert.equal(folders.length,1);
 assert.equal(fs.readFileSync(path.join(history,folders[0],'prior-run/raw.jsonl'),'utf8'),'old audit trace\n');
});

test('第二阶段已有报告或上游回执引用审计目录时拒绝危险恢复',t=>{
 const {file,runDir}=fixture(t),state=JSON.parse(fs.readFileSync(file));
 Object.assign(state,{start:'environment',steps:['environment','orchestrator'],receipts:[{node:'environment',status:'completed',outputs:[]}],status:'failed'});
 fs.writeFileSync(file,JSON.stringify(state));fs.rmSync(state.lock,{recursive:true,force:true});
 fs.writeFileSync(path.join(runDir,'audit-report.json'),JSON.stringify({findings:[]}));
 assert.throws(()=>resumeState(file),/节点重跑入口/);
 assert.ok(fs.existsSync(path.join(runDir,'audit-report.json')));
 assert.ok(!fs.existsSync(state.lock));
 fs.rmSync(path.join(runDir,'audit-report.json'));
 const referenced=path.join(runDir,'environment-proof.json');fs.writeFileSync(referenced,'{}');
 state.receipts[0].outputs=manifest([referenced]);fs.writeFileSync(file,JSON.stringify(state));
 assert.throws(()=>resumeState(file),/上游回执引用审计目录/);
 assert.equal(fs.readFileSync(referenced,'utf8'),'{}');
 assert.ok(!fs.existsSync(state.lock));
});

test('第二阶段归档后的准备异常恢复原目录与失败状态',t=>{
 const {file,runDir}=fixture(t),state=JSON.parse(fs.readFileSync(file));
 Object.assign(state,{start:'environment',steps:['environment','orchestrator'],receipts:[{node:'environment',status:'completed',outputs:[]}],status:'failed'});
 fs.writeFileSync(file,JSON.stringify(state));fs.rmSync(state.lock,{recursive:true,force:true});
 fs.writeFileSync(path.join(runDir,'raw.jsonl'),'keep original trace\n');
 const task=path.join(path.dirname(file),'tasks/orchestrator');fs.mkdirSync(task,{recursive:true});
 fs.writeFileSync(path.join(task,'task.json'),JSON.stringify({status:'failed'}));
 const rename=fs.renameSync;
 fs.renameSync=(from,to)=>{if(from===task)throw Error('injected preparation failure');return rename(from,to);};
 try{assert.throws(()=>resumeState(file),/injected preparation failure/);}
 finally{fs.renameSync=rename;}
 assert.equal(fs.readFileSync(path.join(runDir,'raw.jsonl'),'utf8'),'keep original trace\n');
 assert.ok(fs.existsSync(path.join(task,'task.json')));
 assert.equal(JSON.parse(fs.readFileSync(file)).status,'failed');
 assert.ok(!fs.existsSync(state.lock));
});

test('第二阶段归档回滚失败仍释放项目锁',t=>{
 const {file,runDir}=fixture(t),state=JSON.parse(fs.readFileSync(file));
 Object.assign(state,{start:'environment',steps:['environment','orchestrator'],receipts:[{node:'environment',status:'completed',outputs:[]}],status:'failed'});
 fs.writeFileSync(file,JSON.stringify(state));fs.rmSync(state.lock,{recursive:true,force:true});
 fs.writeFileSync(path.join(runDir,'raw.jsonl'),'keep original trace\n');
 const task=path.join(path.dirname(file),'tasks/orchestrator');fs.mkdirSync(task,{recursive:true});
 const rename=fs.renameSync;
 fs.renameSync=(from,to)=>{
   if(from===task)throw Error('injected preparation failure');
   if(String(from).endsWith('/prior-run'))throw Error('injected rollback failure');
   return rename(from,to);
 };
 try{assert.throws(()=>resumeState(file),/归档回滚受阻/);}
 finally{fs.renameSync=rename;}
 assert.ok(!fs.existsSync(state.lock));
 const history=path.join(path.dirname(file),'recovery-history');
 const archived=fs.readdirSync(history).map(name=>path.join(history,name,'prior-run/raw.jsonl')).find(fs.existsSync);
 assert.ok(archived);
 assert.equal(fs.readFileSync(archived,'utf8'),'keep original trace\n');
});


function recoveryFixture(t,{includeAttachment=true}={}) {
 const {file,runDir,project}=fixture(t),recovered=runDir+'-recovery';
 const state=JSON.parse(fs.readFileSync(file));
 Object.assign(state,{start:'environment',steps:['environment','orchestrator'],
   receipts:[{node:'environment',status:'completed',outputs:[]}],
   status:'failed',runDir:recovered,recoveredFrom:runDir,source:'/tmp'});
 fs.writeFileSync(file,JSON.stringify(state));fs.rmSync(state.lock,{recursive:true,force:true});
 fs.mkdirSync(path.join(recovered,'artifacts'),{recursive:true});
 const report=path.join(recovered,'audit-report.json'),markdown=path.join(recovered,'audit-report.md'),
   evidence=path.join(recovered,'artifacts/infra-one.json');
 fs.writeFileSync(report,JSON.stringify({project,source_version:'test-commit',
   findings:[],coverage:{analysis_mode:'assembly-only'},
   execution:{source_run:runDir,target_commit:'test-commit',verification:'unverified'}}));
 fs.writeFileSync(markdown,'# Recovery report\n');fs.writeFileSync(evidence,'{"evidence":true}\n');
 fs.writeFileSync(path.join(recovered,'checkpoint.json'),JSON.stringify({source_run:runDir,
   target:'/tmp',target_commit:'test-commit',assembly:{sha256:'test'}}));
 fs.writeFileSync(path.join(recovered,'run-meta.json'),JSON.stringify({agent:'durable-recovery',
   project,recovered_from:runDir,commit:'test-commit',reports_complete:true,
   delivery_accepted:true,status:'success',exit_code:0}));
 const digest=file=>createHash('sha256').update(fs.readFileSync(file)).digest('hex');
 const files=[report,markdown,...(includeAttachment?[evidence]:[])].map(file=>({path:file,sha256:digest(file)}));
 const receiptDir=path.join(recovered,'.stage-submissions/orchestrator');
 fs.mkdirSync(receiptDir,{recursive:true});
 fs.writeFileSync(path.join(receiptDir,'accepted.json'),JSON.stringify({stage:'orchestrator',
   decision:'accepted',checked_at:new Date().toISOString(),artifact:report,
   sha256:digest(report),files}));
 return {file,runDir,recovered,project,report,evidence,state};
}

test('阶段 II 复用同轮已验收恢复报告，保留原轨迹并继续交付',async t=>{
 const {file,runDir,recovered,report}=recoveryFixture(t);
 fs.writeFileSync(path.join(runDir,'raw.jsonl'),'original trace\n');
 const restored=resumeState(file);
 assert.equal(restored.runDir,recovered);assert.equal(restored.reuseRecoveryRun,true);
 assert.equal(fs.readFileSync(path.join(runDir,'raw.jsonl'),'utf8'),'original trace\n');
 const history=path.join(path.dirname(file),'recovery-history');
 assert.ok(fs.readdirSync(history).every(name=>!fs.existsSync(path.join(history,name,'prior-recovery'))));
 const receipt=await execute(restored,'orchestrator',file);
 assert.equal(receipt.status,'completed');
 assert.ok(receipt.outputs.some(item=>item.file===report));
 assert.equal(fs.readFileSync(path.join(runDir,'raw.jsonl'),'utf8'),'original trace\n');
});

test('恢复附件被改动时不复用；归档旧运行后重跑而不丢证据',t=>{
 const {file,runDir,recovered,evidence}=recoveryFixture(t);
 fs.writeFileSync(path.join(runDir,'raw.jsonl'),'old original\n');
 fs.writeFileSync(evidence,'changed after acceptance');
 const restored=resumeState(file);
 assert.equal(restored.runDir,runDir);assert.equal(restored.reuseRecoveryRun,undefined);
 assert.ok(!fs.existsSync(recovered));
 const history=path.join(path.dirname(file),'recovery-history');
 const folder=path.join(history,fs.readdirSync(history)[0]);
 assert.equal(fs.readFileSync(path.join(folder,'prior-run/raw.jsonl'),'utf8'),'old original\n');
 assert.equal(fs.readFileSync(path.join(folder,'prior-recovery/artifacts/infra-one.json'),'utf8'),'changed after acceptance');
});

test('恢复回执漏附件或来源错误时拒绝复用',t=>{
 const {file,runDir,recovered}=recoveryFixture(t,{includeAttachment:false});
 fs.writeFileSync(path.join(runDir,'raw.jsonl'),'old original\n');
 const restored=resumeState(file);
 assert.equal(restored.runDir,runDir);
 assert.ok(fs.existsSync(path.join(path.dirname(file),'recovery-history',
   fs.readdirSync(path.join(path.dirname(file),'recovery-history'))[0],'prior-recovery','audit-report.json')));
 assert.ok(!fs.existsSync(recovered));
});

test('恢复报告标记错误时即使回执哈希正确也不能复用',t=>{
 const {file,runDir,recovered,report}=recoveryFixture(t);
 const value=JSON.parse(fs.readFileSync(report));value.coverage.analysis_mode='full';
 fs.writeFileSync(report,JSON.stringify(value));
 const receiptFile=path.join(recovered,'.stage-submissions/orchestrator/accepted.json');
 const receipt=JSON.parse(fs.readFileSync(receiptFile));
 const digest=createHash('sha256').update(fs.readFileSync(report)).digest('hex');
 receipt.sha256=digest;receipt.files.find(item=>item.path===report).sha256=digest;
 fs.writeFileSync(receiptFile,JSON.stringify(receipt));
 const restored=resumeState(file);
 assert.equal(restored.runDir,runDir);
 const history=path.join(path.dirname(file),'recovery-history');
 const archived=path.join(history,fs.readdirSync(history)[0],'prior-recovery/audit-report.json');
 assert.equal(JSON.parse(fs.readFileSync(archived)).coverage.analysis_mode,'full');
});

test('恢复报告来源与本轮不符时不能复用',t=>{
 const {file,runDir,recovered}=recoveryFixture(t);
 const metaFile=path.join(recovered,'run-meta.json');
 const meta=JSON.parse(fs.readFileSync(metaFile));meta.recovered_from='/another/run';
 fs.writeFileSync(metaFile,JSON.stringify(meta));
 const restored=resumeState(file);
 assert.equal(restored.runDir,runDir);
 assert.ok(!fs.existsSync(recovered));
});
