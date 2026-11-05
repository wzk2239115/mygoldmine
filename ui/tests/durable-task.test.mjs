import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {execFileSync,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {launchTask,taskStatus,waitTask,stopTask,taskLive} from '../server/durable-task.mjs';
const moduleFile=fileURLToPath(new URL('../server/durable-task.mjs',import.meta.url));
function fixture(t){const root=fs.mkdtempSync(path.join(os.tmpdir(),'durable-task-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root;}
test('发起进程退出后任务继续运行，重复登记仍是同一进程',async t=>{
 const root=fixture(t),directory=path.join(root,'task'),proof=path.join(root,'proof');
 const spec={program:process.execPath,args:['-e',`setTimeout(()=>require('fs').writeFileSync(${JSON.stringify(proof)},'done'),1400)`],cwd:root,timeoutMs:10000,successCodes:[0]};
 const source=`import {launchTask} from ${JSON.stringify(moduleFile)};console.log(JSON.stringify(launchTask(${JSON.stringify(directory)},${JSON.stringify(spec)})));`;
 const started=JSON.parse(execFileSync(process.execPath,['--input-type=module','-e',source],{encoding:'utf8'}));
 const again=launchTask(directory,spec);assert.equal(again.pid,started.pid);
 const result=await waitTask(started.file,{pollMs:25});assert.equal(result.status,'completed');assert.equal(fs.readFileSync(proof,'utf8'),'done');assert.ok(result.heartbeatAt);
 assert.throws(()=>launchTask(directory,{...spec,args:[]}),/不匹配/);
});
test('实际超时会停止任务及子进程，不伪造成功',async t=>{
 const root=fixture(t),proof=path.join(root,'proof');
 const task=launchTask(path.join(root,'task'),{program:process.execPath,args:['-e',`setTimeout(()=>require('fs').writeFileSync(${JSON.stringify(proof)},'bad'),2000)`],cwd:root,timeoutMs:100,successCodes:[0]});
 const result=await waitTask(task.file,{pollMs:25});assert.equal(result.status,'failed');assert.match(result.error,/超过/);assert.equal(fs.existsSync(proof),false);
});
test('非零退出与进程身份不匹配均不算完成',async t=>{
 const root=fixture(t),task=launchTask(path.join(root,'task'),{program:process.execPath,args:['-e','process.exit(7)'],cwd:root,timeoutMs:10000});
 const result=await waitTask(task.file,{pollMs:25});assert.equal(result.exitCode,7);assert.equal(result.status,'failed');
 assert.equal(taskLive({pid:process.pid,processStart:'wrong'}),false);
});
test('停止指定任务保留终态，不停止其他任务',async t=>{
 const root=fixture(t),task=launchTask(path.join(root,'task'),{program:process.execPath,args:['-e','setTimeout(()=>{},10000)'],cwd:root,timeoutMs:20000});
 for(let i=0;i<100&&taskStatus(task.file).status!=='running';i++)await new Promise(r=>setTimeout(r,10));
 stopTask(task.file);assert.equal((await waitTask(task.file,{pollMs:25})).status,'failed');
});
test('环境构建重复请求接管当前任务，真实退出码10作为部分可用结果保留',async t=>{
 const root=fixture(t),out=path.join(root,'env');fs.mkdirSync(path.join(root,'scripts/env'),{recursive:true});fs.mkdirSync(out);
 fs.writeFileSync(path.join(root,'scripts/env/build_env.sh'),'sleep 1\nprintf done > "$1/proof"\nexit 10\n');
 const args=[moduleFile,'--start-build',root,out,out];
 const first=JSON.parse(execFileSync(process.execPath,args,{encoding:'utf8'}));
 const second=JSON.parse(execFileSync(process.execPath,args,{encoding:'utf8'}));assert.equal(first.taskFile,second.taskFile);assert.equal(second.reused,true);
 const denied=spawnSync(process.execPath,[moduleFile,'--stop-build',out],{encoding:'utf8',env:{...process.env,ENV_BUILD_TASK_OWNER:'another-workflow'}});assert.equal(denied.status,1);assert.match(denied.stderr,/不能停止/);
 const result=await waitTask(first.taskFile,{pollMs:25});assert.equal(result.status,'completed');assert.equal(result.exitCode,10);assert.equal(fs.readFileSync(path.join(out,'proof'),'utf8'),'done');
});

test('超时清理另建进程组且忽略终止信号的后代',async t=>{
 const root=fixture(t),pidFile=path.join(root,'grandchild.pid');
 const grandchild="process.on('SIGTERM',()=>{});setTimeout(()=>{},30000)";
 const parent="const {spawn}=require('child_process'),fs=require('fs');const child=spawn(process.execPath,['-e',"+JSON.stringify(grandchild)+"],{detached:true,stdio:'ignore'});fs.writeFileSync("+JSON.stringify(pidFile)+",String(child.pid));setTimeout(()=>{},30000)";
 const task=launchTask(path.join(root,'task'),{program:process.execPath,args:['-e',parent],cwd:root,timeoutMs:500});
 const result=await waitTask(task.file,{pollMs:25});assert.equal(result.status,'failed');
 const pid=Number(fs.readFileSync(pidFile,'utf8'));let stat=null;
 try{stat=fs.readFileSync('/proc/'+pid+'/stat','utf8');}catch{}
 assert.ok(!stat || stat.split(') ')[1].startsWith('Z '));
});
