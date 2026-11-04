import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
const read = file => { try { return JSON.parse(fs.readFileSync(file,'utf8')); } catch { return null; } };
const write = (file,data) => { const temp=`${file}.tmp`;fs.writeFileSync(temp,JSON.stringify(data,null,2));fs.renameSync(temp,file); };
const fail = message => { const error=new Error(message);error.status=409;throw error; };
export function nodeAttempts(runDir,node) {
  const root=path.join(`${runDir}.meta`,'node-retries',node);
  if(!fs.existsSync(root))return [];
  return fs.readdirSync(root).map(id=>read(path.join(root,id,'attempt.json'))).filter(Boolean).sort((a,b)=>a.startedAt.localeCompare(b.startedAt));
}
export function retryEligibility(run,node) {
  if(!['visual','verify'].includes(node))return '该节点暂不支持独立重跑，请使用项目重跑';
  if(fs.existsSync(path.join(path.resolve(run.runDir,'../../..'),'runs',`.learning-cycle-${run.project}.lock`)))return '该项目正在执行学习循环';
  if(run.isLive)return '项目正在运行，请等待本次流程结束';
  const status=read(`${run.runDir}.meta/status.json`) || {};
  const report=read(path.join(run.runDir,'audit-report.json'));
  if(!Array.isArray(report?.findings))return '缺少有效的审计报告';
  if(node==='verify' && (!status.env_image || !status.target))return '缺少环境镜像或源码信息';
  return '';
}
export function startNodeRetry({repoRoot,run,node,models}) {
  const reason=retryEligibility(run,node);if(reason)fail(reason);
  const lock=path.join(repoRoot,'runs',`.node-retry-${run.project}.lock`);
  try { fs.mkdirSync(lock); } catch { fail('该项目已有节点重跑任务，请稍后再试'); }
  const id=randomUUID();const root=path.join(`${run.runDir}.meta`,'node-retries',node,id);
  try {
    fs.mkdirSync(root,{recursive:true});
    const workspace=path.join(root,'output');fs.mkdirSync(workspace);
    fs.copyFileSync(path.join(run.runDir,'audit-report.json'),path.join(workspace,'audit-report.json'));
    const status=read(`${run.runDir}.meta/status.json`) || {};
    const model=models[node] || models.audit;
    const job={id,node,project:run.project,runId:run.runId,repoRoot,root,workspace,lock,model,status:'running',startedAt:new Date().toISOString(),source:status.target,image:status.env_image};
    write(path.join(root,'attempt.json'),job);
    const fd=fs.openSync(path.join(root,'worker.log'),'a');
    const child=spawn(process.execPath,[fileURLToPath(import.meta.url),'--worker',path.join(root,'attempt.json')],{cwd:repoRoot,detached:true,stdio:['ignore',fd,fd]});
    child.on('error', error => {
      write(path.join(root,'attempt.json'), {...job,status:'failed',resultStatus:'failed',error:error.message,endedAt:new Date().toISOString()});
      fs.rmSync(lock,{recursive:true,force:true});
    });
    fs.closeSync(fd);child.unref();
    return {id,node,status:'running'};
  } catch(error) { fs.rmSync(lock,{recursive:true,force:true});throw error; }
}
async function worker(file) {
  const job=read(file);let code=1;
  try {
    let args;
    if(job.node==='visual')args=['scripts/mine/visual_report.sh','--project',job.project,'--run-dir',job.workspace,'--model',job.model];
    else args=['scripts/verify/phase4_verify_agent.sh','--project',job.project,'--run-dir',job.workspace,'--source',job.source,'--image',job.image,'--model',job.model,'--output',path.join(job.workspace,'verify/agent')];
    code=await new Promise((resolve,reject)=>{const child=spawn('bash',args,{cwd:job.repoRoot,stdio:'inherit'});child.on('error',reject);child.on('close',c=>resolve(c ?? 1));});
    if(job.node==='visual') {
      const summary=read(path.join(job.workspace,'visual-rendered/visual-summary.json'));
      job.resultStatus=summary?.steps?.render_attack_scenes_agentic?.ok?'completed':summary?.scene_count?'degraded':'failed';
    } else job.resultStatus=code===0?'completed':'failed';
  } catch(error) { job.error=error.message; }
  finally { job.status=code===0?'completed':'failed';job.exitCode=code;job.endedAt=new Date().toISOString();write(file,job);fs.rmSync(job.lock,{recursive:true,force:true});
    const originalRun=path.resolve(job.root,'../../..').replace(/\.meta$/,'');
    const collector=path.join(job.repoRoot,'scripts/stages/skill_bank.py');
    if(fs.existsSync(collector)) await new Promise(resolve=>{const child=spawn('python3',[collector,'collect','--project',job.project,'--root',originalRun],{cwd:job.repoRoot,stdio:'ignore'});child.on('error',resolve);child.on('close',resolve);}); }
}
if(process.argv[2]==='--worker')await worker(process.argv[3]);
